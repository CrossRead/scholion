"""Access to the PERSONAL genomic database (the patient's full VCF).

Separation of layers:
  - loci.json (coordinates) — a PORTABLE public reference book (in knowledge/).
  - the VCF itself (genome/*.full.vcf.gz) — PERSONAL, only on the owner's local machine.
    Path: env SCHOLION_GENOME_VCF, otherwise a search in <repo>/genome/. Never enters git (.gitignore).

A query by position goes through bcftools (when installed) or pysam (fallback). Returns the
patient's genotype in allele letters — used by compute_phenotype and by the locus lookup.
"""
from __future__ import annotations
import glob
import json
import os
import shutil
import subprocess
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t

_ENSEMBL = "https://rest.ensembl.org/variation/human/{}?content-type=application/json"


@lru_cache(maxsize=1)
def loci() -> Dict[str, Any]:
    return core._read_knowledge("loci.json")


def locus(rsid: str) -> Optional[Dict[str, Any]]:
    return loci().get("loci", {}).get(rsid)


# ---- universal resolution rsID → GRCh38 coordinate (live Ensembl + cache) ----
def _cache_file() -> Path:
    p = core.mkdir_private(core.cache_dir())
    return p / "rsid_cache.json"


def _load_cache() -> Dict[str, Any]:
    f = _cache_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        return {}


def _save_cache(d: Dict[str, Any]) -> None:
    try:
        core.write_json(_cache_file(), d, indent=1)
    except Exception:
        pass


def resolve_rsid(rsid: str, allow_network: bool = True) -> Optional[Dict[str, Any]]:
    """Coordinate + annotation for ANY rsID.

    Priority: 1) the curated catalogue loci.json (fast, pharmacogenetics);
    2) the local cache; 3) Ensembl REST live (current ClinVar/dbSNP) → cache.
    Offline or an error → None (then only the catalogue is used). An rsID is a public
    identifier; the patient's genotype is NOT sent anywhere in the process.
    """
    rsid = (rsid or "").strip()
    if not rsid:
        return None
    loc = locus(rsid)
    if loc:
        return {**loc, "rsid": rsid, "source": "catalog"}
    cache = _load_cache()
    if rsid in cache:
        return {**cache[rsid], "rsid": rsid, "source": "cache"}
    if not allow_network:
        return None
    try:
        from . import net
        data = net.get_json(_ENSEMBL.format(rsid))
        if not data:
            return None
        m = [x for x in data.get("mappings", []) if x.get("assembly_name") == "GRCh38"
             and str(x.get("seq_region_name", "")) in _MAIN_CHR]
        if not m:
            return None
        mm = m[0]
        al = (mm.get("allele_string", "") or "").split("/")
        rec = {"chrom": str(mm["seq_region_name"]), "pos": int(mm["start"]),
               "ref": al[0] if al else None, "alt": "/".join(al[1:]) if len(al) > 1 else None,
               "clinical_significance": data.get("clinical_significance", []),
               "consequence": data.get("most_severe_consequence"),
               "gene": None}
        cache[rsid] = rec
        _save_cache(cache)
        return {**rec, "rsid": rsid, "source": "ensembl"}
    except Exception:
        return None


_MAIN_CHR = {str(i) for i in range(1, 23)} | {"X", "Y", "MT", "M"}


def vcf_path() -> Optional[Path]:
    """Path to the personal full VCF. env SCHOLION_GENOME_VCF, or a search in genome/."""
    env = os.environ.get("SCHOLION_GENOME_VCF")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    bases = list(core.genome_bases())
    cfg = core.source_config().get("genome")
    if cfg:
        bases.insert(0, Path(cfg).expanduser())
    for base in bases:
        hits = sorted(glob.glob(str(base / "*.vcf.gz")))
        # ignore the derived ClinVar VCF, take the main one
        hits = [h for h in hits if not h.endswith(".clinvar.vcf.gz")] or hits
        if hits:
            return Path(hits[0])
    return None


#: Assemblies are told apart by the length of a chromosome, which is a fact about
#: the reference rather than a claim in a header somebody may have edited. chr1 is
#: enough on its own; chr2 and chrX are here for files whose header lists only a
#: few contigs. The numbers are the lengths in the primary assembly of each build.
_LENGTH_TO_ASSEMBLY = {
    249250621: "GRCh37", 248956422: "GRCh38", 248387328: "T2T-CHM13v2.0",   # chr1
    243199373: "GRCh37", 242193529: "GRCh38", 242696752: "T2T-CHM13v2.0",   # chr2
    155270560: "GRCh37", 156040895: "GRCh38", 154259566: "T2T-CHM13v2.0",   # chrX
}

