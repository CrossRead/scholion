"""Pure-Python access to a bgzip+tabix VCF — without bcftools and without pysam.

Why: on some machines (and inside an isolated sandbox) bcftools is unavailable,
and a personal VCF of ~200 MB takes minutes for a full pass. Here the linear
.tbi index is read, a seek is made to the required BGZF block, and only that
block is decompressed. A single-position query takes milliseconds.

The .tbi format: https://samtools.github.io/hts-specs/tabix.pdf
Virtual offset: the high 48 bits are the block's offset in the file, the low 16
are the offset inside the decompressed block. BGZF blocks are self-contained
gzip members, so gzip.GzipFile can read starting from a block boundary.
"""
from __future__ import annotations

import gzip
import os
import struct
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .i18n import t as _t


class TabixIndex:
    """Linear .tbi index (bins are skipped — for VCF the linear index suffices)."""

    def __init__(self, path: str | Path):
        with gzip.open(str(path), "rb") as fh:
            raw = fh.read()
        if raw[:4] != b"TBI\x01":
            raise ValueError(_t("genome.bad_tabix", path=path))
        p = 4
        (n_ref, _fmt, _col_seq, _col_beg, _col_end,
         _meta, _skip, l_nm) = struct.unpack_from("<8i", raw, p)
        p += 32
        names = raw[p:p + l_nm].split(b"\x00")
        p += l_nm
        self.names: Dict[str, int] = {n.decode(): i for i, n in enumerate(names) if n}
        self.linear: Dict[int, Tuple[int, ...]] = {}
        for r in range(n_ref):
            (n_bin,) = struct.unpack_from("<i", raw, p); p += 4
            for _ in range(n_bin):
                (_bin, n_chunk) = struct.unpack_from("<Ii", raw, p); p += 8
                p += 16 * n_chunk
            (n_intv,) = struct.unpack_from("<i", raw, p); p += 4
            self.linear[r] = struct.unpack_from("<%dQ" % n_intv, raw, p)
            p += 8 * n_intv

    def contigs(self) -> List[str]:
        return list(self.names)

    def voffset(self, chrom: str, pos: int) -> Optional[int]:
        """Virtual offset of the start of the 16 kb interval that contains pos."""
        r = self.names.get(chrom)
        if r is None:
            return None
        ioff = self.linear.get(r) or ()
        if not ioff:
            return 0
        k = min((pos - 1) >> 14, len(ioff) - 1)
        while k >= 0 and ioff[k] == 0:
            k -= 1
        return ioff[k] if k >= 0 else 0


@lru_cache(maxsize=8)
def _index_cached(vcf: str, stamp: tuple) -> TabixIndex:
    """Keyed on the index file's own identity, never on its path alone."""
    return TabixIndex(vcf + ".tbi")


def _index(vcf: str) -> TabixIndex:
    """The parsed index, cached until the index on disk changes.

    The cache used to be keyed on the path. Nothing invalidated it — `reset_cache`
    clears the JSON readers and the knowledge files, and its own note says
    readers are invalidated by mtime, which was true of every reader but this
    one. In a short-lived CLI call that is invisible; `serve` runs for as long as
    somebody leaves the tab open, and the genome pipeline here is run by hand in
    another terminal. Rebuild and re-index a VCF under a running server and the
    old index stays: `voffset` then answers with an offset computed for a file
    that no longer exists, the seek lands somewhere arbitrary, and the read comes
    back empty.

    Empty is the dangerous answer rather than a visible one. For a VCF made by
    `bcftools call -mv` a missing row means HOMOZYGOUS FOR THE REFERENCE, so a
    stale index does not produce an error or a gap — it produces a confident,
    ordinary-looking genotype.

    So the key carries the modification time and the size of the `.tbi` itself.
    That is one `stat` per query against decompressing a block, and it makes this
    reader behave the way the rest of them already claim to. An index that cannot
    be stat'd is looked up under an empty stamp and left to fail where it failed
    before — a missing index is the caller's `except`, not this function's.
    """
    try:
        st = os.stat(vcf + ".tbi")
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = ()
    return _index_cached(vcf, stamp)


# Kept reachable under the name callers already know, the same way `genome.py`
# forwards `assembly_of.cache_clear`: a second store nobody can clear is how a
# cache becomes permanent.
_index.cache_clear = _index_cached.cache_clear                  # type: ignore[attr-defined]


def contigs(vcf: str) -> List[str]:
    try:
        return _index(vcf).contigs()
    except Exception:
        return []


def _scan(lines, chrom: str, pos: int, window: int, seen: bool):
    """Rows of `chrom` inside [pos, pos+window] from one batch of raw lines.

    Returns (rows, seen, stop). This lives outside `query()` because what was
    wrong here was the stopping rule, not the I/O, and the rule is testable only
    if it can be run without a bgzf file and an index.

    The rule. A VCF is sorted by contig, so a row of another contig means one of
    two different things depending on where we are. Before the first row of our
    own contig it is the tail of the previous one — the index lands us at the
    start of a block, not at our first row — and we skip it. After our contig has
    been seen, it means our contig is over: there is nothing further to find, and
    the scan stops. It used to `continue` in both cases, so a query for a position
    past the end of a contig decompressed the file to EOF — on a 200 MB personal
    VCF a single call of minutes, and inside the PGS re-genotyping loop a hang.
    """
    out = []
    for ln in lines:
        if not ln or ln.startswith(b"#"):
            continue
        fields = ln.decode("utf-8", "replace").split("\t")
        if fields[0] != chrom:
            if seen:
                return out, seen, True
            continue
        seen = True
        try:
            p = int(fields[1])
        except ValueError:
            continue
        if pos <= p <= pos + window:
            out.append(fields)
        elif p > pos + window:
            return out, seen, True
    return out, seen, False


def query(vcf: str, chrom: str, pos: int, window: int = 0) -> List[List[str]]:
    """VCF rows in [pos, pos+window]. Empty = the site is not in the file.

    For a VCF produced by `bcftools mpileup | call -mv`, a missing row means a
    homozygote for the reference (coverage has to be kept in mind separately).
    """
    try:
        idx = _index(vcf)
    except Exception:
        return []
    v = idx.voffset(chrom, pos)
    if v is None:
        return []
    coffset, uoffset = v >> 16, v & 0xFFFF
    out: List[List[str]] = []
    try:
        with open(vcf, "rb") as fh:
            fh.seek(coffset)
            gz = gzip.GzipFile(fileobj=fh)
            need = uoffset
            while need > 0:                       # skip forward inside the block
                chunk = gz.read(min(need, 1 << 16))
                if not chunk:
                    break
                need -= len(chunk)
            tail = b""
            stop = False
            seen = False
            while not stop:
                chunk = gz.read(1 << 20)
                if not chunk:
                    break
                *lines, tail = (tail + chunk).split(b"\n")
                rows, seen, stop = _scan(lines, chrom, pos, window, seen)
                out.extend(rows)
            gz.close()
    except Exception:
        return out
    return out
