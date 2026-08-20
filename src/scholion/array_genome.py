"""Consumer genotyping arrays, with a three-valued answer per locus.

A chip and a sequenced genome fail in opposite directions, and the difference is
the whole reason this module exists rather than a branch inside `genome.py`.

In a variants-only VCF, a position with no row was READ and found to match the
reference. Assuming reference there is a defensible reading (the project marks it
`assumed_ref` and says so). On an array, a position with no row was NEVER
INTERROGATED — the chip carries a few hundred thousand of the three billion
positions, and the ones it does not carry are simply absent. Carrying the VCF
assumption across would turn «this chip cannot see that locus» into «you do not
have that variant», which is the single most dangerous sentence a tool like this
can produce.

So every lookup answers one of three ways, and the three are never collapsed:

  called       — the chip interrogated the position and returned a genotype
  no_call      — the chip carries the position and the call failed («--», «00»)
  not_on_chip  — the position is not on this array at all

The third is not an error and not an absence of variants: it is a statement about
the instrument, and it is what `limits` needs in order to say what this input can
and cannot support.

Formats read, all plain text exports the person downloads themselves:
23andMe (TSV, `rsid chromosome position genotype`), AncestryDNA (TSV with
`allele1`/`allele2` in separate columns), MyHeritage and FamilyTreeDNA (quoted
CSV), Living DNA (TSV). Detection is by the header, not by the file name — the
name is whatever the person saved it as.
"""
from __future__ import annotations

import csv
import glob
import re
import io
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from . import core
from .i18n import t as _t

#: What a chip prints when it interrogated the position and got nothing.
_NO_CALL = {"--", "-", "00", "0", "", "NN", "??"}

#: Vendors, in the order their header is tried. The tuple is
#: (name, the header substring that identifies it, the reader).
VENDORS = ("23andMe", "AncestryDNA", "MyHeritage", "FamilyTreeDNA", "LivingDNA")

_CACHE: Dict[str, Tuple[float, Dict[str, str], str]] = {}


#: What the search looks at. It used to be the three bare text extensions, and
#: that is how four arrays out of seven in the PGP corpus became «no genome
#: found»: a provider hands people a `.zip`, AncestryDNA a `.txt.bz2`, and the
#: vendored `text_io` peels every one of those by magic bytes — the search simply
#: never offered them to it. Extensions still decide only what is LOOKED AT;
#: what a file IS remains decided by content, in `_sniff_vendor`. A `.vcf.gz`
#: caught by `*.gz` here is turned down there, by the detector, as a genome.
_SEARCH_PATTERNS = ("*.txt", "*.csv", "*.tsv",
                    "*.txt.gz", "*.csv.gz", "*.tsv.gz", "*.gz",
                    "*.txt.bz2", "*.csv.bz2", "*.tsv.bz2", "*.bz2",
                    "*.xz", "*.zip", "*.tar", "*.tar.gz", "*.tgz")


def array_path() -> Optional[Path]:
    """The person's array export: env SCHOLION_ARRAY_FILE, or a search in genome/.

    Deliberately separate from `SCHOLION_GENOME_VCF`. A machine may hold both — a
    chip from years ago and a sequenced genome since — and which one answered a
    question has to stay visible rather than being decided by whichever search
    ran first.
    """
    env = os.environ.get("SCHOLION_ARRAY_FILE")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    bases = list(core.genome_bases())
    cfg = core.source_config().get("genome")
    if cfg:
        bases.insert(0, Path(cfg).expanduser())
    for base in bases:
        for pattern in _SEARCH_PATTERNS:
            for hit in sorted(glob.glob(str(base / pattern))):
                if _sniff_vendor(Path(hit)):
                    return Path(hit)
    return None


def _open_text(path: Path):
    """A decoded text stream over the payload, however the file is wrapped.

    Routed through the vendored `text_io` (task 74), which peels zip / tar /
    gzip / bzip2 / xz by magic bytes and picks the genomic member out of a
    provider archive, discarding its README. Falls back to a plain open when the
    vendored module is unavailable, so a source tree without it still reads bare
    exports rather than failing.
    """
    try:
        from .vendor.genomi.text_io import open_genomic_binary
    except Exception:
        return io.open(path, encoding="utf-8", errors="ignore", newline="")
    import contextlib

    @contextlib.contextmanager
    def _stream():
        with open_genomic_binary(path) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8", errors="replace", newline="")
            try:
                yield text
            finally:
                text.detach()
    return _stream()


