"""Installed-package PGS recalculation: local inputs, pinned models, atomic report.

Reading results never starts this operation. Public weights are fetched only
on confirmation; genotypes stay local. Missing calls can be filled from a
matching BAM, one chromosome at a time, without preparing the whole genome.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import tempfile
import urllib.request

from . import core, genome, population, prs, sites
from .i18n import t as _t
from .pgs_scoring import ScoringVCF, _open, dosage


class Stopped(Exception):
    """Cancellation before publication of a complete profile report."""


def _check(stop):
    from . import container
    container.gate()
    if stop is not None and stop():
        raise Stopped()


def _input():
    """Only explicitly connected paths or paths belonging to the selected profile."""
    named = os.environ.get("SCHOLION_PRS_VCF")
    if named:
        return Path(named).expanduser()
    connected = genome.vcf_path()
    old = core.prs_results().get("_meta") or {}
    candidates = []
    if connected:
        previous = old.get("connected_genome")
        changed = previous and (previous.get("path") != str(connected.resolve()) or
                               previous.get("stat") != _stamp(connected))
        if changed:
            return connected
        candidates = [str(connected.parent / "scoring_sites.recomputed.vcf.gz"),
                      str(connected.parent / "scoring_sites.vcf.gz")]
    candidates += [old.get("last_recalculation_input_vcf"), old.get("input_vcf")]
    if connected:
        candidates.append(str(connected))
    for name in candidates:
        if name and Path(name).expanduser().is_file():
            return Path(name).expanduser()
    return None


def _traits(only=None):
    traits, _ = prs._sex_filtered(prs._load_traits())
    if only:
        traits = [t for t in traits if t.get("term") in only]
    return traits


def preflight(only=None):
    """Cheap readiness, not a full score or an implicit population assignment."""
    path = _input()
    panel = prs.resolve_superpopulation()
    traits = _traits(only)
    pins = prs._pinned_models()
    selected = [t for t in traits if (pins.get(t.get("term")) or {}).get("pgs_id")]
    result = {"status": "ready", "reason": None, "vcf": str(path) if path else None,
              "traits": len(selected), "unavailable_models": [t["term"] for t in traits if t not in selected],
              "population": panel, "assembly": None}
    def refuse(reason):
        result.update(status="needs_input", reason=reason, message=_t("prs.recompute." + reason))
        return result
    if path is None or not path.is_file():
        return refuse("no_input")
    try:
        genome.assembly_evidence.cache_clear()
        build = genome.assembly_evidence(str(path)).get("assembly")
        result["assembly"] = build
        if build not in ("GRCh37", "GRCh38"):
            return refuse("build_unknown")
        samples = population.samples(path)
        if len(samples) != 1:
            return refuse("sample_mismatch")
        connected = genome.vcf_path()
        check = core.ancestry_check()
        expected = check.get("samples") or (population.samples(connected) if connected else [])
        if expected and samples != expected:
            return refuse("sample_mismatch")
    except (OSError, ValueError, EOFError):
        return refuse("invalid_vcf")
    if panel["source"] == "default":
        return refuse("population_unknown")
    if not selected:
        return refuse("no_models")
    if not shutil.which("uvx"):
        return refuse("no_uvx")
    result["message"] = _t("prs.recompute.ready")
    from . import gene_region
    bam, reference = gene_region.bam_path(), gene_region.reference_path()
    if bam:
        req = {"vcf": str(path), "bam": str(bam), "reference": str(reference) if reference else None,
               "bcftools": shutil.which("bcftools")}
        reason = sites.refusal(req)
        result["bam_preparation"] = {"available": reason is None, "reason": reason}
        if reason:
            result["message"] += " " + _t("recompute.why." + reason)
    return result


def recalculation_status(data):
    """A changed input/population, not an application version, invalidates reuse."""
    from .pgs_validation import recalculation_status as scoring_status
    rows = data.get("traits", [])
    pins = prs._pinned_models()
    applicable = [row for row in rows if (pins.get(row.get("term")) or {}).get("pgs_id")]
    result = scoring_status(applicable)
    if not rows and genome.vcf_path():
        selected = [t for t in _traits() if (pins.get(t.get("term")) or {}).get("pgs_id")]
        if selected:
            return {"required": True, "traits": len(selected), "reason": "not_calculated"}
    if result["required"]:
        return result
    meta = data.get("_meta") or {}
    connected = genome.vcf_path()
    previous = meta.get("connected_genome")
    if connected and previous and (str(connected.resolve()) != previous.get("path") or
                                   _stamp(connected) != previous.get("stat")):
        return {"required": True, "traits": len(rows), "reason": "input_changed"}
    panel = prs.resolve_superpopulation()
    if (meta.get("superpopulation") and panel["source"] != "default"
            and meta["superpopulation"] != panel["value"]):
        return {"required": True, "traits": len(rows), "reason": "population_changed"}
    for row in applicable:
        if row.get("pgs_id") != pins[row["term"]]["pgs_id"]:
            return {"required": True, "traits": len(applicable), "reason": "model_changed"}
        witness = row.get("scoring_validation") or {}
        build = witness.get("genome_build")
        if build in ("GRCh37", "GRCh38"):
            model = prs._cache_root() / "scores" / f"{row['pgs_id']}_hmPOS_{build}.txt.gz"
            if witness.get("model_stat") and model.is_file() and _stamp(model) != witness["model_stat"]:
                return {"required": True, "traits": len(applicable), "reason": "model_changed"}
        path = witness.get("input_vcf")
        if path and witness.get("input_stat") and Path(path).is_file() and _stamp(Path(path)) != witness["input_stat"]:
            return {"required": True, "traits": len(rows), "reason": "input_changed"}
    return result


def _stamp(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _model_rows(path, build):
    meta, header = {}, None
    with _open(path) as stream:
        for line in stream:
            if line.startswith("#"):
                if "=" in line:
                    key, val = line.lstrip("#").strip().split("=", 1)
                    meta[key] = val
                continue
            if header is None:
                header = line.rstrip().split("\t")
                if meta.get("HmPOS_build") != build or not {"hm_chr", "hm_pos", "effect_allele"} <= set(header):
                    raise ValueError("Model coordinates are not verified for " + build)
                continue
            row = dict(zip(header, line.rstrip("\n").split("\t")))
            chrom, pos = row.get("hm_chr", "").removeprefix("chr"), row.get("hm_pos", "")
            if chrom == "MT":
                chrom = "M"
            if not chrom or not pos:
                # Unmapped rows remain unmatched in scoring; never invent a coordinate.
                continue
            if chrom not in {str(i) for i in range(1, 23)} | {"X", "Y", "M"} or not pos.isdigit() or int(pos) < 1:
                raise ValueError("Unsupported model coordinate")
            yield chrom, int(pos), row
    if header is None:
        raise ValueError("Empty model file")


def _models(traits, build, progress, stop):
    """Download only public pinned weights, never genotype or clinical data."""
    pins = prs._pinned_models()
    paths = []
    for i, trait in enumerate(traits):
        _check(stop)
        pid = (pins.get(trait["term"]) or {}).get("pgs_id")
        if not pid:
            continue
        if not re.fullmatch(r"PGS\d+", pid):
            raise ValueError("Invalid pinned score ID")
        if progress:
            progress(i, len(traits), _t("prs.recompute.model", id=pid))
        path = prs._cache_root() / "scores" / f"{pid}_hmPOS_{build}.txt.gz"
        if not path.exists():
            if os.environ.get("SCHOLION_OFFLINE") == "1":
                raise ValueError(_t("prs.recompute.model_missing", id=pid))
            path.parent.mkdir(parents=True, exist_ok=True)
            url = (f"https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/{pid}/ScoringFiles/"
                   f"Harmonized/{pid}_hmPOS_{build}.txt.gz")
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
                temp = Path(output.name)
                try:
                    with urllib.request.urlopen(url, timeout=30) as response:
                        while True:
                            _check(stop)
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                    output.close()
                    if next(iter(_model_rows(temp, build)), None) is None:
                        raise ValueError("Empty downloaded model")
                    os.replace(temp, path)
                finally:
                    output.close()
                    temp.unlink(missing_ok=True)
        paths.append(path)
    return paths


def _missing(vcf, models, build, stop):
    missing = set()
    source = ScoringVCF(vcf)
    try:
        for path in models:
            _check(stop)
            for chrom, pos, row in _model_rows(path, build):
                other = row.get("other_allele") or row.get("hm_inferOtherAllele") or ""
                if not set(other.upper()) <= set("ACGT"):
                    other = ""
                value, _ = dosage(row["effect_allele"], other, source.get(chrom, str(pos)))
                if value is None:
                    missing.add((chrom, pos))
    finally:
        source.close()
    return missing


def _run_cancellable(commands, stop):
    """Bounded local subprocesses; no stdout/stderr pipe can fill unnoticed."""
    processes, errors = [], []
    try:
        for i, argv in enumerate(commands):
            _check(stop)
            err = tempfile.TemporaryFile()
            errors.append(err)
            previous = processes[-1] if processes else None
            process = subprocess.Popen(argv, stdin=previous.stdout if previous else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE if i < len(commands) - 1 else subprocess.DEVNULL,
                                       stderr=err)
            if previous and previous.stdout is not None:
                previous.stdout.close()
            processes.append(process)
        while any(p.poll() is None for p in processes):
            _check(stop)
            time.sleep(0.1)
        tails = []
        for err in errors:
            err.seek(0)
            tails.append(err.read()[-600:].decode("utf-8", "replace"))
        return {"rc": next((p.returncode for p in processes if p.returncode), 0),
                "stderr": "\n".join(tails)}
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for err in errors:
            err.close()


def _augment(vcf, missing, build, progress, stop, run=None):
    """Only missing model positions, all-site calling, verified sample/build."""
    from . import gene_region, fastalite
    bam, reference = gene_region.bam_path(), gene_region.reference_path()
    if bam is None:
        # A VCF-only user still gets the measured score with its actual coverage.
        return vcf, "vcf_only"
    req = {"vcf": str(vcf), "bam": str(bam), "reference": str(reference) if reference else None,
           "bcftools": shutil.which("bcftools")}
    reason = sites.refusal(req)
    if reason:
        raise ValueError(_t("recompute.why." + reason))
    alignment = sites.alignment_build(str(bam))
    fa = fastalite.Fasta(reference)
    ref_build = sites._CHR1.get((fa.index.get("chr1") or fa.index.get("1") or (0,))[0])
    if alignment["assembly"] != build or ref_build != build:
        raise ValueError(_t("prs.recompute.build_mismatch"))
    target = vcf.parent / "scoring_sites.recomputed.vcf.gz"
    run = run or (lambda commands: _run_cancellable(commands, stop))
    per_chrom = {}
    for chrom, pos in missing:
        actual = alignment["prefix"] + chrom
        if actual not in alignment["contigs"] or actual not in fa.index or pos > fa.index[actual][0]:
            raise ValueError(_t("prs.recompute.build_mismatch"))
        per_chrom.setdefault(chrom, []).append(pos)
    def execute(commands):
        _check(stop)
        result = run(commands)
        _check(stop)
        if result.get("rc"):
            raise ValueError(str(result.get("stderr") or "PGS genotyping failed")[-600:])
    with tempfile.TemporaryDirectory(prefix=".pgs-sites-", dir=target.parent) as folder:
        work = Path(folder)
        base = work / "base.vcf.gz"
        excluded = work / "replaced.bed"
        excluded.write_text("".join(f"{prefix}{chrom}\t{pos-1}\t{pos}\n"
                                  for chrom, pos in sorted(missing) for prefix in ("", "chr")), encoding="utf-8")
        execute([["bcftools", "view", "-T", "^" + str(excluded), "-Oz", "-o", str(base), str(vcf)]])
        execute([["bcftools", "index", "-t", str(base)]])
        parts = [str(base)]
        chroms = sorted(per_chrom, key=lambda c: int(c) if c.isdigit() else {"X": 23, "Y": 24, "M": 25}[c])
        for i, chrom in enumerate(chroms):
            if progress:
                progress(i, len(chroms), _t("prs.recompute.chromosome", chrom=chrom))
            bed = work / f"{chrom}.bed"
            bed.write_text("".join(f"{alignment['prefix']}{chrom}\t{pos-1}\t{pos}\n" for pos in sorted(per_chrom[chrom])), encoding="utf-8")
            part = work / f"{chrom}.vcf.gz"
            execute([["bcftools", "mpileup", "-R", str(bed), "-f", str(reference), "-a", "FORMAT/DP", "-Ou", str(bam)],
                     ["bcftools", "call", "-m", "-Oz", "-o", str(part)]])
            if population.samples(part) != population.samples(vcf):
                raise ValueError(_t("prs.recompute.sample_mismatch"))
            execute([["bcftools", "index", "-t", str(part)]])
            parts.append(str(part))
        merged = work / target.name
        execute([["bcftools", "concat", "-a", "-Ou"] + parts,
                 ["bcftools", "sort", "-Oz", "-o", str(merged)]])
        execute([["bcftools", "index", "-t", str(merged)]])
        os.replace(merged, target)
        os.replace(str(merged) + ".tbi", str(target) + ".tbi")
    return target, "targeted_bam"


def calculate(confirm=False, only=None, progress=None, stop=None):
    """Complete local operation. Failed/cancelled work never replaces the report."""
    from . import container, pgs_results
    with container.pinned():
        plan = preflight(only)
        if not confirm:
            return {"ok": False, "status": "not_confirmed", "plan": plan}
        if plan["status"] != "ready":
            return {"ok": False, **plan}
        try:
            traits = [t for t in _traits(only) if (prs._pinned_models().get(t["term"]) or {}).get("pgs_id")]
            vcf, build = Path(plan["vcf"]), plan["assembly"]
            models = _models(traits, build, progress, stop)
            missing = _missing(vcf, models, build, stop)
            preparation = "reused_scoring_vcf"
            if missing:
                vcf, preparation = _augment(vcf, missing, build, progress, stop)
            _check(stop)
            def tick(done, total, item=None):
                _check(stop)
                if progress:
                    progress(done, total, item)
            raw = prs.report(str(vcf), traits=traits, normalize=False, progress=tick, stop=stop)
            _check(stop)
            connected = genome.vcf_path()
            if connected:
                raw["connected_genome"] = {"path": str(connected.resolve()), "stat": _stamp(connected)}
            result = pgs_results.save(raw, prs._pinned_models(), stop=stop)
            result.update(preparation=preparation, missing_before=len(missing),
                          message=_t("prs.recompute.written") if result["ok"] else _t("prs.recompute.stopped"))
            return result
        except (Stopped, prs.PrsCancelled):
            return {"ok": False, "status": "stopped", "message": _t("prs.recompute.stopped")}
        except (OSError, ValueError, RuntimeError, EOFError) as exc:
            return {"ok": False, "status": "failed", "error": str(exc),
                    "message": _t("prs.recompute.failed")}