#: Only as a fallback: a `##reference=` line says what somebody wrote there, and
#: people write the path to a file they no longer have. A contig length cannot lie.
_REFERENCE_HINTS = (
    ("grch38", "GRCh38"), ("hg38", "GRCh38"),
    ("grch37", "GRCh37"), ("hg19", "GRCh37"), ("b37", "GRCh37"), ("hs37", "GRCh37"),
    ("chm13", "T2T-CHM13v2.0"), ("t2t", "T2T-CHM13v2.0"),
)


def _header_text(vcf: str, limit: int = 4000) -> str:
    """The header of a VCF, however it is compressed. Stdlib only, on purpose.

    `gzip` reads BGZF because BGZF *is* gzip — a conforming reader does not care
    that the stream is made of blocks. So the header is available with no index,
    no bcftools and no pysam, which matters here: the check has to work in the
    installation where the least is present, not in the one where the most is.
    """
    try:
        import gzip
        opener = gzip.open if str(vcf).endswith((".gz", ".bgz")) else open
        out = []
        with opener(vcf, "rt", encoding="utf-8", errors="replace") as fh:   # type: ignore[operator]
            for i, line in enumerate(fh):
                if not line.startswith("#") or i > limit:
                    break
                out.append(line)
        return "".join(out)
    except (OSError, EOFError, UnicodeError):
        return ""


#: The last stretch of chr1 that exists in GRCh37 and does not exist in GRCh38.
#: A variant there is proof the file is not GRCh38 — the coordinate is past the
#: end of that chromosome. The test only ever adds information: rows found means
#: GRCh37, rows not found means nothing at all, and it is reported that way.
_BEYOND_GRCH38_CHR1 = (248956422, 249250621)


def _probe_assembly(vcf: str) -> Optional[str]:
    """Ask the data when the header will not say.

    A header can be silent — `bcftools view -G`, a hand-assembled file, a
    provider that strips contig lines. The variants themselves cannot be: a row
    on chr1 past 248,956,422 cannot exist in GRCh38, because the chromosome ends
    there. One indexed query settles it in one direction, which is more than the
    header gave us.
    """
    lo, hi = _BEYOND_GRCH38_CHR1
    try:
        rows = _query_region_range(vcf, "1", lo + 1, hi)
    except Exception:                                        # noqa: BLE001
        return None
    return "GRCh37" if rows else None


def _query_region_range(vcf: str, chrom: str, start: int, end: int) -> List[List[str]]:
    pref = _chr_prefix(vcf)
    name = f"{pref}{chrom}" if not str(chrom).startswith("chr") else str(chrom)
    if _have_bcftools():
        out = subprocess.run(["bcftools", "view", "-H", "-r", f"{name}:{start}-{end}", vcf],
                             capture_output=True, text=True, timeout=60).stdout
        return [ln.split("\t") for ln in out.splitlines() if ln]
    from . import tabixlite
    return tabixlite.query(vcf, name, start, window=end - start)


@lru_cache(maxsize=8)
def assembly_of(vcf: str) -> Optional[str]:
    """Which reference build this file was called against, or None if it cannot be told.

    None is a real answer and must not be turned into a guess. A file whose header
    carries no contig lengths and no reference line tells us nothing, and refusing
    on nothing is the same mistake as answering on nothing.
    """
    # Declared by the person beats anything we can infer. Someone who knows which
    # build their file is in should be able to say so in one variable rather than
    # be told to rewrite the header of a fifty-gigabyte file.
    declared = os.environ.get("SCHOLION_GENOME_ASSEMBLY")
    if declared:
        return declared.strip()
    head = _header_text(vcf)
    if not head:
        return _probe_assembly(vcf)
    for line in head.splitlines():
        if line.startswith("##contig=") and "length=" in line:
            try:
                length = int(line.split("length=", 1)[1].split(",")[0].split(">")[0])
            except (ValueError, IndexError):
                continue
            hit = _LENGTH_TO_ASSEMBLY.get(length)
            if hit:
                return hit
    for line in head.splitlines():
        if line.startswith("##reference="):
            low = line.lower()
            for needle, name in _REFERENCE_HINTS:
                if needle in low:
                    return name
    return _probe_assembly(vcf)


