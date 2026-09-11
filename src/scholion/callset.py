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

#: Three windows chosen for the opposite reason: they are among the most
#: gene-dense stretches of the genome, so an EXOME reads thick here while it
#: reads like nothing at all in the windows above. That contrast — not an
#: absolute number — is what separates an exome from a narrow panel, and a
#: contrast survives depth, ancestry and the caller's settings in a way a
#: threshold does not. Five megabases wide so that the half-megabase offset
#: between builds cannot walk a probe off its target.
#: None of these overlaps a window above: a row counted twice would make a panel
#: look like an exome, and the first draft of this tuple did exactly that on
#: chromosome 1.
CODING_PROBES = (("19", 35_000_000, 5_000_000),
                 ("11", 62_000_000, 5_000_000),
                 ("17", 40_000_000, 5_000_000))

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

#: An exome answered `sparse` until this was written, and `sparse` closes ClinVar
#: and the ACMG list — so the one input on which a pathogenic-variant screen is
#: most obviously worth running was the input on which it never ran. That is not
#: caution, it is a refusal aimed at the wrong file.
#:
#: The rule is a shape, not a level: gene-poor windows near-empty AND gene-dense
#: windows carrying real numbers, in at least two of the three, with a clear
#: contrast between them. A narrow panel fails it — a few hundred genes are not
#: dense in three unrelated stretches at once — and a whole genome never reaches
#: it, because it is dense in the gene-poor windows too and is classified before.
#:
#: HONESTY ABOUT THESE TWO NUMBERS: the thresholds in `THRESHOLD_EVIDENCE` above
#: were measured on real files. These two were not — the corpus holds no exome
#: yet. They are set from the arithmetic (an exome captures on the order of a few
#: per cent of a gene-dense window, against a whole genome's ~1500/Mb there) and
#: they are due to be re-measured the day a real exome enters the corpus. Until
#: then the contrast rule is what carries the decision, and it is the part that
#: does not depend on where exactly the line sits.
EXOME_CODING_PER_MB = 20
EXOME_CONTRAST = 5

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


def _coding_probes(vcf: str) -> List[Dict[str, int]]:
    """The gene-dense windows, where an EMPTY window is a measurement.

    `_probe` returns None for a window it could not read, and «no rows» and «no
    such contig» look identical from there. In the gene-poor windows that
    conflation is harmless; here it is the whole question, because a panel's
    zero and an exome's thousands are the two answers being told apart. So the
    file's own contig list is consulted: a contig that IS in the file and holds
    no rows in the window contributes a real zero.
    """
    from . import tabixlite
    try:
        present = {str(c).lower().replace("chr", "") for c in tabixlite.contigs(vcf)}
    except Exception:
        present = set()
    out: List[Dict[str, int]] = []
    for chrom, start, width in CODING_PROBES:
        p = _probe(vcf, chrom, start, width)
        if p is None and chrom.lower() in present:
            p = {"observed": 0, "imputed": 0, "blocks": 0}
        if p is not None:
            out.append(p)
    return out


def _compose(vcf: str) -> Dict[str, int]:
    """Substitutions against indels among the first rows that carry an allele."""
    import gzip
    snv = indel = seen = 0
    try:
        with gzip.open(vcf, "rt", encoding="utf-8", errors="replace") as fh:
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


def _exome_shape(m: Dict[str, Any]) -> bool:
    """Empty where genes are not, populated where they are — that is an exome."""
    rich = m.get("coding_per_mb")
    if rich is None or rich < EXOME_CODING_PER_MB:
        return False
    if (m.get("coding_probes_dense") or 0) < 2:
        return False
    poor = m.get("observed_per_mb") if m.get("measured") else 0
    poor = 0 if poor is None else poor
    if poor >= PANEL_PER_MB:
        return False
    return rich >= EXOME_CONTRAST * max(poor, 1)


def _classify(m: Dict[str, Any]) -> str:
    # Composition first, and deliberately before `measured`: what a file
    # CONTAINS is read from the file itself and does not need an index, while
    # breadth does. A call set holding no substitutions is a partial call set
    # whether or not its windows could be probed.
    if m.get("only_indels"):
        return "partial_callset_indels"
    if m.get("only_snvs"):
        return "partial_callset_snvs"
    # Imputation is decided before breadth, as before: a file that is mostly a
    # model is that whatever its windows say.
    share = m.get("imputed_share")
    if share is not None and share >= 0.5:
        return "imputed_panel"
    # And before «unmeasured», because an exome's gene-poor windows are empty by
    # construction — the very silence that used to leave it unmeasured is half
    # of the evidence that it IS an exome.
    if _exome_shape(m):
        return "exome"
    if not m.get("measured"):
        return "unmeasured"
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
    # Nanosecond mtime: a file rewritten within the same second at the same size
    # is a different file, and a whole-second key served the old measurement
    # for it.
    import hashlib
    key = hashlib.sha1(
        f"{os.path.abspath(vcf)}|{st.st_size}|{st.st_mtime_ns}".encode()
    ).hexdigest()[:16]
    # `callset2`: an entry written before the coding probes existed carries no
    # `coding_per_mb`, and reading it back would classify every exome as sparse
    # for as long as the cache lives.
    return base / f"callset2-{key}.json"


def measure(vcf: Optional[str]) -> Dict[str, Any]:
    """Measure this call set. Cheap enough to run from a status command.

    Everything here is read through the index or from the head of the file; no
    pass over the whole thing, because a status command that takes twelve
    seconds is a status command nobody runs.
    """
    empty = {"measured": False, "class": "unmeasured", "observed_per_mb": None,
             "probes": [], "snv": 0, "indel": 0, "sampled": 0,
             "only_indels": False, "only_snvs": False,
             "imputed_share": None, "reference_blocks": False,
             "coding_per_mb": None, "coding_probes": [], "coding_probes_dense": 0}
    if not vcf or not os.path.exists(vcf):
        return empty

    cp = _cache_path(vcf)
    if cp is not None and cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass

    probes = [_probe(vcf, c, s, w) for c, s, w in PROBES]
    good = [p for p in probes if p is not None]
    coding = _coding_probes(vcf)
    if not good and not coding:
        # Every window is read through the index, so a file with no index is not
        # a file of unknown breadth — it is a file nobody looked at. That silence
        # used to become `unmeasured`, and `unmeasured` closes paths. The single
        # linear pass counts the same windows on the way through.
        from . import linear as _lin
        counted = _lin.probe_counts(vcf)
        if counted:
            good = [p for p in counted.get("probes", []) if p]
            coding = [p for p in counted.get("coding", []) if p]
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
    if coding:
        wide = CODING_PROBES[0][2] // 1_000_000
        per_rich = sorted(p["observed"] // wide for p in coding)
        out["coding_probes"] = [p["observed"] for p in coding]
        out["coding_per_mb"] = per_rich[len(per_rich) // 2]
        out["coding_probes_dense"] = sum(1 for v in per_rich if v >= EXOME_CODING_PER_MB)
    out["class"] = _classify(out)

    if cp is not None:
        try:
            cp.parent.mkdir(parents=True, exist_ok=True)
            # Whole or not at all: two status requests on the web server's
            # threads measured the same file at once and wrote the same entry
            # over each other, and a third reader parsed the half they left.
            tmp = cp.with_name(f"{cp.name}.{os.getpid()}.tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            os.replace(tmp, cp)
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
