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
import struct
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .i18n import t as _t


class TabixIndex:
    """Linear .tbi index (bins are skipped — for VCF the linear index suffices)."""

    def __init__(self, path: str | Path):
        raw = gzip.open(str(path), "rb").read()
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
def _index(vcf: str) -> TabixIndex:
    return TabixIndex(vcf + ".tbi")


def contigs(vcf: str) -> List[str]:
    try:
        return _index(vcf).contigs()
    except Exception:
        return []


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
            while not stop:
                chunk = gz.read(1 << 20)
                if not chunk:
                    break
                *lines, tail = (tail + chunk).split(b"\n")
                for ln in lines:
                    if not ln or ln.startswith(b"#"):
                        continue
                    fields = ln.decode("utf-8", "replace").split("\t")
                    if fields[0] != chrom:
                        continue
                    try:
                        p = int(fields[1])
                    except ValueError:
                        continue
                    if pos <= p <= pos + window:
                        out.append(fields)
                    elif p > pos + window:
                        stop = True
                        break
            gz.close()
    except Exception:
        return out
    return out
