"""How well the alignment read the genes the panels ask about — from the package.

Why this module exists. A gene whose coverage nobody measured cannot be called
clear: «nothing found» over it is a statement about the file, not about the
person, and every entry of this product says so out loud. Until 13.09.2026 the
measurement lived in `src/ingest/qc_callability.sh` — a shell script of the
source tree — and the table it wrote held the 93 genes of the ACMG SF and CPIC
panels. The genetic half of a body system has been composed from GenCC since
0.5.0: 1203 genes. So on a real profile 1120 of them were honestly reported as
not read, and the step that closes that was one a person could run only by
cloning the repository. Here it is a command of the package, like the
genotyping of the catalogue positions beside it.

What it does. The genes are the ones the panels actually read: the ACMG
secondary-findings list, the CPIC genes, the base composition of every body
system and the genes of the curated positions. Their coordinates come from the
local ClinVar VCF — the span of that gene's variants, padded — because a gene
symbol is not a coordinate and this build carries no gene annotation of its own.
Depth comes from `samtools depth` over one interval at a time: the index means a
fraction of a percent of the alignment is read rather than all of it.

What it deliberately does not do. It does not judge. The table holds the
fractions of bases at 1×, 10×, 20× and 30×; whether that is enough is decided in
`engine/genomics.gene_coverage`, against the file's own median and the number of
copies the person carries — a threshold that would be wrong for a hemizygous
chromosome, or for a shallower genome, has no business being frozen into a file.

Standard library only; `samtools` is an external program.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

OUT_NAME = "callability.tsv"
RECORD_NAME = "callability.json"
PART_NAME = ".callability.part"
#: The padding around the span of a gene's ClinVar variants. The span is not the
#: gene: it is where the variants somebody reported in it lie, which is narrower
#: than the gene at one end and, for a gene with a distant regulatory entry,
#: wider at the other. Ten kilobases is what the project's own pipeline used
#: from the start, and the number is here rather than in three places.
PAD = 10_000
#: Reads below this mapping quality do not count as having read a base.
MIN_MAPQ = 20
THRESHOLDS = (1, 10, 20, 30)
#: GENEINFO may be the FIRST INFO field, and is then preceded by a tab.
_GENEINFO = re.compile(r"[;\t]GENEINFO=([^;\s]*)")
_HEADER = ("gene", "panel", "chrom", "length_bp", "mean_depth", "rel_to_panel",
           "pct_1x", "pct_10x", "pct_20x", "pct_30x", "start", "end")

Progress = Callable[[int, int, Optional[str]], None]


class Stopped(Exception):
    """A stop was requested between two genes."""


def genes() -> Dict[str, str]:
    """Every gene the panels read, each tagged with the list that asks for it."""
    from . import core
    out: Dict[str, str] = {}
    def add(names, tag):
        for name in names:
            g = str(name or "").strip().upper()
            if g:
                out.setdefault(g, tag)
    try:
        add(core._read_knowledge("acmg_sf.json").get("genes") or {}, "ACMG")
    except Exception:                                                # noqa: BLE001
        pass
    try:
        cpic = core._read_knowledge("cpic_drug_gene.json")
        add(cpic.get("genes") or {}, "CPIC")
        add(cpic.get("genes_of_interest") or [], "CPIC")
    except Exception:                                                # noqa: BLE001
        pass
    try:
        for spec in (core._read_knowledge("gencc_gene_disease.json").get("systems") or {}).values():
            add((spec.get("genes") or {}), "PANEL")
    except Exception:                                                # noqa: BLE001
        pass
    try:
        for spec in (core._read_knowledge("system_gene_panels.json").get("systems") or {}).values():
            add((p.get("gene") for p in (spec.get("positions") or [])), "PANEL")
    except Exception:                                                # noqa: BLE001
        pass
    return out


def clinvar_path() -> Optional[Path]:
    """The published ClinVar VCF, named or lying beside the genome."""
    from . import core
    env = os.environ.get("SCHOLION_CLINVAR_VCF")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    for base in core.genome_bases():
        for name in ("clinvar.vcf.gz", "clinvar.chr.vcf.gz"):
            if (base / name).exists():
                return base / name
    return None


def requirements() -> Dict[str, Optional[str]]:
    """What the measurement needs, each found or None."""
    from . import gene_region
    bam = gene_region.bam_path()
    cv = clinvar_path()
    return {"bam": str(bam) if bam else None, "clinvar": str(cv) if cv else None,
            "samtools": shutil.which("samtools")}


def refusal(req: Optional[Dict[str, Optional[str]]] = None) -> Optional[str]:
    """Why the measurement cannot run here — a code — or None."""
    req = req if req is not None else requirements()
    if not req.get("bam"):
        return "no_bam"
    bam = Path(str(req["bam"]))
    if not any(p.exists() for p in (Path(str(bam) + ".bai"), bam.with_suffix(".bai"),
                                    Path(str(bam) + ".csi"))):
        return "no_index"
    if not req.get("clinvar"):
        return "no_clinvar"
    if not req.get("samtools"):
        return "no_samtools"
    return None


def out_path() -> Path:
    from . import core
    return core.profile_dir() / OUT_NAME


def _record() -> Optional[Dict[str, Any]]:
    try:
        rec = json.loads((out_path().parent / RECORD_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def state() -> Dict[str, Any]:
    """Whether the coverage table covers the genes the panels read.

    `no_vcf` — this profile has no genome, so the step does not apply; `missing`
    — no table; `older_than_panels` — it was measured over fewer genes than the
    panels now hold; `current`; `unrecorded` — a table with no record beside it,
    which cannot be told apart from a current one and is not asked to be
    rebuilt.
    """
    from . import genome
    wanted = genes()
    out = out_path()
    res: Dict[str, Any] = {"genes_wanted": len(wanted), "path": str(out),
                           "refusal": refusal(), "record": None}
    if genome.vcf_path() is None:
        # No genome at all: the coverage of genes nobody has sequenced is not a
        # gap in this profile, it is a step that does not apply to it. Said here
        # rather than as «you need an alignment», which would stand unanswerable
        # in the plan of every profile that holds laboratory results only.
        res["status"] = "no_vcf"
        return res
    if not out.exists():
        res["status"] = "missing"
        return res
    rec = _record()
    if not rec:
        res["status"] = "unrecorded"
        return res
    res["record"] = rec
    held = int(rec.get("genes_requested") or 0)
    res["genes_held"] = held
    res["status"] = "current" if held >= len(wanted) else "older_than_panels"
    return res


def spans(wanted: Dict[str, str], clinvar: str,
          prefix: str = "chr") -> Tuple[Dict[str, Tuple[str, int, int]], List[str]]:
    """Where each gene's ClinVar variants lie: (contig, start, end), plus the ones with none.

    A gene ClinVar has never heard of gets no interval and no row, and the engine
    then says «the table does not hold this gene» — which is true, and different
    from «read poorly». Inventing a span for it would be the worse answer.
    """
    span: Dict[str, Tuple[str, int, int]] = {}
    with gzip.open(clinvar, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            m = _GENEINFO.search(line)
            if not m:
                continue
            hit = {p.split(":")[0].upper() for p in m.group(1).split("|")} & set(wanted)
            if not hit:
                continue
            f = line.split("\t", 3)
            chrom, pos = f[0], int(f[1])
            for g in hit:
                c, lo, hi = span.get(g, (chrom, pos, pos))
                if c == chrom:
                    span[g] = (c, min(lo, pos), max(hi, pos))
    out = {}
    for g, (c, lo, hi) in span.items():
        # ClinVar calls the mitochondrion MT; a GRCh38 alignment calls it chrM.
        name = "M" if c == "MT" else c
        out[g] = ((prefix + name) if not name.startswith("chr") else name,
                  max(0, lo - PAD), hi + PAD)
    return out, sorted(set(wanted) - set(span))


def _depth(bam: str, region: str, length: int,
           run: Optional[Callable[[List[str]], Any]] = None) -> Dict[str, float]:
    """One interval: the mean depth and the fraction of bases at each threshold.

    Positions samtools does not print are positions no read covered; the
    denominator is the interval, not the output, so an unread stretch lowers the
    fractions instead of vanishing from them.
    """
    argv = ["samtools", "depth", "-Q", str(MIN_MAPQ), "-r", region, bam]
    if run is not None:
        lines = run(argv)
        it = (l.encode() if isinstance(l, str) else l for l in lines)
    else:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL)
        it = proc.stdout  # type: ignore[assignment]
    total = 0
    at = {t: 0 for t in THRESHOLDS}
    for raw in it:
        try:
            d = int(raw[raw.rindex(b"\t") + 1:])
        except (ValueError, IndexError):
            continue
        total += d
        for t in THRESHOLDS:
            if d >= t:
                at[t] += 1
    if run is None:
        proc.stdout.close()                                          # type: ignore[union-attr]
        proc.wait()
    n = max(1, length)
    return {"mean": total / n, **{f"p{t}": 100.0 * at[t] / n for t in THRESHOLDS}}


def _measured(part: Path) -> Dict[str, str]:
    if not part.exists():
        return {}
    out = {}
    for line in part.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("gene\t"):
            out[line.split("\t", 1)[0]] = line
    return out


def measure(progress: Optional[Progress] = None, stop: Optional[Callable[[], bool]] = None,
            run: Optional[Callable[[List[str]], Any]] = None) -> Dict[str, Any]:
    """Measure every panel gene from the alignment into `callability.tsv`.

    Resumable per gene: over a thousand intervals, a step that starts from the
    beginning after any interruption is a step people stop running. What was
    measured stays in a part file beside the profile until the whole run
    finishes, and the table is replaced only then.
    """
    from . import __version__, bamlite
    req = requirements()
    why = refusal(req)
    if why:
        return {"ok": False, "status": "refused", "reason": why}
    bam, clinvar = str(req["bam"]), str(req["clinvar"])
    try:
        lengths = bamlite.reference_lengths(bam)
    except (OSError, ValueError) as exc:
        return {"ok": False, "status": "refused", "reason": "alignment_unreadable",
                "error": type(exc).__name__}
    prefix = "chr" if "chr1" in lengths else ""
    wanted = genes()
    if not wanted:
        return {"ok": False, "status": "refused", "reason": "no_genes"}
    started = time.monotonic()
    target = out_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.parent / PART_NAME
    done = _measured(part)
    where, without = spans(wanted, clinvar, prefix)
    order = [g for g in sorted(where) if where[g][0] in lengths]
    outside = sorted(g for g in where if where[g][0] not in lengths)
    total = len(order)
    try:
        with part.open("a", encoding="utf-8") as fh:
            for i, g in enumerate(order):
                if stop is not None and stop():
                    raise Stopped()
                if g in done:
                    continue
                if progress is not None:
                    progress(i, total, g)
                chrom, lo, hi = where[g]
                hi = min(hi, lengths[chrom])
                d = _depth(bam, f"{chrom}:{lo + 1}-{hi}", hi - lo, run)
                fh.write("\t".join((
                    g, wanted[g], chrom, str(hi - lo), f"{d['mean']:.1f}", "",
                    f"{d['p1']:.1f}", f"{d['p10']:.1f}", f"{d['p20']:.1f}", f"{d['p30']:.1f}",
                    str(lo), str(hi))) + "\n")
                fh.flush()
        if progress is not None:
            progress(total, total, None)
        rows = _measured(part)
        if not rows:
            return {"ok": False, "status": "failed", "step": "depth", "rc": 0,
                    "error": "no interval produced a row"}
        _write_table(target, rows)
        record = {"engine": __version__, "genes_requested": len(wanted),
                  "genes_measured": len(rows), "genes_without_clinvar": len(without),
                  "alignment": Path(bam).name, "min_mapq": MIN_MAPQ,
                  "written": date.today().isoformat()}
        tmp = target.parent / f".{RECORD_NAME}.tmp-{os.getpid()}"
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, target.parent / RECORD_NAME)
        try:
            part.unlink(missing_ok=True)
        except OSError:
            # A part file that cannot be removed is not a failed measurement:
            # the table and its record are already written, and the next run
            # reads the part only to skip what it holds. Raising here would
            # report a finished step as broken.
            pass
    except Stopped:
        return {"ok": False, "status": "stopped", "measured": len(_measured(part)),
                "genes": total}
    return {"ok": True, "status": "written", "path": str(target), "genes": len(rows),
            "without_clinvar": len(without), "outside_the_alignment": len(outside),
            "seconds": round(time.monotonic() - started, 1)}


def _write_table(target: Path, rows: Dict[str, str]) -> None:
    """The table, with each gene's depth against the median of the same kind of locus.

    `rel_to_panel` is filled in here rather than in the loop: it is a ratio to the
    median, and the median is only known once every interval has been measured.
    """
    parsed = []
    for line in rows.values():
        f = line.split("\t")
        try:
            parsed.append((f, float(f[4])))
        except (ValueError, IndexError):
            continue
    sex = sorted(d for f, d in parsed if f[2] in ("chrX", "chrY", "X", "Y") and d > 0)
    autosomal = sorted(d for f, d in parsed if f[2] not in ("chrX", "chrY", "X", "Y") and d > 0)
    med = autosomal[len(autosomal) // 2] if autosomal else 0.0
    med_sex = sex[len(sex) // 2] if sex else 0.0
    out = []
    for f, d in parsed:
        ref = med_sex if (f[2] in ("chrX", "chrY", "X", "Y") and med_sex) else med
        f = list(f)
        f[5] = f"{(d / ref):.2f}" if ref else "0"
        out.append(f)
    out.sort(key=lambda f: (float(f[8]), float(f[5] or 0)))
    tmp = target.parent / f".{OUT_NAME}.tmp-{os.getpid()}"
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write("\t".join(_HEADER) + "\n")
        for f in out:
            fh.write("\t".join(f) + "\n")
    os.replace(tmp, target)
