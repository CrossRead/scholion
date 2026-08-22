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
import re
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


def _search_bases() -> List[Path]:
    bases = list(core.genome_bases())
    cfg = core.source_config().get("genome")
    if cfg:
        bases.insert(0, Path(cfg).expanduser())
    return bases


#: Companions of the main VCF, produced by our own pipeline. They sit in the same
#: folder by design and must never be counted as «a second genome»: `loci_sites`
#: and friends are called from the very same reads.
_DERIVED_VCFS = {"loci_sites.vcf.gz", "scoring_sites.vcf.gz",
                 "scoring_sites_ext.vcf.gz", "longevity_sites.vcf.gz"}


#: A gVCF is a valid genome file and is NOT a variants-only VCF: it carries
#: reference BLOCKS rather than one row per site, so a position inside a block
#: returns no row at all. Read as a plain VCF it answers «reference» for whole
#: stretches — including the stretches that were never covered. That is the same
#: silence this layer exists to remove, so a gVCF is named rather than read.
_GVCF_SUFFIXES = (".g.vcf.gz", ".gvcf.gz", ".g.vcf", ".gvcf")


def _is_gvcf(path) -> bool:
    return any(str(path).lower().endswith(s) for s in _GVCF_SUFFIXES)


def vcf_candidates() -> List[Path]:
    """Every file in the search path that could be THE genome — not just the first.

    Task 63. The old code took `sorted(glob(...))[0]` and said nothing. Three real
    shapes break on that, and all three are silent: a per-chromosome set, where
    `chr1.vcf.gz` sorts first and APOE on chromosome 19 then comes back as
    «reference» while `chr19.vcf.gz` is never opened; a folder holding two
    people's files, where the answer is about whoever's name sorts earlier; and a
    trio, which is one file but the same class of mistake one level down.

    Listing them is what makes the refusal possible. Choosing between them is not
    ours to do — the person knows which file is theirs, and `SCHOLION_GENOME_VCF`
    is how they say so.
    """
    out: List[Path] = []
    for base in _search_bases():
        hits = sorted(glob.glob(str(base / "*.vcf.gz")))
        hits = [h for h in hits
                if not h.endswith(".clinvar.vcf.gz")
                and not _is_gvcf(h)
                and Path(h).name not in _DERIVED_VCFS]
        if hits:
            return [Path(h) for h in hits]
    return out


def _resolved_vcf() -> Optional[Path]:
    """The file the search lands on, before it is asked whose it is."""
    env = os.environ.get("SCHOLION_GENOME_VCF")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    hits = vcf_candidates()
    return hits[0] if len(hits) == 1 else None


def not_ours() -> Optional[Dict[str, Any]]:
    """Whether the genome found describes somebody other than this profile.

    Task 102. The project can fetch a published reference genome so that the
    genomic layer has something real to work on. It is a real genome of a real
    other person, and next to the demonstration profile — a fictional third
    person — it would produce a case belonging to nobody: this pharmacogenetic
    genotype, that laboratory history, one report. The folder says whose the
    file is (`SUBJECT.json`), the profile says whose its data are, and when the
    two differ nothing is read.
    """
    from . import subject as _subject
    p = _resolved_vcf()
    return _subject.genome_conflict(p) if p is not None else None


def vcf_path() -> Optional[Path]:
    """Path to the personal full VCF. env SCHOLION_GENOME_VCF, or a search in genome/.

    Returns None when the folder holds MORE THAN ONE candidate. That is not a
    failure to find a genome — `available()` reports it as an ambiguity with the
    names in it — it is a refusal to answer as if the choice had been obvious.

    Returns None as well when the file belongs to a different person from the
    profile (`not_ours`). The check sits HERE, in the one place every reader of
    the genome passes through, rather than beside each conclusion: a caveat
    printed next to an answer is read after the answer has been believed.
    """
    p = _resolved_vcf()
    if p is None:
        return None
    from . import subject as _subject
    return None if _subject.genome_conflict(p) else p


@lru_cache(maxsize=8)
def samples_of(vcf: str) -> List[str]:
    """The sample names on the `#CHROM` line — the list, not the first one.

    A trio, a family file or a joint call carries several. Reading column ten
    without looking is how somebody's mother's genotype is reported as theirs.
    BGZF is ordinary gzip at the member level, so the header reads without tabix.
    """
    import gzip
    try:
        with gzip.open(vcf, "rt", errors="replace") as fh:
            for line in fh:
                if line.startswith("#CHROM"):
                    return line.rstrip("\n").split("\t")[9:]
                if not line.startswith("#"):
                    break
    except Exception:
        return []
    return []


def sample_index(vcf: str) -> Optional[int]:
    """Which column answers — the chosen sample, or None when nobody chose.

    One sample: it is the one, and no choice was needed. Several: the choice is
    the person's, made with `SCHOLION_GENOME_SAMPLE`; until then nothing answers.
    """
    names = samples_of(vcf)
    want = os.environ.get("SCHOLION_GENOME_SAMPLE")
    if want:
        return names.index(want) if want in names else None
    return 0 if len(names) == 1 else None


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

#: What a provider's own pipeline stamps into the header, and which build that
#: pipeline calls against. Task 75.
#:
#: This is the third-weakest evidence there is and it exists for one narrow,
#: real class: an exome or a panel whose header carries no `##contig` lengths
#: and whose data hold no variant past the end of chromosome 1 — nothing to
#: measure and nothing to probe. On a whole genome none of this is reached,
#: because the probe settles it from the data.
#:
#: Two rules make it evidence rather than a guess, and both are enforced by
#: `tests/test_a_provider_signature_names_a_build.py`:
#:
#:   * **every requirement must be present.** A signature that recognises only
#:     the PROVIDER answers nothing: DRAGEN runs against either build, so the
#:     Dante Labs entry demands the reference path as well, and it is the path
#:     that carries the build.
#:   * **every entry says why in prose.** «Sequencing.com → GRCh38» is a claim
#:     about what that service ships, and a claim nobody wrote down is one
#:     nobody can check when it stops being true.
#:
#: What is deliberately NOT here: «an array is GRCh37 by default». That is the
#: silent default this whole layer exists to remove — a genotyping array with
#: no evidence of its build gets `None`, and the genomic layer stays off.
_PROVIDER_SIGNATURES = (
    {"provider": "Sequencing.com", "assembly": "GRCh38",
     "needs": (r"##(source|dataAnalysisProvider)=Sequencing\.com",),
     "why": "the service builds against GRCh38 only, and stamps its own name into the header",
     "sample": "##dataAnalysisProvider=Sequencing.com"},
    {"provider": "Dante Labs (DRAGEN)", "assembly": "GRCh37",
     "needs": (r"##DRAGENCommandLine=<ID=dragen", r"##reference=\S*grch37\S*"),
     "why": ("DRAGEN runs against either build, so the provider alone settles nothing; "
             "the reference path in the same header is what names GRCh37"),
     "sample": ("##DRAGENCommandLine=<ID=dragen,Version=\"05.021\">\n"
                "##reference=file:///references/grch37/reference.bin")},
    {"provider": "Nebula Genomics (MegaBOLT)", "assembly": "GRCh38",
     "needs": (r"MegaBOLT_scheduler",),
     "why": "the MegaBOLT pipeline this provider runs is aligned to GRCh38",
     "sample": "##commandline=MegaBOLT_scheduler --runtype WGS"},
)


