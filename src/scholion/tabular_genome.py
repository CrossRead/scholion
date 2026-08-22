"""Genomic data that is readable and is not a seekable VCF.

Task 89, and the direct continuation of task 64: naming a file was the first
half, and reading it is the second. Eight files in the reference corpus stopped
answering «the full VCF is not connected» and started saying what they are —
and three of them are ordinary VCFs whose only fault is the container they
arrived in, while two are genotype tables that carry exactly what a consumer
chip carries.

Neither can be read the way a genome is read. A tabix index seeks by position
and none of these can be indexed without first being rewritten with tools the
person does not have. But the catalogue is finite — fifty-four loci — so one
pass over the file collects every position that could ever be asked for, and
the pass is cached. That is a different thing from a genome, and it is reported
as a different thing:

* a **container VCF** is a real call set, so the same measurement as any other
  call set is made from the same pass — and here it is exact rather than probed,
  because the whole file goes past;
* a **genotype table** is a list of chosen positions, so it carries the array's
  ceiling: a position with no row was never interrogated, and reporting the
  reference there would turn «this instrument cannot see that locus» into «you
  do not have that variant».

What is deliberately NOT read, with the reason, because an unexplained gap is
indistinguishable from an oversight:

* **A VCF that went through a spreadsheet.** Its header lines are quoted and its
  columns are no longer tab-separated; the structure is gone, not hidden. The
  honest answer is the original export, which is what the status says.
* **A Complete Genomics `var` table.** It is a real call set, but a diploid
  genotype there is spread over two allele rows with their own ploidy and
  no-call vocabulary. The vendor ships a converter (`cgatools mkvcf`) that is
  correct by construction; a reimplementation here would be a second, worse one.
* **FTDNA-era archives keyed by an internal SNP number** (`6248,Mt,T,T`). There
  is no rsID in the file and no public mapping shipped with this build, so the
  catalogue cannot be matched at all.
"""

from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import json
import lzma
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from .i18n import t as _t

GENOME_BASES = 3_100_000_000  # for variants per megabase over a whole pass


def _open_text(path: str) -> Optional[Iterator[str]]:
    """Line iterator over a file in whatever it is wrapped in — by magic bytes."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4)
    except OSError:
        return None
    try:
        if head[:2] == b"\x1f\x8b":
            return io.TextIOWrapper(gzip.open(path, "rb"), errors="replace")
        if head[:3] == b"BZh":
            return io.TextIOWrapper(bz2.open(path, "rb"), errors="replace")
        if head[:6] == b"\xfd7zXZ\x00":
            return io.TextIOWrapper(lzma.open(path, "rb"), errors="replace")
        if head[:2] == b"PK":
            zf = zipfile.ZipFile(path)
            names = [n for n in zf.namelist() if not n.endswith("/")]
            if not names:
                return None
            # The biggest member: a provider archive also holds its README, and a
            # README that parses as nothing would look like an unreadable genome.
            biggest = max(names, key=lambda n: zf.getinfo(n).file_size)
            return io.TextIOWrapper(zf.open(biggest), errors="replace")
        return open(path, "r", errors="replace")
    except Exception:
        return None


def _cache_file(path: str, kind: str) -> Optional[Path]:
    try:
        from . import core
        st = os.stat(path)
    except Exception:
        return None
    key = hashlib.sha1(
        f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}|{kind}".encode()).hexdigest()[:16]
    return Path(core.cache_dir()) / f"tabular-{key}.json"


def _catalogue() -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, int], str]]:
    """Catalogue loci by rsID, and by (chromosome, position) in BOTH builds."""
    from . import genome
    loci = (genome.loci().get("loci") or {})
    by_pos: Dict[Tuple[str, int], str] = {}
    for rs, l in loci.items():
        chrom = str(l.get("chrom") or "").lstrip("chr")
        for field in ("pos", "pos_grch37"):
            if l.get(field):
                by_pos[(chrom, int(l[field]))] = rs
    return loci, by_pos


def _scan_container_vcf(path: str) -> Dict[str, Any]:
    """One pass: the catalogue's rows, and what the whole call set is made of."""
    loci, by_pos = _catalogue()
    wanted = {rs.lower() for rs in loci}
    found: Dict[str, Dict[str, Any]] = {}
    snv = indel = total = 0
    sample_col = 9
    lines = _open_text(path)
    if lines is None:
        return {"ok": False, "reason": "unreadable"}
    with lines:
        for line in lines:
            if line[:1] == "#":
                continue
            f = line.rstrip("\r\n").split("\t")
            if len(f) < 5:
                continue
            alts = [a for a in f[4].split(",") if a not in ("<NON_REF>", ".", "")]
            if alts:
                total += 1
                if len(f[3]) == 1 and all(len(a) == 1 for a in alts):
                    snv += 1
                else:
                    indel += 1
            rs = f[2].lower() if f[2].lower().startswith("rs") else None
            key = rs if (rs and rs in wanted) else None
            if key is None:
                try:
                    key = by_pos.get((f[0].lstrip("chr"), int(f[1])))
                except ValueError:
                    key = None
                key = key.lower() if key else None
            if key is None or key in found:
                continue
            gt = None
            if len(f) > sample_col and len(f) > 8 and "GT" in f[8].split(":"):
                cell = f[sample_col].split(":")
                raw = cell[f[8].split(":").index("GT")]
                idx = [i for i in raw.replace("|", "/").split("/") if i.isdigit()]
                alleles = [f[3]] + f[4].split(",")
                try:
                    gt = "".join(alleles[int(i)] for i in idx) if idx else None
                except (IndexError, ValueError):
                    gt = None
            found[key] = {"genotype": gt, "ref": f[3], "alt": f[4], "filter": f[6] if len(f) > 6 else ""}
    per_mb = round(total / (GENOME_BASES / 1_000_000))
    return {"ok": True, "kind": "container_vcf", "loci": found,
            "variants": total, "snv": snv, "indel": indel,
            "observed_per_mb": per_mb,
            "only_indels": bool(total >= 1000 and snv == 0),
            "only_snvs": bool(total >= 1000 and indel == 0)}


