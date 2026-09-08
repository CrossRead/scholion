"""Gene symbol → coordinates and coding exons, without a curated catalogue.

The gap this closes (task 127). `loci.json` is a curated book of pharmacogenetic
LOCI: it answers «what is at rs4149056» and, by extension, «which of my catalogued
loci belong to SLCO1B1». It was never a gene index, and it is not obliged to become
one — but until now a question about a gene outside it («is there an activating
variant in CASR?») met «Gene CASR is not in the coordinate reference», which reads
as an answer about the genome when it is an answer about a lookup table.

Three sources, in this order, and the answer always says which one spoke:
  1. the cache, written by whichever of the two below answered first;
  2. a local Ensembl GFF3, if the machine has one — the same annotation the
     project's own `csq` step already downloads, so on the owner's machine this
     path needs no network at all;
  3. Ensembl REST, live.
When all three are silent the answer is not an empty result but a named absence:
what is missing, and what would fix it. A gene symbol is public information; the
owner's genotypes take no part in resolving it and are never sent anywhere.
"""
from __future__ import annotations

import gzip
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core

_ENSEMBL_SYMBOL = ("https://rest.ensembl.org/lookup/symbol/homo_sapiens/{}"
                   "?content-type=application/json;expand=1")

#: The assembly the whole project speaks. A GFF3 or a REST answer in another build
#: is not a usable coordinate here — it is a coordinate for someone else's file.
ASSEMBLY = "GRCh38"

_ID_GENE = re.compile(r"ID=gene:([^;]+)")
_ID_TX = re.compile(r"ID=transcript:([^;]+)")
_PARENT_GENE = re.compile(r"Parent=gene:([^;]+)")
_PARENT_TX = re.compile(r"Parent=transcript:([^;]+)")
_NAME = re.compile(r"(?:^|;)Name=([^;]+)")


def gff3_search_roots() -> List[Path]:
    """Folders searched for a local annotation — the list the refusal has to print.

    «No local annotation» is only a usable sentence when it comes with where the
    looking happened; otherwise the reader cannot tell a missing file from a file
    in the wrong place, and those need opposite actions.
    """
    # Declared locations only. Nothing here walks UP from where the code or the
    # profile sits: that expression is how the lab and wearable searches once
    # reached into somebody's documents, and `test_lab_dir_boundary` guards the
    # class rather than those two instances. An annotation anywhere else is named
    # by `SCHOLION_GENE_GFF3` — one variable, deliberately, instead of a search
    # that is convenient until the day it finds the wrong file.
    roots: List[Path] = list(core.genome_bases())
    roots += [Path.home() / "genomic_work" / "csq"]
    out, seen = [], set()
    for r in roots:
        s = str(r)
        if s not in seen:
            seen.add(s)
            out.append(r)
    return out


def gff3_candidates() -> List[Path]:
    """Local Ensembl GFF3 files, most specific first.

    `SCHOLION_GENE_GFF3` wins outright, and — as everywhere else in this project —
    an explicit setting switches the search off rather than adding to it: a test
    pointed at a small fixture must not silently reach the owner's real annotation.
    """
    env = os.environ.get("SCHOLION_GENE_GFF3")
    if env:
        p = Path(env).expanduser()
        return [p] if p.exists() else []
    out: List[Path] = []
    seen = set()
    for base in gff3_search_roots():
        try:
            if not base.exists():
                continue
        except OSError:
            continue
        # A canonical-transcript file is preferred: it is an order of magnitude
        # smaller, and one canonical transcript is what a report should quote.
        for pattern in ("*canon*.gff3.gz", "*.gff3.gz", "*.gff3"):
            for p in sorted(base.glob(pattern)):
                if str(p) not in seen:
                    seen.add(str(p))
                    out.append(p)
    return out


def _cache_file() -> Path:
    return core.mkdir_private(core.cache_dir()) / "genes_cache.json"


def _load_cache() -> Dict[str, Any]:
    f = _cache_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        return {}


def _save_cache(d: Dict[str, Any]) -> None:
    try:
        core.write_json(_cache_file(), d, indent=1)
    except Exception:
        pass