def _head(path: Path, lines: int = 40) -> str:
    try:
        with _open_text(path) as fh:
            return "".join(next(fh, "") for _ in range(lines))
    except Exception:
        return ""


#: Their format name → ours. The vendored detector answers with its own
#: vocabulary; one map, here, keeps that vocabulary from spreading through this
#: module.
_VENDOR_OF_FORMAT = {"23andme": "23andMe", "ancestrydna": "AncestryDNA",
                     "myheritage": "MyHeritage", "ftdna": "FamilyTreeDNA",
                     "livingdna": "LivingDNA", "genome": "23andMe"}


def _sniff_vendor(path: Path) -> Optional[str]:
    """Which vendor wrote this file — decided by CONTENT, never by its name.

    The decision is delegated to the vendored Genomi detector (task 74). Its
    signatures are stricter than a header scan: FamilyTreeDNA and MyHeritage
    share a CSV header and are told apart by the ABSENCE of a comment block,
    which a keyword search cannot see. It also unwraps the .zip a provider
    actually hands people and throws away the README inside it.

    The local fallback below stays for one case the detector does not cover: a
    file whose vendor banner was stripped by a spreadsheet round-trip but whose
    column row is still unmistakable. It runs only when the detector declines.
    """
    try:
        from .vendor.genomi.detection import detect_source
        det = detect_source(path)
        if det.source_kind == "consumer_genotype_array":
            return _VENDOR_OF_FORMAT.get(det.source_format, det.source_format)
        if det.source_kind:
            return None          # a real genome file, not an array — not ours to read
    except Exception:
        pass                     # fall through to the header scan
    head = _head(path)
    if not head:
        return None
    low = head.lower()
    if "23andme" in low:
        return "23andMe"
    if "ancestrydna" in low or "\tallele1\tallele2" in low:
        return "AncestryDNA"
    if "myheritage" in low:
        return "MyHeritage"
    if "family tree dna" in low or "ftdna" in low:
        return "FamilyTreeDNA"
    if "living dna" in low or "livingdna" in low:
        return "LivingDNA"
    for ln in head.splitlines():
        t = ln.strip().lower().lstrip("#").strip()
        if t.startswith("rsid") and "chromosome" in t and "position" in t:
            return "AncestryDNA" if "allele1" in t else (
                "MyHeritage" if "," in t else "23andMe")
    return None


_ASSEMBLY_IN_PROSE = re.compile(r"assembly\s+build\s+(\d+)", re.IGNORECASE)


def declared_assembly(path: Optional[Path] = None) -> Optional[str]:
    """The build the export states in its own header, in prose.

    23andMe writes «# We are using reference human assembly build 37». Reading
    that beats the folklore that arrays are always GRCh37: the file says, and a
    file that says something is a better source than a default that assumes it.
    Returns None when the header states nothing — which is itself worth knowing,
    and is the one change made to the vendored detector for the same reason.
    """
    p = path or array_path()
    if not p:
        return None
    m = _ASSEMBLY_IN_PROSE.search(_head(p, 60))
    if not m:
        return None
    return {"37": "GRCh37", "36": "NCBI36", "38": "GRCh38"}.get(m.group(1))


def strand_ambiguous_loci() -> Dict[str, Any]:
    """Catalogue loci whose two alleles are their own complement (A/T, C/G).

    Computed, not listed. If a provider reports the minus strand, the observed
    alleles for such a locus still land inside {ref, alt} — the error is
    indistinguishable from a correct call, and among these six sit the
    chemotherapy dosing genes DPYD and TPMT. So they are marked with a lowered
    status on array input rather than handed over beside the rest.
    """
    from . import genome
    out = {}
    for rs, loc in (genome.loci().get("loci") or {}).items():
        pair = {str(loc.get("ref")), str(loc.get("alt"))}
        if pair in ({"A", "T"}, {"C", "G"}):
            out[rs.lower()] = {"gene": loc.get("gene"), "ref": loc.get("ref"),
                               "alt": loc.get("alt")}
    return out


