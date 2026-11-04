"""Local mitochondrial short-variant screen and maternal lineage from one indexed BAM."""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import time
from functools import lru_cache
from typing import Any
from uuid import uuid4

from . import container, core, gene_region
from .i18n import t

RESULT = "mitochondria.json"
SCHEMA = 1
METHOD = 2
JOB = ".mitochondria-job.json"
RCRS = "NC_012920.1"
RCRS_MD5 = "c68f52674c9fb33aef52dcf399755519"
LENGTH = 16569
SPACER = 3107
TREE = "phylotree-rcrs@17.3"
MIN_DEPTH = 100
MIN_AF = .01
MAJOR_AF = .95
BASE_QUALITY = 30
MAP_QUALITY = 30
LINKS = {
    "method": "https://pubmed.ncbi.nlm.nih.gov/32906214/",
    "mutserve": "https://github.com/seppinho/mutserve/releases/tag/v2.0.3",
    "haplogrep": "https://github.com/genepi/haplogrep3/releases/tag/v3.3.2",
    "tree": "https://github.com/genepi/phylotree-rcrs-17/releases/tag/17.3",
    "clinvar": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/",
}
_BASES = "ACGT"
_CONTIGS = {"M", "MT", "CHRM", "CHRMT"}
_BAM_ASSEMBLY_LENGTHS = {249250621, 248956422}
_TIMEOUT = 120


class Refused(ValueError):
    """A named prerequisite or analysis failure, without leaking a local path."""


def _index(path: Path) -> Path | None:
    return next((p for p in (Path(str(path) + ".bai"), path.with_suffix(".bai"),
                             Path(str(path) + ".csi"), path.with_suffix(".csi")) if p.is_file()), None)