def _signature_assembly(head: str) -> Optional[Dict[str, str]]:
    """The provider signature this header carries, if every requirement is met."""
    for sig in _PROVIDER_SIGNATURES:
        if all(re.search(pat, head, re.I) for pat in sig["needs"]):
            return {"assembly": sig["assembly"], "provider": sig["provider"],
                    "why": sig["why"]}
    return None


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
    rows = _query_pysam(vcf, name, start, end)
    if rows is not None:
        return rows
    from . import tabixlite
    return tabixlite.query(vcf, name, start, window=end - start)


#: How a build was established, weakest last. The order is the ranking: a fact
#: about the reference beats a claim in a header, and a claim beats an inference
#: about whoever produced the file.
ASSEMBLY_EVIDENCE = ("declared", "contig_length", "provider_signature",
                     "reference_line", "probe")

#: The two that are neither measured nor stated by the person. Everything shown
#: about a file established this way says so.
ASSEMBLY_WEAK = ("provider_signature", "reference_line")


@lru_cache(maxsize=8)
def assembly_evidence(vcf: str) -> Dict[str, Any]:
    """Which build, and HOW that was established. `{"assembly": None}` if it cannot be.

    Task 75 added the third step and, with it, the reason to return the step at
    all. Four routes lead to the same word «GRCh37», and they are not the same
    claim: a contig length is a fact about the reference, a `##reference=` line
    is a path somebody wrote and may no longer own, and a provider signature is
    an inference about the pipeline that made the file. Returning only the word
    made the strongest and the weakest indistinguishable downstream.
    """
    # Declared by the person beats anything we can infer. Someone who knows which
    # build their file is in should be able to say so in one variable rather than
    # be told to rewrite the header of a fifty-gigabyte file.
    declared = os.environ.get("SCHOLION_GENOME_ASSEMBLY")
    if declared:
        return {"assembly": declared.strip(), "how": "declared"}
    head = _header_text(vcf)
    if not head:
        probed = _probe_assembly(vcf)
        return {"assembly": probed, "how": "probe" if probed else None}
    for line in head.splitlines():
        if line.startswith("##contig=") and "length=" in line:
            try:
                length = int(line.split("length=", 1)[1].split(",")[0].split(">")[0])
            except (ValueError, IndexError):
                continue
            hit = _LENGTH_TO_ASSEMBLY.get(length)
            if hit:
                return {"assembly": hit, "how": "contig_length"}
    # The provider signature goes BEFORE the reference line and after the contig
    # lengths. Before, because a signature identifies the pipeline that actually
    # produced the file, while a reference path is a string about somebody's
    # disk; after, because a length cannot be edited into being wrong without
    # also being a different reference.
    sig = _signature_assembly(head)
    if sig:
        return {"assembly": sig["assembly"], "how": "provider_signature",
                "provider": sig["provider"], "why": sig["why"]}
    for line in head.splitlines():
        if line.startswith("##reference="):
            low = line.lower()
            for needle, name in _REFERENCE_HINTS:
                if needle in low:
                    return {"assembly": name, "how": "reference_line",
                            "detail": line.strip()[:200]}
    probed = _probe_assembly(vcf)
    return {"assembly": probed, "how": "probe" if probed else None}


def assembly_of(vcf: str) -> Optional[str]:
    """Which reference build this file was called against, or None if it cannot be told.

    None is a real answer and must not be turned into a guess. A file whose header
    carries no contig lengths, no signature and no reference line tells us nothing,
    and refusing on nothing is the same mistake as answering on nothing.
    """
    return assembly_evidence(vcf).get("assembly")


#: One cache, one way to clear it. This function used to be the cached one, and
#: callers — tests among them — clear it by name. Keeping a SECOND cache here so
#: that the old name still has a `cache_clear` of its own would leave two stores
#: of the same answer, cleared separately: the project's own defect class, in the
#: function that decides which coordinates a genome is read in.
assembly_of.cache_clear = assembly_evidence.cache_clear                  # type: ignore[attr-defined]
assembly_of.cache_info = assembly_evidence.cache_info                    # type: ignore[attr-defined]


#: Which field of a locus holds its position in which build. The catalogue's own
#: `pos` is and stays GRCh38 — adding a second build must not change the meaning
#: of a field that a hundred lines already read.
_POS_FIELD = {"GRCh38": "pos", "GRCh37": "pos_grch37"}


def locus_position(loc: Dict[str, Any], assembly: Optional[str]) -> Optional[int]:
    """This locus's position in that build, or None if the catalogue lacks it.

    None is an answer: a locus carried in GRCh38 only cannot be read out of a
    GRCh37 file, and the honest response is to say which build the coordinate is
    missing for. What must NOT happen is converting one coordinate into the
    other on the fly — the offset between builds is not constant even inside one
    chromosome (405 kb of spread on chr1 across the pairs measured on the corpus),
    so arithmetic would produce a plausible number pointing at the wrong base.
    """
    field = _POS_FIELD.get(assembly or "")
    if not field:
        return None
    pos = loc.get(field)
    return int(pos) if pos else None


def catalogue_assemblies() -> List[str]:
    """The builds the catalogue can actually answer in, measured not declared.

    GRCh38 is the catalogue's own. GRCh37 is listed only when at least one locus
    carries `pos_grch37`, so a half-filled catalogue cannot advertise a build it
    would then refuse on. The count of loci per build is what `genome-status`
    prints, because «supports GRCh37» and «supports 30 of 54 loci in GRCh37» are
    different promises.
    """
    out = ["GRCh38"]
    if any(l.get("pos_grch37") for l in (loci().get("loci") or {}).values()):
        out.append("GRCh37")
    return out


def catalogue_coverage_by_assembly() -> Dict[str, int]:
    """How many loci each build can be read in — the honest form of the promise."""
    all_loci = (loci().get("loci") or {}).values()
    return {"GRCh38": sum(1 for l in all_loci if l.get("pos")),
            "GRCh37": sum(1 for l in all_loci if l.get("pos_grch37")),
            "total": len(list(all_loci))}


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
            bad = file_unreadable(gz)
            if bad:
                return bad
    return None


def file_unreadable(path) -> Optional[Dict[str, str]]:
    """Is THIS file readable at all — asked of the file that was chosen.

    Task 64, and the reason it is a separate function. The diagnosis below was
    already correct; it was simply never asked when it mattered. `available()`
    called `unusable_nearby()` only when no VCF had been found or no reader was
    installed — and a reader is essentially always installed, so a `.vcf.gz`
    compressed with ordinary gzip was found by the glob, declared «Genome
    connected», and then answered `TT (reference)` at APOE on a file that cannot
    be read at all. The system held both facts and compared neither with the
    other. It is now asked of the chosen file, before anything is declared.
    """
    if path is None:
        return None
    p = str(path)
    if p.endswith(".vcf"):
        return {"path": p, "reason": "plain",
                "fix": f"bgzip -c {p} > {p}.gz && tabix -p vcf {p}.gz"}
    try:
        with open(p, "rb") as fh:
            head = fh.read(4)
    except OSError:
        return None
    # BGZF is a gzip member carrying an extra field; byte 3 (FLG) has FEXTRA set.
    if len(head) == 4 and head[:2] == b"\x1f\x8b" and not (head[3] & 0x04):
        return {"path": p, "reason": "gzip_not_bgzip",
                "fix": f"gunzip -c {p} | bgzip -c > {p}.bgz && mv {p}.bgz {p} && tabix -p vcf {p}"}
    return None