@lru_cache(maxsize=1)
def catalogue_assembly() -> str:
    """The build the coordinate catalogue is written in. One source: loci.json."""
    try:
        import json
        meta = json.loads((Path(__file__).resolve().parent / "knowledge" / "loci.json")
                          .read_text(encoding="utf-8")).get("_meta") or {}
        return str(meta.get("assembly") or "GRCh38")
    except (OSError, ValueError):
        return "GRCh38"


def unusable_nearby() -> Optional[Dict[str, str]]:
    """A genome file that IS there and cannot be read — named instead of ignored.

    `vcf_path` looks for `*.vcf.gz`, because that is the only shape the readers
    can seek into. Everything else is invisible to it, and "not connected" is
    then printed at a person whose genome is lying in that very folder. For the
    audience this project is for — people who have their own file — that is the
    first thing half of them will meet, and it reads as "your file is not
    supported" rather than "your file needs one command".

    Two shapes get here. A plain `.vcf`, which providers hand out routinely. And
    a `.vcf.gz` compressed with ordinary gzip rather than bgzip: it looks right,
    it is not, and `tabix` on it fails with a message about the format that
    explains nothing to someone who did not know there were two gzips.
    """
    for base in list(core.genome_bases()):
        for plain in sorted(glob.glob(str(base / "*.vcf"))):
            return {"path": plain, "reason": "plain", "fix": f"bgzip -c {plain} > {plain}.gz && tabix -p vcf {plain}.gz"}
        for gz in sorted(glob.glob(str(base / "*.vcf.gz"))):
            try:
                with open(gz, "rb") as fh:
                    head = fh.read(4)
            except OSError:
                continue
            # BGZF is a gzip member carrying an extra field; byte 3 (FLG) has FEXTRA set.
            if head[:2] == b"\x1f\x8b" and not (head[3] & 0x04):   # gzip without FEXTRA → not BGZF
                return {"path": gz, "reason": "gzip_not_bgzip",
                        "fix": f"gunzip -c {gz} | bgzip -c > {gz}.bgz && mv {gz}.bgz {gz} && tabix -p vcf {gz}"}
    return None


def _have_bcftools() -> bool:
    return shutil.which("bcftools") is not None


def available() -> Dict[str, Any]:
    """Status of the genomic database, for the UI and the skill."""
    vp = vcf_path()
    engine = None
    if _have_bcftools():
        engine = "bcftools"
    elif _have_pysam():
        engine = "pysam"
    elif vp is not None and Path(str(vp) + ".tbi").exists():
        engine = "tabixlite"
    # Also when the file WAS found: a gzip-not-bgzip archive is found by the glob,
    # reports «no index», and then tabix refuses it for a reason the message never
    # mentions. Say it here instead of letting the person meet it in tabix.
    near = unusable_nearby() if (vp is None or engine is None) else None
    # The build decides whether the genomic layer may answer at all. Our catalogue
    # is in one assembly; a file called against another puts every locus half a
    # million bases off — APOE rs429358 sits at 19:44,908,684 in GRCh38 and at
    # 19:45,411,941 in GRCh37. The query then lands in a different gene, and the
    # answer comes back either empty (a real finding lost) or full (somebody
    # else's variant reported as APOE). Both are silent. So: refuse, and do not
    # lift coordinates over on the fly — that would add a source of error to the
    # layer that exists to remove them.
    asm = assembly_of(str(vp)) if vp is not None else None
    want = catalogue_assembly()
    asm_mismatch = bool(asm and asm != want)
    return {
        "unusable": near,
        "assembly": asm,
        "assembly_expected": want,
        "assembly_mismatch": asm_mismatch,
        "assembly_unknown": vp is not None and asm is None,
        "vcf_present": vp is not None,
        "vcf": str(vp) if vp else None,
        "engine": engine,
        "ready": vp is not None and engine is not None and not asm_mismatch,
    }


def _have_pysam() -> bool:
    try:
        import pysam  # noqa: F401
        return True
    except Exception:
        return False


@lru_cache(maxsize=8)
def _chr_prefix(vcf: str) -> str:
    """Determine whether the VCF contigs carry the 'chr' prefix."""
    if _have_bcftools():
        try:
            out = subprocess.run(["bcftools", "view", "-h", vcf], capture_output=True, text=True, timeout=30).stdout
            return "chr" if "##contig=<ID=chr" in out else ""
        except Exception:
            pass
    try:
        from . import tabixlite
        ctgs = tabixlite.contigs(vcf)
        if ctgs:
            return "chr" if any(c.startswith("chr") for c in ctgs) else ""
    except Exception:
        pass
    return "chr"


