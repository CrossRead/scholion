"""The ACMG secondary-findings screen, run from the installed package.

Two facts met here and neither was visible from inside.

The screen does not compute when it is asked: it reads a table, and a separate
pass writes that table by matching a personal variant file against ClinVar. The
pass lived in the data-preparation directory, which travels in the source
archive and **not in the wheel** — so after an ordinary `pip install` the product
could say «the ACMG scan has not been run» and offer no way to run it. The
sentence was true and the situation it described was ours.

And the pass matched by POSITION with no check that the two files speak the same
coordinate system. ClinVar is published per assembly; the preparation guide names
the GRCh38 file by default, and a great many personal files are GRCh37. Run
crossed, the scan finds nothing at all — or, worse, matches a position that in
the other build belongs to a different base. A silent zero is the shape of answer
this project exists to remove, and it stood in the one screen whose subject is
whether somebody carries a variant worth acting on today.

So: the scan is here, in the package, reachable by one command with no bcftools,
no tabix and no index — both files are read as streams, from beginning to end.
And the build of each is established the way every build in this project is
established, from the file itself, before a single position is compared.

A third set of facts came out of the audit before 0.4.11, all of one shape: a row
that matched a ClinVar position was taken as a finding without asking whose
genotype it held, which allele it held, or whether it held one at all. Column ten
was read in a family file where column ten is somebody's mother. A row with two
alternate alleles was reported for the pathogenic one when the person carried the
other. A genotype of `./.` — the file saying «not read here» — became a finding,
because a no-call is not a reference and the only test was «is it a reference».
And the build of the ClinVar file was asked of the same reader that answers for
the personal file, so the one variable a person sets to declare THEIR build was
taken as the answer for both, and the crossed-build refusal switched itself off
for exactly the person it was written for. Each of those is now a named step
below: the column is chosen, the allele index is required in the genotype, a
no-call is counted and said, and the ClinVar header is read on its own.

What the screen is, and is not, is unchanged: 84 genes of ACMG SF v3.3, ClinVar
pathogenic and likely-pathogenic only, conflicting interpretations excluded, and
the reporting rule of each gene applied rather than assumed. It does not decide
whether anybody is ill. It does not see structural variants, repeat expansions or
pseudogene regions, and an empty result is a normal and rather good outcome that
means «nothing of this kind was found in what was read».
"""
from __future__ import annotations

import gzip
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from . import core
from .i18n import plural as _plural
from .i18n import t as _t

PATHO_TOKENS = ("Pathogenic", "Likely_pathogenic")
INFO_RE = {k: re.compile(rf"(?:^|;){k}=([^;]*)")
           for k in ("GENEINFO", "CLNSIG", "CLNREVSTAT", "CLNDN", "RS")}

#: Where the published file for each build lives. Named here rather than left to
#: the reader, because «download ClinVar» is the instruction that produced the
#: crossed-build run this module refuses.
CLINVAR_URL = {
    "GRCh38": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz",
    "GRCh37": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/clinvar.vcf.gz",
}

#: How many data lines of the personal VCF pass between two progress reports.
PROGRESS_EVERY = 100000
OUT_NAME = "acmg_sf_hits.tsv"
#: The table's provenance, beside it. A JSON sidecar rather than `#` lines in the
#: table, because the reader of the table takes its first line as the header and
#: a comment line there would become a row.
META_NAME = "acmg_sf_hits.meta.json"
COLS = ["gene", "chrom", "pos", "ref", "alt", "rsid", "zygosity", "reportable",
        "clnsig", "review", "inheritance", "report_rule", "phenotype", "clndn",
        "filter"]

#: What a FILTER column says when the caller stood behind the call. `.` is «no
#: filter was applied», which is not the same as «failed one»; an empty field is
#: the same silence.
_FILTER_PASSED = ("PASS", ".", "")


# ── small readers, identical in meaning to the ones the preparation pass used ──
def _info(info: str, key: str) -> str:
    m = INFO_RE[key].search(info)
    return m.group(1) if m else ""


