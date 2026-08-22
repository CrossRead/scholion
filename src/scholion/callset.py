"""What is actually inside a call set — measured, never assumed.

Task 87. Before this module the input had exactly two classes, `array` and
`sequenced`, and every `sequenced` input was described to the reader as «a whole
genome — every base the sequencing reached, so both single variants and
polygenic scores are computable». Run against a corpus of real third-party
files, that sentence was printed over seven inputs and was false for all seven:
an imputed gVCF, two genotyping chips distributed as VCF, a low-pass screen and
two DRAGEN call sets that contained indels and no SNVs at all.

The failure is the one this project keeps finding in itself — a precondition
that was never checked, replaced by a plausible default and delivered with the
confidence of a measurement. So this module measures instead of assuming, and
where a measurement is impossible it says `unmeasured` rather than guessing.

Three measurements, all exact, none of them an estimate of anything else:

* **Breadth** — the number of OBSERVED variants per megabase inside three fixed
  ten-megabase windows, read through the index. Observed means the row carries a
  real alternative allele and its FILTER is `PASS` or empty; an imputed or
  filtered row is not an observation, and counting it as one is how a file that
  is 98 % imputation looked denser than a whole genome.
* **Composition** — how many of the first rows are substitutions and how many
  are indels. A call set with no SNVs at all cannot answer for an SNV, and no
  amount of reading will change that.
* **Reference blocks** — whether the file is a gVCF, in which most rows are
  spans of «same as the reference» rather than variants.

The thresholds below are calibrated against measured files, not chosen for
roundness; the numbers are in `THRESHOLD_EVIDENCE` so that the next person can
check them instead of trusting them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Three windows, deliberately gene-poor, so that a targeted panel (an exome)
#: reads as thin here — that IS the signal. Chromosome and start are fixed so
#: two runs of the same file give the same number.
PROBES = (("1", 20_000_000, 10_000_000),
          ("1", 150_000_000, 10_000_000),
          ("2", 50_000_000, 10_000_000))

SAMPLE_ROWS = 20_000

#: Observed variants per megabase. Measured, on real files:
THRESHOLD_EVIDENCE = {
    "whole genome (30x WGS, provider VCF)": (1547, 1616),
    "genotyping chip distributed as VCF": (147, 452),
    "call set split by variant type (indels only)": (256, 380),
    "low-pass screen": (17, 81),
    "imputed gVCF, counting only observed rows": (23, 70),
}
DENSE_PER_MB = 800      # below the lowest whole genome (1547), above the highest chip (452)
PANEL_PER_MB = 100      # separates a chip from a low-pass screen

_IMPUTED_TOKENS = {"IMP", "IMPUTED", "IMP_PASS"}
_OPEN_FILTERS = {"PASS", ".", ""}


def _is_snv(ref: str, alts: List[str]) -> bool:
    return len(ref) == 1 and all(len(a) == 1 for a in alts)


def _real_alts(alt: str) -> List[str]:
    return [a for a in alt.split(",") if a not in ("<NON_REF>", ".", "")]


def _probe(vcf: str, chrom: str, start: int, width: int) -> Optional[Dict[str, int]]:
    """One window, read through the index. None when the window cannot be read."""
    from . import tabixlite
    rows: List[List[str]] = []
    for prefix in (chrom, "chr" + chrom):
        try:
            rows = tabixlite.query(vcf, prefix, start, width)
        except Exception:
            rows = []
        if rows:
            break
    if not rows:
        return None
    observed = imputed = blocks = 0
    for r in rows:
        if len(r) < 7:
            continue
        alts = _real_alts(r[4])
        if not alts:
            blocks += 1
            continue
        tokens = set(r[6].replace(",", ";").split(";"))
        if tokens & _IMPUTED_TOKENS:
            imputed += 1
        elif r[6] in _OPEN_FILTERS:
            observed += 1
    return {"observed": observed, "imputed": imputed, "blocks": blocks}


def _compose(vcf: str) -> Dict[str, int]:
    """Substitutions against indels among the first rows that carry an allele."""
    import gzip
    snv = indel = seen = 0
    try:
        with gzip.open(vcf, "rt", errors="replace") as fh:
            for line in fh:
                if line[:1] == "#":
                    continue
                f = line.split("\t", 8)
                if len(f) < 5:
                    continue
                alts = _real_alts(f[4])
                if not alts:
                    continue
                seen += 1
                if _is_snv(f[3], alts):
                    snv += 1
                else:
                    indel += 1
                if seen >= SAMPLE_ROWS:
                    break
    except Exception:
        return {"snv": 0, "indel": 0, "sampled": 0}
    return {"snv": snv, "indel": indel, "sampled": seen}


def _classify(m: Dict[str, Any]) -> str:
    # Composition first, and deliberately before `measured`: what a file
    # CONTAINS is read from the file itself and does not need an index, while
    # breadth does. A call set holding no substitutions is a partial call set
    # whether or not its windows could be probed.
    if m.get("only_indels"):
        return "partial_callset_indels"
    if m.get("only_snvs"):
        return "partial_callset_snvs"
    if not m.get("measured"):
        return "unmeasured"
    share = m.get("imputed_share")
    if share is not None and share >= 0.5:
        return "imputed_panel"
    per_mb = m.get("observed_per_mb")
    if per_mb is None:
        return "unmeasured"
    if per_mb >= DENSE_PER_MB:
        return "whole_genome"
    if per_mb >= PANEL_PER_MB:
        return "panel"
    return "sparse"


def _cache_path(vcf: str) -> Optional[Path]:
    try:
        from . import core
        base = Path(core.cache_dir())
    except Exception:
        return None
    try:
        st = os.stat(vcf)
    except OSError:
        return None
    # hashlib, not hash(): the built-in is salted per process, so the key would
    # change on every run and the cache would never once be read.
    import hashlib
    key = hashlib.sha1(
        f"{os.path.abspath(vcf)}|{st.st_size}|{int(st.st_mtime)}".encode()
    ).hexdigest()[:16]
    return base / f"callset-{key}.json"


def measure(vcf: Optional[str]) -> Dict[str, Any]:
    """Measure this call set. Cheap enough to run from a status command.

    Everything here is read through the index or from the head of the file; no
    pass over the whole thing, because a status command that takes twelve
    seconds is a status command nobody runs.
    """
    empty = {"measured": False, "class": "unmeasured", "observed_per_mb": None,
             "probes": [], "snv": 0, "indel": 0, "sampled": 0,
             "only_indels": False, "only_snvs": False,
             "imputed_share": None, "reference_blocks": False}
    if not vcf or not os.path.exists(vcf):
        return empty

    cp = _cache_path(vcf)
    if cp is not None and cp.exists():
        try:
            return json.loads(cp.read_text())
        except Exception:
            pass

    probes = [_probe(vcf, c, s, w) for c, s, w in PROBES]
    good = [p for p in probes if p is not None]
    comp = _compose(vcf)

    out: Dict[str, Any] = dict(empty)
    out.update(comp)
    out["only_indels"] = bool(comp["sampled"] >= 1000 and comp["snv"] == 0)
    out["only_snvs"] = bool(comp["sampled"] >= 1000 and comp["indel"] == 0)
    out["probes"] = [p["observed"] for p in good]
    if good:
        out["measured"] = True
        per = sorted(p["observed"] // (PROBES[0][2] // 1_000_000) for p in good)
        out["observed_per_mb"] = per[len(per) // 2]
        seen_alt = sum(p["observed"] + p["imputed"] for p in good)
        out["imputed_share"] = (round(sum(p["imputed"] for p in good) / seen_alt, 3)
                                if seen_alt else None)
        out["reference_blocks"] = any(p["blocks"] for p in good)
    out["class"] = _classify(out)

    if cp is not None:
        try:
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(json.dumps(out))
        except Exception:
            pass
    return out


def answers_variant(m: Dict[str, Any], ref: str, alt: str) -> bool:
    """Could a variant of this shape appear in this call set at all?

    A file that holds indels and no substitutions has not «read the reference»
    at an SNV position — the position is outside what the file contains, and
    reporting it as reference is a statement about the person made from a
    property of the file.
    """
    alts = _real_alts(alt or "")
    if not alts or not ref:
        return True
    snv = _is_snv(ref, alts)
    if snv and m.get("only_indels"):
        return False
    if not snv and m.get("only_snvs"):
        return False
    return True
