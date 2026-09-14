"""Pure-Python read depth over a region of a BAM — without samtools and without pysam.

Why this exists. A variants-only VCF records where the genome DIFFERS from the
reference; it cannot tell «this position matches the reference» apart from «this
position was never read». For a clinical question that difference is the whole
answer: «no activating variant in CASR» means nothing until it is known that CASR
was read. `qc_callability.sh` answers this natively for a fixed list of genes; a
question about a gene outside that list had no answer at all, and an answer that
exists only for a pre-chosen list is what task 127 was opened about.

Calibration. Against the native run (`qc_callability.sh` → mosdepth, --mapq 20) on
the owner's own BAM, four genes over the same intervals, this module reproduces
mean, ≥1×, ≥10×, ≥20× and ≥30× EXACTLY — MTHFR 24.9834 / 40135 / 39550 / 31400 /
10290, SDHB 24.0059, APOE 21.0220, GLA 12.5463, every count identical. The test
`test_depth_matches_the_native_callability_run` pins that, skipping when the BAM
is not on the machine.

That exactness was earned, not assumed. A first version counted D and N as depth
and, worse, let a non-counted operation fail to advance the reference position, so
everything after a deletion was placed wrong. It still agreed with the native run
to within 0.04 % — close enough to have been called agreement and shipped. What
the near-miss actually meant was a bug, and it is the reason the calibration here
demands equality rather than closeness: on this kind of number, «almost the same»
is the shape a misplacement takes.

The .bai format: https://samtools.github.io/hts-specs/SAMv1.pdf §5.2. A BGZF virtual
offset holds the block's offset in the file in its high 48 bits and the offset inside
the decompressed block in its low 16 — the same convention `tabixlite` already reads.
"""
from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: CIGAR operations that place the read on the reference and are counted as depth:
#: M, = and X. D and N are deliberately NOT counted — a deleted or skipped base is
#: spanned by the read but not read, and `samtools depth` does not count it either.
_REF_CONSUMING = {0, 7, 8}

#: Flags excluded, matching the default of both engines `qc_callability.sh` can use:
#: unmapped (0x4), secondary (0x100), QC-fail (0x200), duplicate (0x400) — mosdepth's
#: default filter 1796. Counting these would inflate depth in exactly the repetitive
#: regions where an inflated number misleads most.
_SKIP_FLAGS = 0x4 | 0x100 | 0x200 | 0x400

#: The same MAPQ floor the native callability run uses. A read the aligner could not
#: place confidently is not evidence that a position was read.
DEFAULT_MIN_MAPQ = 20


def _reg2bins(beg: int, end: int) -> List[int]:
    """Every index bin that can overlap [beg, end) — 0-based, end-exclusive."""
    if end <= beg:
        return []
    end -= 1
    out = [0]
    for shift, start in ((26, 1), (23, 9), (20, 73), (17, 585), (14, 4681)):
        out.extend(range(start + (beg >> shift), start + (end >> shift) + 1))
    return out


class BamIndex:
    """The .bai of a BAM: bin index plus linear index, per reference."""

    def __init__(self, path: str | Path):
        raw = Path(path).read_bytes()
        if raw[:4] != b"BAI\x01":
            raise ValueError(f"not a .bai index: {path}")
        p = 4
        (n_ref,) = struct.unpack_from("<i", raw, p); p += 4
        self.bins: List[Dict[int, List[Tuple[int, int]]]] = []
        self.linear: List[Tuple[int, ...]] = []
        for _ in range(n_ref):
            (n_bin,) = struct.unpack_from("<i", raw, p); p += 4
            b: Dict[int, List[Tuple[int, int]]] = {}
            for _ in range(n_bin):
                (bin_id, n_chunk) = struct.unpack_from("<Ii", raw, p); p += 8
                chunks = []
                for _ in range(n_chunk):
                    beg, end = struct.unpack_from("<QQ", raw, p); p += 16
                    chunks.append((beg, end))
                b[bin_id] = chunks
            (n_intv,) = struct.unpack_from("<i", raw, p); p += 4
            self.linear.append(struct.unpack_from("<%dQ" % n_intv, raw, p))
            p += 8 * n_intv
            self.bins.append(b)

    def chunks(self, ref: int, beg: int, end: int) -> List[Tuple[int, int]]:
        if ref < 0 or ref >= len(self.bins):
            return []
        b, lin = self.bins[ref], self.linear[ref]
        # The linear index gives the earliest virtual offset that can hold a read
        # overlapping the 16 kb window containing `beg`; chunks ending before it
        # cannot contain one and are dropped before any decompression happens.
        i = beg >> 14
        min_off = lin[i] if i < len(lin) else (lin[-1] if lin else 0)
        out = []
        for bid in _reg2bins(beg, end):
            for cb, ce in b.get(bid, ()):
                if ce > min_off:
                    out.append((cb, ce))
        out.sort()
        return _merge(out)