def _query_region(vcf: str, chrom: str, pos: int) -> List[List[str]]:
    """VCF rows at the position (bcftools). Empty = the site is not variant (reference)."""
    pref = _chr_prefix(vcf)
    name = f"{pref}{chrom}" if not str(chrom).startswith("chr") else str(chrom)
    if _have_bcftools():
        region = f"{name}:{pos}-{pos}"
        try:
            r = subprocess.run(["bcftools", "view", "-H", "-r", region, vcf],
                               capture_output=True, text=True, timeout=60)
            return [ln.split("\t") for ln in r.stdout.splitlines() if ln.strip()]
        except Exception:
            return []
    # without bcftools — our own reader of the tabix index (see tabixlite.py)
    try:
        from . import tabixlite
        return tabixlite.query(vcf, name, int(pos))
    except Exception:
        return []


def genotype_from_vcf(rsid: str) -> Optional[Dict[str, Any]]:
    """The patient's genotype by rsID out of the personal VCF.

    Returns {'genotype': 'GA', 'confidence': 'called'|'assumed_ref', 'source': 'vcf', ...}
    or None when there is no database, engine or locus. A missing variant row while the
    database is present = homozygous reference (a -mv VCF does not store reference sites).
    """
    loc = resolve_rsid(rsid, allow_network=False) or locus(rsid)
    if not loc:
        return None
    return _gt_at(loc)


# VCFs called WITHOUT -v: they also hold reference sites (0/0) together with depth.
# Needed to tell «reference, read N times» from «the position is absent from the file».
_SITES_FILES = ("loci_sites.vcf.gz", "scoring_sites.vcf.gz",
                "scoring_sites_ext.vcf.gz", "longevity_sites.vcf.gz")
_MIN_DEPTH = 10          # below this the call is unreliable, we mark it explicitly


def _sites_vcfs() -> List[str]:
    vp = vcf_path()
    if not vp:
        return []
    out = []
    for name in _SITES_FILES:
        p = vp.parent / name
        if p.exists() and (_have_bcftools() or Path(str(p) + ".tbi").exists()):
            out.append(str(p))
    return out


