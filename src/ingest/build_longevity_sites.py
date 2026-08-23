#!/usr/bin/env python3
"""LongevityMap rsID → GRCh38 positions (via Ensembl REST) → BED + an rs↔pos map.

The longevitymap.json catalog stores rsIDs only (no coordinates). To learn the
owner's GENOTYPES at these variants, the rsIDs must be resolved into GRCh38 positions,
then re-genotyped from merged.bam (prs_genotype_sites.sh with OUT=...).

Network access is required (Ensembl) — run this on the Mac, not in the cloud sandbox.
A certificate failure is handed to `net.certificate_fallback`, which retries
without verification only with SCHOLION_TLS_INSECURE=1 and says so when it does.

    python3 build_longevity_sites.py [longevitymap.json] [out.bed] [rsmap.json]
    ONLY_SIGNIFICANT=1 python3 build_longevity_sites.py   # significant only (509)
"""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                      # src/ — for `scholion`
from scholion import net                                       # noqa: E402

DEF_CATALOG = os.path.join(HERE, "..", "scholion", "knowledge", "longevitymap.json")
CATALOG = sys.argv[1] if len(sys.argv) > 1 else DEF_CATALOG
OUT_BED = sys.argv[2] if len(sys.argv) > 2 else "/tmp/longevity_sites.bed"
OUT_MAP = sys.argv[3] if len(sys.argv) > 3 else "/tmp/longevity_rsmap.json"
ONLY_SIG = os.environ.get("ONLY_SIGNIFICANT", "0") == "1"
ENSEMBL = "https://rest.ensembl.org/variation/homo_sapiens"
CANON = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}


def _post(ids):
    body = json.dumps({"ids": ids}).encode()
    req = urllib.request.Request(ENSEMBL, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=60)
    except urllib.error.URLError as e:
        # Not «does the message mention SSL» — that answered yes to a protocol
        # error and to a proxy refusing CONNECT, and dropped verification for
        # both. `net.certificate_fallback` decides by the type of the failure and
        # by whether the person permitted the retry; it raises if either answer
        # is no. These coordinates are what the owner's longevity positions are
        # re-genotyped at, so an answer from an unchecked channel is a wrong
        # position, not a slow one.
        r = urllib.request.urlopen(req, timeout=60, context=net.certificate_fallback(e))
    return json.loads(r.read().decode())


def main():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    V = cat["variants"]
    rsids = []
    for rs, m in V.items():
        if ONLY_SIG and not any(a.lower() == "significant" for a in (m.get("associations") or [])):
            continue
        if rs.startswith("rs"):
            rsids.append(rs)
    print(f"rsIDs to resolve: {len(rsids)} ({'significant only' if ONLY_SIG else 'all'})")

    rsmap = {}   # "chrN:pos" -> rsID
    resolved = 0
    B = 190
    for i in range(0, len(rsids), B):
        batch = rsids[i:i + B]
        for attempt in range(3):
            try:
                res = _post(batch)
                break
            except Exception as e:  # noqa
                if attempt == 2:
                    print(f"  batch {i}: error {e}", file=sys.stderr); res = {}
                else:
                    time.sleep(2)
        for rs, info in (res or {}).items():
            for mp in (info.get("mappings") or []):
                if mp.get("assembly_name") != "GRCh38":
                    continue
                chrom = str(mp.get("seq_region_name"))
                start = mp.get("start")
                if chrom in CANON and isinstance(start, int):
                    c = "chrM" if chrom == "MT" else "chr" + chrom
                    rsmap[f"{c}:{start}"] = rs
                    resolved += 1
                    break
        print(f"  resolved {resolved}/{len(rsids)}…", file=sys.stderr)

    # BED (sorted by chromosome/position)
    def key(k):
        c, p = k.split(":"); c = c[3:]
        order = {"X": 23, "Y": 24, "M": 25}
        if c in order:
            return (order[c], int(p))
        if c.isdigit():
            return (int(c), int(p))
        return (99, int(p))
    rows = sorted(rsmap, key=key)
    with open(OUT_BED, "w") as o:
        for k in rows:
            c, p = k.split(":"); p = int(p)
            o.write(f"{c}\t{p-1}\t{p}\n")
    json.dump(rsmap, open(OUT_MAP, "w"), ensure_ascii=False, indent=0)
    print(f"✓ resolved {len(rsmap)} positions out of {len(rsids)} rsIDs")
    print(f"BED: {OUT_BED}")
    print(f"rs↔pos map: {OUT_MAP}")
    print("Next: OUT=<project>/genome/longevity_sites.vcf.gz bash prs_genotype_sites.sh " + OUT_BED)


if __name__ == "__main__":
    main()