def _delimiter(path: Path) -> str:
    """Tab or comma — decided by counting them in the first data-looking line.

    It used to be `vendor in ("MyHeritage", "FamilyTreeDNA")`, that is, decided
    by the LABEL rather than by the bytes. A real 23andMe export re-saved through
    a spreadsheet arrives comma-separated, was read with a tab delimiter, and
    yielded zero rows — and the product then answered locus queries with «this
    position is not on the 23andMe array at all». That was the single confident
    wrong answer in the whole PGP corpus run: a parse failure served as a fact
    about the chip. The vendor label describes who wrote the file, not how the
    file is punctuated, and a person who opens their export in Excel changes the
    second without touching the first.
    """
    try:
        with _open_text(path) as fh:
            for _ in range(200):
                line = next(fh, None)
                if line is None:
                    break
                t = line.strip().lstrip('"').strip()
                if not t or t.startswith("#"):
                    continue
                return "," if t.count(",") > t.count("\t") else "\t"
    except Exception:
        pass
    return "\t"


def _rows(path: Path, vendor: str) -> Iterable[Tuple[str, str]]:
    """(rsid, genotype) for every row, in the file's own spelling."""
    with _open_text(path) as fh:
        reader = csv.reader(fh, delimiter=_delimiter(path))
        header_seen = False
        for row in reader:
            if not row:
                continue
            first = row[0].strip().strip('"')
            if first.startswith("#"):
                continue
            if not header_seen and first.lower() == "rsid":
                header_seen = True
                continue
            # Internal vendor identifiers (`i3002401`) are the vendor's own probes,
            # not dbSNP records. They cannot be matched to the catalogue by rsID
            # and are skipped rather than half-matched.
            if not first.lower().startswith("rs"):
                continue
            # CRLF: the real exports end their lines with \r\n, and a naive split
            # leaves the carriage return glued to the genotype — «AA\r» matches
            # nothing and looks like a no-call.
            cells = [c.strip().strip('"').strip("\r") for c in row]
            if vendor == "AncestryDNA" and len(cells) >= 5:
                gt = f"{cells[3]}{cells[4]}"
            elif len(cells) >= 4:
                gt = cells[3]
            else:
                continue
            yield first, gt.upper()


def index() -> Dict[str, Any]:
    """rsid → genotype for the whole array, plus what produced it.

    The index is the ONLY thing that can answer «is this locus on the chip at
    all», which is why the whole file is read rather than scanned per query: the
    absence of an rsid is an answer here, and an answer cannot be given by a
    search that stopped early.
    """
    p = array_path()
    if not p:
        return {"ok": False, "reason": "no_array"}
    try:
        mt = p.stat().st_mtime
    except OSError:
        return {"ok": False, "reason": "no_array"}
    hit = _CACHE.get(str(p))
    if hit and hit[0] == mt:
        return {"ok": True, "path": str(p), "vendor": hit[2], "genotypes": hit[1],
                "markers": len(hit[1])}
    vendor = _sniff_vendor(p)
    if not vendor:
        return {"ok": False, "reason": "unrecognised_format", "path": str(p)}
    genotypes: Dict[str, str] = {}
    for rsid, gt in _rows(p, vendor):
        genotypes.setdefault(rsid.lower(), gt)
    if not genotypes:
        # Vendor recognised, not one row read. Whatever the cause — a punctuation
        # this reader does not know, a truncated download, an archive holding
        # something else — the one thing it is NOT is a fact about the chip. An
        # empty index would make every locus answer «not on this array», which is
        # a confident statement about the instrument derived from our own
        # failure to read the file. So the index refuses instead.
        return {"ok": False, "reason": "array_unreadable", "path": str(p),
                "vendor": vendor}
    _CACHE[str(p)] = (mt, genotypes, vendor)
    return {"ok": True, "path": str(p), "vendor": vendor, "genotypes": genotypes,
            "markers": len(genotypes)}


