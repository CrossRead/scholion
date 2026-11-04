"""Genotype the catalogue positions from the alignment: the file that lets «no row» mean «the reference».

A full VCF is called with `-v`: it lists the positions where a person differs
from the reference and nothing else. A catalogue position missing from it is
therefore «reference OR not covered», and every panel that reads it prints «not
read» rather than choose. Genotyping the catalogue positions from the BAM
without `-v` writes a real `0/0` with its depth beside the VCF
(`loci_sites.vcf.gz`), and the genome reader takes it as the evidence.

**The file answers for the catalogue it was made from.** When a release grows
the catalogue, the positions it added are absent from a file made earlier — 0.5.1
grew it from 61 to 113, and a profile genotyped in August read 21 of its 92 panel
positions as not read. So the file carries a record beside it
(`loci_sites.json`): the build that wrote it, the number of catalogue positions
and the catalogue's date. `state()` compares that record with the catalogue this
build carries; a file with no record is judged by its date against the
catalogue's.

**What it needs, and refuses by name:** the personal VCF (for the folder the file
is written into), the alignment with its index, the reference FASTA with its
`.fai`, and `bcftools` on PATH. The work runs one chromosome at a time so that
progress can be reported and a stop honoured between chromosomes; the finished
file replaces the old one only when every chromosome succeeded, so an
interrupted run leaves the previous file as it was.

Standard library only; `bcftools` is an external program.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

OUT_NAME = "loci_sites.vcf.gz"
RECORD_NAME = "loci_sites.json"
_CANON = [str(i) for i in range(1, 23)] + ["X", "Y"]
#: The length of chromosome 1 tells the build of an alignment apart; the header
#: of a BAM carries it whatever the contigs are called.
_CHR1 = {248956422: "GRCh38", 249250621: "GRCh37"}

Progress = Callable[[int, int, Optional[str]], None]


class Stopped(Exception):
    """A stop was requested between two chromosomes."""


def catalogue() -> Dict[str, Any]:
    """One batch catalogue for core loci and supported thematic positions."""
    from . import core
    data = core._read_knowledge_raw("loci.json")
    thematic = core._read_knowledge_raw("thematic_variant_annotations.json")
    loci = dict(data.get("loci") or {})
    excluded = []
    for rsid, entry in (thematic.get("variants") or {}).items():
        if rsid in loci:
            continue
        if (entry.get("personal_call_supported") is not True
                or entry.get("ref") not in {"A", "C", "G", "T"}
                or entry.get("alt") not in {"A", "C", "G", "T"}):
            excluded.append({"rsid": rsid, "gene": entry.get("gene"),
                             "reason": "unsupported_variant_type"})
            continue
        loci[rsid] = entry
    stamps = [str((book.get("_meta") or {}).get("catalog_updated")
                  or (book.get("_meta") or {}).get("updated") or "")[:10]
              for book in (data, thematic)]
    # Description/source edits do not require reading the alignment again.
    identities = {rsid: {key: row.get(key) for key in
                        ("chrom", "pos", "pos_grch37", "ref", "alt", "assembly_alleles")}
                  for rsid, row in loci.items()}
    fingerprint = hashlib.sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest()
    return {"loci": loci, "positions": len(loci), "updated": max(stamps) or None,
            "fingerprint": fingerprint, "excluded": excluded}


def requirements() -> Dict[str, Optional[str]]:
    """What the genotyping needs, each found or None."""
    from . import gene_region, genome
    vcf = genome.vcf_path()
    bam = gene_region.bam_path()
    ref = gene_region.reference_path()
    return {"vcf": str(vcf) if vcf else None, "bam": str(bam) if bam else None,
            "reference": str(ref) if ref else None, "bcftools": shutil.which("bcftools")}


def refusal(req: Optional[Dict[str, Optional[str]]] = None) -> Optional[str]:
    """Why the genotyping cannot run here — a code — or None."""
    req = req if req is not None else requirements()
    if not req.get("vcf"):
        return "no_vcf"
    if not req.get("bam"):
        return "no_bam"
    bam = Path(req["bam"])
    if not any(p.exists() for p in (Path(str(bam) + ".bai"), bam.with_suffix(".bai"),
                                     Path(str(bam) + ".csi"))):
        return "no_index"
    if not req.get("reference"):
        return "no_reference"
    if not req.get("bcftools"):
        return "no_bcftools"
    return None


def out_path(vcf: Optional[str] = None) -> Optional[Path]:
    """Beside the personal VCF — the one folder the genome reader looks in."""
    if vcf is None:
        from . import genome
        found = genome.vcf_path()
        vcf = str(found) if found else None
    return Path(vcf).parent / OUT_NAME if vcf else None


def _read_record(out: Path) -> Optional[Dict[str, Any]]:
    try:
        rec = json.loads((out.parent / RECORD_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def state() -> Dict[str, Any]:
    """Whether the catalogue positions have been genotyped for the catalogue this build carries.

    `missing` — no file; `older_than_catalogue` — the file holds fewer positions
    than the catalogue, or was made before its date; `current`; `unrecorded` — a
    file with no record made after the catalogue's date, which cannot be told
    apart from a current one and is not asked to be rebuilt; `no_vcf`.
    """
    cat = catalogue()
    req = requirements()
    out = out_path(req.get("vcf"))
    res: Dict[str, Any] = {"catalogue_positions": cat["positions"],
                           "catalogue_updated": cat["updated"],
                           "excluded": cat.get("excluded", []),
                           "path": str(out) if out else None,
                           "refusal": refusal(req), "record": None}
    if out is None:
        res["status"] = "no_vcf"
        return res
    if not out.exists():
        res["status"] = "missing"
        return res
    rec = _read_record(out)
    if rec:
        res["record"] = rec
        held = int(rec.get("catalogue_positions") or 0)
        res["positions_held"] = held
        same = (rec.get("catalogue_fingerprint") == cat["fingerprint"]
                if cat.get("fingerprint") else
                held >= cat["positions"] and (rec.get("catalogue_updated") or None) == cat["updated"])
        res["status"] = "current" if same else "older_than_catalogue"
        return res
    made = date.fromtimestamp(out.stat().st_mtime).isoformat()
    res["made"] = made
    res["status"] = ("older_than_catalogue" if cat["updated"] and made < cat["updated"]
                     else "unrecorded")
    return res


def alignment_build(bam: str) -> Dict[str, Any]:
    """The build and contig naming of an alignment, read from its header."""
    from . import bamlite
    lengths = bamlite.reference_lengths(bam)
    prefix = "chr" if "chr1" in lengths else ""
    return {"assembly": _CHR1.get(lengths.get(prefix + "1") or 0), "prefix": prefix,
            "contigs": set(lengths)}


def bed_rows(loci: Dict[str, Any], build: Dict[str, Any]) -> Dict[str, List[Tuple[int, str]]]:
    """Catalogue positions per chromosome, in the alignment's build — never converted.

    A locus the catalogue carries in one build only is left out for the other,
    for the reason `genome.locus_position` gives: an offset between builds is not
    a constant, and arithmetic would point at a plausible wrong base.
    """
    from . import genome
    rows: Dict[str, Dict[int, str]] = {}
    for rsid, loc in (loci or {}).items():
        chrom = str(loc.get("chrom") or "")
        chrom = chrom[3:] if chrom.startswith("chr") else chrom
        if chrom not in _CANON:
            continue
        pos = genome.locus_position(loc, build.get("assembly"))
        if not pos or (build.get("prefix", "") + chrom) not in (build.get("contigs") or set()):
            continue
        rows.setdefault(chrom, {}).setdefault(int(pos), f"{rsid}|{loc.get('gene') or ''}")
    return {c: sorted(v.items()) for c, v in rows.items()}


def _run_pipeline(cmds: List[List[str]]) -> Dict[str, Any]:
    """Run commands piped into each other; the error text of all of them, kept short."""
    procs: List[subprocess.Popen] = []
    errs = []
    prev = None
    for i, argv in enumerate(cmds):
        err = tempfile.TemporaryFile()
        errs.append(err)
        p = subprocess.Popen(argv, stdin=prev.stdout if prev is not None else subprocess.DEVNULL,
                             stdout=subprocess.PIPE if i < len(cmds) - 1 else subprocess.DEVNULL,
                             stderr=err)
        if prev is not None and prev.stdout is not None:
            prev.stdout.close()
        procs.append(p)
        prev = p
    codes = [p.wait() for p in procs]
    tail = []
    for err in errs:
        err.seek(0)
        tail.append(err.read()[-400:].decode("utf-8", "replace"))
        err.close()
    rc = next((c for c in codes if c != 0), 0)
    return {"rc": rc, "stderr": "\n".join(t for t in tail if t.strip())}


def verify_position(loc: Dict[str, Any], assembly: str, bam: Path) -> Dict[str, Any]:
    """Call one diploid autosomal SNP from local reads, without writing genome files."""
    from . import fastalite, gene_region, genome
    from .variant_readings import digest

    inputs = {**requirements(), "bam": str(bam)}
    why = refusal(inputs)
    if why:
        return {"reason": why}
    pos = genome.locus_position(loc, assembly)
    loc = genome.locus_alleles(loc, assembly)
    chrom = str(loc.get("chrom") or "").removeprefix("chr")
    ref, alt = loc.get("ref"), loc.get("alt")
    if (not pos or chrom not in _CANON[:22] or ref not in {"A", "C", "G", "T"}
            or alt not in {"A", "C", "G", "T"} or ref == alt):
        return {"reason": "unsupported_locus"}
    vcf = str(inputs["vcf"])
    sample_index = genome.sample_index(vcf)
    samples = genome.samples_of(vcf)
    if sample_index is None or sample_index >= len(samples):
        return {"reason": "sample_mismatch"}
    reference = str(inputs["reference"])
    try:
        build = alignment_build(str(bam))
        fa = fastalite.Fasta(reference)
        contig = build["prefix"] + chrom
        fasta_build = _CHR1.get((fa.index.get("chr1") or fa.index.get("1") or (0,))[0])
        if build["assembly"] != assembly or fasta_build != assembly:
            return {"reason": "build_mismatch"}
        if contig not in build["contigs"] or contig not in fa.index or fa.fetch(contig, pos, pos) != ref:
            return {"reason": "reference_mismatch"}
        stat = bam.stat()
        tool = str(inputs["bcftools"])
        pileup = subprocess.run([tool, "mpileup", "-r", f"{contig}:{pos}-{pos}", "-f", reference,
                                "-a", "FORMAT/DP", "-Ou", str(bam)], capture_output=True, check=True, timeout=20)
        called = subprocess.run([tool, "call", "-m", "--keep-unseen-allele", "-a", "FORMAT/GQ", "-Ov"],
                                input=pileup.stdout, capture_output=True, check=True, timeout=20)
        lines = called.stdout.decode("utf-8").splitlines()
        header = next((line.split("\t") for line in lines if line.startswith("#CHROM")), [])
        if header[9:] != [samples[sample_index]]:
            return {"reason": "sample_mismatch"}
        rows = [line.split("\t") for line in lines if line and not line.startswith("#")]
        if len(rows) != 1 or rows[0][0] != contig or int(rows[0][1]) != pos:
            return {"reason": "no_call"}
        row = gene_region._parse_row(rows[0])
        raw = row.get("genotype") or ""
        alleles = [ref, *row["alt"].split(",")]
        gt = raw.replace("|", "/").split("/")
        if (row["ref"] != ref or len(gt) != 2
                or any(not a.isdigit() or int(a) >= len(alleles) or alleles[int(a)] not in (ref, alt)
                       for a in gt)):
            return {"reason": "no_call"}
        quality = row.get("genotype_quality")
        likelihood_gap = None
        if gt == ["0", "0"] and quality is None:
            # bcftools omits GQ on reference calls. Keep the unobserved allele
            # and require likelihood separation from every alternative GT.
            fields = dict(zip(rows[0][8].split(":"), rows[0][9].split(":")))
            pl = fields.get("PL", "").split(",")
            if len(pl) >= 3 and all(value.isdigit() for value in pl):
                likelihood_gap = min(map(int, pl[1:])) - int(pl[0])
        if (row["filter"] not in ("PASS", ".") or (row.get("depth") or 0) < 10
                or ((quality if quality is not None else likelihood_gap) or 0) < 20):
            return {"reason": "low_quality"}
        after = bam.stat()
        if (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
                stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns):
            return {"reason": "read_failed"}
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return {"reason": "read_failed"}
    return {"genotype": "".join(alleles[int(a)] for a in gt), "raw_genotype": raw,
            "phased": "|" in raw, "confidence": "confirmed_ref" if gt == ["0", "0"] else "called",
            "source": "bam", "assembly": assembly, "read_pos": pos,
            "depth": row["depth"], "genotype_quality": quality,
            "likelihood_gap_phred": likelihood_gap,
            "variant_identity": {"assembly": assembly, "chrom": contig, "pos": pos,
                                 "ref": ref, "alt": alt},
            "source_identity": {"file": bam.name, "path_key": digest(str(bam.resolve())),
                                "revision_method": "filesystem_stat", "size": stat.st_size,
                                "mtime_ns": stat.st_mtime_ns, "ctime_ns": stat.st_ctime_ns}}


def genotype(progress: Optional[Progress] = None, out: Optional[str] = None,
             run: Optional[Callable[[List[List[str]]], Dict[str, Any]]] = None,
             stop: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
    """Genotype every catalogue position from the alignment into `loci_sites.vcf.gz`."""
    from . import __version__
    req = requirements()
    why = refusal(req)
    if why:
        return {"ok": False, "status": "refused", "reason": why}
    bam, ref = str(req["bam"]), str(req["reference"])
    try:
        build = alignment_build(bam)
    except (OSError, ValueError) as exc:
        return {"ok": False, "status": "refused", "reason": "alignment_unreadable",
                "error": type(exc).__name__}
    if not build["assembly"]:
        return {"ok": False, "status": "refused", "reason": "alignment_build_unknown"}
    cat = catalogue()
    per_chrom = bed_rows(cat["loci"], build)
    chroms = [c for c in _CANON if per_chrom.get(c)]
    if not chroms:
        return {"ok": False, "status": "refused", "reason": "no_positions_in_build",
                "assembly": build["assembly"]}
    target = Path(out) if out else out_path(req["vcf"])
    assert target is not None
    target.parent.mkdir(parents=True, exist_ok=True)
    run = run or _run_pipeline
    started = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix=".loci_sites-", dir=str(target.parent)))
    total = len(chroms)
    written = sum(len(per_chrom[c]) for c in chroms)
    try:
        parts = []
        for i, chrom in enumerate(chroms):
            if stop is not None and stop():
                raise Stopped()
            if progress is not None:
                progress(i, total, build["prefix"] + chrom)
            bed = work / f"{chrom}.bed"
            bed.write_text("".join(f"{build['prefix']}{chrom}\t{pos - 1}\t{pos}\t{name}\n"
                                   for pos, name in per_chrom[chrom]), encoding="utf-8")
            part = work / f"{chrom}.vcf.gz"
            # Without `-v`: a reference call is the whole point of the file.
            r = run([["bcftools", "mpileup", "-R", str(bed), "-f", ref, "-a", "FORMAT/DP",
                      "-Ou", bam],
                     ["bcftools", "call", "-m", "-Oz", "-o", str(part)]])
            if r.get("rc"):
                return {"ok": False, "status": "failed", "step": build["prefix"] + chrom,
                        "rc": r.get("rc"), "error": str(r.get("stderr") or "")[-600:]}
            parts.append(str(part))
        if stop is not None and stop():
            raise Stopped()
        if progress is not None:
            progress(total, total, None)
        merged = work / OUT_NAME
        for argv in (["bcftools", "concat", "-Oz", "-o", str(merged)] + parts,
                     ["bcftools", "index", "-t", "-f", str(merged)]):
            r = run([argv])
            if r.get("rc"):
                return {"ok": False, "status": "failed", "step": argv[1], "rc": r.get("rc"),
                        "error": str(r.get("stderr") or "")[-600:]}
        # The file first, then its index: a reader that meets the new file with
        # the old index fails loudly on a mismatch, never answers from it.
        os.replace(merged, target)
        os.replace(str(merged) + ".tbi", str(target) + ".tbi")
        record = {"engine": __version__, "catalogue_positions": cat["positions"],
                  "catalogue_updated": cat["updated"], "catalogue_fingerprint": cat.get("fingerprint"),
                  "excluded": cat.get("excluded", []), "positions_written": written,
                  "assembly": build["assembly"], "alignment": Path(bam).name,
                  "written": date.today().isoformat()}
        tmp = target.parent / f".{RECORD_NAME}.tmp-{os.getpid()}"
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, target.parent / RECORD_NAME)
    except Stopped:
        return {"ok": False, "status": "stopped"}
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"ok": True, "status": "written", "path": str(target), "positions": written,
            "chromosomes": total, "assembly": build["assembly"],
            "seconds": round(time.monotonic() - started, 1)}
