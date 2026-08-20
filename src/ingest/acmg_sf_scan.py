#!/usr/bin/env python3
"""A pass over the ACMG SF v3.3 secondary findings — strictly by the gene list.

Why this is separate from the general ClinVar layer: clinvar_hits.tsv answers the
question "what significant material is in the genome at all" and holds everything —
from pharmacogenetics to weak associations. ACMG SF answers a different question: "does
a healthy person carry a finding the medical community considers worth acting on".
That is a short, checkable list of 84 genes, and it has to be examined separately.

Input  — TWO files: the personal full VCF (genome/*.full.vcf.gz) and the original NCBI
         ClinVar VCF (~/genomic_work/clinvar/clinvar.vcf.gz). The original one precisely:
         it carries the GENEINFO field with the gene symbol, which our annotated VCF lacks —
         annotate_clinvar.sh transfers only CLNSIG/CLNDN/CLNREVSTAT/RS. The first version
         of this script read the annotated file and silently found zero every time.
Output — genome/acmg_sf_hits.tsv (may be empty — that is a normal and rather good outcome).

    python3 src/ingest/acmg_sf_scan.py [personal.vcf.gz] [clinvar.vcf.gz]

Environment variables: SCHOLION_GENOME_VCF, SCHOLION_CLINVAR_VCF.

The reporting rules are taken from knowledge/acmg_sf.json:
  any            — report on a single P/LP variant;
  biallelic      — only on two (otherwise carriership, flagged separately);
  hfe_c282y_hom  — only the p.C282Y homozygote.
The script does NOT decide whether the person is ill: it only selects what is subject to
discussion with a geneticist at all, and explicitly marks zygosity and review status.
"""
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "src" / "scholion" / "knowledge" / "acmg_sf.json"
OUTDIR = ROOT / "genome"

PATHO_TOKENS = ("Pathogenic", "Likely_pathogenic")
INFO_RE = {k: re.compile(rf"(?:^|;){k}=([^;]*)") for k in ("GENEINFO", "CLNSIG", "CLNREVSTAT", "CLNDN", "RS")}


def _info(info: str, key: str) -> str:
    m = INFO_RE[key].search(info)
    return m.group(1) if m else ""


def _text(value) -> str:
    """A curated field of the catalogue → one string.

    Printed fields in knowledge/*.json are per-language maps ({"en": …, "ru": …}).
    The TSV keeps one language; the report re-reads the phenotype from the catalogue
    in the reader's own language, so English is written here.
    """
    if isinstance(value, dict):
        return value.get("en") or next(iter(value.values()), "")
    return value


def _is_plp(sig: str) -> bool:
    """P/LP without the "conflicting" ones: a conflict is uncertainty, not a finding."""
    if not sig or sig.startswith("Conflicting"):
        return False
    return any(t in sig for t in PATHO_TOKENS)


def _norm_chrom(c: str) -> str:
    c = c[3:] if c.startswith("chr") else c
    return "M" if c == "MT" else c


def _zygosity(sample_field: str) -> str:
    gt = sample_field.split(":")[0].replace("|", "/")
    a = [x for x in gt.split("/") if x.isdigit()]
    if not a:
        return "?"
    if all(x == "0" for x in a):
        return "ref"
    return "hom" if len(set(a)) == 1 else "het"


def _find(argv, n, env, patterns, what):
    if len(argv) > n:
        return Path(argv[n])
    import os
    if os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    for pat in patterns:
        hits = sorted(Path(pat[0]).expanduser().glob(pat[1])) if Path(pat[0]).expanduser().exists() else []
        hits = [h for h in hits if ".clinvar." not in h.name] if what == "personal VCF" else hits
        if hits:
            return hits[0]
    sys.exit(f"{what} not found; give the path as an argument or through {env}")