#: Suffix → the class of input it is. Task 64: eleven formats printed one
#: sentence — «the full VCF is not connected» — at people whose file was lying in
#: that very folder. What each of these needs is different, and only naming the
#: class can say which. Extensions decide only what is LOOKED at; a consumer
#: array inside a `.zip` is claimed by the array reader before this table is
#: consulted, and never reaches it.
_FOREIGN_INPUTS = (
    ((".bcf",), "bcf"),
    ((".vcf.bgz", ".vcf.bz2", ".vcf.xz", ".vcf.zst"), "vcf_container"),
    ((".g.vcf.gz", ".gvcf.gz", ".g.vcf"), "gvcf"),
    ((".bam", ".cram", ".sam"), "alignment"),
    ((".fastq", ".fq", ".fastq.gz", ".fq.gz"), "reads"),
    ((".zip", ".tar", ".tar.gz", ".tgz", ".7z", ".rar"), "archive"),
    ((".23andme.txt", ".ancestrydna.txt"), "array"),
)


def _peek_text(path: str, limit: int = 8192) -> str:
    """The first few kilobytes of a file, whatever it is wrapped in.

    By magic bytes, not by extension. The corpus contains a VCF called `.bz2`, a
    VCF called `…vcf_5B1_5D.gz` (a provider URL-encoded the square brackets in
    its own file name) and a VCF that somebody opened in a spreadsheet and saved
    back with every header line in quotes. Not one of them can be recognised
    from its name, and all three are ordinary readable data.
    """
    try:
        with open(path, "rb") as fh:
            head = fh.read(4)
    except OSError:
        return ""
    try:
        if head[:2] == b"\x1f\x8b":
            import gzip as _gz
            with _gz.open(path, "rb") as fh:
                return fh.read(limit).decode("utf-8", "replace")
        if head[:3] == b"BZh":
            import bz2 as _bz
            with _bz.open(path, "rb") as fh:
                return fh.read(limit).decode("utf-8", "replace")
        if head[:6] == b"\xfd7zXZ\x00":
            import lzma as _xz
            with _xz.open(path, "rb") as fh:
                return fh.read(limit).decode("utf-8", "replace")
        if head[:2] == b"PK":
            import zipfile as _zip
            with _zip.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                if not names:
                    return ""
                # The biggest member: a provider archive also carries its README,
                # and a README parses as nothing at all.
                with zf.open(max(names, key=lambda n: zf.getinfo(n).file_size)) as fh:
                    return fh.read(limit).decode("utf-8", "replace")
        with open(path, "rb") as fh:
            return fh.read(limit).decode("utf-8", "replace")
    except Exception:
        return ""


def _sniff_kind(path: str) -> Optional[str]:
    """Name a data file by what is inside it, when its name says nothing useful."""
    text = _peek_text(path)
    if not text:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()][:12]
    if not lines:
        return None
    first = lines[0].lstrip("\ufeff")
    if first.startswith("##fileformat=VCF") or first.startswith('"##fileformat=VCF'):
        # A VCF that went through a spreadsheet: every header line comes back
        # quoted and the commas inside descriptions are now field separators.
        # That is a different repair from «recompress it», so it is a different
        # sentence.
        if any(ln.startswith('"##') for ln in lines[1:]):
            return "vcf_spreadsheet"
        return "vcf_compressed"
    if any(ln.startswith("##FileFormat=Genos") or "##Columns=" in ln for ln in lines):
        return "genotype_table"
    # Complete Genomics shipped its own `var` table for years, and PGP is full of
    # them. It is a variant call set — just not in anybody else's format — and
    # the vendor's own converter turns it into a VCF in one command.
    if any(ln.startswith(">locus") and "varType" in ln for ln in lines) or \
            any("cgatools" in ln for ln in lines if ln.startswith("#")):
        return "cg_var_table"
    body = [ln for ln in lines if not ln.startswith(("#", '"#'))]
    if body:
        cells = body[0].split("\t")
        if len(cells) >= 4 and cells[1].strip().isdigit():
            return "variant_table"
    return None


def foreign_inputs() -> List[Dict[str, str]]:
    """Files in the genome folder that ARE genomic data and are not a readable VCF.

    Each is named by its own class, because «no genome» is false in front of a
    person whose BAM, FASTQ, BCF or provider archive is sitting right there. The
    array reader gets first refusal on archives and text exports: anything it
    claimed is not listed here, so a 23andMe zip reads as an array rather than
    being reported as an unopened archive.
    """
    from . import array_genome as _arr
    claimed = {str(_arr.array_path() or "")}
    out: List[Dict[str, str]] = []
    seen = set()
    for base in _search_bases():
        for hit in sorted(glob.glob(str(base / "*"))):
            if hit in claimed or hit in seen or Path(hit).is_dir():
                continue
            low = hit.lower()
            if low.endswith(".tbi") or low.endswith(".csi"):
                continue
            # The gVCF test comes first: every gVCF name also ends in `.vcf.gz`,
            # and the generic skip below would swallow it into «this is the
            # genome» — which is exactly the reading that goes wrong.
            if _is_gvcf(low):
                seen.add(hit)
                out.append({"path": hit, "kind": "gvcf"})
                continue
            if low.endswith(".vcf.gz") or low.endswith(".vcf"):
                continue
            # The BYTES ARE ASKED FIRST, and the name only after them. A VCF
            # zipped by its provider used to be called «an archive, not opened
            # blind here» — true of the name and false of the file, which holds
            # one member and that member is a VCF. Looking inside is not opening
            # it blind; it is the opposite.
            kind = _sniff_kind(hit)
            if not kind:
                for suffixes, k in _FOREIGN_INPUTS:
                    if any(low.endswith(s) for s in suffixes):
                        kind = k
                        break
            if kind:
                seen.add(hit)
                out.append({"path": hit, "kind": kind})
    return out


def _index_usable(vp) -> bool:
    """An index that works, in either of the two shapes htslib writes.

    Two separate defects met here, and both printed a genotype-shaped non-answer
    — `genotype **?** ()` — over a file nothing could read.

    * Only `.tbi` was ever looked for. `.csi` is what tabix writes for long
      contigs and what several providers ship; a file indexed that way was
      declared connected and then answered nothing.
    * The reader was chosen by what is INSTALLED, not by what can be done with
      this file. pysam is installed almost everywhere, so a file with no index at
      all — or with a truncated one — reported «Genome connected» and answered
      out of an empty query. Every reader here seeks by position, so every reader
      needs an index; asking for one is not a preference of one backend.
    """
    tbi, csi = _tbi_usable(vp, ".tbi"), _tbi_usable(vp, ".csi")
    if not (tbi or csi):
        return False
    # `.csi` is readable by bcftools and by pysam. Our own `tabixlite` reads the
    # tabix index only — so on a machine with neither library a csi-only file is
    # NOT readable, and saying otherwise is how it came to answer «reference» at
    # every locus. The phase-0 report closed this item after measuring it on a
    # machine that had bcftools; the conclusion was true there and false here.
    return True if (_have_bcftools() or _have_pysam()) else tbi


