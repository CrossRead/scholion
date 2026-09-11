"""Reading a VCF that has no index — one pass over the file, and only once.

Every reader in this project seeks by position, and seeking needs an index. That
was defensible while the index was somebody else's problem; it stopped being so
the first time an outside reviewer ran the package over three clinical files.
The files were valid, bgzip-compressed, single-sample VCFs. They arrived without
`.tbi`, and the machine had no bcftools, no tabix and no pysam — which is the
ordinary state of an ordinary machine. The genomic layer reported that it could
not read them, and the reviewer installed pysam into a temporary directory and
built the indexes himself. A physician will not do that.

So: when there is no index, the file is read the only way a file can be read
without one — from the beginning to the end, once. What is collected in that one
pass is fixed and small:

* the rows standing on the catalogue's positions, in BOTH builds, because which
  build the file is in is decided elsewhere and this pass must not care;
* the counts inside the probe windows the call-set measurement needs, so that a
  file with no index still gets a measured class instead of `unmeasured`, which
  closes paths;
* the header line, so the sample columns are known.

The result is cached under the file's identity — path, size, modification time
— so the pass happens once per file rather than once per question. It is kept
BESIDE THE GENOME, not in the application cache: the rows it holds are somebody's
genotypes at APOE, F5 and DPYD, and the application cache is a folder that
`SCHOLION_CACHE_DIR` may point anywhere. The genome folder is already the place
that holds this person's data and is already closed to git by three independent
guards; a copy of fifty-four of its rows belongs nowhere else.

A pass that does not reach the end of the file is not a pass. It used to return
an empty result, and an empty result at a position reads as «no row here — the
reference»: a file cut in half by an interrupted copy answered `assumed_ref` at
every locus past the cut, including a heterozygous APOE ε4 carrier reported as a
non-carrier. So the end of the file is proven before the pass starts — bgzip
writes an empty block as its last 28 bytes, and a file without it ended somewhere
other than where its writer stopped — and a pass that fails half-way is
remembered as a failure and answered as one.

This is deliberately not an index builder. Writing a `.tbi` means writing bins
and virtual offsets that bcftools and pysam will also trust, and an index that is
subtly wrong is worse than no index at all: it answers, and it answers from the
wrong place. A private snapshot cannot be mistaken for one.

Standard library only.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Above this, reading the whole file once stops being a wait and becomes a hang,
#: and the honest answer is the one this package gave before the pass existed:
#: the file needs an index.
#:
#: The cap is on the COMPRESSED size, because that is the only number known
#: before the pass starts, so it has to stand in for the uncompressed one. A VCF
#: compresses roughly seven to ten times; the standard-library gzip reader,
#: followed by a split per line and a lookup per row, gets through text at some
#: tens of megabytes per second on an ordinary machine — arithmetic, not a
#: measurement, and the reason the number is generous in neither direction.
#: At 2 GB compressed that is on the order of 15–20 GB of text and a wait of
#: minutes; the earlier cap of 8 GB was 60–80 GB of text, which is hours with
#: no progress shown, and a status command that takes hours is a hang under
#: another name. A provider's whole-genome VCF is a few hundred megabytes to
#: about a gigabyte and a half and stays inside; a gVCF of the same sample is
#: several times that and is the one input that should go through an index
#: anyway. Raisable by anybody who would rather wait than install htslib.
MAX_MB = int(os.environ.get("SCHOLION_LINEAR_MAX_MB") or 2048)

#: The rows of a single pass are worth keeping only while the file is the same
#: file. Anything about the person stays out of the key. Bumped when the key or
#: the shape changed: 2 — the identity moved to nanosecond mtime, and the file
#: moved beside the genome.
_CACHE_VERSION = 2

#: The 28 bytes bgzip writes last: an empty BGZF block. htslib compares the tail
#: of a file against exactly these bytes to decide whether it was truncated, and
#: so does this module — a file that ends anywhere else ended where a copy or a
#: download stopped, not where its writer did.
BGZF_EOF = (b"\x1f\x8b\x08\x04\x00\x00\x00\x00\x00\xff\x06\x00\x42\x43\x02\x00"
            b"\x1b\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00")

_IMPUTED_TOKENS = {"IMP", "IMPUTED", "IMP_PASS"}
_OPEN_FILTERS = {"PASS", ".", ""}


class Unreadable(Exception):
    """This file cannot be read by the single pass, and here is why.

    Raised, never returned as `[]`: an empty list at a position is read as «no
    row here — the reference», which is a sentence about the person, and a file
    that could not be read has said nothing about the person at all.
    `why` is one of the words `why_not` answers with; `detail` is what the
    reader saw, for the person who has to fix the file.
    """

    def __init__(self, why: str, detail: str = ""):
        super().__init__(why)
        self.why = why
        self.detail = detail


def norm_chrom(name: Any) -> str:
    """`chr19`, `19` and `Chr19` are one contig written three ways."""
    s = str(name).strip().lower()
    return s[3:] if s.startswith("chr") else s


def bgzf_eof_missing(vcf: str) -> bool:
    """A BGZF file that does not end in the empty block bgzip always writes.

    Only a BGZF file is asked — the gzip magic with the FEXTRA flag — because
    ordinary gzip has no such marker, and a file of that shape is already turned
    away one level up for the reason that no index can seek into it. For a file
    that IS block-compressed this is the one cheap fact about its end: every
    block carries its own checksum, so a cut inside a block is caught while
    reading, but a cut exactly between two blocks is a valid gzip stream that
    simply stops early. The reviewer's file, cut in half, was that.
    """
    try:
        with open(vcf, "rb") as fh:
            head = fh.read(4)
            if len(head) < 4 or head[:2] != b"\x1f\x8b" or not (head[3] & 0x04):
                return False
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            if size < len(BGZF_EOF):
                return True
            fh.seek(size - len(BGZF_EOF))
            return fh.read(len(BGZF_EOF)) != BGZF_EOF
    except OSError:
        return False


def pass_failure(vcf: str) -> Optional[str]:
    """What the last pass over this file died of, if it did — else None."""
    snap = _MEMO.get(_stamp(vcf)) or {}
    return snap.get("failed") or None


def why_not(vcf: Optional[str]) -> Optional[str]:
    """Why this file cannot be read without an index — or None when it can.

    Each answer is a word rather than a False, because every one of them is a
    different sentence to the person: `truncated` (the file ended early),
    `pass_failed` (the pass over it died, and the detail says where),
    `too_large` (past `MAX_MB`; the honest answer is the old one — this file
    needs an index), `not_a_vcf`, `missing`.
    """
    if not vcf or not os.path.exists(vcf):
        return "missing"
    vcf = str(vcf)
    # A pass that failed is remembered for as long as the process lives, and it
    # is asked FIRST: a file whose pass died is not made readable by a snapshot
    # from before it was damaged, nor by being small.
    if pass_failure(vcf):
        return "pass_failed"
    # A pass already made settles the rest at once, and settles it without
    # touching the file: asked once per locus, the sniff below would otherwise
    # re-open the same file fifty-four times a command.
    if _cached_only(vcf):
        return None
    if bgzf_eof_missing(vcf):
        return "truncated"
    try:
        if os.path.getsize(vcf) > MAX_MB * 1024 * 1024:
            return "too_large"
    except OSError:
        return "missing"
    try:
        with _open(vcf) as fh:
            head = fh.readline()
    except Exception:
        return "not_a_vcf"
    if head.startswith("##fileformat=VCF") or head.startswith("#CHROM"):
        return None
    return "not_a_vcf"


def usable(vcf: Optional[str]) -> bool:
    """Can this file be read at all without an index, and within reason?

    The shape — a file that exists, opens as a VCF and ends where bgzip ended
    it. And the size: past `MAX_MB` a single pass is no longer a wait but a
    hang, and a reader that claims a file and then answers nothing is the defect
    this project has fixed twice already. `why_not` says which of these it was;
    this is the yes-or-no of the same question.
    """
    return why_not(vcf) is None


def _cached_only(vcf: str) -> bool:
    """Has the pass over this file already been paid for once?

    Asked before the size cap, because a snapshot that exists costs nothing to
    read and refusing it would be a refusal aimed at work already done.
    """
    snap = _lookup_cache(vcf)
    return bool(snap) and not snap.get("failed")


def _open(vcf: str):
    if vcf.endswith(".gz") or vcf.endswith(".bgz"):
        return gzip.open(vcf, "rt", encoding="utf-8", errors="replace")
    return open(vcf, "rt", encoding="utf-8", errors="replace")


def _cache_path(vcf: str, signature: str) -> Optional[Path]:
    """Where the snapshot of this file lives: beside the genome, never in the
    application cache.

    The snapshot holds the sample columns of the rows it kept — genotypes at
    fifty-four clinical loci, in clear text. `core.cache_dir()` is the folder for
    reference databases fetched from the network, and `SCHOLION_CACHE_DIR` may
    point it at any disk; the first genome folder is the one place already
    understood to hold this person's data, and the one place the `.gitignore`,
    the pre-commit hook and the sanitizer all already refuse to let out. A
    sub-folder, so that nothing that lists the genome folder for inputs — the
    foreign-input sweep, the VCF search — has to know the file is there.

    Only into a genome folder that EXISTS. An absent one means «no genome
    connected», and the cache creating it would make the product believe one
    is — a status that says «connected» over a folder holding nothing but our
    own notes. Where there is no folder, there is no disk cache; the memo above
    still carries the pass for the life of the process.
    """
    try:
        from . import core
        bases = core.genome_bases()
        if not bases or not Path(bases[0]).is_dir():
            return None
        base = Path(bases[0]) / "cache"
    except Exception:
        return None
    try:
        st = os.stat(vcf)
    except OSError:
        return None
    key = hashlib.sha1(
        f"{_CACHE_VERSION}|{os.path.abspath(vcf)}|{st.st_size}|{st.st_mtime_ns}|{signature}"
        .encode()).hexdigest()[:16]
    return base / f"linear-{key}.json"


def _wanted_positions() -> Dict[str, List[str]]:
    """Every catalogue position, in both builds — the only rows this pass keeps.

    Both builds on purpose: the file's own build is established from its contig
    lengths, and that happens after this pass. Collecting one build here would
    make the pass depend on an answer it is supposed to help produce.
    """
    from . import genome
    out: Dict[str, List[str]] = {}
    for rsid, loc in (genome.loci().get("loci") or {}).items():
        chrom = norm_chrom(loc.get("chrom"))
        for field in ("pos", "pos_grch37"):
            pos = loc.get(field)
            if pos:
                out.setdefault(f"{chrom}:{int(pos)}", []).append(rsid)
    return out


def _probe_windows():
    from . import callset
    return list(callset.PROBES), list(callset.CODING_PROBES)


#: One process, one read of the snapshot. Without this every locus of the 54
#: re-opened and re-parsed the cache file — 54 times the same JSON, per command.
#: A failed pass is memoised here too, as `{"failed": detail}`, so that the next
#: question about the same file is refused rather than paid for again — and never
#: written to disk, because a failure is not a fact about the file that outlives
#: the process: the person may replace the file in the meantime.
_MEMO: Dict[str, Any] = {}

#: The pass is minutes long and the web server answers each request on its own
#: thread. Two status requests arriving together used to start two passes over
#: the same file and write the same snapshot twice, half-overlapping. One pass at
#: a time; the second request finds the memo the first one left.
_PASS_LOCK = threading.Lock()


def _stamp(vcf: str) -> str:
    """The file's identity for this process — nanosecond mtime, because a file
    rewritten within the same second at the same size is a different file, and
    a whole-second stamp handed the old genotypes back for the new file."""
    try:
        st = os.stat(vcf)
    except OSError:
        return ""
    return f"{os.path.abspath(vcf)}|{st.st_size}|{st.st_mtime_ns}"


def _lookup_cache(vcf: str) -> Dict[str, Any]:
    """The snapshot for this file if one has already been made, else {}."""
    stamp = _stamp(vcf)
    if not stamp:
        return {}
    if stamp in _MEMO:
        return _MEMO[stamp]
    try:
        wanted = _wanted_positions()
        poor, rich = _probe_windows()
    except Exception:
        return {}
    signature = hashlib.sha1(
        ("|".join(sorted(wanted)) + "||" + repr(poor) + repr(rich)).encode()).hexdigest()[:12]
    cp = _cache_path(vcf, signature)
    if cp is not None and cp.exists():
        try:
            out = json.loads(cp.read_text(encoding="utf-8"))
            _MEMO[stamp] = out
            return out
        except Exception:
            return {}
    return {}


def snapshot(vcf: Optional[str]) -> Dict[str, Any]:
    """One pass over the file, or the cached result of the last one.

    Returns {'rows': {'19:44908684': [row, …]}, 'probes': [...], 'coding': [...],
    'samples': [...], 'variants': int}. An empty dict when the file cannot be
    read at all; `{'failed': detail}` when the pass started and did not reach the
    end — the difference between the two is the difference between «nothing was
    asked» and «the question was asked and the file could not answer».
    """
    if not vcf or not os.path.exists(vcf):
        return {}
    vcf = str(vcf)
    cached = _lookup_cache(vcf)
    if cached:
        return cached
    if not usable(vcf):
        return {}
    with _PASS_LOCK:
        # Whoever held the lock before us may have made the pass we were about
        # to make; the memo is checked again on the inside for that reason.
        cached = _lookup_cache(vcf)
        if cached:
            return cached
        return _pass(vcf)


def _pass(vcf: str) -> Dict[str, Any]:
    wanted = _wanted_positions()
    poor, rich = _probe_windows()
    signature = hashlib.sha1(
        ("|".join(sorted(wanted)) + "||" + repr(poor) + repr(rich)).encode()).hexdigest()[:12]
    cp = _cache_path(vcf, signature)

    windows = [(norm_chrom(c), int(s), int(s) + int(w), i, "poor")
               for i, (c, s, w) in enumerate(poor)]
    windows += [(norm_chrom(c), int(s), int(s) + int(w), i, "rich")
                for i, (c, s, w) in enumerate(rich)]
    counts = {("poor", i): {"observed": 0, "imputed": 0, "blocks": 0} for i in range(len(poor))}
    counts.update({("rich", i): {"observed": 0, "imputed": 0, "blocks": 0} for i in range(len(rich))})

    rows: Dict[str, List[List[str]]] = {}
    samples: List[str] = []
    variants = 0
    stamp = _stamp(vcf)
    try:
        with _open(vcf) as fh:
            for line in fh:
                if line[:1] == "#":
                    if line.startswith("#CHROM"):
                        samples = line.rstrip("\r\n").split("\t")[9:]
                    continue
                f = line.rstrip("\r\n").split("\t")
                if len(f) < 8:
                    continue
                variants += 1
                chrom = norm_chrom(f[0])
                try:
                    pos = int(f[1])
                except ValueError:
                    continue
                key = f"{chrom}:{pos}"
                if key in wanted:
                    rows.setdefault(key, []).append(f)
                for wc, start, end, i, kind in windows:
                    if chrom == wc and start <= pos < end:
                        alts = [a for a in f[4].split(",") if a not in ("<NON_REF>", ".", "")]
                        cell = counts[(kind, i)]
                        if not alts:
                            cell["blocks"] += 1
                        elif set(f[6].replace(",", ";").split(";")) & _IMPUTED_TOKENS:
                            cell["imputed"] += 1
                        elif f[6] in _OPEN_FILTERS:
                            cell["observed"] += 1
                        break
    except Exception as exc:                                       # noqa: BLE001
        # Half a pass is not a pass. What was collected before the failure is
        # thrown away — rows past the point of failure would otherwise answer
        # «reference» — and the failure itself is what the next question meets.
        failed = {"failed": f"{type(exc).__name__}: {exc}"[:200],
                  "variants_before_failure": variants}
        if stamp:
            _MEMO[stamp] = failed
        return failed

    out = {"rows": rows, "samples": samples, "variants": variants,
           "probes": [counts[("poor", i)] for i in range(len(poor))],
           "coding": [counts[("rich", i)] for i in range(len(rich))]}
    if cp is not None:
        try:
            # `parents=False`: `_cache_path` has already refused a genome folder
            # that does not exist, and this must never be the call that makes one.
            cp.parent.mkdir(exist_ok=True)
            # Written whole or not at all: a reader that opens the file while it
            # is being written would otherwise parse half a snapshot — and the
            # half it parses answers for the positions it does not hold.
            tmp = cp.with_name(f"{cp.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            os.replace(tmp, cp)
        except Exception:
            pass
    if stamp:
        _MEMO[stamp] = out
    return out


def rows_at(vcf: Optional[str], chrom: Any, pos: int) -> List[List[str]]:
    """The rows on one position, out of the single pass. `[]` — none there.

    Raises `Unreadable` when there was no pass to read from: the empty list is
    reserved for a file that WAS read to its end and holds nothing here.
    """
    why = why_not(vcf)
    if why is not None:
        raise Unreadable(why, pass_failure(str(vcf)) or "")
    snap = snapshot(vcf)
    if not snap or snap.get("failed"):
        raise Unreadable("pass_failed", (snap or {}).get("failed") or "")
    return snap.get("rows", {}).get(f"{norm_chrom(chrom)}:{int(pos)}", [])


def probe_counts(vcf: Optional[str]) -> Dict[str, Any]:
    """The window counts the call-set measurement asks for, from the same pass.
    `{}` when there was no pass — the measurement then says `unmeasured`, which
    is the true state of a file nobody could read to the end."""
    snap = snapshot(vcf)
    if not snap or snap.get("failed"):
        return {}
    return {"probes": snap.get("probes") or [], "coding": snap.get("coding") or [],
            "variants": snap.get("variants") or 0}
