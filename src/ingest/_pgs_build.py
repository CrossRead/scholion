"""Coordinate provenance for PGS position lists and BAM preparation (stdlib)."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

LENGTHS = {
    249250621: "GRCh37", 243199373: "GRCh37", 155270560: "GRCh37",
    248956422: "GRCh38", 242193529: "GRCh38", 156040895: "GRCh38",
}


def requested_build():
    build = os.environ.get("PGS_GENOME_BUILD")
    if build not in ("GRCh37", "GRCh38"):
        raise ValueError("Set PGS_GENOME_BUILD=GRCh37 or GRCh38 to the verified BAM/FASTA build; no default is assumed.")
    return build


def model_header(path, build):
    header = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("#"):
                break
            if "=" in line:
                key, value = line.lstrip("#").strip().split("=", 1)
                header[key] = value
    if header.get("HmPOS_build") != build:
        raise ValueError(f"Model harmonized build is not {build}: {path}")
    return {"pgs_id": header.get("pgs_id"), "original_build": header.get("genome_build"),
            "harmonized_build": header.get("HmPOS_build")}


def bed_metadata(path, build, models):
    path = Path(path)
    data = {"genome_build": build, "bed_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "models": models}
    Path(str(path) + ".meta.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def check_bed(path, build):
    path = Path(path)
    meta = json.loads(Path(str(path) + ".meta.json").read_text(encoding="utf-8"))
    if meta.get("genome_build") != build or meta.get("bed_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("BED build/provenance does not match; regenerate the position list.")
    if not meta.get("models") or any(m.get("harmonized_build") != build for m in meta["models"]):
        raise ValueError("BED has no matching model coordinate provenance.")
    return meta


def assembly_from_lengths(lengths):
    builds = {LENGTHS[n] for n in lengths if n in LENGTHS}
    return next(iter(builds)) if len(builds) == 1 else None


def check_inputs(bed, bam, fasta):
    build = requested_build()
    check_bed(bed, build)
    header = subprocess.run(["samtools", "view", "-H", str(bam)], check=True,
                            capture_output=True, text=True).stdout
    bam_contigs = {}
    for line in header.splitlines():
        if line.startswith("@SQ\t"):
            values = dict(field.split(":", 1) for field in line.split("\t")[1:] if ":" in field)
            bam_contigs[values["SN"]] = int(values["LN"])
    fasta_contigs = {}
    with open(str(fasta) + ".fai", encoding="utf-8") as handle:
        for line in handle:
            fields = line.split("\t")
            fasta_contigs[fields[0]] = int(fields[1])
    if assembly_from_lengths(bam_contigs.values()) != build or assembly_from_lengths(fasta_contigs.values()) != build:
        raise ValueError("BAM, FASTA and BED must have the same verified coordinate build.")
    with open(bed, encoding="utf-8") as handle:
        for line in handle:
            fields = line.split()
            if len(fields) < 3 or fields[0] not in bam_contigs or fields[0] not in fasta_contigs:
                raise ValueError("BED chromosome names do not match BAM/FASTA.")
            if bam_contigs[fields[0]] != fasta_contigs[fields[0]] or not 0 <= int(fields[1]) < int(fields[2]) <= fasta_contigs[fields[0]]:
                raise ValueError("BED position or BAM/FASTA contig length is inconsistent.")
    return build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bed")
    parser.add_argument("bam")
    parser.add_argument("fasta")
    args = parser.parse_args()
    try:
        print(check_inputs(args.bed, args.bam, args.fasta))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"PGS coordinate check refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