def _tbi_usable(vp, suffix: str = ".tbi") -> bool:
    """A .tbi that EXISTS is not necessarily a .tbi that WORKS.

    tabixlite swallows a read error and returns nothing, and «nothing at this
    position» then becomes «homozygous reference» with an assumed_ref label — on
    every locus at once. Reproduced by truncating the index: the person was
    declared reference at SLCO1B1, CYP2C19, DPYD, TPMT and given advice on it. A
    real tabix index is a BGZF file; the cheap, honest check is that the sidecar
    is non-empty and carries the gzip magic. A deeper corruption still slips
    through — but the empty/truncated case, which is what a failed index build
    leaves behind, does not.
    """
    from pathlib import Path as _P
    tbi = _P(str(vp) + suffix)
    try:
        with open(tbi, "rb") as fh:
            head = fh.read(2)
    except OSError:
        return False
    return len(head) == 2 and head == b"\x1f\x8b"


#: The three readers this project can put a genome through, strongest first.
#: A closed vocabulary, because `SCHOLION_GENOME_ENGINE=bcftool` must not read
#: as «no preference» — that is the silent default the pin exists to remove.
ENGINES = ("bcftools", "pysam", "tabixlite")


def engine_pin() -> Optional[str]:
    """Which reader the person pinned, if any.

    Task 78. Without this the reader is whichever happens to be installed
    (`shutil.which("bcftools")`), and that is a property of the machine, not of
    the project. It matters for one specific reason: the internal reference
    test is run to measure what a NEW user gets — somebody with no external
    tools, going through `tabixlite` — and on a machine that has bcftools the
    same run silently measures the other path instead. The instrument was
    reading a different scale from the one printed on it. With the pin the run
    is made twice, once through each reader, and a disagreement between them is
    itself a measurement.
    """
    v = (os.environ.get("SCHOLION_GENOME_ENGINE") or "").strip()
    return v or None


def engine_problem() -> Optional[Dict[str, str]]:
    """Why a pinned reader cannot be used — a word nobody declared, or one that
    is not installed here.

    Both are refusals rather than fallbacks, and that is the whole point. Silently
    ignoring the pin gives a run through a different reader than the one asked
    for, which is exactly the state this was written to end — and it would do it
    at the moment somebody is trying to measure carefully.
    """
    pin = engine_pin()
    if pin is None:
        return None
    if pin not in ENGINES:
        return {"reason": "engine_unknown", "value": pin,
                "accepted": ", ".join(ENGINES)}
    if pin == "bcftools" and shutil.which("bcftools") is None:
        return {"reason": "engine_missing", "value": pin, "accepted": ""}
    if pin == "pysam" and not _pysam_importable():
        return {"reason": "engine_missing", "value": pin, "accepted": ""}
    return None


def _have_bcftools() -> bool:
    pin = engine_pin()
    if pin is not None and pin != "bcftools":
        return False
    return shutil.which("bcftools") is not None