def _text(value) -> str:
    """A curated field of the catalogue → one string; the table keeps English."""
    if isinstance(value, dict):
        return value.get("en") or next(iter(value.values()), "")
    return value


def _is_plp(sig: str) -> bool:
    """P/LP without the conflicting ones: a conflict is uncertainty, not a finding."""
    if not sig or sig.startswith("Conflicting"):
        return False
    return any(t in sig for t in PATHO_TOKENS)


def _norm_chrom(c: str) -> str:
    c = c[3:] if c.startswith("chr") else c
    return "M" if c == "MT" else c


def _alleles(sample_field: str) -> List[str]:
    """The allele indices of a genotype, phase dropped — `0/1`, `1|2`, `./.`, `1`."""
    return sample_field.split(":")[0].replace("|", "/").split("/")


def _is_no_call(alleles: List[str]) -> bool:
    """`./.` and its haploid `.`: the file did not read this position."""
    return not any(a.isdigit() for a in alleles)


def _zygosity(alleles: List[str], alt_index: int) -> Optional[str]:
    """How many copies of THIS alternate allele the genotype carries.

    None when it carries none: a row `REF G, ALT A,T` with `2/2` matched ClinVar's
    `G>A` by position and by the first ALT, and the person has two copies of T.
    Deciding from «is any allele non-reference» reported them homozygous for a
    variant they do not have. `hom` only when every allele is this one — a
    partial call `./1` is one copy seen, and is written as such.
    """
    want = str(alt_index)
    if want not in alleles:
        return None
    return "hom" if all(a == want for a in alleles) else "het"


