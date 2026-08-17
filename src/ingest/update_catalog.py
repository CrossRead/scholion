#!/usr/bin/env python3
"""Update of the CURATED locus catalog (knowledge/loci.json) from Ensembl.

Two modes of "updatability" in the project:
  1) Completeness of "all clinically significant SNPs" → annotate_clinvar.sh (a fresh ClinVar).
  2) The hot pharmacogenetics catalog (loci.json) → this script: it checks/refreshes the
     GRCh38 coordinates and clinical significance of the catalog's loci, and can ADD new
     rsIDs (write them in --add rs.. rs..). That is how new knowledge enters the catalog.

The catalog is PORTABLE and PUBLIC — it holds no patient genotypes. It downloads only
public Ensembl records by rsID.

Run (on a machine with internet access):
  python3 update_catalog.py                 # refresh the coordinates of existing loci
  python3 update_catalog.py --add rs1801133 rs1799853   # add new ones + refresh
  python3 update_catalog.py --dry-run       # show what would change, without writing
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ENSEMBL = "https://rest.ensembl.org/variation/human/{}?content-type=application/json"
MAIN_CHR = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
LOCI = Path(__file__).resolve().parents[1] / "scholion" / "knowledge" / "loci.json"


def fetch(rsid: str) -> dict | None:
    req = urllib.request.Request(ENSEMBL.format(rsid),
                                 headers={"User-Agent": "scholion-catalog", "Accept": "application/json"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
    except Exception as e:
        print(f"  ! {rsid}: network/error {e}", file=sys.stderr)
        return None
    m = [x for x in data.get("mappings", [])
         if x.get("assembly_name") == "GRCh38" and str(x.get("seq_region_name", "")) in MAIN_CHR]
    if not m:
        return None
    mm = m[0]
    al = (mm.get("allele_string", "") or "").split("/")
    return {"chrom": str(mm["seq_region_name"]), "pos": int(mm["start"]),
            "ref": al[0] if al else None, "alt": "/".join(al[1:]) if len(al) > 1 else None,
            "clinical_significance": data.get("clinical_significance", []),
            "consequence": data.get("most_severe_consequence")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", nargs="*", default=[], help="new rsIDs to add")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cat = json.loads(LOCI.read_text(encoding="utf-8"))
    loci = cat.setdefault("loci", {})
    for rs in args.add:
        loci.setdefault(rs, {})

    changed, added, skipped = 0, 0, 0
    for rsid in list(loci.keys()):
        rec = fetch(rsid)
        time.sleep(0.2)  # polite towards Ensembl
        if not rec:
            skipped += 1
            continue
        cur = loci[rsid]
        was_new = not cur.get("chrom")
        # keep the manual fields (gene, star, note), refresh coordinates/significance
        for k in ("chrom", "pos", "ref", "alt", "clinical_significance", "consequence"):
            if rec.get(k) is not None and cur.get(k) != rec[k]:
                cur[k] = rec[k]
                changed += 1
        if was_new:
            added += 1
            print(f"  + {rsid}: {rec['chrom']}:{rec['pos']} {rec.get('consequence','')}")
    cat.setdefault("_meta", {})["catalog_updated"] = time.strftime("%Y-%m-%d")

    print(f"\nTotals: fields updated {changed}, new loci {added}, skipped {skipped}.")
    if args.dry_run:
        print("(dry-run — the file was not written)")
        return 0
    LOCI.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written to: {LOCI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
