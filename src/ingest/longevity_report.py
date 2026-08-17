#!/usr/bin/env python3
"""Longevity report: the owner's genotypes × the LongevityMap catalog.

Input:
  - longevity_sites.vcf.gz  (re-genotyped from merged.bam over the LongevityMap BED)
  - longevity_rsmap.json    ("chrN:pos" -> rsID; from build_longevity_sites.py)
  - longevitymap.json       (catalog: rsID -> gene/population/significance/PMID)
Output: a markdown report (which longevity variants the owner carries).

    python3 longevity_report.py <longevity_sites.vcf.gz> <rsmap.json> <catalog.json> [out.md]

PERSONAL (holds genotypes) — keep it in profile/, not in the Project docs.
"""
from __future__ import annotations
import gzip, json, os, sys
from collections import defaultdict
from pathlib import Path

try:                                   # the sample identifier is not in the code
    from _sample import sample_id
except ImportError:                     # launched from outside the script's folder
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _sample import sample_id
SAMPLE_ID = sample_id()


VCF = sys.argv[1]
RSMAP = sys.argv[2]
CATALOG = sys.argv[3]
OUT = sys.argv[4] if len(sys.argv) > 4 else "/tmp/longevity_report.md"

# The direction of the "favourable for longevity" allele comes from the literature, for
# the few well-studied variants. The rest are "carriership, with the direction to be
# looked up in the primary source (PMID)".
KNOWN = {
    "rs2802292": ("FOXO3", "G", "the G allele is associated with longevity (the most replicated longevity variant)"),
    "rs7412":    ("APOE",  "T", "T = the ε2 component (favourable for longevity)"),
    "rs429358":  ("APOE",  "C", "C = the ε4 component (risk: Alzheimer's, shorter lifespan)"),
    "rs2075650": ("TOMM40","G", "G is linked to the ε4 haplotype (risk)"),
    "rs5882":    ("CETP",  "G", "G (Val405) — associated with longevity/cognitive preservation in a number of cohorts"),
    "rs1800795": ("IL6",   "C", "a polymorphism of the IL6 promoter; the direction depends on the population"),
    "rs1799752": ("ACE",   None, "an ACE insertion/deletion; studied in longevity, the results are mixed"),
}


def parse_gt(fmt, sample):
    keys = fmt.split(":")
    vals = sample.split(":")
    d = dict(zip(keys, vals))
    return d.get("GT", "./.")


