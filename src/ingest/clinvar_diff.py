#!/usr/bin/env python3
"""Diff of two clinvar_hits.tsv snapshots → genome/whats_new.json.

Compares the previous and the fresh snapshot of the patient's ClinVar hits and singles
out what is SIGNIFICANT and new: newly appeared actionable hits (pathogenic/pharmaco-
genetics/risk factors/protective) and variants whose CLASSIFICATION became more actionable
(e.g. uncertain → pathogenic). Noise (association/uncertain) is kept out of the report.

    python3 clinvar_diff.py <prev.tsv> <new.tsv> <out.json> [release] [date]
stdlib only.
"""
import csv, json, sys

_GENERIC_DN = {"not_specified", "not_provided", "see_cases", ""}
_TIER_ORDER = {"pathogenic": 0, "drug": 1, "risk": 2, "protective": 3, "association": 4, "uncertain": 5}
_ACTIONABLE = {"pathogenic", "drug", "risk", "protective"}


def tier(sig):
    s = (sig or "").lower()
    if "pathogenic" in s and "conflicting" not in s:
        return "pathogenic"
    if "drug_response" in s:
        return "drug"
    if "risk" in s and "conflicting" not in s:
        return "risk"
    if "protective" in s:
        return "protective"
    if "association" in s:
        return "association"
    return "uncertain"


def disease(clndn):
    for part in (clndn or "").split("|"):
        p = part.strip()
        if p.lower() not in _GENERIC_DN:
            return p.replace("_", " ")
    return ""


def load(path):
    out = {}
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8"), delimiter="\t"))
    except FileNotFoundError:
        return out
    for r in rows:
        rsid = (r.get("rsid") or "").strip()
        key = rsid if rsid and rsid != "." else f"{r.get('chrom')}:{r.get('pos')}:{r.get('alt')}"
        out[key] = {"rsid": rsid, "clnsig": r.get("clnsig", ""),
                    "disease": disease(r.get("clndn", "")), "tier": tier(r.get("clnsig", ""))}
    return out


def main():
    prev = load(sys.argv[1]) if len(sys.argv) > 1 else {}
    new = load(sys.argv[2])
    out_path = sys.argv[3] if len(sys.argv) > 3 else "whats_new.json"
    release = sys.argv[4] if len(sys.argv) > 4 else ""
    date = sys.argv[5] if len(sys.argv) > 5 else ""

    # The diff historically looked only at appearances and changes. Because of that a
    # collapse from hundreds of hits to a couple of dozen (annotation ran against the wrong
    # VCF) passed silently: "0 new, 0 changed" — formally true. Disappearances now count too.
    new_hits, changed = [], []
    for k, v in new.items():
        if v["tier"] not in _ACTIONABLE:
            continue
        if k not in prev:
            new_hits.append(v)
        elif prev[k]["clnsig"] != v["clnsig"] and _TIER_ORDER[v["tier"]] < _TIER_ORDER.get(prev[k]["tier"], 9):
            changed.append({**v, "old": prev[k]["clnsig"].replace("_", " ")})
    order = lambda x: _TIER_ORDER.get(x["tier"], 9)
    new_hits.sort(key=order); changed.sort(key=order)

    data = {"last_checked": date, "clinvar": {
        "release": release, "new": new_hits, "changed": changed,
        "removed": [prev[k] for k in prev if k not in new],
        "collapse_warning": (
            "WARNING: the number of findings dropped by more than half while the number of "
            "new ones is zero. Almost always this means the wrong input VCF was annotated "
            "(a derived subset instead of the full genome), not a change in ClinVar. "
            "Check which file annotate_clinvar.sh picked, and do not replace "
            "clinvar_hits.prev.tsv until you have worked it out."
            if (prev and len(new) * 2 < len(prev) and not new_hits) else None),
        "counts": {"new": len(new_hits), "changed": len(changed),
                   "removed": len([k for k in prev if k not in new]),
                   "prev_total": len(prev), "new_total": len(new)}}}
    json.dump(data, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    removed_n = len([k for k in prev if k not in new])
    print(f"✓ {out_path}: new actionable {len(new_hits)}, changed {len(changed)}, "
          f"gone {removed_n} (was {len(prev)} → now {len(new)})")
    if prev and len(new) * 2 < len(prev) and not new_hits:
        print("🔴 A COLLAPSE IN THE NUMBER OF FINDINGS with zero new ones — the wrong VCF was "
              "probably annotated. Work it out before relying on clinvar_hits.tsv.")


if __name__ == "__main__":
    main()