def _clinvar_header(path: str) -> Dict[str, Optional[str]]:
    """What the ClinVar header says about itself: its build, and its release date.

    Read here, out of this file's own lines, and NOT through the reader that
    establishes the personal file's build. That reader honours
    `SCHOLION_GENOME_ASSEMBLY` first — a declared build beats anything inferred,
    which is right for the file the person is declaring it about. Routed through
    it, the same variable answered for ClinVar as well, so a person who declared
    GRCh37 for a headerless file and downloaded the GRCh38 ClinVar saw «GRCh37
    against GRCh37» and a scan that ran. The refusal against crossed builds was
    disarmed by the one documented way of naming a build.

    The same rule of evidence as everywhere else, with no declaration on top: a
    contig length is a property of the reference and cannot be stale; the
    `##reference=` line is what somebody wrote, accepted only where no length
    was found.
    """
    from .genome import _LENGTH_TO_ASSEMBLY   # one table of lengths, not two
    out: Dict[str, Optional[str]] = {"assembly": None, "file_date": None}
    by_line: Optional[str] = None
    try:
        with gzip.open(str(path), "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line[0] != "#":
                    break
                if line.startswith("##contig=") and "length=" in line:
                    try:
                        length = int(line.split("length=", 1)[1].split(",")[0].split(">")[0])
                    except (ValueError, IndexError):
                        continue
                    hit = _LENGTH_TO_ASSEMBLY.get(length)
                    if hit and not out["assembly"]:
                        out["assembly"] = hit
                elif line.startswith("##reference=") and by_line is None:
                    value = line.split("=", 1)[1]
                    if "GRCh38" in value or "hg38" in value:
                        by_line = "GRCh38"
                    elif "GRCh37" in value or "hg19" in value:
                        by_line = "GRCh37"
                elif line.startswith("##fileDate="):
                    out["file_date"] = line.split("=", 1)[1].strip() or None
    except (OSError, EOFError):
        return out
    if not out["assembly"]:
        out["assembly"] = by_line
    return out


def clinvar_assembly(path: str) -> Optional[str]:
    """Which build this ClinVar file is published for, read out of the file."""
    return _clinvar_header(path)["assembly"]


def _catalogue() -> Dict[str, Any]:
    """The catalogue WITHOUT language resolution.

    The table this pass writes is an artefact, not a page: the report re-reads
    every printed field from the catalogue in the reader's own language. Reading
    the resolved catalogue here would make the file itself depend on the language
    of whoever happened to run the scan.
    """
    return core._read_knowledge_raw("acmg_sf.json")


def _index(clinvar_vcf: str, genes: Dict[str, Any]):
    """ClinVar P/LP variants in the listed genes → {(chrom,pos,ref,alt): record}."""
    idx: Dict[tuple, Dict[str, str]] = {}
    scanned = 0
    with gzip.open(clinvar_vcf, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            scanned += 1
            if "athogenic" not in line:          # a cheap pre-filter, not a decision
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
            idx[(_norm_chrom(f[0]), f[1], f[3], f[4])] = {
                "genes": sorted(hit), "clnsig": sig,
                "review": _info(info, "CLNREVSTAT"),
                "clndn": _info(info, "CLNDN"),
                "rsid": ("rs" + _info(info, "RS")) if _info(info, "RS") else ""}
    return idx, scanned


def _decide(rows: List[Dict[str, Any]]) -> None:
    """Each gene's own reporting rule, applied — never assumed.

    Only rows whose call the caller itself stood behind take part. A row whose
    FILTER is anything but PASS is written into the table as `filtered` and does
    not enter the count of a gene: a LowQual heterozygote in a biallelic gene must
    not turn the other, clean heterozygote into «needs phase», and must not be
    handed over as a finding on its own.
    """
    per_gene: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        if not r["passed"]:
            r["reportable"] = "filtered"
            continue
        per_gene.setdefault(r["gene"], []).append(r)
    for _gene, rs in per_gene.items():
        rule = rs[0]["report_rule"]
        if rule == "biallelic":
            # A homozygote is unambiguous. Two heterozygotes are not: they are
            # biallelic only in trans, and an unphased file cannot tell that from
            # cis — where the person is a carrier with a normal second copy.
            # Calling two hets «biallelic» turns a carrier into a patient.
            if any(r["zygosity"] == "hom" for r in rs):
                verdict = "yes"
            elif len(rs) >= 2:
                verdict = "needs_phase"
            else:
                verdict = "carrier_only"
            for r in rs:
                r["reportable"] = verdict
        elif rule == "hfe_c282y_hom":
            for r in rs:
                r["reportable"] = ("yes" if (r["rsid"] == "rs1800562" and r["zygosity"] == "hom")
                                   else "carrier_only")
        elif rule in ("truncating_only", "mh_associated_only"):
            # The molecular class decides, and this pass reads significance rather
            # than consequence. So it does not decide: the hit is handed over
            # marked as needing that class established.
            for r in rs:
                r["reportable"] = "needs_variant_class"
        else:
            for r in rs:
                r["reportable"] = "yes"


def read_meta(base) -> Optional[Dict[str, Any]]:
    """The provenance sidecar of the table in `base`, or None where there is none.

    `base` is the folder the table lives in; the table's own path is accepted
    too, for a caller that has just found the table and wants to know what it is.
    A sidecar that does not parse is the same as none: the reader must not build
    on a half-read record of which build a table was matched in.
    """
    p = Path(base)
    if p.suffix == ".tsv":
        p = p.parent
    p = p / META_NAME
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _refuse_sample(genome, personal: str) -> Dict[str, Any]:
    """Why no column of this file can be read as the person.

    Called once `genome.sample_index` has answered None. That reader already
    knows the rule — one sample is the one, several need a choice, a named sample
    must exist — and answers None for every way of failing it. The scan needs
    the reason, because each reason closes differently, and «read column ten»
    is what it was doing before.
    """
    names = genome.samples_of(personal)
    want = os.environ.get("SCHOLION_GENOME_SAMPLE")
    if not names:
        return {"status": "no_sample_column", "message": _t("acmg_scan.no_sample_column")}
    if want:
        return {"status": "sample_not_found", "sample": want, "samples": names,
                "message": _t("acmg_scan.sample_not_found", name=want,
                              names=", ".join(names))}
    cmd = f"SCHOLION_GENOME_SAMPLE={names[0]} scholion acmg-scan"
    return {"status": "several_samples", "samples": names, "fix": cmd,
            "message": _t("acmg_scan.several_samples", names=", ".join(names), cmd=cmd)}


def scan(personal_vcf: Optional[str] = None, clinvar_vcf: Optional[str] = None,
         out_dir: Optional[str] = None,
         progress: Optional[Callable[[int, int, Optional[str]], None]] = None) -> Dict[str, Any]:
    """Run the screen and write the table. Every refusal names what closes it."""
    from . import genome
    personal = personal_vcf or (str(genome.vcf_path()) if genome.vcf_path() else None)
    if not personal or not Path(personal).exists():
        return {"status": "no_genome", "message": _t("acmg_scan.no_genome")}

    # Whose column. A trio or a joint call puts several people side by side, and
    # column ten is the first of them, not the person asking.
    col = genome.sample_index(personal)
    if col is None:
        return _refuse_sample(genome, personal)
    sample = genome.samples_of(personal)[col]

    asm = genome.assembly_of(personal)
    if not asm:
        # Symmetric with the ClinVar refusal below. A file with no contig lengths,
        # no signature and no reference line, and no index for the probe, has a
        # build nobody established — and matching it against a ClinVar whose
        # build IS known is the crossed-build run with one side left blank.
        return {"status": "personal_assembly_unknown",
                "message": _t("acmg_scan.personal_assembly_unknown")}

    if not clinvar_vcf:
        # One search for the published ClinVar, shared with the coverage step
        # and the recompute plan.
        from .coverage import clinvar_path
        found = clinvar_path()
        clinvar_vcf = str(found) if found else (os.environ.get("SCHOLION_CLINVAR_VCF") or None)
    if not clinvar_vcf or not Path(clinvar_vcf).exists():
        # Not «run the preparation»: the one file this needs, named, for the build
        # this person's file is actually in.
        url = CLINVAR_URL.get(asm, CLINVAR_URL["GRCh38"])
        return {"status": "no_clinvar", "assembly": asm, "url": url,
                "message": _t("acmg_scan.no_clinvar", assembly=asm, url=url)}

    cv = _clinvar_header(clinvar_vcf)
    cv_asm = cv["assembly"]
    if cv_asm and asm != cv_asm:
        # The defect this module was written for. Crossed builds do not fail: they
        # return nothing, or they match a coordinate that belongs to another base.
        return {"status": "assembly_mismatch", "assembly": asm, "clinvar_assembly": cv_asm,
                "url": CLINVAR_URL.get(asm, ""),
                "message": _t("acmg_scan.assembly_mismatch", personal=asm, clinvar=cv_asm,
                              url=CLINVAR_URL.get(asm, ""))}
    if not cv_asm:
        return {"status": "clinvar_assembly_unknown", "assembly": asm,
                "url": CLINVAR_URL.get(asm, ""),
                "message": _t("acmg_scan.clinvar_assembly_unknown", assembly=asm,
                              url=CLINVAR_URL.get(asm, ""))}

    cat = _catalogue()
    genes = cat["genes"]
    idx, cv_scanned = _index(clinvar_vcf, genes)
    if not idx:
        return {"status": "clinvar_empty", "clinvar_scanned": cv_scanned,
                "message": _t("acmg_scan.clinvar_empty")}

    rows: List[Dict[str, Any]] = []
    scanned = 0
    no_calls = 0
    total_bytes = os.path.getsize(personal)
    with open(personal, "rb") as raw, \
            gzip.open(raw, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            scanned += 1
            if progress is not None and scanned % PROGRESS_EVERY == 0:
                # Compressed bytes consumed: the one measure of «how far» a
                # stream offers without reading it twice.
                progress(raw.tell(), total_bytes, line.split("\t", 1)[0])
            f = line.rstrip("\r\n").split("\t")
            if len(f) < 10 + col:
                continue
            chrom = _norm_chrom(f[0])
            # The index of each ALT is what the genotype refers to: `1` is the
            # first ALT, `2` the second. ClinVar records one ALT per row, so a
            # match names the index whose copies are to be counted, not the row.
            hits = [(k, alt, idx.get((chrom, f[1], f[3], alt)))
                    for k, alt in enumerate(f[4].split(","), 1)]
            hits = [h for h in hits if h[2]]
            if not hits:
                continue
            alleles = _alleles(f[9 + col])
            if _is_no_call(alleles):
                # The file did not read this position. Neither a reference nor a
                # finding — and not dropped either: the count is said with the
                # result, because «none found» over an unread P/LP position is a
                # weaker sentence than «none found».
                no_calls += 1
                continue
            filt = f[6] if len(f) > 6 else "."
            for k, alt, rec in hits:
                zyg = _zygosity(alleles, k)
                if zyg is None:
                    continue
                for g in rec["genes"]:
                    rows.append({"gene": g, "chrom": f[0], "pos": f[1], "ref": f[3], "alt": alt,
                                 "rsid": rec["rsid"], "zygosity": zyg, "clnsig": rec["clnsig"],
                                 "review": rec["review"], "clndn": rec["clndn"],
                                 "phenotype": _text(genes[g]["phenotype"]),
                                 "inheritance": genes[g]["inheritance"],
                                 "report_rule": genes[g]["report_rule"],
                                 "filter": filt, "passed": filt in _FILTER_PASSED})
    _decide(rows)

    # Where the screen looks. `scholion acmg` reads the table out of the genome
    # folder; writing it beside the variant file put it somewhere else the moment
    # the file lived somewhere else — «ok, the table is written» followed by «the
    # scan has not been run».
    target = Path(out_dir) if out_dir else core.genome_bases()[0]
    target.mkdir(parents=True, exist_ok=True)
    out = target / OUT_NAME
    with out.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in sorted(rows, key=lambda r: (r["reportable"] != "yes", r["gene"])):
            fh.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in COLS) + "\n")

    yes = sum(1 for r in rows if r["reportable"] == "yes")
    filtered = sum(1 for r in rows if r["reportable"] == "filtered")
    meta = {
        "table": OUT_NAME,
        "assembly": asm,
        "clinvar_assembly": cv_asm,
        "clinvar_path": str(Path(clinvar_vcf).resolve()),
        "clinvar_file_date": cv["file_date"],
        "personal_path": str(Path(personal).resolve()),
        "sample": sample,
        "catalogue_version": (cat.get("_meta") or {}).get("version"),
        "scanned": datetime.now().astimezone().isoformat(timespec="seconds"),
        "personal_records": scanned,
        "clinvar_records": cv_scanned,
        "found": len(rows),
        "no_calls": no_calls,
        "filtered": filtered,
    }
    (target / META_NAME).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")

    message = _t("acmg_scan.done", found=len(rows), yes=yes, path=str(out))
    if no_calls:
        message += " " + _plural(no_calls, "acmg_scan.no_calls")
    if filtered:
        message += " " + _plural(filtered, "acmg_scan.filtered")
    return {"status": "ok", "assembly": asm, "clinvar_assembly": cv_asm,
            "clinvar_file_date": cv["file_date"], "sample": sample,
            "version": (cat.get("_meta") or {}).get("version"),
            "genes": len(genes), "clinvar_variants": len(idx),
            "clinvar_scanned": cv_scanned, "scanned": scanned,
            "found": len(rows), "to_discuss": yes,
            "carrier_only": len(rows) - yes - filtered,
            "no_calls": no_calls, "filtered": filtered,
            "table": str(out), "meta": str(target / META_NAME),
            "message": message}
