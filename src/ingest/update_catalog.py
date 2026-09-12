#!/usr/bin/env python3
"""Update of the CURATED locus catalog (knowledge/loci.json) from Ensembl.

Two modes of "updatability" in the project:
  1) Completeness of "all clinically significant SNPs" → annotate_clinvar.sh (a fresh ClinVar).
  2) The hot pharmacogenetics catalog (loci.json) → this script: it checks/refreshes the
     GRCh38 coordinates and clinical significance of the catalog's loci, and can ADD new
     rsIDs (write them in --add rs.. rs..). That is how new knowledge enters the catalog.

The catalog is PORTABLE and PUBLIC — it holds no patient genotypes. It downloads only
public Ensembl records by rsID.

**What this script may not do to an entry that already exists: change its alleles.**
One documented run of `--add` refreshed every existing locus as well and wrote what
Ensembl returns in `alt` — the full observed set, `A/T`, `C/G`, `A/C`. The catalogue's
invariant is one nucleotide in `ref` and one in `alt`; the genotype comparison rests on
it. Thirty-five of fifty-five loci came out compound, among them the ones dose answers
are drawn from — SLCO1B1 for statin myopathy, CYP2C9 for warfarin, CYP2C19 for
clopidogrel. The suite caught it, which is the only reason it was seen: a user who ran
the documented command and does not run the tests would have had a quietly broken
catalogue and a script that printed «Written to:» over it.

So: coordinates and significance are refreshed, alleles are not. A disagreement about
alleles is REPORTED and never applied — if the catalogue is wrong about an allele, that
is a curation decision with a source behind it, not a side effect of a refresh. A new
locus is added only when the source gives exactly one alternative nucleotide; a position
Ensembl reports as three-allele is named and left out, because guessing which of the
three the literature studied would be writing down a number nobody published. And the
whole file is checked against its own invariant before it is written: a run that would
break it writes nothing and exits non-zero.

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
from typing import Any, Dict, List, Tuple

ENSEMBL = "https://rest.ensembl.org/variation/human/{}?content-type=application/json"
MAIN_CHR = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
LOCI = Path(__file__).resolve().parents[1] / "scholion" / "knowledge" / "loci.json"

#: The fields a refresh may rewrite. `ref` and `alt` are deliberately absent —
#: see the module docstring. Keeping the list here rather than inline is the
#: point: the next person adding a field has to decide which side it is on.
REFRESHABLE = ("chrom", "pos", "clinical_significance", "consequence")

#: What counts as a nucleotide the catalogue can hold. Single characters only:
#: the comparison in `genome._gt_at` reads one base from each side.
BASES = set("ACGT")


def fetch(rsid: str) -> Dict[str, Any] | None:
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
    alleles = [a for a in (mm.get("allele_string", "") or "").split("/") if a]
    # The alleles travel as a LIST and are never joined into a string. The bug
    # this script carried was one `"/".join(...)` — a field that holds one
    # nucleotide receiving three, and nothing downstream able to tell.
    return {"chrom": str(mm["seq_region_name"]), "pos": int(mm["start"]),
            "alleles": alleles,
            "clinical_significance": data.get("clinical_significance", []),
            "consequence": data.get("most_severe_consequence")}


def single_pair(alleles: List[str]) -> Tuple[str, str] | None:
    """`['A', 'G'] → ('A', 'G')`; anything else → None, which is an answer."""
    if len(alleles) != 2:
        return None
    ref, alt = alleles[0].upper(), alleles[1].upper()
    if ref in BASES and alt in BASES:
        return ref, alt
    return None


def invariant_problems(cat: Dict[str, Any]) -> List[str]:
    """Every entry holds one nucleotide in `ref` and one in `alt`, or is named here."""
    out: List[str] = []
    for rsid, e in (cat.get("loci") or {}).items():
        if not isinstance(e, dict):
            out.append(f"{rsid}: the entry is not a record")
            continue
        ref, alt = str(e.get("ref") or ""), str(e.get("alt") or "")
        if ref.upper() not in BASES:
            out.append(f"{rsid}: ref={e.get('ref')!r}")
            continue
        # Either a comparable pair, or a position held with the alleles observed
        # there and no alternative chosen — and never both, because an entry
        # carrying both would be compared against the chosen one while looking
        # like it had refused to choose.
        observed = e.get("alleles_observed")
        if observed:
            if alt:
                out.append(f"{rsid}: holds both alt={alt!r} and alleles_observed")
            elif not (isinstance(observed, list) and len(observed) >= 3
                      and all(str(a).upper() in BASES for a in observed)):
                out.append(f"{rsid}: alleles_observed={observed!r}")
            continue
        if alt.upper() not in BASES:
            out.append(f"{rsid}: ref={e.get('ref')!r} alt={e.get('alt')!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", nargs="*", default=[], help="new rsIDs to add")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cat = json.loads(LOCI.read_text(encoding="utf-8"))
    loci = cat.setdefault("loci", {})

    # The entry is created only once the source has answered. The old order —
    # `setdefault(rs, {})` before fetching — left an empty record behind for
    # every rsID the network or the filter refused, and those records then read
    # as loci with no gene and no alleles.
    wanted = [rs for rs in args.add if rs not in loci]

    changed = added = skipped = 0
    disagreed: List[str] = []
    multiallelic: List[str] = []
    for rsid in list(loci.keys()) + wanted:
        rec = fetch(rsid)
        time.sleep(0.2)  # polite towards Ensembl
        if not rec:
            skipped += 1
            continue
        pair = single_pair(rec["alleles"])
        if rsid in loci:
            cur = loci[rsid]
            for k in REFRESHABLE:
                if rec.get(k) is not None and cur.get(k) != rec[k]:
                    cur[k] = rec[k]
                    changed += 1
            # Alleles are compared and not written. A refresh that silently
            # rewrites them is how this file came to hold `A/T` in a field the
            # genotype comparison reads one character from.
            if pair and (str(cur.get("ref") or "").upper(), str(cur.get("alt") or "").upper()) != pair:
                disagreed.append(f"{rsid}: catalogue {cur.get('ref')}>{cur.get('alt')}, "
                                 f"Ensembl {pair[0]}>{pair[1]}")
            elif not pair:
                multiallelic.append(f"{rsid}: {'/'.join(rec['alleles'])}")
            continue
        if not pair:
            # The position is held WITHOUT an alternative allele. Its coordinate
            # and the alleles observed there are facts and are written down;
            # which of the alternatives a paper studied is not in the source, so
            # no `alt` is invented and every reader refuses by name. Task 167:
            # the state is represented rather than the locus dropped.
            multiallelic.append(f"{rsid}: {'/'.join(rec['alleles'])}")
            loci[rsid] = {"chrom": rec["chrom"], "pos": rec["pos"],
                          "ref": (rec["alleles"][0].upper() if rec["alleles"] else None),
                          "alleles_observed": [a.upper() for a in rec["alleles"]],
                          "clinical_significance": rec["clinical_significance"],
                          "consequence": rec["consequence"]}
            added += 1
            continue
        loci[rsid] = {"chrom": rec["chrom"], "pos": rec["pos"],
                      "ref": pair[0], "alt": pair[1],
                      "clinical_significance": rec["clinical_significance"],
                      "consequence": rec["consequence"]}
        added += 1
        print(f"  + {rsid}: {rec['chrom']}:{rec['pos']} {rec.get('consequence','')}")

    cat.setdefault("_meta", {})["catalog_updated"] = time.strftime("%Y-%m-%d")

    print(f"\nTotals: fields updated {changed}, new loci {added}, skipped {skipped}.")
    if disagreed:
        print("\nAlleles NOT changed — the catalogue and Ensembl disagree. "
              "Deciding which is right is curation, with a source, not a refresh:")
        for line in disagreed:
            print("  · " + line)
    if multiallelic:
        print("\nPositions with more than one alternative allele. They are held with the "
              "alleles observed there and NO alternative chosen — which of them a study "
              "meant is not in the source — and every reader refuses on them by name:")
        for line in multiallelic:
            print("  · " + line)

    # The last thing before writing, and the reason it is here: «Written to:»
    # printed over a broken catalogue is worse than a crash, because it reads
    # like success.
    problems = invariant_problems(cat)
    if problems:
        print(f"\n✗ the update would break the catalogue's own invariant "
              f"({len(problems)} entries) — nothing was written:", file=sys.stderr)
        for line in problems[:20]:
            print("  · " + line, file=sys.stderr)
        return 1

    if args.dry_run:
        print("(dry-run — the file was not written)")
        return 0
    LOCI.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written to: {LOCI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
