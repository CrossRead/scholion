"""Determine a PGS reference population from prepared, depth-checked genotypes.

Only public rsIDs are sent to Ensembl to obtain population allele frequencies;
no genotypes or personal identifiers leave the machine. Reference frequencies
are cached locally. This is a coarse five-panel comparison, not admixture.
"""
from __future__ import annotations

import argparse
from datetime import date
import gzip
import hashlib
import json
import math
import os
import time
from pathlib import Path
import urllib.request

SUPERPOPS = ("AFR", "AMR", "EAS", "EUR", "SAS")
MIN_DP = 15
MIN_SPACING = 1_000_000
TARGET_N = 320
MIN_MARKERS = 100
MIN_DELTA = 10.0


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def genome_stamp(path: Path) -> dict:
    """Detect replacement/editing without hashing a whole-genome file."""
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def samples(path: Path) -> list[str]:
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#CHROM"):
                return line.rstrip("\n").split("\t")[9:]
            if not line.startswith("#"):
                break
    return []


def load_panel(vcf: Path, mapping: dict) -> list:
    """Keep diploid autosomal SNPs with known depth; reference calls stay in."""
    rows: list[tuple[str, int, int, str, str]] = []
    opener = gzip.open if vcf.name.endswith(".gz") else open
    with opener(vcf, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 10 or p[6] not in ("PASS", "."):
                continue
            chrom = p[0].removeprefix("chr")
            if chrom not in {str(n) for n in range(1, 23)}:
                continue
            rs = mapping.get(f"{p[0]}:{p[1]}") or mapping.get(f"{chrom}:{p[1]}")
            alts = [a for a in p[4].split(",") if a not in (".", "<*>")]
            if not isinstance(rs, str) or not rs.startswith("rs") or not rs[2:].isdigit() or len(p[3]) != 1 or len(alts) > 1 or any(len(a) != 1 for a in alts):
                continue
            fields = dict(zip(p[8].split(":"), p[9].split(":")))
            try:
                dp = int(fields.get("DP", "0"))
                indices = [int(n) for n in fields.get("GT", "./.").replace("|", "/").split("/")]
                alleles = [p[3]] + alts
                if dp < MIN_DP or len(indices) != 2 or any(n < 0 or n >= len(alleles) for n in indices):
                    continue
                rows.append((rs, int(chrom), int(p[1]), alleles[indices[0]], alleles[indices[1]]))
            except ValueError:
                continue
    rows.sort(key=lambda row: (row[1], row[2]))
    panel = []
    last: dict[int, int] = {}
    for row in rows:
        if row[1] in last and row[2] - last[row[1]] < MIN_SPACING:
            continue
        panel.append(row)
        last[row[1]] = row[2]
    return panel[:TARGET_N]


def fetch_frequencies(rsid: str) -> dict:
    """Public reference lookup; the request contains only the rsID."""
    if not rsid.startswith("rs") or not rsid[2:].isdigit():
        return {}
    time.sleep(0.08)
    url = f"https://rest.ensembl.org/variation/homo_sapiens/{rsid}?pops=1;content-type=application/json"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Content-Type": "application/json"}), timeout=30) as response:
        data = json.loads(response.read())
    out: dict[str, dict[str, float]] = {}
    for entry in data.get("populations", []):
        name = entry.get("population", "")
        if name.startswith("1000GENOMES:phase_3:"):
            out.setdefault(name.rsplit(":", 1)[1], {})[entry.get("allele", "")] = float(entry.get("frequency", 0.0))
    return out


def determine(vcf: Path, rsmap: Path, *, output: Path | None = None) -> dict:
    """Analyze prepared scoring-independent sites; never substitute a population."""
    from . import core, store
    if not vcf.is_file() or not rsmap.is_file():
        return {"status": "needs_genotypes", "verdict_superpop": None}
    try:
        vcf_sha, map_sha = fingerprint(vcf), fingerprint(rsmap)
        sample_names = samples(vcf)
        if len(sample_names) != 1:
            raise ValueError("one sample is required")
        mapping = json.loads(rsmap.read_text(encoding="utf-8"))
        if not isinstance(mapping, dict):
            raise ValueError("rsID map is not an object")
        panel = load_panel(vcf, mapping)
    except (OSError, ValueError, EOFError, TypeError, AttributeError):
        return {"status": "invalid_genotypes", "verdict_superpop": None}
    if len(panel) < MIN_MARKERS:
        return {"status": "insufficient_genotypes", "verdict_superpop": None, "n_snps": len(panel)}
    cache_path = core.cache_dir() / "population-frequencies.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, EOFError, TypeError, AttributeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    offline = os.environ.get("SCHOLION_OFFLINE") == "1"
    likelihood = {pop: 0.0 for pop in SUPERPOPS}
    used = 0
    changed = False
    reference_unavailable = False
    for rs, _chrom, _position, a1, a2 in panel:
        frequencies = cache.get(rs)
        if not frequencies and not offline and not reference_unavailable:
            try:
                frequencies = fetch_frequencies(rs)
            except OSError:
                # One unreachable service must not cost a timeout per marker.
                reference_unavailable = True
                frequencies = None
            except (ValueError, EOFError, TypeError, AttributeError):
                frequencies = None
            if frequencies:
                cache[rs] = frequencies
                changed = True
        if not isinstance(frequencies, dict) or not all(isinstance(frequencies.get(pop), dict) for pop in SUPERPOPS):
            continue
        if not all(a1 in frequencies[pop] and a2 in frequencies[pop]
                   and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                           and math.isfinite(value) and 0 <= value <= 1
                           for value in frequencies[pop].values())
                   and math.isclose(sum(frequencies[pop].values()), 1.0, abs_tol=0.01)
                   for pop in SUPERPOPS):
            continue
        for pop in SUPERPOPS:
            af = frequencies[pop]
            f1 = min(max(af.get(a1, 0.0), 0.001), 0.999)
            f2 = min(max(af.get(a2, 0.0), 0.001), 0.999)
            likelihood[pop] += math.log((2.0 if a1 != a2 else 1.0) * f1 * f2)
        used += 1
    if changed:
        store._write_json(cache_path, cache)
    if used < MIN_MARKERS:
        return {"status": "reference_unavailable", "verdict_superpop": None, "n_snps": used}
    try:
        unchanged = fingerprint(vcf) == vcf_sha and fingerprint(rsmap) == map_sha
    except OSError:
        unchanged = False
    if not unchanged:
        return {"status": "invalid_genotypes", "verdict_superpop": None}
    ranked = sorted(likelihood, key=lambda pop: likelihood[pop], reverse=True)
    delta = likelihood[ranked[0]] - likelihood[ranked[1]]
    weights = {pop: math.exp(likelihood[pop] - likelihood[ranked[0]]) for pop in SUPERPOPS}
    total = sum(weights.values())
    result = {"status": "determined" if delta > MIN_DELTA else "ambiguous",
              "verdict_superpop": ranked[0] if delta > MIN_DELTA else None,
              "date": date.today().isoformat(),
              "method": "genotype log-likelihood under 1000 Genomes phase 3 frequencies; diploid autosomal SNPs, DP>=15, spacing>=1 Mb",
              "n_snps": used, "delta_ll_top2": round(delta, 4),
              "samples": sample_names,
              "posterior": {pop: round(value / total, 6) for pop, value in weights.items()},
              "source_vcf": str(vcf.resolve()), "source_vcf_sha256": vcf_sha,
              "source_rsmap": str(rsmap.resolve()), "source_rsmap_sha256": map_sha,
              "caveats": ["Coarse reference-panel assignment, not admixture fractions.",
                          "Residual linkage and marker ascertainment limit the likelihood comparison."]}
    if output is not None:
        store._write_json(output, result)
        core.reset_cache()
    return result