def load_genotypes(vcf, rsmap):
    """rsID -> (genotype_str, ref, alt, carrier_bool)"""
    out = {}
    op = gzip.open if vcf.endswith(".gz") else open
    with op(vcf, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 10:
                continue
            chrom, pos, _id, ref, alt = p[0], p[1], p[2], p[3], p[4]
            rs = rsmap.get(f"{chrom}:{pos}")
            if not rs:
                continue
            gt = parse_gt(p[8], p[9])
            alleles = [ref] + [a for a in alt.split(",") if a not in (".", "<*>")]
            idx = []
            for tok in gt.replace("|", "/").split("/"):
                if tok.isdigit() and int(tok) < len(alleles):
                    idx.append(int(tok))
            gstr = "/".join(alleles[i] for i in idx) if idx else "./."
            carrier = any(i > 0 for i in idx)  # carries a non-reference allele
            out[rs] = (gstr, ref, alt, carrier)
    return out


def main():
    rsmap = json.load(open(RSMAP, encoding="utf-8"))
    cat = json.load(open(CATALOG, encoding="utf-8"))["variants"]
    geno = load_genotypes(VCF, rsmap)

    sig = lambda m: any(a.lower() == "significant" for a in (m.get("associations") or []))

    genotyped = len(geno)
    carriers = {rs: g for rs, g in geno.items() if g[3]}
    sig_carriers = {rs: g for rs, g in carriers.items() if rs in cat and sig(cat[rs])}

    L = []
    L.append("# Longevity — the genetic layer (LongevityMap)\n")
    L.append(f"_Subject: {SAMPLE_ID}. Source: LongevityMap (HAGR). "
             f"{genotyped} rsIDs of the catalogue were resolved and genotyped; "
             f"a non-reference allele is carried at {len(carriers)}, of which significant associations — {len(sig_carriers)}._\n")
    L.append("## ⚠️ How to read this\n")
    L.append("- LongevityMap is a **literature catalogue** of variants studied in longevity, not a risk score. "
             "Many associations are not replicated and depend on the population (mostly Danish, Caucasian and Italian cohorts).\n")
    L.append("- The catalogue **does not store the direction of the allele**, so for most variants all that can be said is "
             "«you carry a variant in gene X», plus the PMID. For the few well-studied ones (below) the direction is known.\n")
    L.append("- This is a research layer for a conversation with a doctor, **not a diagnosis**.\n")

    # 1. Known famous variants
    L.append("\n## Key (well-studied) variants\n")
    L.append("| rsID | Gene | Your genotype | Interpretation |")
    L.append("|---|---|---|---|")
    for rs, (gene, fav, note) in KNOWN.items():
        if rs in geno:
            gstr, ref, alt, carrier = geno[rs]
            mark = ""
            if fav and fav in gstr.split("/"):
                mark = " ✔carries the stated allele"
            L.append(f"| {rs} | {gene} | {gstr} | {note}{mark} |")
        else:
            L.append(f"| {rs} | {gene} | — (not genotyped) | {note} |")

    # APOE ε hint
    if "rs429358" in geno and "rs7412" in geno:
        g1 = geno["rs429358"][0]; g2 = geno["rs7412"][0]
        L.append(f"\n**APOE:** rs429358={g1}, rs7412={g2}. "
                 "The combination of these two determines ε2/ε3/ε4 (the exact diplotype needs phasing; "
                 "ε4 — risk, ε2 — favourable). Cross-check against the APOE status in the genotype analysis.\n")

    # 2. Significant carriers by gene
    L.append("\n## Significant associations where the variant is carried (by gene)\n")
    if sig_carriers:
        bygene = defaultdict(list)
        for rs, g in sig_carriers.items():
            gene = (cat[rs].get("gene") or "?").split(",")[0]
            bygene[gene].append((rs, g, cat[rs]))
        for gene in sorted(bygene):
            L.append(f"\n**{gene}**\n")
            L.append("| rsID | Genotype | Population | PMID |")
            L.append("|---|---|---|---|")
            for rs, g, m in sorted(bygene[gene]):
                pop = ", ".join(m.get("populations") or [])[:50]
                pm = ", ".join(m.get("pmids") or [])
                L.append(f"| {rs} | {g[0]} | {pop} | {pm} |")
    else:
        L.append("_None — either not genotyped, or a reference homozygote at the significant variants._\n")

    L.append("\n---\n_A research layer. The direction of most associations is not encoded; "
             "consult the primary sources (PMID). Not a medical recommendation._\n")

    open(OUT, "w", encoding="utf-8").write("\n".join(L))

    # --- structured JSON alongside the md (for the application/engine) ---
    known_out = []
    for rs, (gene, fav, note) in KNOWN.items():
        if rs in geno:
            gstr = geno[rs][0]
            known_out.append({"rsid": rs, "gene": gene, "genotype": gstr, "note": note,
                              "carries_named_allele": bool(fav and fav in gstr.split("/"))})
        else:
            known_out.append({"rsid": rs, "gene": gene, "genotype": None, "note": note,
                              "carries_named_allele": None})
    apoe_hint = None
    if "rs429358" in geno and "rs7412" in geno:
        r1, r2 = geno["rs429358"][0], geno["rs7412"][0]
        # ε determination: rs429358 C = the ε4 component, rs7412 T = the ε2 component
        a1 = set(r1.split("/")); a2 = set(r2.split("/"))
        eps = None
        if a1 == {"T"} and a2 == {"C"}:
            eps = "ε3/ε3"
        elif a1 == {"T"} and a2 == {"C", "T"}:
            eps = "ε2/ε3"
        elif a1 == {"T"} and a2 == {"T"}:
            eps = "ε2/ε2"
        elif a1 == {"C", "T"} and a2 == {"C"}:
            eps = "ε3/ε4"
        elif a1 == {"C"} and a2 == {"C"}:
            eps = "ε4/ε4"
        elif a1 == {"C", "T"} and a2 == {"C", "T"}:
            eps = "ε2/ε4"
        apoe_hint = {"rs429358": r1, "rs7412": r2, "epsilon": eps}
    sig_out = {}
    for rs, g in sig_carriers.items():
        gene = (cat[rs].get("gene") or "?").split(",")[0]
        sig_out.setdefault(gene, []).append({
            "rsid": rs, "genotype": g[0],
            "populations": cat[rs].get("populations") or [],
            "pmids": cat[rs].get("pmids") or []})
    data = {
        "_meta": {"source": "LongevityMap (HAGR)", "subject_id": SAMPLE_ID,
                  "genotyped": genotyped, "carriers": len(carriers),
                  "significant_carriers": len(sig_carriers),
                  "disclaimer": ("A literature catalogue, not a risk score. The direction of most "
                                 "associations is not encoded (see the PMIDs). Not a diagnosis.")},
        "apoe": apoe_hint,
        "known": known_out,
        "significant_by_gene": sig_out,
    }
    json_path = OUT[:-3] + ".json" if OUT.endswith(".md") else OUT + ".json"
    import json as _json
    open(json_path, "w", encoding="utf-8").write(_json.dumps(data, ensure_ascii=False, indent=2))

    print(f"✓ {OUT}")
    print(f"✓ {json_path}")
    print(f"  genotyped {genotyped}, carrier at {len(carriers)}, significant-carrier {len(sig_carriers)}"
          + (f", APOE {apoe_hint['epsilon']}" if apoe_hint and apoe_hint.get('epsilon') else ""))


if __name__ == "__main__":
    main()