def status(rsid: str) -> Dict[str, Any]:
    """The three-valued answer for one locus.

    `not_on_chip` is returned as a positive statement rather than as None,
    because every caller has to be able to tell it apart from «no array loaded»
    — and because it is the answer a person most needs: the chip cannot see this,
    so nothing about it has been ruled in or out.
    """
    idx = index()
    if not idx.get("ok"):
        if idx.get("reason") == "array_unreadable":
            return {"status": "array_unreadable", "reason": "array_unreadable",
                    "vendor": idx.get("vendor"), "path": idx.get("path"),
                    "note": _t("array.unreadable", vendor=idx.get("vendor") or "")}
        return {"status": "no_array", "reason": idx.get("reason")}
    gt = (idx["genotypes"] or {}).get((rsid or "").lower())
    if gt is None:
        return {"status": "not_on_chip", "source": "array", "vendor": idx["vendor"],
                "note": _t("array.not_on_chip", vendor=idx["vendor"])}
    if gt in _NO_CALL or set(gt) <= {"-", "0", "?"}:
        return {"status": "no_call", "source": "array", "vendor": idx["vendor"],
                "note": _t("array.no_call")}
    amb = strand_ambiguous_loci().get((rsid or "").lower())
    if amb:
        return {"status": "called_strand_ambiguous", "genotype": gt, "source": "array",
                "vendor": idx["vendor"], "confidence": "called_array_ambiguous",
                "gene": amb.get("gene"),
                "note": _t("array.strand_ambiguous", gene=amb.get("gene") or "",
                           ref=amb.get("ref"), alt=amb.get("alt"))}
    return {"status": "called", "genotype": gt, "source": "array",
            "vendor": idx["vendor"], "confidence": "called_array",
            "note": _t("array.called", vendor=idx["vendor"])}


def catalogue_coverage() -> Dict[str, Any]:
    """The three numbers, per the task's own acceptance: called / no-call / absent.

    Measured against THIS catalogue, and the distinction matters: 85 % is an
    honest number for a catalogue of common pharmacogenetic and trait variants
    and would be a dishonest one for a catalogue of rare pathogenic variants,
    where the chip's predictive value collapses.
    """
    from . import genome
    idx = index()
    if not idx.get("ok"):
        out = {"available": False, "reason": idx.get("reason", "no_array")}
        if idx.get("reason") == "array_unreadable":
            out.update({"vendor": idx.get("vendor"), "path": idx.get("path"),
                        "note": _t("array.unreadable", vendor=idx.get("vendor") or "")})
        return out
    called, no_call, absent, ambiguous = [], [], [], []
    amb = strand_ambiguous_loci()
    for rs in (genome.loci().get("loci") or {}):
        st = status(rs)
        if st["status"] == "called":
            called.append(rs)
        elif st["status"] == "called_strand_ambiguous":
            called.append(rs)
            ambiguous.append({"rsid": rs, "gene": amb.get(rs.lower(), {}).get("gene")})
        elif st["status"] == "no_call":
            no_call.append(rs)
        else:
            absent.append(rs)
    total = len(called) + len(no_call) + len(absent)
    return {"available": True, "vendor": idx["vendor"], "markers": idx["markers"],
            "assembly_declared": declared_assembly(),
            "catalogue_total": total, "called": len(called), "no_call": len(no_call),
            "absent": len(absent), "absent_rsids": sorted(absent),
            "strand_ambiguous": ambiguous,
            "pct": round(100.0 * len(called) / total, 1) if total else 0.0}


def summary() -> Dict[str, Any]:
    """What kind of input this is, for `limits` and for the genome report."""
    idx = index()
    if not idx.get("ok"):
        return {"available": False, "reason": idx.get("reason", "no_array")}
    return {"available": True, "vendor": idx["vendor"], "markers": idx["markers"],
            "path": idx["path"],
            # Said once, here, so no caller has to remember it: an array is not a
            # sequenced genome and the difference is not a matter of degree.
            "caveat": _t("array.what_it_cannot_do")}
