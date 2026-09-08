"""From a gene name to the owner's own reads — without a curated catalogue.

Task 127. The question that opened it was clinical and ordinary: high phosphate with
a PTH that is not raised puts activating variants of CASR, GNA11 and AP2S1 into the
differential, and there the answer changes the treatment — calcium and vitamin D
help in one branch and harm in the other. `genome --gene CASR` answered «Gene CASR
is not in the coordinate reference». That sentence is true about `loci.json` and
false about the genome: the reads were there the whole time.

What this module puts together, and the order matters:

  1. **Coordinates** for any gene — `genes.resolve` (local GFF3, else Ensembl).
  2. **Variants** in that interval, from the personal VCF.
  3. **Which of them are coding**, by intersecting with the CDS of the canonical
     transcript, and **what they do to the protein**, computed from the same
     reference FASTA the reads were called against — not asked of a web service.
  4. **Coverage of the region**, from the BAM.

Point 4 is not decoration. Points 1–3 can only ever report what DIFFERS from the
reference; every clinically reassuring answer this module gives is of the form
«no such variant», and that sentence is empty until the region is known to have
been read. So coverage travels with the answer, always — and when it cannot be
computed the answer says so in place of the number, rather than omitting the row
and letting silence read as «fine».

The same rule governs every other absence here: a gene that will not resolve, a
missing reference, a missing BAM each produce a named gap with the fix beside it.
The one thing this module must never do is answer «nothing found» when what
happened was «nothing looked».
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import core, genes
from .i18n import t as _t

#: Read-depth thresholds reported for every region. 10× is the floor at which a
#: heterozygote can be called at all; 20× is the working threshold the project's
#: own callability step uses. Both are printed because the honest answer to «was
#: this read?» is a distribution, not a yes.
THRESHOLDS = (1, 10, 20, 30)


# ---------------------------------------------------------------- the alignment
def bam_path() -> Optional[Path]:
    """The alignment the personal VCF was called from, if it is on this machine.

    `SCHOLION_GENOME_BAM` wins; otherwise the layout the project's own pipeline
    writes (`genomic_work/<sample>/<sample>.merged.bam`) is tried, with the sample
    taken from the VCF's own file name rather than guessed.
    """
    env = os.environ.get("SCHOLION_GENOME_BAM")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    from . import genome
    vcf = genome.vcf_path()
    stems = []
    if vcf is not None:
        name = vcf.name
        for suffix in (".full.vcf.gz", ".vcf.gz", ".vcf"):
            if name.endswith(suffix):
                stems.append(name[: -len(suffix)])
                break
    for base in list(core.genome_bases()) + [Path.home() / "genomic_work"]:
        for stem in stems:
            for cand in (base / stem / f"{stem}.merged.bam",
                         base / stem / f"{stem}.markdup.bam",
                         base / f"{stem}.merged.bam"):
                try:
                    if cand.exists() and Path(str(cand) + ".bai").exists():
                        return cand
                except OSError:
                    continue
    return None


def reference_path() -> Optional[Path]:
    """The reference FASTA, needed to say what a variant does to the protein."""
    env = os.environ.get("SCHOLION_GENOME_REFERENCE")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() and Path(str(p) + ".fai").exists() else None
    # Declared locations only — see the note in `genes.gff3_search_roots`.
    roots = [b / "reference" for b in core.genome_bases()]
    roots += [Path.home() / "genomic_work" / "reference"]
    for root in roots:
        try:
            if not root.exists():
                continue
            for p in sorted(root.glob("*.fa")) + sorted(root.glob("*.fasta")):
                if Path(str(p) + ".fai").exists():
                    return p
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------- pieces
def _gap(what: str, fix: str) -> Dict[str, str]:
    return {"what": what, "fix": fix}


def _parse_row(row: List[str]) -> Dict[str, Any]:
    """One VCF data line into the fields a report quotes, and nothing more."""
    fmt = (row[8].split(":") if len(row) > 8 else [])
    val = (row[9].strip().split(":") if len(row) > 9 else [])
    call = dict(zip(fmt, val))
    ad = call.get("AD")
    return {"chrom": row[0], "pos": int(row[1]), "ref": row[3], "alt": row[4],
            "qual": row[5], "genotype": call.get("GT"),
            "depth": int(call["DP"]) if call.get("DP", "").isdigit() else None,
            "allele_depth": [int(x) for x in ad.split(",") if x.isdigit()] if ad else None,
            "rsid": row[2] if len(row) > 2 and row[2] not in (".", "") else None}


def _in_cds(pos: int, cds: List[List[Any]]) -> bool:
    return any(a <= pos <= b for _, a, b in cds)


def _clinvar_in_region(chrom: str, start: int, end: int) -> List[Dict[str, Any]]:
    """The owner's ClinVar hits inside the interval, from genome/clinvar_hits.tsv.

    That table holds the findings the ClinVar step kept — it is not a list of every
    annotated variant, so an empty result here means «no flagged finding», never
    «no variant». The distinction is carried in the report, not left to the reader.
    """
    out: List[Dict[str, Any]] = []
    bare = chrom[3:] if chrom.startswith("chr") else chrom
    for base in core.genome_bases():
        f = base / "clinvar_hits.tsv"
        if not f.exists():
            continue
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                head = fh.readline().rstrip("\n").split("\t")
                for line in fh:
                    v = line.rstrip("\n").split("\t")
                    if len(v) < len(head):
                        continue
                    rec = dict(zip(head, v))
                    c = rec.get("chrom", "")
                    if (c.startswith("chr") and c[3:] or c) != bare:
                        continue
                    try:
                        p = int(rec.get("pos", ""))
                    except ValueError:
                        continue
                    if start <= p <= end:
                        out.append(rec)
        except OSError:
            continue
        break
    return out


def _coverage(chrom: str, start: int, end: int, cds: List[List[Any]]) -> Dict[str, Any]:
    """Depth over the gene and over its coding sequence, or a named absence."""
    bam = bam_path()
    if bam is None:
        return {"source": None,
                "why": _t("gene.coverage_no_bam"),
                "fix": "SCHOLION_GENOME_BAM=/path/to/sample.merged.bam"}
    from . import bamlite
    try:
        whole = bamlite.depth(bam, chrom, start, end)
    except KeyError:
        return {"source": None, "why": _t("gene.coverage_contig", chrom=chrom), "fix": ""}
    except Exception as exc:                                       # noqa: BLE001
        return {"source": None, "why": f"{type(exc).__name__}: {exc}", "fix": ""}
    out: Dict[str, Any] = {"source": "bam", "file": str(bam),
                           "min_mapq": bamlite.DEFAULT_MIN_MAPQ,
                           "gene": bamlite.summarise(whole, THRESHOLDS)}
    if cds:
        picked: List[int] = []
        for _, a, b in sorted(cds, key=lambda x: x[1]):
            picked += whole[max(a - start, 0):max(b - start + 1, 0)]
        out["cds"] = bamlite.summarise(picked, THRESHOLDS)
    return out


def _protein(loc: Dict[str, Any], variants: List[Dict[str, Any]],
             gaps: List[Dict[str, str]]) -> None:
    """Annotate coding variants in place with what they do to the protein."""
    ref_fa = reference_path()
    if ref_fa is None:
        gaps.append(_gap(_t("gene.no_reference"), "SCHOLION_GENOME_REFERENCE=/path/to/GRCh38.fa"))
        return
    from . import fastalite
    try:
        fa = fastalite.Fasta(ref_fa)
    except Exception as exc:                                       # noqa: BLE001
        gaps.append(_gap(f"{type(exc).__name__}: {exc}", ""))
        return
    contig = genes.match_contig(loc["chrom"], fa.contigs())
    if contig is None:
        gaps.append(_gap(_t("gene.reference_contig", chrom=loc["chrom"]), ""))
        return
    cds: List[Tuple[str, int, int]] = [(contig, a, b) for _, a, b in loc["cds"]]
    for v in variants:
        if not v.get("coding"):
            continue
        try:
            v["protein"] = fastalite.protein_change(
                fa, cds, loc["strand"], v["pos"], v["ref"], v["alt"])
        except Exception as exc:                                   # noqa: BLE001
            v["protein"] = {"kind": "error", "detail": f"{type(exc).__name__}: {exc}"}


# ----------------------------------------------------------------------- report
def report(gene: str, allow_network: bool = True) -> Dict[str, Any]:
    """Everything the owner's own data can say about one gene, gaps included."""
    from . import genome
    gaps: List[Dict[str, str]] = []
    loc = genes.resolve(gene, allow_network=allow_network)
    if not loc:
        # Not «unknown gene»: named sources were asked and each was silent, and
        # WHICH of them was silent is the whole of what the owner does next. An
        # annotation that was read and does not hold the symbol is a different
        # situation from no annotation at all — the first points at the symbol,
        # the second at the machine — so the two are never merged into one line.
        consulted = [str(x) for x in genes.gff3_candidates()]
        return {"status": "unresolved_gene", "gene": gene,
                "consulted": consulted,
                "searched": consulted or [str(x) for x in genes.gff3_search_roots()],
                "network": allow_network,
                "message": _t("gene.unresolved_not_in_annotation", gene=gene) if consulted
                           else _t("gene.unresolved_no_annotation", gene=gene),
                "fix": "SCHOLION_GENE_GFF3=/path/to/ensembl.gff3.gz"}

    st = genome.available()
    out: Dict[str, Any] = {"status": "ok", "region": True, "gene": loc["gene"],
                           "location": loc, "genome_ready": st["ready"]}
    if not st["ready"]:
        out["status"] = "no_genome"
        out["reason"] = st.get("reason")
        out["message"] = _t("genome.refused." + (st.get("reason") or "no_file"))
        return out

    vcf = str(genome.vcf_path())
    rows = genome._query_region_range(vcf, loc["chrom"], loc["start"], loc["end"])
    variants = [_parse_row(r) for r in rows if len(r) > 9]
    for v in variants:
        v["coding"] = _in_cds(v["pos"], loc["cds"])
    if loc["cds"]:
        _protein(loc, variants, gaps)
    else:
        gaps.append(_gap(_t("gene.no_cds", gene=loc["gene"]), ""))

    coding = [v for v in variants if v.get("coding")]
    # «Changing the protein: 0» must never be printed when the protein layer did
    # not run: a count of zero and an uncomputed count look identical on the page
    # and mean opposite things. Without the reference the field is None, and the
    # report prints that it was not computed.
    computed = all("protein" in v for v in coding)
    consequential = (sum(1 for v in coding
                         if (v.get("protein") or {}).get("kind")
                         not in ("synonymous", "not_coding", "not_substitution",
                                 "reference_mismatch", "error", None))
                     if computed else None)
    out["variants"] = {"total": len(variants), "coding": len(coding),
                       "coding_rows": coding, "consequential": consequential,
                       "consequence_computed": computed}
    out["clinvar"] = _clinvar_in_region(loc["chrom"], loc["start"], loc["end"])
    out["coverage"] = _coverage(loc["chrom"], loc["start"], loc["end"], loc["cds"])
    if out["coverage"].get("source") is None:
        gaps.append(_gap(out["coverage"].get("why", ""), out["coverage"].get("fix", "")))
    # Two blind spots of short reads that no amount of depth removes. They are
    # stated on every answer rather than only on the reassuring ones, because a
    # caveat that appears only beside good news is read as a hedge, not a fact.
    out["blind_spots"] = [_t("gene.blind_cnv"), _t("gene.blind_noncoding")]
    out["gaps"] = gaps
    return out