def _ref_evidence(loc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Confirmation of the reference from a sites VCF: a genuine 0/0 with depth.

    A missing row in the main (-mv) VCF means «reference OR no coverage» — these are
    different things and must not be conflated. Here the position is looked up in files
    called without -v; when 0/0 is there, the reference is confirmed and the depth is known.
    """
    for vcf in _sites_vcfs():
        try:
            rows = _query_region(vcf, loc["chrom"], loc["pos"])
        except Exception:
            continue
        for f in rows:
            if len(f) < 10 or str(f[1]) != str(loc["pos"]):
                continue
            fmt, sample = f[8].split(":"), f[9].split(":")
            gt_raw = sample[fmt.index("GT")] if "GT" in fmt else sample[0]
            idx = [i for i in gt_raw.replace("|", "/").split("/") if i.isdigit()]
            if not idx or any(i != "0" for i in idx):
                continue          # not the reference — the main VCF decides
            dp = None
            if "DP" in fmt:
                try:
                    dp = int(sample[fmt.index("DP")])
                except Exception:
                    dp = None
            return {"depth": dp, "evidence_file": Path(vcf).name}
    return None


def _gt_at(loc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The patient's genotype at a resolved locus position (chrom/pos/ref) from the VCF."""
    vp = vcf_path()
    if not vp:
        return None
    if not _have_bcftools() and not Path(str(vp) + ".tbi").exists():
        return None
    ref = loc.get("ref", "N")
    lines = _query_region(str(vp), loc["chrom"], loc["pos"])
    if not lines:
        ev = _ref_evidence(loc)
        if ev:
            dp = ev.get("depth")
            out = {"genotype": f"{ref}{ref}", "confidence": "confirmed_ref", "source": "vcf",
                   "depth": dp, "evidence_file": ev.get("evidence_file"),
                   "note": _t("genome.confirmed_ref")}
            if dp is not None and dp < _MIN_DEPTH:
                out["note"] += _t("genome.low_depth_suffix", depth=dp)
                out["low_depth"] = True
            return out
        return {"genotype": f"{ref}{ref}", "confidence": "assumed_ref", "source": "vcf",
                "note": _t("genome.assumed_ref_note")}
    # take the first variant row at the position
    for f in lines:
        if len(f) < 10:
            continue
        vref, valt = f[3], f[4].split(",")
        fmt = f[8].split(":")
        sample = f[9].split(":")
        gt_raw = sample[fmt.index("GT")] if "GT" in fmt else sample[0]
        idx = [i for i in gt_raw.replace("|", "/").split("/") if i.isdigit()]
        alleles = [vref] + valt
        try:
            gt = "".join(alleles[int(i)] for i in idx)
        except (IndexError, ValueError):
            gt = "?"
        dp = None
        if "DP" in fmt:
            try:
                dp = int(sample[fmt.index("DP")])
            except Exception:
                dp = None
        out = {"genotype": gt, "confidence": "called", "source": "vcf",
               "ref": vref, "alt": f[4], "depth": dp}
        if dp is not None and dp < _MIN_DEPTH:
            out["low_depth"] = True
            out["note"] = _t("genome.low_depth", depth=dp)
        return out
    return {"genotype": f"{ref}{ref}", "confidence": "assumed_ref", "source": "vcf"}


def lookup(rsid: Optional[str] = None, gene: Optional[str] = None) -> Dict[str, Any]:
    """Public lookup: by rsID (any — catalogue/cache/Ensembl) or by gene (catalogue loci)."""
    st = available()
    if rsid:
        loc = resolve_rsid(rsid, allow_network=True)
        if not loc:
            return {"status": "unknown_rsid", "rsid": rsid,
                    "message": _t("genome.rsid_unknown", rsid=rsid)}
        base = {"status": "ok", "rsid": rsid, "gene": loc.get("gene"), "chrom": loc.get("chrom"),
                "pos": loc.get("pos"), "star": loc.get("star"), "note": loc.get("note"),
                "clinical_significance": loc.get("clinical_significance"),
                "consequence": loc.get("consequence"), "resolved_by": loc.get("source")}
        if not st["ready"]:
            base["status"] = "no_genome"
            base["message"] = _t("genome.coordinate_only")
            return base
        base["result"] = _gt_at(loc)
        return base
    if gene:
        items = [rs for rs, l in loci().get("loci", {}).items() if l.get("gene", "").upper() == gene.upper()]
        if not items:
            return {"status": "unknown_gene", "gene": gene}
        return {"status": "ok", "gene": gene,
                "loci": [lookup(rsid=rs) for rs in items] if st["ready"] else [{"rsid": rs, "locus": locus(rs)} for rs in items],
                "genome_ready": st["ready"]}
    return {"status": "error", "message": _t("genome.need_rsid_or_gene")}


# ClinVar clinical significance tiers — in decreasing order of actionability
# The key is the tier; its name and its explanation are printed and live in the catalogue.
_CLINVAR_TIERS = ["pathogenic", "drug", "risk", "protective", "association", "uncertain"]
_TIER_ORDER = {k: i for i, k in enumerate(_CLINVAR_TIERS)}
_REVIEW_RANK = {
    "practice_guideline": 0, "reviewed_by_expert_panel": 1,
    "criteria_provided,_multiple_submitters,_no_conflicts": 2,
    "criteria_provided,_single_submitter": 3,
    "criteria_provided,_conflicting_classifications": 4,
    "no_assertion_criteria_provided": 5,
}
_GENERIC_DN = {"not_specified", "not_provided", "see_cases", ""}


def _clinvar_tier(sig: str) -> str:
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


def _primary_disease(clndn: str) -> str:
    for part in (clndn or "").split("|"):
        p = part.strip()
        if p.lower() not in _GENERIC_DN:
            return p.replace("_", " ")
    return ""


def clinvar_hits(limit: int = 400) -> Dict[str, Any]:
    """The patient's clinically significant findings from genome/clinvar_hits.tsv, laid out
    by tiers of actionability: pathogenic → pharmacogenetics → risk factors → protective →
    weak associations → uncertain. That way the list becomes useful instead of a «wall».

    The file is prepared by annotate_clinvar.sh (fresh ClinVar × the personal VCF)."""
    for base in core.genome_bases():
        f = base / "clinvar_hits.tsv"
        if f.exists():
            break
    else:
        return {"status": "not_run", "hits": [], "tiers": [],
                "message": _t("genome.clinvar_not_run")}
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        return {"status": "error", "message": str(e), "hits": []}
    header = lines[0].split("\t") if lines else []
    rows: List[Dict[str, Any]] = []
    for ln in lines[1:]:
        parts = ln.split("\t")
        if len(parts) < len(header):
            continue
        rec = dict(zip(header, parts))
        tier = _clinvar_tier(rec.get("clnsig", ""))
        rec["tier"] = tier
        rec["disease"] = _primary_disease(rec.get("clndn", ""))
        rec["_rank"] = (_TIER_ORDER.get(tier, 9),
                        _REVIEW_RANK.get((rec.get("review") or "").strip(), 6))
        rows.append(rec)
    rows.sort(key=lambda r: r["_rank"])
    for r in rows:
        r.pop("_rank", None)
    counts = {k: 0 for k in _CLINVAR_TIERS}
    for r in rows:
        counts[r["tier"]] = counts.get(r["tier"], 0) + 1
    tiers = [{"key": k, "label": _t(f"clinvar.tier.{k}"), "hint": _t(f"clinvar.tier.{k}.hint"),
              "count": counts.get(k, 0)}
             for k in _CLINVAR_TIERS if counts.get(k, 0)]
    actionable = counts["pathogenic"] + counts["drug"] + counts["risk"] + counts["protective"]
    return {"status": "ok", "count": len(rows), "actionable": actionable,
            "counts": counts, "tiers": tiers, "hits": rows[:limit], "source": str(f)}


def acmg_sf_catalog() -> Dict[str, Any]:
    return core._read_knowledge("acmg_sf.json")


def penetrance_notes() -> Dict[str, Any]:
    return core._read_knowledge("penetrance.json")


def acmg_sf_findings() -> Dict[str, Any]:
    """ACMG SF secondary findings: a short list of what, once found, calls for action.

    Kept apart from the general ClinVar layer on purpose. The general layer answers «what
    is in the genome at all» and holds everything indiscriminately; this one answers «is
    there anything the medical community considers worth acting on in a healthy person».
    An empty result here is a normal and good outcome, not a sign of breakage.

    The file is prepared by src/ingest/acmg_sf_scan.py.
    """
    cat = acmg_sf_catalog()
    meta = cat.get("_meta", {})
    for base in core.genome_bases():
        f = base / "acmg_sf_hits.tsv"
        if f.exists():
            break
    else:
        return {"status": "not_run", "version": meta.get("version"), "hits": [],
                "message": _t("genome.acmg_not_run")}
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        return {"status": "error", "message": str(e), "hits": []}
    header = lines[0].split("\t") if lines else []
    rows = [dict(zip(header, ln.split("\t"))) for ln in lines[1:] if ln.strip()]
    for r in rows:
        # The phenotype is printed, and the TSV keeps it in the language of the scan.
        # The catalogue is already resolved to the reader's language — take it from there.
        phenotype = (cat.get("genes", {}).get(r.get("gene")) or {}).get("phenotype")
        if phenotype:
            r["phenotype"] = phenotype
    reportable = [r for r in rows if r.get("reportable") == "yes"]
    carriers = [r for r in rows if r.get("reportable") != "yes"]
    return {"status": "ok", "version": meta.get("version"), "published": meta.get("published"),
            "gene_count": meta.get("gene_count"), "new_in_version": meta.get("new_in_v33", []),
            "count": len(rows), "reportable": reportable, "carriers": carriers,
            "hits": rows, "source": str(f), "scanned": core.file_date(f),
            "caveats": meta.get("caveats"), "provenance": meta.get("provenance")}


def apoe_status() -> Dict[str, Any]:
    """The APOE ε status from rs429358 + rs7412 (when the database is connected)."""
    if not available()["ready"]:
        return {"status": "no_genome"}
    g1 = genotype_from_vcf("rs429358")
    g2 = genotype_from_vcf("rs7412")
    if not g1 or not g2:
        return {"status": "no_data"}
    # ε alleles: ε4 = rs429358 C; ε2 = rs7412 T; ε3 = both reference (T, C)
    def eps(a429, a7412):
        if a429 == "C":
            return "ε4"
        if a7412 == "T":
            return "ε2"
        return "ε3"
    a1, a2 = list(g1["genotype"]), list(g2["genotype"])
    # by haplotypes (without phasing — approximately, by the count of alleles)
    e = sorted([eps(a1[0], a2[0]), eps(a1[1], a2[1])])
    return {"status": "ok", "genotype": "/".join(e),
            "rs429358": g1["genotype"], "rs7412": g2["genotype"],
            "note": _t("genome.apoe_note")}