def available() -> Dict[str, Any]:
    """Status of the genomic database, for the UI and the skill."""
    vp = vcf_path()
    # Whose file it is, asked before why it cannot be read: a genome belonging to
    # another person is not an unreadable one, and answering «no genome found»
    # at it would send the reader to look for a file they are holding.
    foreign_person = not_ours()
    # A pin that cannot be honoured stops the layer instead of quietly moving to
    # another reader: somebody who names a reader is measuring, and a measurement
    # taken through the wrong instrument is worse than one not taken.
    engine_bad = engine_problem()
    # The file is asked whether it can be read BEFORE anything is declared about
    # it. This order is the whole of task 64's third item: the check existed and
    # was skipped exactly when a reader was installed, which is almost always.
    near = (file_unreadable(vp) if vp is not None else
            (None if foreign_person else unusable_nearby()))
    if near is not None:
        vp = None
    engine = None
    if engine_bad is not None:
        vp = None
    if vp is not None and _index_usable(vp):
        engine = ("bcftools" if _have_bcftools() else
                  "pysam" if _have_pysam() else "tabixlite")
    # Task 63: several files, or several samples inside one file, is a question
    # for the person and not a coin toss. Both are carried as one shape so that
    # every consumer — CLI, web, plugin, model — meets the same field.
    candidates = vcf_candidates() if not os.environ.get("SCHOLION_GENOME_VCF") else []
    samples = samples_of(str(vp)) if vp is not None else []
    chosen_i = sample_index(str(vp)) if vp is not None else None
    ambiguous = None
    named = os.environ.get("SCHOLION_GENOME_SAMPLE")
    if vp is not None and named and named not in samples:
        # An explicit choice that the file does not contain is not an ambiguity —
        # it is a typo, and answering «no genome» at it would send the person to
        # look for a file they are already holding.
        ambiguous = {"reason": "sample_not_found", "choices": list(samples),
                     "fix": f"SCHOLION_GENOME_SAMPLE={samples[0]} scholion genome-status"
                            if samples else ""}
    elif len(candidates) > 1:
        ambiguous = {"reason": "several_files",
                     "choices": [str(p) for p in candidates],
                     "fix": f"SCHOLION_GENOME_VCF={candidates[0]} scholion genome-status"}
    elif vp is not None and len(samples) > 1 and chosen_i is None:
        ambiguous = {"reason": "several_samples", "choices": list(samples),
                     "fix": f"SCHOLION_GENOME_SAMPLE={samples[0]} scholion genome-status"}
    foreign = foreign_inputs()
    # The build decides whether the genomic layer may answer at all. Our catalogue
    # is in one assembly; a file called against another puts every locus half a
    # million bases off — APOE rs429358 sits at 19:44,908,684 in GRCh38 and at
    # 19:45,411,941 in GRCh37. The query then lands in a different gene, and the
    # answer comes back either empty (a real finding lost) or full (somebody
    # else's variant reported as APOE). Both are silent. So: refuse, and do not
    # lift coordinates over on the fly — that would add a source of error to the
    # layer that exists to remove them.
    # An array is a DIFFERENT CLASS of input, not a weaker VCF. It is reported
    # beside the sequenced path rather than folded into it, so that no consumer
    # can read `ready` and quietly believe it has a genome: `input_class` is the
    # field that says what actually answered, and `limits` prints its ceiling.
    from . import array_genome as _arr
    arr = _arr.summary()
    # A third class of input, and it earns its own name for the same reason the
    # array does (task 89): a VCF that arrived in a container and a table of
    # chosen positions are both readable, and neither is a seekable genome. The
    # scan is only started when nothing better is present, because it is one pass
    # over the whole file.
    tab = {"available": False}
    if vp is None and not arr.get("available"):
        try:
            from . import tabular_genome as _tab
            tab = _tab.summary()
        except Exception:
            tab = {"available": False}
    asm_ev = assembly_evidence(str(vp)) if vp is not None else {}
    asm = asm_ev.get("assembly")
    want = catalogue_assembly()
    # A file in a build the catalogue carries coordinates for is NOT a mismatch.
    # It used to be: `loci.json` existed only in GRCh38, so seven of the eight
    # real genomes in the PGP corpus were turned away — correctly, given what the
    # catalogue then knew, and uselessly, given what the files were.
    served = catalogue_assemblies()
    asm_mismatch = bool(asm and asm not in served)
    ready = ((vp is not None and engine is not None and not asm_mismatch
              and ambiguous is None and chosen_i is not None)
             or bool(arr.get("available")) or bool(tab.get("available")))
    return {
        "unusable": near,
        # Which reader answered, and whether it was chosen or merely available.
        # Two runs of the reference test that name different readers are not
        # comparable, and until this field existed nothing said which was which.
        "engine_pinned": engine_pin(),
        "engine_problem": engine_bad,
        # Not a fault of the file and not an ambiguity: the file is readable and
        # is somebody else's. It travels as its own field so that no consumer can
        # fold it into «no genome» — which is the sentence that would let the two
        # people quietly become one case.
        "not_ours": foreign_person,
        # Which file, whose sample, and what else was lying beside it. Silence on
        # any of the three is what let «the first one alphabetically» pass for an
        # answer about a person.
        "vcf_count": len(candidates),
        "vcf_choices": [str(p) for p in candidates] if len(candidates) > 1 else [],
        "samples": samples,
        "sample": samples[chosen_i] if (chosen_i is not None and chosen_i < len(samples)) else None,
        "ambiguous": ambiguous,
        "foreign": foreign,
        "assembly": asm,
        # HOW the build was established, not only what it is. A build taken from
        # a provider's signature or from a `##reference=` path is a weaker claim
        # than one measured off a contig length, and the difference belongs where
        # the answer is, not in a release note.
        "assembly_how": asm_ev.get("how"),
        "assembly_provider": asm_ev.get("provider"),
        "assembly_why": asm_ev.get("why"),
        "assembly_detail": asm_ev.get("detail"),
        "assembly_weak": asm_ev.get("how") in ASSEMBLY_WEAK,
        "assembly_expected": want,
        # Which coordinate set will actually be used to read this file, and how
        # much of the catalogue is reachable that way. A build the catalogue only
        # half covers is a different promise from one it covers whole, and the
        # difference belongs in the answer rather than in a release note.
        "assembly_served": served,
        "coordinates": asm if (asm in served) else None,
        "catalogue_by_assembly": catalogue_coverage_by_assembly(),
        "assembly_mismatch": asm_mismatch,
        "assembly_unknown": vp is not None and asm is None,
        "vcf_present": vp is not None,
        "vcf": str(vp) if vp else None,
        "engine": engine,
        "array": arr if arr.get("available") else None,
        # A file that IS an array and could not be read is a third state, and it
        # has to be visible: `array: null` alone reads as «no array here».
        "array_unreadable": (arr.get("reason") == "array_unreadable"),
        "tabular": tab if tab.get("available") else None,
        # What is ACTUALLY in this file — measured, not assumed. `input_class`
        # stays two-valued for everything already reading it; `input_profile` is
        # the measured class, and that is the one deciding what may be promised.
        "callset": (_callset_of(vp) if (vp is not None and engine is not None
                                        and not asm_mismatch and ambiguous is None
                                        and chosen_i is not None) else None),
        "input_profile": ((_callset_of(vp) or {}).get("class")
                          if (vp is not None and engine is not None and not asm_mismatch
                              and ambiguous is None and chosen_i is not None)
                          else ("array" if arr.get("available")
                                else (tab.get("class") if tab.get("available") else None))),
        "input_class": ("sequenced" if (vp is not None and engine is not None
                                        and not asm_mismatch and ambiguous is None
                                        and chosen_i is not None)
                        else ("array" if arr.get("available")
                              else ("tabular" if tab.get("available") else None))),
        "ready": ready,
        # One machine-readable word for «why not», so that the locus command and
        # the status command cannot tell a person two different stories about the
        # same folder — which is what task 64's second item was.
        "reason": (None if ready else
                   ((ambiguous or {}).get("reason") if ambiguous else
                    None) or (
                    (engine_bad or {}).get("reason") if engine_bad else
                    None) or (
                    "another_person" if foreign_person else
                    "unreadable_file" if near else
                    "assembly_unsupported" if asm_mismatch else
                    "no_engine" if (vp is not None and engine is None) else
                    "sample_not_chosen" if (vp is not None and chosen_i is None) else
                    "foreign_input" if foreign else
                    "no_file")),
    }


#: Every value `available()["reason"]` can take. An explicit enumeration rather
#: than a set of literals scattered through one conditional, because
#: `tests/test_no_refusal_prints_a_key.py` has to be able to walk it: a reason
#: added without a sentence is what printed ⟦genome.refused_head.not_on_chip⟧ at
#: half the array owners in the reference corpus.
REFUSAL_REASONS = (
    "unreadable_file", "assembly_unsupported", "no_engine", "sample_not_chosen",
    "foreign_input", "no_file", "several_files", "several_samples",
    "sample_not_found", "another_person", "engine_unknown", "engine_missing",
)


def _callset_of(vp) -> Optional[Dict[str, Any]]:
    """Measured contents of the chosen VCF; never raises into a status command."""
    try:
        from . import callset
        return callset.measure(str(vp))
    except Exception:
        return None


def _pysam_importable() -> bool:
    try:
        import pysam  # noqa: F401
        return True
    except Exception:
        return False


def _have_pysam() -> bool:
    pin = engine_pin()
    if pin is not None and pin != "pysam":
        return False
    return _pysam_importable()


@lru_cache(maxsize=8)
def _chr_prefix(vcf: str) -> str:
    """Determine whether the VCF contigs carry the 'chr' prefix."""
    if _have_bcftools():
        try:
            out = subprocess.run(["bcftools", "view", "-h", vcf], capture_output=True, text=True, timeout=30).stdout
            return "chr" if "##contig=<ID=chr" in out else ""
        except Exception:
            pass
    if _have_pysam():
        try:
            import pysam
            with pysam.VariantFile(vcf) as vf:
                ctgs = list(vf.header.contigs)
            if ctgs:
                return "chr" if any(str(c).startswith("chr") for c in ctgs) else ""
        except Exception:
            pass
    try:
        from . import tabixlite
        ctgs = tabixlite.contigs(vcf)
        if ctgs:
            return "chr" if any(c.startswith("chr") for c in ctgs) else ""
    except Exception:
        pass
    # The header itself, read straight out of the gzip stream. It needs no index
    # and no library, so it answers where the two above cannot — which is exactly
    # the case that used to fall through to the guess below.
    head = _header_text(vcf) or ""
    if "##contig=" in head:
        return "chr" if "##contig=<ID=chr" in head else ""
    # Last resort. It used to be «chr», unconditionally and silently: on a file
    # whose contigs are `1`, `19`, `X` that turns every query into a lookup of a
    # contig that does not exist, every lookup returns nothing, and nothing is
    # read as «reference». An unprefixed name is what the VCF specification
    # writes by default, so that is the safer of the two guesses — but the real
    # answer is that we could not read the header, and a query that finds no such
    # contig must not come back as a reference call.
    return ""


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
    # pysam before tabixlite: it was already being REPORTED as the reader while
    # never being used to read anything, and it is the only one of the three that
    # can seek a `.csi` without an external binary.
    rows = _query_pysam(vcf, name, int(pos), int(pos))
    if rows is not None:
        return rows
    # without either — our own reader of the tabix index (see tabixlite.py)
    try:
        from . import tabixlite
        return tabixlite.query(vcf, name, int(pos))
    except Exception:
        return []


