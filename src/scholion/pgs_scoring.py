"""Local, allele-aware scoring of harmonized PGS files using called genotypes.

No absent position is imputed. Model downloads and reference calibration belong
in prs.py; this module reads local files only. A private disk index bounds RAM
and is discarded after the report. Model weights never enter a profile.
"""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile

ALGORITHM = "scholion-called-alleles-v1"
_BASES = set("ACGT")
_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _open(path):
    with open(path, "rb") as stream:
        compressed = stream.read(2) == b"\x1f\x8b"
    return gzip.open(path, "rt", encoding="utf-8") if compressed else open(path, encoding="utf-8")


def _sha(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dosage(effect: str, other: str, records):
    """Resolve diploid dosage once per model row; never guess an unknown strand.

    Opposite-strand matching requires both non-palindromic SNP alleles. An
    effect-only SNP in a complete forward-strand call can have dose zero.
    Indels require an exact allele match; symbolic/partial calls are excluded.
    Conflicting equally supported rows are excluded rather than picked by order.
    """
    effect = effect.upper()
    other = (other or "").upper()
    if not effect or not set(effect) <= _BASES:
        return None, "unsupported_allele"
    candidates = []
    for ref, alts, indices in records or []:
        site = [ref.upper()] + [a.upper() for a in alts]
        if len(indices) != 2 or any(not isinstance(i, int) or i < 0 or i >= len(site) for i in indices):
            continue
        calls = [site[i] for i in indices]
        if any(not c or not set(c) <= _BASES for c in calls):
            continue
        present = set(site) - {".", "<*>", "<NON_REF>"}
        if effect in present:
            rank = 3 if other in present else 2
            candidates.append((rank, calls.count(effect), "carried" if effect in calls else "zero"))
        elif other and other in present and all(c == other for c in calls):
            candidates.append((2, 0, "zero"))
        elif not other and len(effect) == 1 and all(len(c) == 1 for c in calls):
            candidates.append((1, 0, "zero"))
        if (len(effect) == len(other) == 1 and set(other) <= _BASES
                and effect != other and effect.translate(_COMPLEMENT) != other):
            flipped = {effect.translate(_COMPLEMENT), other.translate(_COMPLEMENT)}
            if flipped <= present:
                candidates.append((3, calls.count(effect.translate(_COMPLEMENT)), "flip"))
    if not candidates:
        return None, "no_call" if records and all(not r[2] for r in records) else "allele_mismatch"
    rank = max(c[0] for c in candidates)
    best = [c for c in candidates if c[0] == rank]
    if len({c[1] for c in best}) != 1:
        return None, "conflicting_calls"
    return best[0][1], best[0][2]


class ScoringVCF:
    """A single-sample VCF, indexed locally once for an entire report."""

    def __init__(self, path):
        self.path = Path(path)
        self.temp = tempfile.TemporaryDirectory(prefix="scholion-pgs-")
        self.db = sqlite3.connect(str(Path(self.temp.name) / "calls.sqlite"))
        self.db.execute("CREATE TABLE calls (chrom TEXT, pos TEXT, record TEXT)")
        self.db.execute("PRAGMA journal_mode=OFF")
        self.sample = None
        self.sha256 = None
        try:
            before = self.path.stat()
            batch = []
            with _open(self.path) as stream:
                for line in stream:
                    if line.startswith("#CHROM"):
                        fields = line.rstrip().split("\t")
                        if len(fields) != 10:
                            raise ValueError("PGS scoring requires exactly one VCF sample")
                        self.sample = fields[9]
                    elif line.startswith("#") or not line.strip():
                        continue
                    else:
                        fields = line.rstrip("\n").split("\t")
                        if self.sample is None or len(fields) != 10:
                            raise ValueError("Invalid single-sample VCF record")
                        fmt = dict(zip(fields[8].split(":"), fields[9].split(":")))
                        gt = re.split(r"[/|]", fmt.get("GT", "."))
                        indices = [int(v) for v in gt] if len(gt) == 2 and all(v.isdigit() for v in gt) else []
                        if fields[6] not in ("PASS", ".") or fmt.get("FT", "PASS") not in ("PASS", "."):
                            indices = []
                        record = json.dumps((fields[3], fields[4].split(","), indices))
                        batch.append((fields[0].removeprefix("chr"), fields[1], record))
                        if len(batch) >= 10000:
                            self.db.executemany("INSERT INTO calls VALUES (?,?,?)", batch)
                            batch = []
            if self.sample is None:
                raise ValueError("Missing VCF sample header")
            self.db.executemany("INSERT INTO calls VALUES (?,?,?)", batch)
            self.db.execute("CREATE INDEX coordinate ON calls(chrom,pos)")
            self.db.commit()
            self.sha256 = _sha(self.path)
            if (before.st_size, before.st_mtime_ns) != (self.path.stat().st_size, self.path.stat().st_mtime_ns):
                raise ValueError("VCF changed while scoring")
            self.stat = (before.st_size, before.st_mtime_ns)
        except Exception:
            self.close()
            raise

    def close(self):
        self.db.close()
        self.temp.cleanup()

    def get(self, chrom, pos):
        return [json.loads(r[0]) for r in self.db.execute(
            "SELECT record FROM calls WHERE chrom=? AND pos=?", (chrom, pos))]

    def score(self, model, build):
        """Return a score, both coverage measures and a reproducible input witness."""
        path = Path(model)
        model_stat = path.stat()
        variants = matched = 0
        parts, total_mass, matched_mass = [], 0.0, 0.0
        reasons = Counter()
        metadata, header = {}, None
        with _open(path) as stream:
            for line in stream:
                if line.startswith("#"):
                    if "=" in line:
                        k, v = line.lstrip("#").strip().split("=", 1)
                        metadata[k] = v
                    continue
                fields = line.rstrip("\n").split("\t")
                if header is None:
                    header = fields
                    if metadata.get("HmPOS_build") != build:
                        raise ValueError("Harmonized model coordinates do not match the genome build")
                    if not {"hm_chr", "hm_pos", "effect_allele"} <= set(header):
                        raise ValueError("Missing harmonized scoring columns")
                    continue
                variants += 1
                row = dict(zip(header, fields))
                try:
                    per_dose = all(f"dosage_{d}_weight" in row for d in range(3))
                    weights = [float(row[f"dosage_{d}_weight"]) for d in range(3)] if per_dose else [float(row["effect_weight"])]
                    if not all(math.isfinite(w) for w in weights):
                        raise ValueError("Non-finite weight")
                    mass = max(abs(w) for w in weights)
                except (KeyError, ValueError):
                    reasons["unsupported_weight"] += 1
                    continue
                total_mass += mass
                chrom, pos = row.get("hm_chr", "").removeprefix("chr"), row.get("hm_pos", "")
                if not chrom or not pos.isdigit():
                    reasons["missing_coordinate"] += 1
                    continue
                records = self.get(chrom, pos)
                if not records:
                    reasons["missing_position"] += 1
                    continue
                other = row.get("other_allele") or row.get("hm_inferOtherAllele") or ""
                # Ambiguous inferred alternatives (e.g. A/G) cannot orient a SNP.
                if not set(other.upper()) <= _BASES:
                    other = ""
                dose, status = dosage(row.get("effect_allele", ""), other, records)
                if dose is None:
                    reasons[status] += 1
                    continue
                dominant = row.get("is_dominant", "False").lower() in ("true", "1")
                recessive = row.get("is_recessive", "False").lower() in ("true", "1")
                if dominant and recessive:
                    reasons["unsupported_weight"] += 1
                    continue
                if per_dose:
                    value = weights[dose]
                else:
                    value = weights[0] * (int(dose > 0) if dominant else int(dose == 2) if recessive else dose)
                parts.append(value)
                matched_mass += mass
                matched += 1
                reasons[status] += 1
        if (model_stat.st_size, model_stat.st_mtime_ns) != (path.stat().st_size, path.stat().st_mtime_ns):
            raise ValueError("Model changed while scoring")
        after = self.path.stat()
        if self.stat != (after.st_size, after.st_mtime_ns):
            raise ValueError("VCF changed while scoring")
        witness = {"checked": not reasons["unsupported_weight"], "algorithm": ALGORITHM,
                   "input_sha256": self.sha256, "input_vcf": str(self.path.resolve()),
                   "model_sha256": _sha(path),
                   "sample": self.sample, "genome_build": build,
                   "input_stat": {"size": self.stat[0], "mtime_ns": self.stat[1]},
                   "model_stat": {"size": model_stat.st_size, "mtime_ns": model_stat.st_mtime_ns},
                   "counts": dict(reasons), "variants_total": variants,
                   "variants_matched": matched, "absent_positions_imputed": 0}
        return {"score": math.fsum(parts), "variants_total": variants, "variants_matched": matched,
                "match_rate": matched / variants if variants else 0.0,
                "weight_mass_total": total_mass, "weight_mass_matched": matched_mass,
                "weight_mass_coverage": matched_mass / total_mass if total_mass else 0.0,
                "scoring_validation": witness, "model_harmonized_build": metadata.get("HmPOS_build"),
                "model_original_build": metadata.get("genome_build"),
                "genome_build": build, "detected_genome_build": build}
