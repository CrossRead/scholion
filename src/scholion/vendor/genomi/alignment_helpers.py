"""Two helpers lifted from Genomi's `alignment.py`, verbatim.

`detection.py` imports `paired_fastq_r1_name` / `paired_fastq_r2_name` from its
neighbouring `alignment.py` — a 479-line module whose remaining contents drive an
external aligner and are of no use here. Rather than vendor the whole file for
two functions, the two functions, their private helper and the regular
expression they share are reproduced below exactly as they stand upstream.

VENDORED FROM GENOMI — https://github.com/exon-research/genomi
commit 07a255e, file src/genomi/active_genome_index/alignment.py
Copyright Exon Research. Licensed under the Apache License, Version 2.0.

Change from upstream: extraction only — the four objects below are byte-identical
to their originals; nothing else from that module was taken. See UPSTREAM.md.
"""
from __future__ import annotations

import re
from pathlib import Path

_FASTQ_PAIR_TOKEN = re.compile(
    r"^(?P<stem>.+?)(?P<sep>[_.])(?P<marker>R?[12])(?P<suffix>(?:[_.][^/]*)?\.(?:fastq|fq)(?:\.gz|\.bgz)?)$",
    re.IGNORECASE,
)


def paired_fastq_r2_name(r1_name: str) -> str | None:
    return _paired_fastq_name(r1_name, expected_marker={"R1", "1"}, target_marker="R2")


def paired_fastq_r1_name(r2_name: str) -> str | None:
    return _paired_fastq_name(r2_name, expected_marker={"R2", "2"}, target_marker="R1")


def _paired_fastq_name(name: str, *, expected_marker: set[str], target_marker: str) -> str | None:
    match = _FASTQ_PAIR_TOKEN.match(Path(name).name)
    if not match:
        return None
    marker = match.group("marker")
    marker_upper = marker.upper()
    if marker_upper not in expected_marker:
        return None
    if marker_upper in {"R1", "R2"}:
        replacement = target_marker
    else:
        replacement = target_marker[-1]
    return f"{match.group('stem')}{match.group('sep')}{replacement}{match.group('suffix')}"