def _query_pysam(vcf: str, name: str, start: int, end: int) -> Optional[List[List[str]]]:
    """Rows through pysam, or None when pysam is not the one to ask.

    None and [] are different answers and are kept apart on purpose: [] means the
    site is not variant, None means this reader did not run and the next one
    should. Collapsing them is how «no reader» became «reference».
    """
    if not _have_pysam():
        return None
    try:
        import pysam
        with pysam.VariantFile(vcf) as vf:
            return [str(rec).rstrip("\n").split("\t")
                    for rec in vf.fetch(name, max(start - 1, 0), end)]
    except Exception:
        return None


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
        # Each sites file answers in its OWN build, exactly as the main VCF does.
        pos = locus_position(loc, assembly_of(vcf))
        if pos is None:
            continue
        try:
            rows = _query_region(vcf, loc["chrom"], pos)
        except Exception:
            continue
        for f in rows:
            if len(f) < 10 or str(f[1]) != str(pos):
                continue
            col = 9 + (sample_index(vcf) or 0)
            if len(f) <= col:
                continue
            fmt, sample = f[8].split(":"), f[col].split(":")
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
    """The patient's genotype at a resolved locus — from the VCF, or from an array.

    The array branch never reaches the reference assumptions below it, and that
    is deliberate. In a variants-only VCF a position with no row WAS read and
    matched the reference. On a chip a position with no row was never
    interrogated at all, and carrying the assumption across would turn «this
    instrument cannot see that locus» into «you do not have that variant».
    """
    vp = vcf_path()
    if not vp:
        from . import array_genome as _arr
        st = _arr.status(loc.get("rsid") or "")
        if st.get("status") in ("called", "called_strand_ambiguous"):
            # A strand-ambiguous call used to fall through every branch here and
            # return None, so the locus command answered «the genome file is
            # there and cannot be read» over a chip that had called the position
            # perfectly well. Task 1 asked for these six loci to carry a lowered
            # status, not to vanish: among them are two DPYD markers that dose
            # chemotherapy, and silence about them is the worst of the three
            # possible answers. Found by the guard added for task 88.
            return {"genotype": st["genotype"],
                    "confidence": st.get("confidence") or "called_array",
                    "source": "array", "vendor": st.get("vendor"),
                    "strand_ambiguous": st.get("status") == "called_strand_ambiguous",
                    "note": st.get("note")}
        if st.get("status") == "no_array":
            # Nothing on a chip either — but a VCF in a container or a genotype
            # table may still be here, and it is READ rather than named (task 89).
            try:
                from . import tabular_genome as _tab
                ts = _tab.status(loc.get("rsid") or "")
            except Exception:
                ts = {"status": "no_tabular"}
            if ts.get("status") == "called":
                return {"genotype": ts["genotype"],
                        "confidence": ("called" if ts.get("source") == "container_vcf"
                                       else "called_table"),
                        "source": ts.get("source"), "note": ts.get("note")}
            if ts.get("status") in ("no_call", "not_in_file", "assumed_ref_tabular"):
                return {"genotype": None, "confidence": ts["status"],
                        "source": ts.get("source"), "note": ts.get("note")}
        if st.get("status") in ("no_call", "not_on_chip", "array_unreadable"):
            # `array_unreadable` travels with the other two on purpose. It is not
            # «no array» — there IS a file and its vendor was recognised — and it
            # is emphatically not «not on the chip»: our failure to read a file
            # must never be reported as a property of the instrument.
            return {"genotype": None, "confidence": st["status"], "source": "array",
                    "vendor": st.get("vendor"), "note": st.get("note")}
        return None
    if not _index_usable(vp):
        return None
    # A file that cannot be read gives no genotype — not «reference». This is the
    # same guard as in `available()`, placed here too because a caller may reach
    # a locus without asking for the status first.
    if file_unreadable(vp):
        return None
    col = sample_index(str(vp))
    if col is None:
        # Several samples and nobody said which. Reporting column ten would be
        # reporting somebody — possibly a relative — as the person asking.
        return {"genotype": None, "confidence": "sample_not_chosen", "source": "vcf",
                "samples": samples_of(str(vp)),
                "note": _t("genome.sample_not_chosen",
                           names=", ".join(samples_of(str(vp))[:8]))}
    ref = loc.get("ref", "N")
    # The file's own build decides which coordinate is used. A GRCh37 file is
    # read at `pos_grch37`; nothing is converted, because the offset between
    # builds is not constant even within a chromosome and a converted coordinate
    # would point at a real base that is the wrong one.
    asm = assembly_of(str(vp))
    pos = locus_position(loc, asm) if asm else loc.get("pos")
    if pos is None:
        return {"genotype": None, "confidence": "no_coordinates_for_assembly",
                "source": "vcf", "assembly": asm,
                "note": _t("genome.no_coordinates_for_assembly",
                           assembly=asm or "?", rsid=loc.get("rsid") or "")}
    lines = _query_region(str(vp), loc["chrom"], pos)
    if not lines and asm is None:
        # «No row here» and «we are looking in the wrong coordinate system» produce
        # exactly the same silence, and when the build is not established we cannot
        # tell them apart. Calling it «reference» picks one of the two and says
        # nothing about the choice — which is how a GRCh37 file with no contig
        # block reported a heterozygous APOE ε4 carrier as a non-carrier. A row
        # that IS found is different: finding it is itself evidence that the
        # coordinates line up, so that answer still stands.
        return {"genotype": None, "confidence": "no_row_and_build_unknown", "source": "vcf",
                "assembly": None, "note": _t("genome.no_row_and_build_unknown")}
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
        # Task 87. «No row» means «read, and it matched the reference» only in a
        # file that carries variants of that kind at all. A call set split by
        # variant type never read a single substitution, and reporting the
        # reference at one states something about the person from a property of
        # the file.
        from . import callset as _cs
        _m = _cs.measure(str(vp))
        if not _cs.answers_variant(_m, ref, loc.get("alt") or ""):
            return {"genotype": None, "confidence": "not_in_this_callset", "source": "vcf",
                    "assembly": asm, "read_pos": pos, "callset_class": _m.get("class"),
                    "note": _t("genome.not_in_this_callset")}
        return {"genotype": f"{ref}{ref}", "confidence": "assumed_ref", "source": "vcf",
                "assembly": asm, "read_pos": pos,
                "note": _t("genome.assumed_ref_note")}
    # take the first variant row at the position
    for f in lines:
        if len(f) < 10:
            continue
        vref, valt = f[3], f[4].split(",")
        if len(f) <= 9 + col:
            continue
        fmt = f[8].split(":")
        sample = f[9 + col].split(":")
        gt_raw = sample[fmt.index("GT")] if "GT" in fmt else sample[0]
        idx = [i for i in gt_raw.replace("|", "/").split("/") if i.isdigit()]
        # `./.` is NOT a call. An empty genotype string used to travel onward
        # labelled `called`, so the refusal head was assembled from the word
        # «called», no key of that name existed in the message catalogue, and the
        # reader got ⟦genome.refused_head.called⟧ where a sentence belonged.
        if not idx:
            return {"genotype": None, "confidence": "no_call_in_vcf", "source": "vcf",
                    "assembly": asm, "read_pos": pos, "filter": f[6],
                    "note": _t("genome.no_call_in_vcf")}
        alleles = [vref] + valt
        try:
            gt = "".join(alleles[int(i)] for i in idx)
        except (IndexError, ValueError):
            return {"genotype": None, "confidence": "malformed_genotype", "source": "vcf",
                    "assembly": asm, "read_pos": pos, "filter": f[6],
                    "note": _t("genome.malformed_genotype", value=gt_raw[:24])}
        dp = None
        if "DP" in fmt:
            try:
                dp = int(sample[fmt.index("DP")])
            except Exception:
                dp = None
        out = {"genotype": gt, "confidence": "called", "source": "vcf",
               "ref": vref, "alt": f[4], "depth": dp,
               "assembly": asm, "read_pos": pos, "filter": f[6]}
        # Task 87, second half. An imputed genotype is not an observation. The
        # corpus holds a file where 98.8 % of rows carry FILTER=IMP, and the
        # engine read them level with observed ones and signed them «called from
        # the VCF». Every VCF has a FILTER column; not looking at it is how the
        # output of an imputation model is handed over as a measurement.
        _fl = set(f[6].replace(",", ";").split(";"))
        if _fl & {"IMP", "IMPUTED", "IMP_PASS"}:
            out["imputed"] = True
            out["note"] = _t("genome.imputed_call")
        elif f[6] not in ("PASS", ".", ""):
            out["filtered"] = f[6]
            out["note"] = _t("genome.filtered_call", value=f[6])
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
            # Task 64, second item. The locus command used to print one sentence
            # for every refusal — «put genome/*.vcf.gz + .tbi in place» — including
            # to the person whose file IS in place and is simply in another build,
            # or unreadable, or one of three. `genome-status` had been told to
            # distinguish these on 17.08; the locus command was not in that list,
            # and so the two commands contradicted each other in front of the same
            # folder. The reason now travels with the answer.
            base["reason"] = st.get("reason")
            base["ambiguous"] = st.get("ambiguous")
            base["foreign"] = st.get("foreign")
            base["message"] = _t("genome.refused." + (st.get("reason") or "no_file"))
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
# The ClinVar review status in "stars", so a caller can tell a 4-star expert-panel
# assertion from a 0-1-star single-submitter one. The rank above only SORTS; it
# never told the reader that two findings in the same tier carry very different
# weight. For consumer WGS this is the main source of false alarms — a 0-star
# "Pathogenic" is the single most over-called class — so the star count and a
# low-confidence flag now travel with every hit.
_REVIEW_STARS = {
    "practice_guideline": 4, "reviewed_by_expert_panel": 3,
    "criteria_provided,_multiple_submitters,_no_conflicts": 2,
    "criteria_provided,_conflicting_classifications": 1,
    "criteria_provided,_single_submitter": 1,
    "no_assertion_criteria_provided": 0,
    "no_assertion_provided": 0, "": 0,
}


