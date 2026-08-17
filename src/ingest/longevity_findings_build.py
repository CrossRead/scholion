#!/usr/bin/env python3
"""Task #9: generator of profile/longevity_findings.json — the longevity layer for the tab.

A distiller: three inputs × curated directions → the JSON that
engine.longevity_findings() reads ({_meta, apoe, known[], significant_by_gene}).

Inputs (paths from the project root, overridable through environment variables):
  genome/longevity_sites.vcf.gz            (re-genotyped from the BAM, SCHOLION_LONGEVITY_VCF)
  genome/longevity_rsmap.json              ("chrN:pos" -> rsID, SCHOLION_LONGEVITY_RSMAP)
  src/scholion/knowledge/longevitymap.json         (the HAGR catalog, SCHOLION_LONGEVITYMAP)
  src/scholion/knowledge/longevity_directions.json (directions, SCHOLION_LONGEVITY_DIR)

Output: profile/longevity_findings.json (the previous one moves to _backups/).

Principles (the owner's decision):
  1) known[] is the curated core with the allele direction taken from primary sources,
     and the status is shown ALWAYS (carrier of the favourable allele / reference / flag) —
     a negative result is information too;
  2) every core entry carries a short "what to do about it" (action);
  3) significant_by_gene holds the statistically significant LongevityMap carrierships
     WITHOUT a direction: honestly marked as a navigator over PMIDs, not as "pluses".

PERSONAL on output (genotypes) — only in profile/, not in the Project docs.
"""
from __future__ import annotations
import gzip, json, os, shutil, sys
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("SCHOLION_REPO_DIR") or Path(__file__).resolve().parents[2])
VCF = Path(os.environ.get("SCHOLION_LONGEVITY_VCF") or ROOT / "genome/longevity_sites.vcf.gz")
RSMAP = Path(os.environ.get("SCHOLION_LONGEVITY_RSMAP") or ROOT / "genome/longevity_rsmap.json")
CATALOG = Path(os.environ.get("SCHOLION_LONGEVITYMAP") or ROOT / "src/scholion/knowledge/longevitymap.json")
DIRECTIONS = Path(os.environ.get("SCHOLION_LONGEVITY_DIR") or ROOT / "src/scholion/knowledge/longevity_directions.json")
OUT = Path(os.environ.get("SCHOLION_LONGEVITY_OUT") or ROOT / "profile/longevity_findings.json")

for p in (VCF, RSMAP, CATALOG, DIRECTIONS):
    if not p.exists():
        sys.exit(f"❌ missing input: {p}")

rsmap = json.loads(RSMAP.read_text())
catalog = json.loads(CATALOG.read_text()).get("variants", {})
dir_doc = json.loads(DIRECTIONS.read_text())
directions = dir_doc.get("directions", {})


def load_genotypes():
    """rsID -> {alleles: [..], gt: 'G/T', ref, carrier, dp}. Called genotypes only (not ./.)."""
    out = {}
    with gzip.open(VCF, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 10:
                continue
            chrom, pos, ref, alt = p[0], p[1], p[3], p[4]
            rs = rsmap.get(f"{chrom}:{pos}")
            if not rs:
                continue
            fmt = dict(zip(p[8].split(":"), p[9].split(":")))
            gt = fmt.get("GT", "./.")
            if "." in gt:
                continue
            alts = [a for a in alt.split(",") if a not in (".", "<*>")]
            allele_list = [ref] + alts
            try:
                idx = [int(i) for i in gt.replace("|", "/").split("/")]
                alleles = [allele_list[i] for i in idx]
            except (ValueError, IndexError):
                continue
            out[rs] = {"alleles": alleles, "gt": "/".join(alleles), "ref": ref,
                       "carrier": any(i > 0 for i in idx), "dp": fmt.get("DP", "")}
    return out


G = load_genotypes()


def _text(value):
    """A curated field of the catalogue → one string.

    Printed fields in knowledge/*.json are per-language maps ({"en": …, "ru": …}).
    This generator reads the catalogue directly, past core's resolver, and the
    profile it writes keeps one language — English, the language of the report.
    """
    if isinstance(value, dict):
        return value.get("en") or value.get("ru") or next(iter(value.values()), "")
    return value


def _all_text(value):
    """Every language of a curated field at once — for matching on the TEXT.

    A heuristic that looks for a word inside a note must not depend on which
    language happens to be resolved: the recessive rule below would silently stop
    firing the day the note is read in the other language.
    """
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values())
    return str(value or "")


