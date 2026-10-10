"""Prepare and assign a reference population as part of connecting a genome.

The small, scoring-independent genotype file is reused. If it is missing, only
public catalogue rsIDs are resolved; local BAM reads remain on this computer.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import urllib.request

from . import core, genome, population, sites, store


def resolve_positions(build: str, prefix: str, contigs: set) -> dict:
    """Resolve public catalogue rsIDs in the verified alignment assembly."""
    cache_path = core.cache_dir() / f"population-positions-{build}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("assembly") == build and isinstance(cached.get("positions"), dict):
            return {prefix + key.removeprefix("chr"): value for key, value in cached["positions"].items()}
    except (OSError, ValueError, AttributeError):
        pass
    if os.environ.get("SCHOLION_OFFLINE") == "1":
        return {}
    catalogue = json.loads(Path(core.knowledge_path("longevitymap.json")).read_text(encoding="utf-8"))
    rsids = [rs for rs in catalogue.get("variants", {}) if rs.startswith("rs") and rs[2:].isdigit()]
    host = "https://grch37.rest.ensembl.org" if build == "GRCh37" else "https://rest.ensembl.org"
    mapping = {}
    for start in range(0, len(rsids), 190):
        request = urllib.request.Request(host + "/variation/homo_sapiens",
                  data=json.dumps({"ids": rsids[start:start + 190]}).encode(),
                  headers={"Content-Type": "application/json", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read())
        for rs, record in data.items():
            valid = [m for m in record.get("mappings", [])
                     if m.get("assembly_name") == build and str(m.get("seq_region_name")) in {str(n) for n in range(1, 23)}
                     and isinstance(m.get("start"), int) and m["start"] > 0
                     and m.get("end") == m["start"] and m.get("strand") == 1]
            if len(valid) == 1:
                m = valid[0]
                chrom = prefix + str(m["seq_region_name"])
                if chrom in contigs:
                    mapping[f"{chrom}:{m['start']}"] = rs
    # Cache canonical chromosome names, independent of the caller's BAM naming.
    store._write_json(cache_path, {"assembly": build, "positions": {key.removeprefix("chr"): value for key, value in mapping.items()}})
    return mapping


def genotype(vcf: Path, run=None) -> dict:
    """Call reference homozygotes too, after BAM/FASTA/VCF assembly checks."""
    req = sites.requirements()
    req["vcf"] = str(vcf)
    why = sites.refusal(req)
    if why:
        return {"status": why, "verdict_superpop": None}
    bam, ref = str(req["bam"]), str(req["reference"])
    try:
        build = sites.alignment_build(bam)
        assembly = build.get("assembly")
        if assembly not in ("GRCh37", "GRCh38") or genome.assembly_of(str(vcf)) != assembly:
            return {"status": "build_mismatch", "verdict_superpop": None}
        from . import bamlite
        lengths = bamlite.reference_lengths(bam)
        fai = {}
        for line in Path(ref + ".fai").read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            fai[fields[0]] = int(fields[1])
        if sites._CHR1.get(fai.get(build["prefix"] + "1") or 0) != assembly:
            return {"status": "build_mismatch", "verdict_superpop": None}
        mapping = resolve_positions(assembly, build["prefix"], build["contigs"])
        if not mapping:
            return {"status": "reference_unavailable", "verdict_superpop": None}
        rows = []
        for key in mapping:
            chrom, position = key.split(":")
            pos = int(position)
            if chrom not in lengths or lengths[chrom] != fai.get(chrom) or not 0 < pos <= lengths[chrom]:
                return {"status": "build_mismatch", "verdict_superpop": None}
            rows.append((chrom, pos))
        rows.sort(key=lambda row: (int(row[0].removeprefix("chr")), row[1]))
        run = run or sites._run_pipeline
        with tempfile.TemporaryDirectory(prefix=".population-", dir=vcf.parent) as temp:
            work = Path(temp)
            bed = work / "sites.bed"
            bed.write_text("".join(f"{chrom}\t{pos-1}\t{pos}\n" for chrom, pos in rows), encoding="utf-8")
            target = work / "longevity_sites.vcf.gz"
            result = run([["bcftools", "mpileup", "-R", str(bed), "-f", ref, "-a", "FORMAT/DP", "-Ou", bam],
                          ["bcftools", "call", "-m", "-Oz", "-o", str(target)]])
            if result.get("rc"):
                return {"status": "genotyping_failed", "verdict_superpop": None}
            if population.samples(target) != population.samples(vcf):
                return {"status": "sample_mismatch", "verdict_superpop": None}
            result = run([["bcftools", "index", "-t", str(target)]])
            if result.get("rc"):
                return {"status": "genotyping_failed", "verdict_superpop": None}
            os.replace(target, vcf.parent / target.name)
            os.replace(str(target) + ".tbi", str(vcf.parent / target.name) + ".tbi")
            store._write_json(vcf.parent / "longevity_rsmap.json", mapping)
        return {"status": "prepared"}
    except (OSError, ValueError, KeyError, TypeError, EOFError):
        return {"status": "invalid_genotypes", "verdict_superpop": None}


def prepare(vcf: Path | None = None) -> dict:
    """One assignment per active genome; connecting data calls this automatically."""
    from . import container
    with container.pinned(), core.profile_write_lock():
        connected = vcf or genome.vcf_path()
        if connected is None:
            return {"status": "no_vcf", "verdict_superpop": None}
        check = core.ancestry_check()
        applicable = core.ancestry()
        # Legacy determinations are preserved while reading, but a new explicit
        # connection must bind the determination to the selected input.
        try:
            input_stamp = population.genome_stamp(connected)
        except OSError:
            return {"status": "invalid_genotypes", "verdict_superpop": None}
        same_input = (check.get("source_genome") == str(connected.resolve())
                      and check.get("source_genome_stamp") == input_stamp)
        if check.get("status") == "ambiguous" and same_input and check.get("source_vcf"):
            try:
                if population.fingerprint(Path(check["source_vcf"])) == check.get("source_vcf_sha256") and population.fingerprint(Path(check["source_rsmap"])) == check.get("source_rsmap_sha256"):
                    return check
            except (OSError, KeyError, TypeError):
                pass
        if applicable["value"] and (applicable["source"] == "stated" or same_input):
            return {"status": "current", "verdict_superpop": applicable["value"]}
        path = core.profile_dir() / "ancestry_check.json"
        try:
            sample_names = population.samples(connected)
            if len(sample_names) != 1:
                raise ValueError("one diploid sample is required")
        except (OSError, ValueError, EOFError):
            result: dict = {"status": "invalid_genotypes", "verdict_superpop": None}
            store._write_json(path, result)
            core.reset_cache()
            return result
        changed_input = bool(check.get("needs_preparation")) or (bool(check.get("source_genome")) and
                        (check["source_genome"] != str(connected.resolve())
                         or (bool(check.get("source_genome_stamp")) and not same_input)))
        pending = {"status": "running", "verdict_superpop": None, "source_genome": str(connected.resolve()),
                   "source_genome_stamp": input_stamp, "needs_preparation": changed_input}
        store._write_json(path, pending)
        core.reset_cache()
        prepared = connected.parent / "longevity_sites.vcf.gz"
        if not prepared.is_file() or changed_input:
            result = genotype(connected)
            if result.get("status") != "prepared":
                store._write_json(path, {**pending, **result})
                core.reset_cache()
                return result
        result = population.prepare_for_pgs(str(connected))
        result["source_genome"] = str(connected.resolve())
        result["source_genome_samples"] = population.samples(connected)
        result["source_genome_stamp"] = input_stamp
        if population.genome_stamp(connected) != input_stamp:
            result["status"] = "invalid_genotypes"
            result["verdict_superpop"] = None
        store._write_json(path, result)
        core.reset_cache()
        return result


def state() -> dict:
    """Read the shared determination, without analysis, requests or writes."""
    from .i18n import t
    applicable = core.ancestry()
    check = core.ancestry_check()
    value = applicable.get("value")
    status = "determined" if value else check.get("status", "needs_genotypes")
    reason = status if not value and status != "running" else None
    if value:
        note = t("prs.population." + applicable["source"], population=value)
    elif status == "running":
        note = t("prs.population.preparing")
    else:
        note = t("prs.population.unresolved", reason=t("prs.population.reason." + str(reason)))
    return {"value": value, "source": applicable.get("source"), "status": status,
            "date": applicable.get("date"), "n_snps": check.get("n_snps"),
            "reason": reason, "note": note,
            "scope": t("prs.population.scope")}