def _merge(chunks: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Overlapping chunks decompressed twice would count every read in them twice."""
    out: List[Tuple[int, int]] = []
    for cb, ce in chunks:
        if out and cb <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], ce))
        else:
            out.append((cb, ce))
    return out


def references(bam: str | Path) -> Dict[str, int]:
    """Reference name → id, from the BAM header."""
    with open(str(bam), "rb") as fh:
        gz = gzip.GzipFile(fileobj=fh)
        head = gz.read(8)
        if head[:4] != b"BAM\x01":
            raise ValueError(f"not a BAM: {bam}")
        (l_text,) = struct.unpack("<i", head[4:8])
        gz.read(l_text)
        (n_ref,) = struct.unpack("<i", gz.read(4))
        names = {}
        for i in range(n_ref):
            (l_name,) = struct.unpack("<i", gz.read(4))
            names[gz.read(l_name)[:-1].decode()] = i
            gz.read(4)
        return names


def reference_lengths(bam: str | Path) -> Dict[str, int]:
    """Reference name → length, from the BAM header. The length of chromosome 1
    is what tells GRCh38 from GRCh37 whatever the contigs are called."""
    with open(str(bam), "rb") as fh:
        gz = gzip.GzipFile(fileobj=fh)
        head = gz.read(8)
        if head[:4] != b"BAM\x01":
            raise ValueError(f"not a BAM: {bam}")
        (l_text,) = struct.unpack("<i", head[4:8])
        gz.read(l_text)
        (n_ref,) = struct.unpack("<i", gz.read(4))
        lengths = {}
        for _ in range(n_ref):
            (l_name,) = struct.unpack("<i", gz.read(4))
            name = gz.read(l_name)[:-1].decode()
            (lengths[name],) = struct.unpack("<i", gz.read(4))
        return lengths


def _read_chunk(fh, cb: int, ce: int) -> bytes:
    """The decompressed bytes of one index chunk, from virtual offset cb to ce."""
    coff, uoff = cb >> 16, cb & 0xFFFF
    end_coff = ce >> 16
    fh.seek(coff)
    gz = gzip.GzipFile(fileobj=fh)
    buf = bytearray()
    while True:
        piece = gz.read(1 << 20)
        if not piece:
            break
        buf += piece
        # Read past the end block before stopping: a record may straddle a block edge.
        if fh.tell() > end_coff:
            break
    gz.close()
    return bytes(buf[uoff:])


def depth(bam: str | Path, chrom: str, beg: int, end: int, *,
          min_mapq: int = DEFAULT_MIN_MAPQ, bai: Optional[str] = None) -> List[int]:
    """Per-base read depth over the 1-based inclusive interval [beg, end].

    Returns a list of length end-beg+1. Positions never covered are 0 — the number
    the caller most needs to see, so it is never smoothed over or left out.
    """
    bam = str(bam)
    bai = bai or (bam + ".bai")
    refs = references(bam)
    if chrom not in refs:
        raise KeyError(f"contig {chrom} is not in the BAM header")
    ref = refs[chrom]
    idx = BamIndex(bai)
    b0, e0 = beg - 1, end                      # 0-based, half-open
    cov = [0] * (end - beg + 1)
    with open(bam, "rb") as fh:
        for cb, ce in idx.chunks(ref, b0, e0):
            data = _read_chunk(fh, cb, ce)
            p, n = 0, len(data)
            while p + 4 <= n:
                (bsize,) = struct.unpack_from("<i", data, p)
                if bsize < 32 or p + 4 + bsize > n:
                    break
                rec = data[p + 4:p + 4 + bsize]
                p += 4 + bsize
                r_ref, r_pos = struct.unpack_from("<ii", rec, 0)
                l_rn, mapq = rec[8], rec[9]
                n_cig = struct.unpack_from("<H", rec, 12)[0]
                flag = struct.unpack_from("<H", rec, 14)[0]
                if r_ref != ref or flag & _SKIP_FLAGS or mapq < min_mapq:
                    continue
                q, pos = 32 + l_rn, r_pos
                for i in range(n_cig):
                    (op,) = struct.unpack_from("<I", rec, q + 4 * i)
                    oplen, opcode = op >> 4, op & 0xF
                    if opcode in _REF_CONSUMING:
                        for x in range(max(pos, b0), min(pos + oplen, e0)):
                            cov[x - b0] += 1
                        pos += oplen
                    elif opcode in (2, 3):     # D, N advance the reference silently
                        pos += oplen
                    if pos >= e0:
                        break
    return cov


def summarise(cov: List[int], thresholds=(1, 10, 20, 30)) -> Dict[str, float]:
    """Mean, median, minimum and the share of bases at or above each threshold."""
    n = len(cov) or 1
    s = sorted(cov)
    return {
        "bases": len(cov),
        "mean": round(sum(cov) / n, 2),
        "median": s[n // 2] if cov else 0,
        "min": min(cov) if cov else 0,
        **{f"pct_{t}x": round(100.0 * sum(1 for c in cov if c >= t) / n, 2)
           for t in thresholds},
    }
