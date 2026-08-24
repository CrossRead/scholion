#!/usr/bin/env python3
"""Task #10, step 1: superpopulation assignment from the owner's own genotypes.

The question the script answers: is the right reference (EUR 1000G) chosen
for the PGS percentiles. The method needs no Docker/Nextflow: it takes the genotypes
already called from the BAM (longevity_sites.vcf.gz, scattered across the whole genome),
thins them to ~300 positions spaced ≥1 Mb apart (damping LD), pulls the 1000 Genomes
phase 3 frequencies per superpopulation from Ensembl REST (network required — run on the
Mac) and computes the log-likelihood of the genotypes under each population (HWE).

This is an answer at the level of "which of the five superpopulations is closest" — not
fine structure and not admixture percentages. For choosing the percentile reference it
is sufficient; a full PCA projection (pgsc_calc --run_ancestry) is needed only if the
outcome here is ambiguous.

Run:     python3 src/ingest/ancestry_check.py     (~1–2 min, ~300 requests to Ensembl)
Output:  profile/ancestry_check.json + printout. PERSONAL — goes to profile/.
"""
from __future__ import annotations
import gzip, json, math, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VCF = ROOT / "genome/longevity_sites.vcf.gz"
RSMAP = ROOT / "genome/longevity_rsmap.json"
OUT = ROOT / "profile/ancestry_check.json"
SUPERPOPS = ("AFR", "AMR", "EAS", "EUR", "SAS")
MIN_DP = 15
MIN_SPACING = 1_000_000     # ≥1 Mb between positions — LD thinning
TARGET_N = 320
CLAMP = 1e-3                # a frequency of 0 in a population → 0.001 (guard against -inf)

#: Filled by `main()`. It used to be loaded at import, together with a check
#: that exits if the inputs are missing — so merely importing this file read the
#: genome directory, and any invocation at all ran the whole job. There are no
#: arguments to parse either, so `--help` did not ask what it does; it did it.
#: About three hundred requests to Ensembl, on somebody's real genome, from a
#: question. A step of a pipeline has to be askable before it is runnable.
rsmap: dict = {}


def load_panel():
    """Biallelic SNPs with DP≥MIN_DP, thinned by distance. -> [(rsid, chrom, pos, a1, a2)]"""
    rows = []
    with gzip.open(VCF, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 10:
                continue
            chrom, pos, ref, alt = p[0], int(p[1]), p[3], p[4]
            rs = rsmap.get(f"{chrom}:{pos}")
            if not rs:
                continue
            alts = [a for a in alt.split(",") if a not in (".", "<*>")]
            if len(ref) != 1 or any(len(a) != 1 for a in alts) or len(alts) > 1:
                continue
            fmt = dict(zip(p[8].split(":"), p[9].split(":")))
            gt = fmt.get("GT", "./.")
            if "." in gt:
                continue
            try:
                dp = int(fmt.get("DP", "0"))
            except ValueError:
                dp = 0
            if dp < MIN_DP:
                continue
            allele_list = [ref] + alts
            idx = [int(i) for i in gt.replace("|", "/").split("/")]
            a = [allele_list[i] for i in idx]
            if len(a) == 1:      # haploid call (chrX in a male) — doubled for the HWE model
                a = a * 2
            rows.append((rs, chrom, pos, a[0], a[1]))
    rows.sort(key=lambda r: (r[1], r[2]))
    panel, last = [], {}
    for r in rows:
        if r[1] in last and r[2] - last[r[1]] < MIN_SPACING:
            continue
        panel.append(r)
        last[r[1]] = r[2]
    return panel[:TARGET_N]


def fetch_freqs(rsid, tries=3):
    """Ensembl REST: 1000G phase 3 frequencies. -> {pop_label: {allele: freq}} (super- and subpopulations)."""
    url = f"https://rest.ensembl.org/variation/homo_sapiens/{rsid}?pops=1;content-type=application/json"
    for t in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"Content-Type": "application/json"}), timeout=30) as r:
                data = json.loads(r.read())
            out = {}
            for pe in data.get("populations", []):
                name = pe.get("population", "")
                if not name.startswith("1000GENOMES:phase_3:"):
                    continue
                pop = name.rsplit(":", 1)[1]
                out.setdefault(pop, {})[pe.get("allele", "")] = float(pe.get("frequency", 0.0))
            return out
        except Exception:
            time.sleep(2 * (t + 1))
    return None


def _inputs_or_exit(vcf: Path, rsmap_path: Path) -> None:
    """Refuse by name, and only when actually asked to work."""
    for p in (vcf, rsmap_path):
        if not p.exists():
            sys.exit(f"❌ missing input: {p}\n"
                     f"   It is produced by the longevity step of preparing the genome — see\n"
                     f"   `scholion doc preparing-the-genome`.")