def copies_of(rs, allele):
    g = G.get(rs)
    if not g:
        return None
    if allele == "minor":            # recessive entries: the minor allele = non-reference
        return sum(1 for a in g["alleles"] if a != g["ref"])
    return sum(1 for a in g["alleles"] if a.upper() == allele.upper())


# ---- APOE ------------------------------------------------------------------
def apoe_block():
    r429, r7412 = G.get("rs429358"), G.get("rs7412")
    if not r429 or not r7412:
        return {"genotype": "undetermined", "note": "one of the two positions was not read"}
    c = sum(1 for a in r429["alleles"] if a == "C")
    t = sum(1 for a in r7412["alleles"] if a == "T")
    table = {(0, 0): "ε3/ε3", (0, 1): "ε2/ε3", (0, 2): "ε2/ε2",
             (1, 0): "ε3/ε4", (1, 1): "ε2/ε4", (1, 2): "ε1/ε2",
             (2, 0): "ε4/ε4", (2, 1): "ε1/ε4", (2, 2): "ε1/ε1"}
    eps = table.get((c, t), "?")
    notes = {
        "ε2/ε3": "a status favourable for longevity: no ε4 (a below-average population risk of Alzheimer's), ε2 lowers LDL but tends to raise triglycerides/remnants — keep an eye on triglycerides",
        "ε3/ε3": "a neutral (the most common) status",
        "ε2/ε4": "a compound without phase: with C/T+C/T genotypes the very rare ε1/ε3 is theoretically possible too — resolve by phasing if needed",
    }
    return {"genotype": eps,
            "rs429358": r429["gt"] + f" (DP={r429['dp']})",
            "rs7412": r7412["gt"] + f" (DP={r7412['dp']})",
            "note": notes.get(eps, "interpret via the standard table of ε statuses")}


# ---- curated core ----------------------------------------------------------
DEFAULT_VERDICT = {0: "neutral", 1: "lean_plus", 2: "plus"}
# The words by which a note declares a recessive effect, in every language the
# note may be written in. The rule below matches on the TEXT of the note rather
# than on a flag; once the catalogue became multilingual, a Russian-only match
# would have quietly stopped firing and a single copy would have been read as a
# plus. The match therefore runs over all languages of the note at once.
_RECESSIVE_WORDS = ("рецессив", "гомозигот", "recessive", "homozyg")
VERDICT_LABEL = {
    "plus": "🟢 favourable", "plus_partial": "🟢 favourable (partly)",
    "lean_plus": "🟡 a mild plus (half dose)", "neutral": "⚪ neutral/reference",
    "flag": "⚠️ a practical flag", "see_apoe": "→ see the APOE block",
    "not_genotyped": "∅ position not read",
}