def build_index(clinvar_vcf: Path, genes: dict):
    """ClinVar P/LP variants in the listed genes → {(chrom,pos,ref,alt): record}."""
    idx, scanned = {}, 0
    with gzip.open(clinvar_vcf, "rt", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            scanned += 1
            if "athogenic" not in line:          # fast pre-filter without a regex
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 8:
                continue
            info = f[7]
            sig = _info(info, "CLNSIG")
            if not _is_plp(sig):
                continue
            hit = {p.split(":")[0] for p in _info(info, "GENEINFO").split("|") if p} & genes.keys()
            if not hit:
                continue
            key = (_norm_chrom(f[0]), f[1], f[3], f[4])
            idx[key] = {"genes": sorted(hit), "clnsig": sig,
                        "review": _info(info, "CLNREVSTAT"),
                        "clndn": _info(info, "CLNDN"),
                        "rsid": ("rs" + _info(info, "RS")) if _info(info, "RS") else ""}
    return idx, scanned


def main(argv) -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    genes = cat["genes"]
    personal = _find(argv, 1, "SCHOLION_GENOME_VCF", [(str(OUTDIR), "*.vcf.gz")], "personal VCF")
    clinvar = _find(argv, 2, "SCHOLION_CLINVAR_VCF",
                    [("~/genomic_work/clinvar", "clinvar.vcf.gz"),
                     (str(OUTDIR), "clinvar.vcf.gz")], "the original ClinVar VCF")
    print(f"personal VCF: {personal}")
    print(f"ClinVar    : {clinvar}")

    idx, cv_scanned = build_index(clinvar, genes)
    print(f"ClinVar P/LP variants across the {len(genes)} genes of the list: {len(idx)} "
          f"(ClinVar records scanned: {cv_scanned})")
    if not idx:
        sys.exit("the index is empty — check that the ClinVar VCF carries the GENEINFO field")

    rows, scanned = [], 0
    with gzip.open(personal, "rt", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            scanned += 1
            f = line.rstrip("\n").split("\t")
            if len(f) < 10:
                continue
            for alt in f[4].split(","):
                rec = idx.get((_norm_chrom(f[0]), f[1], f[3], alt))
                if not rec:
                    continue
                zyg = _zygosity(f[9])
                if zyg == "ref":
                    continue
                for g in rec["genes"]:
                    rows.append({"gene": g, "chrom": f[0], "pos": f[1], "ref": f[3], "alt": alt,
                                 "rsid": rec["rsid"], "zygosity": zyg, "clnsig": rec["clnsig"],
                                 "review": rec["review"], "clndn": rec["clndn"],
                                 "phenotype": _text(genes[g]["phenotype"]),
                                 "inheritance": genes[g]["inheritance"],
                                 "report_rule": genes[g]["report_rule"]})

    per_gene = {}
    for r in rows:
        per_gene.setdefault(r["gene"], []).append(r)
    for g, rs in per_gene.items():
        rule = rs[0]["report_rule"]
        if rule == "biallelic":
            # A HOMOZYGOTE is unambiguous: both copies carry it, whatever the
            # phase. TWO HETEROZYGOTES are not — they are biallelic only if they
            # sit on DIFFERENT chromosomes (in trans). In cis, both on one copy,
            # the person is a carrier with a normal second copy and has the
            # disease no more than any other carrier.
            #
            # A VCF without phase cannot tell those apart, and calling two hets
            # «biallelic» turns a carrier into a patient. Short-read data usually
            # cannot phase variants far enough apart to settle it; a parent's
            # genotype or long reads can.
            hom = any(r["zygosity"] == "hom" for r in rs)
            if hom:
                for r in rs:
                    r["reportable"] = "yes"
            elif len(rs) >= 2:
                for r in rs:
                    r["reportable"] = "needs_phase"
            else:
                for r in rs:
                    r["reportable"] = "carrier_only"
        elif rule == "hfe_c282y_hom":
            for r in rs:
                r["reportable"] = "yes" if (r["rsid"] == "rs1800562" and r["zygosity"] == "hom") else "carrier_only"
        elif rule in ("truncating_only", "mh_associated_only"):
            # The class of the variant decides, and this scan reads ClinVar's
            # significance, not its molecular consequence. So it does not decide:
            # it hands the hit over marked as needing that class established.
            for r in rs:
                r["reportable"] = "needs_variant_class"
        else:
            for r in rs:
                r["reportable"] = "yes"

    OUTDIR.mkdir(exist_ok=True)
    out = OUTDIR / "acmg_sf_hits.tsv"
    cols = ["gene", "chrom", "pos", "ref", "alt", "rsid", "zygosity", "reportable",
            "clnsig", "review", "inheritance", "report_rule", "phenotype", "clndn"]
    with out.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in sorted(rows, key=lambda r: (r["reportable"] != "yes", r["gene"])):
            fh.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols) + "\n")

    yes = sum(1 for r in rows if r["reportable"] == "yes")
    print(f"records of the personal VCF scanned: {scanned}")
    print(f"findings in the ACMG SF {cat['_meta']['version']} genes: {len(rows)} "
          f"(to be discussed: {yes}, carriership only: {len(rows) - yes})")
    print(f"✓ {out}")
    if not rows:
        print("Empty — a normal and rather good result: most people have no secondary "
              "findings. This does NOT mean «there are no genetic risks»: the method does "
              "not see structural variants, repeat expansions or pseudogene regions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