def main():
    panel = load_panel()
    print(f"panel: {len(panel)} SNPs (DP≥{MIN_DP}, spacing ≥{MIN_SPACING//1000} kb)")
    ll = {p: 0.0 for p in SUPERPOPS}
    sub_ll = {}
    used = 0
    for i, (rs, chrom, pos, a1, a2) in enumerate(panel):
        freqs = fetch_freqs(rs)
        if not freqs or not all(sp in freqs for sp in SUPERPOPS):
            continue
        het = 2.0 if a1 != a2 else 1.0
        ok = True
        contrib = {}
        for pop, af in freqs.items():
            f1 = min(max(af.get(a1, 0.0), CLAMP), 1 - CLAMP)
            f2 = min(max(af.get(a2, 0.0), CLAMP), 1 - CLAMP)
            contrib[pop] = math.log(het * f1 * f2)
        # superpopulations are the main score; subpopulations are a second layer
        for sp in SUPERPOPS:
            ll[sp] += contrib[sp]
        for pop, v in contrib.items():
            if pop not in SUPERPOPS and pop != "ALL":
                sub_ll[pop] = sub_ll.get(pop, 0.0) + v
        used += 1
        if (i + 1) % 50 == 0:
            print(f"  …{i + 1}/{len(panel)} (used {used})")
        time.sleep(0.08)     # politeness towards Ensembl (~12 rps limit)

    if used < 100:
        sys.exit(f"❌ only {used} usable SNPs — too few for a conclusion; check the network/Ensembl")

    best = sorted(ll, key=ll.get, reverse=True)
    d12 = ll[best[0]] - ll[best[1]]
    # posterior under equal priors
    mx = ll[best[0]]
    w = {p: math.exp(ll[p] - mx) for p in SUPERPOPS}
    s = sum(w.values())
    post = {p: w[p] / s for p in SUPERPOPS}
    subs = sorted(sub_ll, key=sub_ll.get, reverse=True)[:5]

    print("\n== Log-likelihood per superpopulation (higher = closer) ==")
    for p in best:
        print(f"  {p}: {ll[p]:12.1f}   posterior {post[p]:.4f}")
    # ΔLL is the ln of the likelihood ratio: ΔLL=10 already means LR≈2×10⁴
    # ("decisive" on the Jeffreys scale even after allowing for the panel's residual LD).
    # Separately: the closeness of AMR to EUR is expected — AMR is itself half European.
    lr_note = "confident (LR>10⁴)" if d12 > 10 else "AMBIGUOUS — now there is a reason for pgsc_calc"
    print(f"\nΔLL(1st − 2nd) = {d12:.1f} over {used} SNPs ({lr_note})")
    print("Closest subpopulations (a second layer, not a standalone conclusion):")
    for p in subs:
        print(f"  {p}: {sub_ll[p]:.1f}")

    OUT.write_text(json.dumps({
        "date": time.strftime("%Y-%m-%d"),
        "method": "log-likelihood of the genotypes (HWE) under 1000G phase 3 frequencies (Ensembl REST); "
                  f"{used} SNPs from longevity_sites (DP≥{MIN_DP}, spacing ≥1 Mb)",
        "log_likelihood": {p: round(ll[p], 1) for p in SUPERPOPS},
        "posterior": {p: round(post[p], 4) for p in SUPERPOPS},
        "verdict_superpop": best[0],
        "delta_ll_top2": round(d12, 1),
        "closest_subpops": {p: round(sub_ll[p], 1) for p in subs},
        "caveats": [
            "the level of superpopulations, not fine structure and not admixture fractions",
            "the panel is thinned to 1 Mb, but full independence of the SNPs is not guaranteed — read ΔLL qualitatively",
            "frequencies from Ensembl/1000G phase 3; alleles rare in a population are clamped from below at 0.001",
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {OUT}")
    print("Next: python3 src/ingest/prs_ancestry_sensitivity.py")


def _cli(argv=None) -> int:
    """An entry point that can be asked what it does without doing it."""
    import argparse
    global VCF, RSMAP, OUT, rsmap
    ap = argparse.ArgumentParser(
        prog="ancestry_check.py",
        description=("Which 1000 Genomes reference panel this genome is closest to — a step of "
                     "preparing a genome, not a question for the person. Reads the re-genotyped "
                     "longevity sites, thins them to about 300 positions at least 1 Mb apart, "
                     "and compares them against the five panels' allele frequencies from "
                     "Ensembl. NEEDS NETWORK: roughly 300 requests, one to two minutes."),
        epilog=("Writes profile/ancestry_check.json. Nothing applies it on its own: the "
                "percentile changes with the panel, so `scholion prs` reads the verdict and "
                "says where it came from."))
    ap.add_argument("--vcf", type=Path, default=VCF, help=f"re-genotyped sites (default: {VCF})")
    ap.add_argument("--rsmap", type=Path, default=RSMAP, help=f"rsID→position map (default: {RSMAP})")
    ap.add_argument("--out", type=Path, default=OUT, help=f"where the verdict goes (default: {OUT})")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would be read and written, ask Ensembl nothing")
    a = ap.parse_args(argv)

    VCF, RSMAP, OUT = a.vcf, a.rsmap, a.out
    if a.dry_run:
        for label, path in (("reads", VCF), ("reads", RSMAP), ("writes", OUT)):
            print(f"  {label:6s} {path}" + ("" if path.exists() or label == "writes"
                                            else "   ← missing"))
        print("  --dry-run: nothing was fetched and nothing was written.")
        return 0
    _inputs_or_exit(VCF, RSMAP)
    rsmap = json.loads(RSMAP.read_text())
    main()
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