def _review_stars(review: str) -> int:
    return _REVIEW_STARS.get((review or "").strip(), 0)


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


def clinvar_normalisation() -> Dict[str, Any]:
    """Whether the ClinVar match ran against left-aligned variants.

    An indel has many equally valid spellings, and `bcftools annotate` matches on
    the exact REF/ALT text. Without left-alignment the same variant in two files
    can fail to meet, and the miss is silent — a pathogenic indel comes out
    looking like a locus with nothing in it. When the reference FASTA was not
    available the pipeline says so here, and the finding list carries the caveat
    instead of implying a completeness it does not have.
    """
    for base in core.genome_bases():
        p = base / "clinvar_norm.json"
        try:
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {"normalised": False, "left_aligned": False, "unknown": True}


def _review_confidence(review: str) -> Optional[str]:
    """The stated meaning of a ClinVar review status, from `penetrance.json`."""
    mods = ((penetrance_notes().get("confidence_modifiers") or {})
            .get("review_status") or {})
    hit = mods.get((review or "").strip())
    # The map is nested two deep — `confidence_modifiers.review_status.<status>` —
    # and the tree resolver localises one level of a named container, so the
    # innermost per-language map arrives raw. Resolved here rather than by
    # widening the resolver, because widening it would let a two-letter data key
    # anywhere in the base be mistaken for a language.
    from .i18n import lang as _lang
    return core._localized(hit, _lang()) if hit else None


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
        rec["stars"] = _review_stars(rec.get("review", ""))
        # `penetrance.json.confidence_modifiers` says, per ClinVar review status,
        # how much weight the classification carries. It was written, translated
        # into two languages, and read by nothing at all — one of the four rows in
        # the audit's table of computed facts the reasoning layer ignores. The
        # star count is a number; this is the sentence that says what the number
        # means, and it belongs on the finding rather than in a file.
        rec["review_confidence"] = _review_confidence(rec.get("review", ""))
        # A pathogenic/risk call resting on 0-1 stars is a claim the evidence does
        # not yet support at the strength its tier implies — surfaced, not hidden.
        rec["low_confidence"] = rec["stars"] <= 1 and tier in ("pathogenic", "risk", "drug")
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
    low_conf = sum(1 for r in rows if r.get("low_confidence"))
    return {"status": "ok", "count": len(rows), "actionable": actionable,
            "counts": counts, "tiers": tiers, "low_confidence": low_conf,
            "hits": rows[:limit], "source": str(f)}


def acmg_sf_catalog() -> Dict[str, Any]:
    return core._read_knowledge("acmg_sf.json")


def penetrance_notes() -> Dict[str, Any]:
    return core._read_knowledge("penetrance.json")