def _pick_transcript(txs: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Ensembl's own canonical tag if the file carries one, else the longest CDS.

    Never «the first one seen»: GFF3 order is not a ranking, and a report that
    quotes an arbitrary transcript will quote a different one after a rebuild.
    """
    if not txs:
        return None
    canon = [t for t, v in txs.items() if v.get("canonical")]
    if canon:
        return sorted(canon)[0]
    return max(txs, key=lambda t: (sum(b - a + 1 for _, a, b in txs[t]["cds"]), t))


def from_gff3(symbol: str, path: Path) -> Optional[Dict[str, Any]]:
    """One pass over a GFF3 for a gene, its transcripts and their CDS."""
    want = symbol.upper()
    gene: Optional[Dict[str, Any]] = None
    gene_id: Optional[str] = None
    txs: Dict[str, Dict[str, Any]] = {}
    tx_of_gene: set = set()
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(str(path), "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            kind, attrs = f[2], f[8]
            if kind == "gene":
                m = _NAME.search(attrs)
                if m and m.group(1).upper() == want:
                    gid = _ID_GENE.search(attrs)
                    gene_id = gid.group(1) if gid else None
                    gene = {"gene": m.group(1), "gene_id": gene_id, "chrom": f[0],
                            "start": int(f[3]), "end": int(f[4]), "strand": f[6]}
                elif gene is not None:
                    # The next gene has begun; everything of ours is already read.
                    break
            elif gene_id and kind in ("mRNA", "transcript"):
                pm = _PARENT_GENE.search(attrs)
                if pm and pm.group(1) == gene_id:
                    tm = _ID_TX.search(attrs)
                    if tm:
                        tx_of_gene.add(tm.group(1))
                        txs[tm.group(1)] = {"cds": [],
                                            "canonical": "Ensembl_canonical" in attrs}
            elif tx_of_gene and kind == "CDS":
                pm = _PARENT_TX.search(attrs)
                if pm and pm.group(1) in tx_of_gene:
                    txs[pm.group(1)]["cds"].append((f[0], int(f[3]), int(f[4])))
    if not gene:
        return None
    tx = _pick_transcript({t: v for t, v in txs.items() if v["cds"]})
    gene["transcript"] = tx
    gene["cds"] = [list(x) for x in sorted(txs[tx]["cds"], key=lambda x: x[1])] if tx else []
    gene["source"] = "gff3"
    gene["source_file"] = str(path)
    gene["assembly"] = ASSEMBLY
    return gene


def from_ensembl(symbol: str) -> Optional[Dict[str, Any]]:
    """Live Ensembl: gene coordinates and the CDS of the canonical transcript."""
    from . import net
    data = net.get_json(_ENSEMBL_SYMBOL.format(symbol))
    if not data or data.get("assembly_name") != ASSEMBLY:
        return None
    chrom = str(data.get("seq_region_name"))
    canonical = (data.get("canonical_transcript") or "").split(".")[0]
    cds: List[List[Any]] = []
    if canonical:
        seg = net.get_json(f"https://rest.ensembl.org/overlap/id/{canonical}"
                           f"?feature=cds;content-type=application/json")
        for s in seg or []:
            if str(s.get("Parent", "")).split(".")[0] == canonical:
                cds.append([chrom, int(s["start"]), int(s["end"])])
    return {"gene": data.get("display_name") or symbol, "gene_id": data.get("id"),
            "chrom": chrom, "start": int(data["start"]), "end": int(data["end"]),
            "strand": "+" if int(data.get("strand", 1)) > 0 else "-",
            "transcript": canonical or None, "cds": sorted(cds, key=lambda x: x[1]),
            "source": "ensembl", "assembly": ASSEMBLY}


def resolve(symbol: str, allow_network: bool = True) -> Optional[Dict[str, Any]]:
    """Coordinates and coding exons of a gene, or None.

    None means «not resolved», never «no such gene»: the caller is expected to say
    which of the three sources was silent and what would make it speak.
    """
    symbol = (symbol or "").strip()
    if not symbol or not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", symbol):
        return None
    key = symbol.upper()
    cache = _load_cache()
    hit = cache.get(key)
    if hit:
        return {**hit, "source": "cache", "resolved_by": hit.get("source", "cache")}
    for path in gff3_candidates():
        try:
            rec = from_gff3(symbol, path)
        except Exception:
            rec = None
        if rec:
            cache[key] = rec
            _save_cache(cache)
            return rec
    if allow_network:
        try:
            rec = from_ensembl(symbol)
        except Exception:
            rec = None
        if rec:
            cache[key] = rec
            _save_cache(cache)
            return rec
    return None


def match_contig(chrom: str, contigs: List[str]) -> Optional[str]:
    """The name THIS file uses for that chromosome — `chr3` and `3` are one contig.

    A gene resolved from an annotation that writes `3` and a VCF that writes `chr3`
    would otherwise produce «no variants in the region», which is the single most
    dangerous wrong answer this module can give: it looks exactly like good news.
    """
    if chrom in contigs:
        return chrom
    bare = chrom[3:] if chrom.startswith("chr") else chrom
    for candidate in (bare, "chr" + bare, "CHR" + bare):
        if candidate in contigs:
            return candidate
    return None