def _scan_genotype_table(path: str) -> Dict[str, Any]:
    """A table of chosen positions: `CHROM BEGIN END ID GENOTYPE`, rsID in ID."""
    loci, _ = _catalogue()
    wanted = {rs.lower() for rs in loci}
    found: Dict[str, Dict[str, Any]] = {}
    rows = 0
    lines = _open_text(path)
    if lines is None:
        return {"ok": False, "reason": "unreadable"}
    with lines:
        for line in lines:
            if line[:1] == "#":
                continue
            f = [c.strip() for c in line.rstrip("\r\n").split("\t")]
            if len(f) < 2:
                f = [c.strip() for c in line.rstrip("\r\n").split(",")]
            if len(f) < 2:
                continue
            rows += 1
            rs = next((c.lower() for c in f if c.lower().startswith("rs")), None)
            if not rs or rs not in wanted or rs in found:
                continue
            gt = None
            for c in reversed(f):
                cleaned = c.replace("/", "").replace("|", "").strip().upper()
                if cleaned and len(cleaned) <= 4 and set(cleaned) <= set("ACGTN-"):
                    gt = None if set(cleaned) <= {"-", "N"} else cleaned
                    break
            found[rs] = {"genotype": gt}
    return {"ok": True, "kind": "genotype_table", "loci": found, "rows": rows}


def source() -> Optional[Tuple[str, str]]:
    """(path, kind) of a readable non-VCF genomic file in the genome folders."""
    from . import genome
    for item in genome.foreign_inputs():
        if item["kind"] in ("vcf_compressed", "genotype_table"):
            return item["path"], item["kind"]
    return None


def index() -> Dict[str, Any]:
    """Everything the catalogue can be answered from, cached by file identity."""
    src = source()
    if not src:
        return {"ok": False, "reason": "no_tabular_source"}
    path, kind = src
    cache = _cache_file(path, kind)
    if cache is not None and cache.exists():
        try:
            data = json.loads(cache.read_text())
            data["path"] = path
            return data
        except Exception:
            pass
    data = (_scan_container_vcf(path) if kind == "vcf_compressed"
            else _scan_genotype_table(path))
    data["path"] = path
    if cache is not None and data.get("ok"):
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(data))
        except Exception:
            pass
    return data


def status(rsid: str) -> Dict[str, Any]:
    """Three-valued, exactly as for a chip: called / no call / not in this file."""
    idx = index()
    if not idx.get("ok"):
        return {"status": "no_tabular", "reason": idx.get("reason", "no_tabular_source")}
    hit = (idx.get("loci") or {}).get((rsid or "").lower())
    container = idx.get("kind") == "container_vcf"
    if hit is None:
        if container and not (idx.get("only_indels") or idx.get("only_snvs")):
            # A call set genuinely read this position and printed no row for it.
            # That is «matched the reference, or was not covered» — the same two
            # readings as in any variants-only VCF, and neither is a finding.
            return {"status": "assumed_ref_tabular", "source": idx["kind"],
                    "path": idx.get("path"), "note": _t("tabular.assumed_ref")}
        return {"status": "not_in_file", "source": idx["kind"], "path": idx.get("path"),
                "note": _t("tabular.not_in_file")}
    if not hit.get("genotype"):
        return {"status": "no_call", "source": idx["kind"], "path": idx.get("path"),
                "note": _t("tabular.no_call")}
    return {"status": "called", "genotype": hit["genotype"], "source": idx["kind"],
            "path": idx.get("path"),
            "note": _t("tabular.called_" + idx["kind"])}


def summary() -> Dict[str, Any]:
    """What kind of input this is, for `limits` and for the genome report."""
    idx = index()
    if not idx.get("ok"):
        return {"available": False, "reason": idx.get("reason", "no_tabular_source")}
    out = {"available": True, "kind": idx["kind"], "path": idx.get("path"),
           "loci_present": len(idx.get("loci") or {})}
    if idx["kind"] == "container_vcf":
        out.update({"variants": idx.get("variants"), "snv": idx.get("snv"),
                    "indel": idx.get("indel"),
                    "observed_per_mb": idx.get("observed_per_mb"),
                    "only_indels": idx.get("only_indels"),
                    "only_snvs": idx.get("only_snvs")})
        from . import callset
        out["class"] = callset._classify({
            "measured": True, "only_indels": idx.get("only_indels"),
            "only_snvs": idx.get("only_snvs"), "imputed_share": None,
            "observed_per_mb": idx.get("observed_per_mb")})
    else:
        out["rows"] = idx.get("rows")
        out["class"] = "genotype_table"
    return out