def _acmg_coverage(cat: Dict[str, Any]) -> Dict[str, Any]:
    """How much of the ACMG SF gene list was actually readable, for THIS answer.

    `limits` has printed this number since the day it was computed, and the ACMG
    report — the flagship claim of the whole layer — did not consult it. So «no
    reportable findings» read identically at 99 % coverage and at 62 %, and a
    BRCA1 covered to 71 % produced the same sentence as a BRCA1 covered whole.
    The number was one command away and in another command's output: the exact
    shape of defect the audit called «a computed fact the reasoning layer
    ignores».

    Two separate deficits are reported, because they need different sentences:
    a gene measured and found WEAK, and a gene not measured at all. Neither is a
    reason to withhold the finding list; both are reasons the word «none» in it
    has to be qualified.
    """
    from . import limits as _limits
    rows = _limits.callability()
    genes = sorted((cat.get("genes") or {}).keys())
    if not genes:
        return {"known": False}
    if not rows:
        return {"known": False, "genes": len(genes),
                "note": _t("acmg.coverage_unknown")}
    weak, unmeasured, measured = [], [], []
    for g in genes:
        row = rows.get(g.upper())
        if not row:
            unmeasured.append(g)
            continue
        measured.append(row["pct_10x"])
        if row["pct_10x"] < _limits.WEAK_10X:
            weak.append({"gene": g, "pct_10x": row["pct_10x"]})
    weak.sort(key=lambda w: w["pct_10x"])
    out = {"known": True, "genes": len(genes), "measured": len(measured),
           "mean_pct_10x": round(sum(measured) / len(measured), 1) if measured else None,
           "weak": weak, "unmeasured": unmeasured,
           "threshold": _limits.WEAK_10X}
    if weak or unmeasured:
        out["qualifies_a_negative"] = True
        out["note"] = _t("acmg.negative_qualified", weak=len(weak),
                         unmeasured=len(unmeasured), genes=len(genes),
                         threshold=f"{_limits.WEAK_10X:g}")
    return out


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
    # THE LAST GATE, applied from the catalogue rather than from the TSV.
    #
    # Three genes are reportable only for a narrow CLASS of variant — TTN for
    # truncating ones, RYR1 and CACNA1S for those established in malignant
    # hyperthermia — and the scan cannot always establish the class. A hit there
    # is not a secondary finding; it is a variant whose class has to be looked at.
    # Re-deciding here, from the catalogue, means a TSV produced before this rule
    # existed cannot walk past it: the file on disk outlives the code that wrote
    # it, and «reportable=yes» in it is only as good as the day it was written.
    narrow = {"truncating_only", "mh_associated_only"}
    needs_class = []
    for r in rows:
        rule = (cat.get("genes", {}).get(r.get("gene")) or {}).get("report_rule")
        if rule in narrow and r.get("reportable") == "yes":
            r["reportable"] = "needs_variant_class"
            r["report_rule"] = rule
            r["report_rule_note"] = (cat.get("genes", {}).get(r.get("gene")) or {}
                                     ).get("report_rule_note")
            needs_class.append(r)
    # Two heterozygous hits in a gene that needs both copies affected: biallelic
    # only if they lie on DIFFERENT chromosomes, and an unphased file cannot say.
    # Re-decided here from the catalogue for the same reason as the narrow rules
    # above — a TSV written before this distinction existed says «yes».
    needs_phase = []
    by_gene = {}
    for r in rows:
        by_gene.setdefault(r.get("gene"), []).append(r)
    for gene, rs in by_gene.items():
        rule = (cat.get("genes", {}).get(gene) or {}).get("report_rule")
        if rule != "biallelic":
            continue
        if any(r.get("zygosity") == "hom" for r in rs):
            continue                      # a homozygote settles it
        if len(rs) >= 2:
            for r in rs:
                if r.get("reportable") == "yes":
                    r["reportable"] = "needs_phase"
                if r not in needs_phase:
                    needs_phase.append(r)
    reportable = [r for r in rows if r.get("reportable") == "yes"]
    carriers = [r for r in rows
                if r.get("reportable") not in ("yes", "needs_variant_class", "needs_phase")]
    return {"status": "ok", "version": meta.get("version"), "published": meta.get("published"),
            # The coverage this answer rests on. «No findings» over a gene read to
            # 71 % is a different sentence from «no findings» over one read whole,
            # and until now they were the same sentence.
            "coverage": _acmg_coverage(cat),
            "gene_count": meta.get("gene_count"), "new_in_version": meta.get("new_in_v33", []),
            "count": len(rows), "reportable": reportable, "carriers": carriers,
            "needs_variant_class": needs_class,
            "needs_phase": needs_phase,
            "hits": rows, "source": str(f), "scanned": core.file_date(f),
            "caveats": meta.get("caveats"), "provenance": meta.get("provenance")}


#: APOE epsilon alleles are HAPLOTYPES of two SNPs. Only these four definitions
#: are written down; the genotype table below is DERIVED from them by enumerating
#: every pair of haplotypes. Typing the table out by hand was tried first and
#: produced two errors in nine rows — a missing common genotype and a swapped
#: pair — which is the argument for deriving it: the biology is four lines and
#: the combinatorics is the computer's job.
_APOE_HAPLOTYPES = {
    "\u03b52": ("T", "T"),   # rs429358 T, rs7412 T
    "\u03b53": ("T", "C"),
    "\u03b54": ("C", "C"),
    "\u03b51": ("C", "T"),   # very rare
}


def _apoe_table():
    """{(rs429358 genotype, rs7412 genotype): [diplotypes]} — every reading.

    A genotype pair with more than one diplotype is genuinely ambiguous without
    phase, and the caller must not choose for the reader.
    """
    out = {}
    names = list(_APOE_HAPLOTYPES)
    for i, a in enumerate(names):
        for b in names[i:]:
            h1, h2 = _APOE_HAPLOTYPES[a], _APOE_HAPLOTYPES[b]
            key = ("".join(sorted(h1[0] + h2[0])), "".join(sorted(h1[1] + h2[1])))
            dip = "/".join(sorted([a, b]))
            out.setdefault(key, [])
            if dip not in out[key]:
                out[key].append(dip)
    return out


_APOE_TABLE = _apoe_table()


def _unordered(gt):
    """«TC» and «CT» are the same genotype; sorting says so."""
    return "".join(sorted((gt or "").upper()))


def apoe_status():
    """The APOE epsilon status from rs429358 + rs7412.

    Derived from the pair of UNORDERED genotypes, never from the order the
    alleles happen to appear in. The previous version paired the first allele of
    one SNP with the first of the other, as though a VCF's allele order encoded
    phase. It does not — an unphased genotype is a multiset — so the same person
    came out \u03b52/\u03b54 or \u03b53/\u03b54 depending on whether their file wrote «CT» or
    «TC». Reproduced before this was rewritten, and the difference is not
    cosmetic: \u03b52 is protective for Alzheimer's disease where \u03b53 is neutral.

    The one common genotype that genuinely needs phase — both SNPs heterozygous —
    is returned as AMBIGUOUS with both readings named. \u03b52/\u03b54 is far more common
    than \u03b51/\u03b53 in every studied population, and that is a reason to say which is
    likely, not a reason to print one of them as the answer.
    """
    st = available()
    if not st["ready"]:
        return {"status": "no_genome"}
    g1 = genotype_from_vcf("rs429358")
    g2 = genotype_from_vcf("rs7412")
    if not g1 or not g2 or not g1.get("genotype") or not g2.get("genotype"):
        # On an array either SNP may be absent or uncalled, and «one of the two
        # is missing» is a different answer from «no genome».
        return {"status": "no_data",
                "rs429358": (g1 or {}).get("genotype"),
                "rs7412": (g2 or {}).get("genotype")}
    k = (_unordered(g1["genotype"]), _unordered(g2["genotype"]))
    readings = _APOE_TABLE.get(k)
    base = {"rs429358": g1["genotype"], "rs7412": g2["genotype"],
            "source": g1.get("source"), "note": _t("genome.apoe_note")}
    if not readings:
        return dict(base, status="unexpected_genotypes",
                    message=_t("genome.apoe_unexpected", a=k[0], b=k[1]))
    if len(readings) == 1:
        return dict(base, status="ok", genotype=readings[0])
    # More than one reading: phase decides and this file does not carry it.
    # \u03b52/\u03b54 outranks \u03b51/\u03b53 by orders of magnitude in every studied population,
    # which is a reason to say which is likely — not a reason to print it as the
    # answer.
    likely = "\u03b52/\u03b54" if "\u03b52/\u03b54" in readings else readings[0]
    others = [x for x in readings if x != likely]
    return dict(base, status="ambiguous_without_phase",
                candidates=readings, likely=likely,
                message=_t("genome.apoe_ambiguous", a=likely, b=", ".join(others)))