def known_block():
    out = []
    for rs, d in directions.items():
        g = G.get(rs)
        entry = {"rsid": rs, "gene": d["gene"], "label": _text(d["label"]),
                 "confidence": d.get("confidence", ""), "pmids": d.get("pmids", [])}
        for opt in ("zygosity_note", "population_caveat", "action"):
            if d.get(opt):
                entry[opt] = _text(d[opt])
        if not g:
            entry.update(genotype="not read", verdict="not_genotyped",
                         status=VERDICT_LABEL["not_genotyped"])
            out.append(entry)
            continue
        entry["genotype"] = g["gt"]
        entry["dp"] = g["dp"]
        if rs in ("rs429358", "rs7412"):
            entry.update(verdict="see_apoe", status=VERDICT_LABEL["see_apoe"])
            out.append(entry)
            continue
        fav = d.get("favorable")
        if fav is None:
            cp = copies_of(rs, "minor")
            vmap = d.get("verdict_by_copies") or {}
            verdict = vmap.get(str(cp), "neutral")
            entry.update(copies_minor=cp, verdict=verdict,
                         status=VERDICT_LABEL.get(verdict, verdict))
        else:
            cp = copies_of(rs, fav)
            vmap = d.get("verdict_by_copies") or {}
            verdict = vmap.get(str(cp)) or DEFAULT_VERDICT.get(cp, "neutral")
            # recessive effects: a single copy does not count as a plus.
            # The rule applies ONLY when the entry has no explicit
            # verdict_by_copies map — an explicit map outranks the heuristic.
            zn = _all_text(d.get("zygosity_note")).lower()
            if not vmap and cp == 1 and any(w in zn for w in _RECESSIVE_WORDS) \
               and verdict in ("lean_plus", "plus_partial"):
                verdict = "neutral"
            fav_label = "minor" if fav == "minor" else fav
            entry.update(copies_favorable=cp, favorable=fav, verdict=verdict,
                         status=f"{VERDICT_LABEL.get(verdict, verdict)} — copies of the favourable allele ({fav_label}): {cp}")
        out.append(entry)
    order = {"plus": 0, "plus_partial": 1, "flag": 2, "lean_plus": 3,
             "see_apoe": 4, "neutral": 5, "not_genotyped": 6}
    out.sort(key=lambda e: (order.get(e["verdict"], 9), e["gene"], e["rsid"]))
    return out


# ---- significant_by_gene (a navigator without a direction) -----------------
def significant_block():
    by_gene = {}
    n_records = n_carriers = 0
    for rs, v in catalog.items():
        if not isinstance(v, dict) or "significant" not in (v.get("associations") or []):
            continue
        n_records += 1
        if rs in directions:
            continue                       # already in the curated core
        g = G.get(rs)
        if not g or not g["carrier"]:
            continue
        n_carriers += 1
        genes = [x for x in (v.get("gene") or "").split(",") if x]
        gene = genes[0] if genes else "?"
        e = {"rsid": rs, "genotype": g["gt"],
             "populations": v.get("populations", []), "pmids": v.get("pmids", []),
             "note": "the direction of the allele is not curated — consult the primary source (PMID)"}
        if len(genes) > 1:
            e["panel_genes"] = len(genes)
            e["note"] = (f"an element of a multi-marker panel ({len(genes)} genes, the gene is nominal) — "
                         "no SNP-level direction has been published")
        by_gene.setdefault(gene, []).append(e)
    for lst in by_gene.values():
        lst.sort(key=lambda e: e["rsid"])
    return by_gene, n_records, n_carriers


apoe = apoe_block()
known = known_block()
sig, n_sig_records, n_sig_carriers = significant_block()

data = {
    "_meta": {
        "generated": str(date.today()),
        "sources": {
            "genotypes": str(VCF.name) + " (re-genotyped from merged.bam over the LongevityMap BED)",
            "catalog": "LongevityMap (HAGR)", "directions": "knowledge/longevity_directions.json",
        },
        "genotyped": len(G),
        "carriers": sum(1 for g in G.values() if g["carrier"]),
        "significant_records": n_sig_records,
        "significant_carriers": n_sig_carriers,
        "known_curated": len(known),
        "unresolved_note": _text((dir_doc.get("unresolved") or {}).get("note", "")),
        "unresolved_genes": (dir_doc.get("unresolved") or {}).get("genes", []),
        "disclaimer": ("Not a diagnosis. The direction of an allele is shown only where it has "
                       "been resolved from primary sources (PMID); «significant» without a "
                       "direction is a navigator over the literature, not a «plus/minus». "
                       "Longevity associations are weaker and less reproducible than clinical "
                       "genetics."),
    },
    "apoe": apoe,
    "known": known,
    "significant_by_gene": sig,
}

if OUT.exists():
    bdir = ROOT / "_backups"
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT, bdir / f"longevity_findings.json.bak-{date.today()}")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✓ {OUT}")
print(f"  positions genotyped: {len(G)}; carriages: {data['_meta']['carriers']}")
print(f"  curated core: {len(known)} entries; significant carriages outside the core: {n_sig_carriers} "
      f"across {len(sig)} genes")
print(f"  APOE: {apoe.get('genotype')}")
print("\nThe core (summary):")
for e in known:
    print(f"  {e['gene']:8} {e['rsid']:12} {e.get('genotype','—'):6} {e.get('status','')}")
