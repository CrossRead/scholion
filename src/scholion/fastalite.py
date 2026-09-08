"""Random access to an .fai-indexed FASTA, and the genetic code — stdlib only.

Why the project needs its own. A variant is reported as chromosome, position and
letters; what a clinician asks about is the protein. Turning one into the other
needs the reference sequence at those coordinates, and the reference is already on
the machine — it is the very file the BAM was called against. Fetching it here,
rather than asking a web service what the consequence is, keeps three things true
at once: the answer is available offline, it is derived from the same assembly the
genome was called against, and no coordinate of the owner's leaves the machine.

The .fai format: name, length, byte offset of the first base, bases per line,
bytes per line. Line breaks are what the offsets have to step over, and they are
the whole of the arithmetic below.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: The standard genetic code, built rather than typed out: the table below is the
#: canonical NCBI table 1 in its conventional base order, and building the map from
#: it is shorter to check than sixty-four hand-written pairs.
_BASES = "TCAG"
_AAS = ("FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG")
CODONS: Dict[str, str] = {
    a + b + c: _AAS[i]
    for i, (a, b, c) in enumerate((x, y, z) for x in _BASES for y in _BASES for z in _BASES)
}

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")


def revcomp(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def translate(seq: str) -> str:
    """Codons to one-letter amino acids; an unknown codon becomes `X`, never a guess."""
    return "".join(CODONS.get(seq[i:i + 3].upper(), "X") for i in range(0, len(seq) - 2, 3))


class Fasta:
    """An .fai-indexed reference. `fetch` takes 1-based inclusive coordinates."""

    def __init__(self, path: str | Path, fai: Optional[str | Path] = None):
        self.path = Path(path)
        fai = Path(fai) if fai else Path(str(path) + ".fai")
        if not fai.exists():
            raise FileNotFoundError(f"no .fai beside the reference: {fai}")
        self.index: Dict[str, Tuple[int, int, int, int]] = {}
        for line in fai.read_text(encoding="utf-8").splitlines():
            f = line.split("\t")
            if len(f) >= 5:
                self.index[f[0]] = (int(f[1]), int(f[2]), int(f[3]), int(f[4]))

    def contigs(self) -> List[str]:
        return list(self.index)

    def fetch(self, chrom: str, start: int, end: int) -> str:
        """Reference bases of [start, end], 1-based inclusive, upper-cased."""
        if chrom not in self.index:
            raise KeyError(f"contig {chrom} is not in the reference index")
        length, offset, per_line, per_line_bytes = self.index[chrom]
        if start < 1 or end > length or end < start:
            raise ValueError(f"{chrom}:{start}-{end} is outside the contig (length {length})")
        need = end - start + 1
        begin = offset + (start - 1) // per_line * per_line_bytes + (start - 1) % per_line
        # Line breaks live inside the span, so read generously and drop them after.
        span = need + need // per_line * (per_line_bytes - per_line) + per_line_bytes
        with self.path.open("rb") as fh:
            fh.seek(begin)
            raw = fh.read(span)
        return raw.replace(b"\n", b"").replace(b"\r", b"")[:need].decode("ascii").upper()


def coding_sequence(fa: Fasta, cds: List[Tuple[str, int, int]], strand: str) -> Tuple[str, List[int]]:
    """The coding sequence of a transcript, and the genomic position of each base.

    The positions travel WITH the sequence rather than being recomputed by the
    caller: a substitution has to be applied at a genomic coordinate, and the
    mapping from coordinate to offset is exactly where a strand mistake hides.
    """
    ivs = sorted(cds, key=lambda x: x[1])
    seq, pos = [], []
    for chrom, a, b in ivs:
        seq.append(fa.fetch(chrom, a, b))
        pos.extend(range(a, b + 1))
    s = "".join(seq)
    if strand in ("-", -1, "-1"):
        return revcomp(s), pos[::-1]
    return s, pos


def protein_change(fa: Fasta, cds: List[Tuple[str, int, int]], strand: str,
                   position: int, ref: str, alt: str) -> Dict[str, object]:
    """What one single-base substitution does to the protein.

    Returns `{"kind": ...}` — `synonymous`, `missense`, `nonsense`, `start_lost`,
    `not_coding`, or `not_substitution` for anything longer than one base, which
    this deliberately does not attempt: an indel's consequence depends on the
    frame of everything downstream, and a wrong answer there is worse than none.
    """
    if len(ref) != 1 or len(alt) != 1:
        return {"kind": "not_substitution"}
    seq, pos = coding_sequence(fa, cds, strand)
    if position not in pos:
        return {"kind": "not_coding"}
    i = pos.index(position)
    minus = strand in ("-", -1, "-1")
    want = revcomp(ref) if minus else ref
    if seq[i] != want:
        # The reference disagreeing with the VCF's REF column means the two are not
        # talking about the same assembly. Saying so is the answer; guessing is not.
        return {"kind": "reference_mismatch", "reference_base": seq[i], "vcf_ref": ref}
    new = seq[:i] + (revcomp(alt) if minus else alt) + seq[i + 1:]
    old_aa, new_aa = translate(seq), translate(new)
    codon = i // 3 + 1
    a, b = old_aa[codon - 1], new_aa[codon - 1]
    kind = ("synonymous" if a == b else
            "start_lost" if codon == 1 and a == "M" else
            "nonsense" if b == "*" else
            "stop_lost" if a == "*" else "missense")
    return {"kind": kind, "codon": codon, "ref_aa": a, "alt_aa": b,
            "hgvs_p": f"p.{a}{codon}{b}" if a != b else f"p.{a}{codon}="}