def prepare_for_pgs(vcf_path: str) -> dict:
    """Use prepared genome sites beside the scoring input, in the active profile."""
    from . import core
    folder = Path(vcf_path).resolve().parent
    prepared = folder / "longevity_sites.vcf.gz"
    if prepared.exists():
        try:
            if samples(prepared) != samples(Path(vcf_path)):
                return {"status": "sample_mismatch", "verdict_superpop": None}
        except (OSError, ValueError, EOFError, TypeError, AttributeError):
            return {"status": "invalid_genotypes", "verdict_superpop": None}
    return determine(prepared, folder / "longevity_rsmap.json",
                     output=core.profile_dir() / "ancestry_check.json")


def _cli(argv=None) -> int:
    from . import core, genome
    connected = genome.vcf_path()
    folder = connected.parent if connected else core.genome_dir()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vcf", type=Path, default=folder / "longevity_sites.vcf.gz")
    parser.add_argument("--rsmap", type=Path, default=folder / "longevity_rsmap.json")
    parser.add_argument("--out", type=Path, default=core.profile_dir() / "ancestry_check.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(f"Reads: {args.vcf} and {args.rsmap}; writes: {args.out}; no requests or writes performed.")
        return 0
    result = determine(args.vcf, args.rsmap, output=args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "determined" else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
