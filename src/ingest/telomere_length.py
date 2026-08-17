#!/usr/bin/env python3
"""
Step 2 — estimating telomere length from WGS.

Primary tool: Telomerecat (ploidy-agnostic, installed through pip).
Optional cross-check: TelSeq (if its output is passed via --telseq).

Writes profile/telomere_length.json (the estimate in bp + metadata + caveats)
and prints a human-readable summary.

PREREQUISITES (on the Mac):
    pip install telomerecat            # pulls in pysam/numpy/pandas/parabam
    # optional, for the cross-check: telseq (needs bamtools)

RUN:
    python3 telomere_length.py \
        --bam ~/genomic_work/<SAMPLE>/<SAMPLE>.merged.bam \
        --out profile/telomere_length.json \
        --threads 8

    # with an external TelSeq cross-check:
    #   telseq -r 150 <SAMPLE>.merged.bam > telseq_out.txt
    #   python3 telomere_length.py ... --telseq telseq_out.txt

WARNING: the script has not been tested on data (the bridge was switched off). Review
it before running. A telomere length estimate from WGS is RELATIVE (better suited to
change over time than as an absolute "true" length); DNBSEQ/non-PCR-free protocols can
bias the estimate — interpret it with caution.
"""
import argparse, json, subprocess, sys, csv, os, shutil, tempfile


def run_telomerecat(bam, threads, workdir):
    if not shutil.which("telomerecat"):
        sys.exit("[!] telomerecat not found. Install it: pip install telomerecat")
    out_csv = os.path.join(workdir, "telomerecat_length.csv")
    cmd = ["telomerecat", "bam2length", "-p", str(threads), "--output", out_csv, bam]
    print("[*] Running:", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)
    with open(out_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("[!] telomerecat produced no result rows")
    r = rows[0]
    # the final column 'Length' is the telomere length estimate (bp); matched case-insensitively
    length_key = next((k for k in r if k.strip().lower() == "length"), None)
    if length_key is None:
        length_key = next((k for k in r if "length" in k.strip().lower()), None)
    try:
        length_bp = float(r[length_key]) if length_key else None
    except (TypeError, ValueError):
        length_bp = None
    return {"tool": "telomerecat", "length_bp": length_bp, "raw": r, "csv": out_csv}


def parse_telseq(path):
    # TelSeq emits a table with a header; the LENGTH_ESTIMATE column (kb) is taken
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    if not rows:
        return None
    key = next((k for k in rows[0] if "LENGTH_ESTIMATE" in (k or "").upper()), None)
    if not key:
        return None
    vals = []
    for row in rows:
        try:
            vals.append(float(row[key]))
        except (TypeError, ValueError):
            pass
    if not vals:
        return None
    mean_kb = sum(vals) / len(vals)
    return {"tool": "telseq", "length_kb": round(mean_kb, 3), "n_readgroups": len(vals)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bam", required=True, help="the path to merged.bam")
    ap.add_argument("--out", default="profile/telomere_length.json")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--telseq", help="optional: a TelSeq output file for cross-checking")
    ap.add_argument("--date", default="", help="the run date YYYY-MM-DD (recorded in the JSON)")
    args = ap.parse_args()

    if not os.path.exists(args.bam):
        sys.exit(f"[!] BAM not found: {args.bam}")

    with tempfile.TemporaryDirectory() as workdir:
        tc = run_telomerecat(args.bam, args.threads, workdir)

        result = {
            "date": args.date,
            "bam": os.path.basename(args.bam),
            "primary": {"tool": "telomerecat", "length_bp": tc["length_bp"], "detail": tc["raw"]},
            "caveat": (
                "A telomere-length estimate from WGS is relative, not absolute. "
                "It is better tracked as a trend under an identical sequencing protocol. "
                "DNBSEQ/non-PCR-free can bias it. Not a diagnosis."
            ),
        }
        if args.telseq:
            ts = parse_telseq(args.telseq)
            if ts:
                result["crosscheck_telseq"] = ts

        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n=== Telomere length (WGS) ===")
    bp = result["primary"]["length_bp"]
    print(f"Telomerecat: {bp:.0f} bp" if bp else "Telomerecat: could not be parsed (see the JSON)")
    if result.get("crosscheck_telseq"):
        print(f"TelSeq (cross-check): {result['crosscheck_telseq']['length_kb']} kb")
    print(f"Written to: {args.out}")
    print("Caveat:", result["caveat"])


if __name__ == "__main__":
    main()