def _witness(path: Path) -> str:
    info = path.stat()
    value = (str(path.resolve()), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def _alignment() -> tuple[Path | None, Path | None]:
    if container.in_use():
        chosen = core.chosen_genome_bam()
        path = Path(chosen).expanduser() if chosen else None
    else:
        path = gene_region.bam_path()
    if not path or path.suffix.lower() != ".bam" or not path.is_file():
        return None, None
    return path, _index(path)


def _tools() -> tuple[Path, dict[str, str], list[str]]:
    configured = os.environ.get("SCHOLION_MTDNA_TOOLS")
    folder = (Path(configured).expanduser() if configured else core.repo_dir() / "mtDNA-tools").resolve()
    commands = {name: shutil.which(name) or "" for name in ("java", "samtools")}
    missing = [name for name, path in commands.items() if not path]
    try:
        import pysam  # noqa: F401 -- the genome extra is checked before reading any BAM
    except ImportError:
        missing.append("pysam")
    missing.extend(name for name in ("mutserve.jar", "haplogrep3.jar", "tree/tree.yaml", "tree/rcrs.fasta")
                   if not (folder / name).is_file())
    return folder, commands, missing


def _status(path: Path | None, index: Path | None, missing: list[str]) -> str:
    return "needs_bam" if not path else "needs_index" if not index else "needs_tools" if missing else "ready"


@lru_cache(maxsize=128)
def _digest(filename: str, witness: str) -> str:
    """Hash tools only when their file identity changes, not on every progress poll."""
    digest = hashlib.sha256()
    with Path(filename).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _method(folder: Path) -> dict[str, Any]:
    files = [folder / "mutserve.jar", folder / "haplogrep3.jar"]
    files += sorted(p for p in (folder / "tree").rglob("*") if p.is_file())
    return {"revision": METHOD, "tree": TREE, "reference": RCRS_MD5,
            "thresholds": [MIN_DEPTH, MIN_AF, MAJOR_AF, BASE_QUALITY, MAP_QUALITY],
            "files": {str(p.relative_to(folder)): _digest(str(p), _witness(p))
                      for p in files if p.is_file()}}


def _annotation() -> str | None:
    from .coverage import clinvar_path
    path = clinvar_path("GRCh38")
    if not path or not Path(path).is_file():
        return None
    files = [Path(path), Path(str(path) + ".tbi"), Path(str(path) + ".csi")]
    return ":".join(_witness(file) for file in files if file.is_file())


def job_status() -> dict[str, Any]:
    from .recompute import _alive
    try:
        job = json.loads((core.profile_dir() / JOB).read_text(encoding="utf-8"))
        if not isinstance(job, dict):
            return {}
        if job.get("status") == "running" and not _alive(job.get("pid")):
            job["status"] = "interrupted"
        return job
    except (OSError, ValueError, TypeError):
        return {}


def _progress(stage: str) -> None:
    with core.profile_write_lock():
        job = job_status()
        if job.get("status") == "running" and job.get("cancel_requested"):
            raise Refused("cancelled")
        if job.get("status") == "running" and job.get("stage") != stage:
            core.write_json(core.profile_dir() / JOB, {**job, "stage": stage})


def cancel() -> dict[str, Any]:
    with core.profile_write_lock():
        job = job_status()
        if job.get("status") == "running":
            core.write_json(core.profile_dir() / JOB, {**job, "cancel_requested": True})
    return report()


@core.in_reading
def report() -> dict[str, Any]:
    folder, _, missing = _tools()
    bam, index = _alignment()
    status = _status(bam, index, missing)
    path = core.profile_dir() / RESULT
    try:
        saved = core.read_profile_json(path)
        result = _localize(saved) if saved.get("schema") == SCHEMA else None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        saved, result = {}, None
        status = "unreadable"
    reasons = []
    try:
        if result:
            if not bam or not index or saved.get("source") != [_witness(bam), _witness(index)]:
                reasons.append("source")
            if saved.get("method") != _method(folder):
                reasons.append("method")
            if "annotation_source" not in saved or saved["annotation_source"] != _annotation():
                reasons.append("annotation")
        current = bool(result and not reasons)
    except OSError:
        current = False
        reasons.append("unavailable")
    job = job_status()
    if job.get("status") == "running":
        status = "running"
    if job.get("stage"):
        job["label"] = t("mt.stage." + job["stage"])
    return {
        "status": status,
        "can_analyze": _status(bam, index, missing) == "ready",
        "message": t("mt.status." + status),
        "missing": missing,
        "tools_folder": folder.name if not os.environ.get("SCHOLION_MTDNA_TOOLS") else None,
        "links": LINKS,
        "limits": [t("mt.limit." + item) for item in ("lineage", "fraction", "clinical", "scope")],
        "current": current,
        "freshness_reasons": reasons,
        "recalculation_required": bool(result and any(r != "annotation" for r in reasons)),
        "job": job,
        "result": result,
    }


def _localize(saved: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in saved.items() if key not in ("source", "method", "annotation_source")}
    variants = []
    for item in saved["variants"]:
        annotation = item.get("clinvar")
        clinical = None
        if annotation:
            key = "clinvar.sig." + annotation["classification"].lower().replace(" ", "_")
            label = t(key)
            clinical = {**annotation, "label": annotation["classification"] if label.startswith("⟦") else label,
                        "review_label": t("mt.clinvar.stars", stars=annotation.get("stars", 0))}
        variants.append({**item, "label": t("mt.variant." + item["status"]), "clinvar": clinical,
                         "discuss": _review_candidate(item)})
    return {**result, "variants": variants}


def _review_candidate(item: dict[str, Any]) -> bool:
    annotation = item.get("clinvar") or {}
    classification = annotation.get("classification", "").lower().replace(" ", "_")
    return (item["status"] == "supported" and annotation.get("stars", 0) >= 2
            and classification in {"pathogenic", "likely_pathogenic", "pathogenic/likely_pathogenic"})


def _run(args: list[str], cwd: Path) -> None:
    try:
        with subprocess.Popen(args, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as process:
            started = time.monotonic()
            try:
                while True:
                    _progress(job_status().get("stage", "reference"))
                    try:
                        process.communicate(timeout=.2)
                        break
                    except subprocess.TimeoutExpired:
                        if time.monotonic() - started >= _TIMEOUT:
                            raise Refused("tool_failed")
                if process.returncode:
                    raise Refused("tool_failed")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused("tool_failed") from exc


def _reference_bases(folder: Path) -> str:
    raw = (folder / "tree/rcrs.fasta").read_text(encoding="ascii").splitlines()
    reference = "".join(line.strip() for line in raw if not line.startswith(">")).upper()
    if len(reference) != LENGTH or hashlib.md5(reference.encode("ascii")).hexdigest() != RCRS_MD5:
        raise Refused("reference_mismatch")
    return reference


def _reference(folder: Path, bam: Path, work: Path) -> tuple[str, str, str]:
    import pysam

    reference = _reference_bases(folder)
    with pysam.AlignmentFile(str(bam), "rb", require_index=True) as alignment:
        header = alignment.header.to_dict()
        sequences = header.get("SQ", [])
        matching = [item for item in sequences if item["SN"].upper() in _CONTIGS]
        if len(matching) != 1 or matching[0]["LN"] != LENGTH:
            raise Refused("reference_mismatch")
        match = matching[0]
        checksum = match.get("M5")
        known_frame = any(row["SN"].removeprefix("chr") == "1" and row["LN"] in _BAM_ASSEMBLY_LENGTHS
                          for row in sequences)
        if (checksum and checksum.lower() != RCRS_MD5) or (not checksum and not known_frame):
            raise Refused("reference_mismatch")
        if len({group["SM"] for group in header.get("RG", []) if group.get("SM")}) > 1:
            raise Refused("multiple_samples")
        contig = match["SN"]
    lines = [reference[i:i+60] for i in range(0, LENGTH, 60)]
    (work / "rCRS.fa").write_text(">" + contig + "\n" + "\n".join(lines) + "\n", encoding="ascii")
    return contig, reference, "md5" if checksum else "length_and_assembly"


def _confirmed(path: Path, reference: str) -> set[tuple[int, str]]:
    """Only validated single-nucleotide rows from the specialist caller."""
    rows = set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not {"Pos", "Ref", "Variant", "Filter"}.issubset(reader.fieldnames or []):
            raise Refused("tool_failed")
        for row in reader:
            pos = int(row["Pos"])
            if (1 <= pos <= LENGTH and pos != SPACER and row["Ref"] == reference[pos-1]
                    and row["Variant"] in tuple(_BASES) and row["Filter"] == "PASS"):
                rows.add((pos, row["Variant"]))
    return rows


def _count_columns(bam: Path, contig: str):
    import pysam

    with pysam.AlignmentFile(str(bam), "rb", require_index=True) as alignment:
        for col in alignment.pileup(contig, 0, LENGTH, truncate=True, stepper="samtools",
                                    min_mapping_quality=MAP_QUALITY, min_base_quality=BASE_QUALITY,
                                    flag_filter=0xf04, max_depth=100000, ignore_overlaps=True,
                                    ignore_orphans=True, compute_baq=False):
            # Upper/lower case is forward/reverse. Insertion and deletion tags
            # attach to the preceding base and do not replace that base call.
            yield col.reference_pos + 1, Counter(col.get_query_sequences(add_indels=True))


def _row(pos, ref, alt, depth, forward, reverse, status):
    return {"position": pos, "ref": ref, "alt": alt, "depth": depth,
            "forward_alt": forward, "reverse_alt": reverse, "fraction": (forward + reverse) / depth,
            "status": status, "clinvar": None}


def _summarize(bam: Path, contig: str, reference: str, confirmed: set[tuple[int, str]]):
    import re

    variants, depths, callable_sites, lineage = [], [], [], []
    seen = {}
    for pos, pile in _count_columns(bam, contig):
        if pos % 256 == 0:
            _progress("reads")
        if pos == SPACER:
            continue
        ref = reference[pos-1]
        counts: Counter[str] = Counter()
        indels: Counter[tuple[str, str, bool]] = Counter()
        for value, count in pile.items():
            if not value or value[0].upper() not in _BASES:
                continue
            base = value[0]
            counts[base] += count
            match = re.fullmatch(r"([+-])(\d+)([ACGTNacgtn]+)", value[1:])
            if match and base.upper() == ref and int(match[2]) == len(match[3]):
                delta = match[3].upper()
                if match[1] == "-" and set(delta) == {"N"}:
                    delta = reference[pos:pos+len(delta)]
                if delta and "N" not in delta and (match[1] == "+" or reference[pos:pos+len(delta)] == delta):
                    key = (ref, ref + delta) if match[1] == "+" else (ref + delta, ref)
                    indels[(*key, base.isupper())] += count
        depth = sum(counts.values())
        seen[pos] = depth
        if depth < MIN_DEPTH:
            continue
        major = max(_BASES, key=lambda b: counts[b] + counts[b.lower()])
        if ((counts[major] + counts[major.lower()]) / depth >= MAJOR_AF
                and min(counts[major], counts[major.lower()]) >= 3):
            callable_sites.append(pos)
            if major != ref:
                lineage.append(f"{pos}{major}")
        for alt in _BASES.replace(ref, ""):
            fw, rv = counts[alt], counts[alt.lower()]
            fraction = (fw + rv) / depth
            if fraction >= MIN_AF or ((pos, alt) in confirmed and fw + rv >= 3):
                status = ("supported" if fraction >= MIN_AF and min(fw, rv) >= 3
                          and (pos, alt) in confirmed else "uncertain")
                variants.append(_row(pos, ref, alt, depth, fw, rv, status))
        for a, b in {(a, b) for a, b, _ in indels}:
            fw, rv = indels[a, b, True], indels[a, b, False]
            if (fw + rv) / depth >= MIN_AF:
                variants.append(_row(pos, a, b, depth, fw, rv, "technical_indel"))
    longest_gap = gap = 0
    for pos in range(1, LENGTH + 1):
        if pos == SPACER:
            continue
        depth = seen.get(pos, 0)
        depths.append(depth)
        gap = gap + 1 if depth < MIN_DEPTH else 0
        longest_gap = max(longest_gap, gap)
    if not any(depths):
        raise Refused("no_reads")
    quality = {"positions": len(depths), "at_min_depth": sum(d >= MIN_DEPTH for d in depths),
               "lineage_callable": len(callable_sites), "median_depth": statistics.median(depths),
               "minimum_depth": min(depths), "longest_gap": longest_gap, "minimum_usable_depth": MIN_DEPTH,
               "minimum_fraction": MIN_AF, "min_mapq": MAP_QUALITY, "min_baseq": BASE_QUALITY}
    return variants, quality, callable_sites, lineage


def _ranges(positions: list[int]) -> str:
    spans: list[list[int]] = []
    for pos in positions:
        if spans and pos == spans[-1][1] + 1:
            spans[-1][1] = pos
        else:
            spans.append([pos, pos])
    return ";".join(f"{start}-{end}" for start, end in spans)


def _haplogroup(java: str, folder: Path, work: Path, callable_sites: list[int],
                lineage: list[str]) -> dict[str, Any]:
    if len(callable_sites) < .98 * (LENGTH - 1):
        return {"status": "insufficient_coverage", "name": None, "tree": TREE}
    config = "repositories: []\nphylotrees:\n  - " + json.dumps(str(folder / "tree/tree.yaml")) + "\n"
    (work / "haplogrep3.yaml").write_text(config, encoding="utf-8")
    (work / "sample.hsd").write_text("SampleID\tRange\tHaploGroup\tPolymorphisms\n"
                                   + "\t".join(["sample", _ranges(callable_sites), "", *lineage, ""]) + "\n",
                                   encoding="utf-8")
    _run([java, "-Xmx1g", "-jar", str(folder / "haplogrep3.jar"), "classify", "--tree", TREE,
          "--metric", "HAMMING", "--hits", "2", "--extend-report", "--in", "sample.hsd",
          "--out", "lineage.tsv"], work)
    with (work / "lineage.tsv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if not rows or not rows[0].get("Haplogroup"):
        raise Refused("tool_failed")
    best = rows[0]
    distance = float(best["Quality"])
    if not math.isfinite(distance):
        raise Refused("tool_failed")
    tied = len(rows) > 1 and float(rows[1]["Quality"]) == distance
    return {"status": "ambiguous" if tied else "classified", "name": None if tied else best["Haplogroup"],
            "tree": TREE, "distance": distance, "missing_markers": best.get("Not_Found_Polys", "").split(),
            "extra_markers": best.get("Remaining_Polys", "").split()}


def _clinvar(variants: list[dict[str, Any]], reference: str) -> dict[str, Any]:
    import pysam
    from .coverage import clinvar_path
    from .clinvar_reference import header_metadata
    from .genome import _primary_disease, _review_stars

    path = clinvar_path("GRCh38")
    if not path:
        return {"status": "unavailable", "date": None}
    try:
        with pysam.VariantFile(str(path)) as db:
            metadata = header_metadata(str(db.header).splitlines())
            contigs = [key for key in db.header.contigs
                       if key.upper() in _CONTIGS and db.header.contigs[key].length in (None, LENGTH)]
            if metadata["assembly"] != "GRCh38" or len(contigs) != 1:
                return {"status": "unverified", "date": None}
            indexed = {}
            for number, row in enumerate(db.fetch(contigs[0])):
                if number % 256 == 0:
                    _progress("annotation")
                if not row.alts or len(row.alts) != 1 or row.ref != reference[row.start:row.stop]:
                    continue
                sig = row.info.get("CLNSIG") or ()
                rev = row.info.get("CLNREVSTAT") or ()
                if not sig:
                    continue
                gene = row.info.get("GENEINFO") or ""
                disease = row.info.get("CLNDN") or ()
                review = ",".join(rev)
                key = (row.pos, row.ref, row.alts[0])
                annotation = {"classification": ", ".join(sig), "review": review,
                              "stars": _review_stars(review), "condition": _primary_disease("|".join(disease)),
                              "gene": str(gene).split(":", 1)[0], "id": row.id if str(row.id).isdigit() else None}
                indexed[key] = annotation if key not in indexed else None
            for row in variants:
                if row["status"] != "technical_indel":
                    row["clinvar"] = indexed.get((row["position"], row["ref"], row["alt"]))
            return {"status": "matched_locally", "date": metadata["file_date"]}
    except Refused:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unverified", "date": None}


def _save(result: dict[str, Any], folder: Path) -> None:
    with core.profile_write_lock():
        _progress("saving")
        bam, index = _alignment()
        if not bam or not index or result["source"] != [_witness(bam), _witness(index)]:
            raise Refused("source_changed")
        if result["method"] != _method(folder) or result["annotation_source"] != _annotation():
            raise Refused("source_changed")
        core.write_json(core.profile_dir() / RESULT, result)
        job = job_status()
        core.write_json(core.profile_dir() / JOB, {**job, "status": "completed"})


def _refresh_annotations() -> dict[str, Any]:
    folder, _, _ = _tools()
    try:
        saved = core.read_profile_json(core.profile_dir() / RESULT)
        annotation = _annotation()
        reference = _reference_bases(folder)
        variants = [{**row, "clinvar": None} for row in saved["variants"]]
        clinvar = _clinvar(variants, reference)
        if clinvar["status"] == "unverified":
            raise Refused("annotation_failed")
        variants.sort(key=_variant_order)
        _save({**saved, "variants": variants, "clinvar": clinvar,
               "annotation_source": annotation, "annotated_at": datetime.now(timezone.utc).isoformat()}, folder)
    except Refused as exc:
        return {**report(), "status": str(exc), "message": t("mt.status." + str(exc))}
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return {**report(), "status": "unreadable", "message": t("mt.status.unreadable")}
    return {**report(), "status": "analyzed", "message": t("mt.status.annotations_updated")}


def _variant_order(variant: dict[str, Any]) -> tuple[bool, bool, float, int, str]:
    return (not _review_candidate(variant), variant["status"] != "supported",
            -variant["fraction"], variant["position"], variant["alt"])


def _analyze() -> dict[str, Any]:
    """Publish only a complete result whose alignment still belongs to this reading."""
    folder, commands, missing = _tools()
    bam, index = _alignment()
    status = _status(bam, index, missing)
    if status != "ready" or bam is None or index is None:
        return report()
    java, samtools = commands["java"], commands["samtools"]
    try:
        witness = [_witness(bam), _witness(index)]
        method, annotation = _method(folder), _annotation()
        with tempfile.TemporaryDirectory(prefix="scholion-mtdna-") as name:
            work = Path(name)
            _progress("reference")
            contig, reference, verification = _reference(folder, bam, work)
            _progress("extract")
            _run([samtools, "view", "-b", "-o", "chrM.bam", str(bam.resolve()), contig], work)
            _run([samtools, "index", "chrM.bam"], work)
            _progress("variants")
            _run([java, "-Xmx1g", "-jar", str(folder / "mutserve.jar"), "call", "--reference", "rCRS.fa",
                  "--contig-name", contig, "--mapQ", str(MAP_QUALITY), "--baseQ", str(BASE_QUALITY),
                  "--level", str(MIN_AF), "--threads", "1", "--no-ansi", "--output", "variants.txt",
                  "chrM.bam"], work)
            confirmed = _confirmed(work / "variants.txt", reference)
            _progress("reads")
            variants, quality, callable_sites, lineage = _summarize(work / "chrM.bam", contig, reference, confirmed)
            _progress("lineage")
            haplogroup = _haplogroup(java, folder, work, callable_sites, lineage)
            _progress("annotation")
            clinvar = _clinvar(variants, reference)
        variants.sort(key=_variant_order)
        result = {"schema": SCHEMA, "source": witness, "created_at": datetime.now(timezone.utc).isoformat(),
                  "method": method, "annotation_source": annotation,
                  "reference": RCRS, "reference_verification": verification, "quality": quality,
                  "haplogroup": haplogroup, "variants": variants, "clinvar": clinvar}
        _save(result, folder)
    except Refused as exc:
        return {**report(), "status": str(exc), "message": t("mt.status." + str(exc))}
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return {**report(), "status": "unreadable", "message": t("mt.status.unreadable")}
    return {**report(), "status": "analyzed", "message": t("mt.status.analyzed")}


@core.in_reading
def analyze(confirm: bool = False, cancel_requested: bool = False, *, annotations_only: bool = False) -> dict[str, Any]:
    """One profile job across CLI, web and agent calls; cancellation retains old bytes."""
    if cancel_requested is True:
        return cancel()
    if confirm is not True:
        return report()
    with core.profile_write_lock():
        if job_status().get("status") == "running":
            return {**report(), "status": "busy", "message": t("mt.status.busy")}
        preview = report()
        if not preview["can_analyze"]:
            return preview
        refresh = preview["freshness_reasons"] == ["annotation"]
        if annotations_only and not refresh:
            return {**preview, "status": "source_changed", "message": t("mt.status.source_changed")}
        job_id = uuid4().hex
        core.write_json(core.profile_dir() / JOB, {"status": "running", "pid": os.getpid(), "id": job_id,
                        "stage": "annotation" if refresh else "reference", "cancel_requested": False})
    state = "interrupted"
    try:
        result = _refresh_annotations() if refresh else _analyze()
        state = "completed" if result["status"] == "analyzed" else result["status"]
    except KeyboardInterrupt:
        state = "cancelled"
        result = {**report(), "status": state, "message": t("mt.status.cancelled")}
    finally:
        with core.profile_write_lock():
            job = job_status()
            if job.get("id") == job_id:
                job = {**job, "status": state}
                core.write_json(core.profile_dir() / JOB, job)
    return {**result, "job": job}


def markdown(data: dict[str, Any]) -> str:
    lines = [f"# {t('mt.title')}", data["message"]]
    if (data.get("job") or {}).get("status") == "running":
        lines.append(t("mt.stage." + data["job"].get("stage", "reference")))
    if data["missing"]:
        lines.append(t("mt.missing", items=", ".join(data["missing"])))
    result = data["result"]
    if result:
        if not data["current"]:
            lines.append(t("mt.annotation_stale" if data.get("freshness_reasons") == ["annotation"] else "mt.stale"))
        group, quality = result["haplogroup"], result["quality"]
        lines.append(t("mt.lineage_value", group=group["name"] or t("mt.lineage_unresolved")))
        lines.append(t("mt.quality_value", covered=quality["at_min_depth"], total=quality["positions"],
                       minimum=quality["minimum_usable_depth"], median=quality["median_depth"]))
        lines.append(t("mt.haplogroup." + group["status"]) + f" · {group['tree']}")
        lines.append(t("mt.quality_detail", gap=quality["longest_gap"], baseq=quality["min_baseq"],
                       mapq=quality["min_mapq"]))
        lines.append(t("mt.reference." + result["reference_verification"]))
        lines.append(t("mt.clinvar." + result["clinvar"]["status"]))
        if result["clinvar"]["date"]:
            lines.append(t("mt.clinvar.date", date=result["clinvar"]["date"]))
        if not result["variants"]:
            lines.append(t("mt.variant_none"))
        for item in result["variants"]:
            clinical = item.get("clinvar") or {}
            lines.append(f"- m.{item['position']}{item['ref']}>{item['alt']} · {item['fraction']:.2%} · "
                         f"{item['forward_alt']} + {item['reverse_alt']} / {item['depth']} · "
                         + item["label"] + (f" · ClinVar: {clinical['label']} · {clinical['review_label']}"
                                            if clinical else "")
                         + (" · " + t("mt.review_candidate") if item["discuss"] else ""))
    lines.extend(data["limits"])
    return "\n\n".join(lines)
