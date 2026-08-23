#!/usr/bin/env python3
"""Build a PORTABLE LongevityMap catalog → knowledge/longevitymap.json.

LongevityMap (HAGR, genomics.senescence.info) is a curated database of genetic
variants associated with longevity. It is a SHARED PUBLIC catalog: it holds
nobody's genotypes, is the same for everyone, and travels freely with the code.
Each person applies THE SAME catalog to THEIR OWN full VCF (by rsID).

Run (on a machine with internet access, e.g. the Mac):
    python3 build_longevitymap.py            # downloads the zip and builds the JSON
    python3 build_longevitymap.py FILE.csv   # build from an already downloaded file

The schema of the source file is not fixed in the HAGR documentation, so the parser is
ADAPTIVE: it identifies columns by fuzzy header matching and pulls rsIDs out of any
field with a regex. If the structure changes, the script will not break.
"""
from __future__ import annotations
import csv, io, json, re, sys, urllib.request, urllib.error, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # src/ — for `scholion`
from scholion import net                                       # noqa: E402

URL = "https://genomics.senescence.info/longevity/longevity_genes.zip"
OUT = Path(__file__).resolve().parents[1] / "scholion" / "knowledge" / "longevitymap.json"
RS = re.compile(r"\brs\d+\b", re.I)
PMID = re.compile(r"\b\d{6,9}\b")


def _download() -> bytes:
    print(f"↓ {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": "Scholion/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.URLError as e:
        # macOS Python.framework often has no root certificates, so verification
        # fails on a machine where nothing at all is wrong with the network. That
        # is the one case worth a second attempt — and whether this is that case
        # is not decided here. `net.certificate_fallback` checks that the failure
        # really was the certificate and that the person allowed the retry
        # (SCHOLION_TLS_INSECURE=1); otherwise it raises and nothing is fetched.
        #
        # What stood here decided from the TEXT of the error and retried with
        # nobody's permission, and the comment justifying it was wrong on the
        # point that mattered: the zip's own integrity check does not make an
        # unverified download safe. A CRC catches a damaged transfer, not a
        # substituted one — whoever can present a certificate this code is no
        # longer looking at can also hand it a perfectly well-formed archive.
        # And this archive becomes knowledge/longevitymap.json, which ships.
        with urllib.request.urlopen(req, timeout=120,
                                    context=net.certificate_fallback(e)) as r:
            return r.read()


def _rows_from_zip(blob: bytes):
    zf = zipfile.ZipFile(io.BytesIO(blob))
    name = next((n for n in zf.namelist() if n.lower().endswith((".csv", ".txt", ".tsv"))), zf.namelist()[0])
    print(f"  unpacked: {name}")
    raw = zf.read(name).decode("utf-8", "replace")
    return _parse_table(raw)


def _parse_table(raw: str):
    # detect the delimiter
    sample = raw[:4000]
    delim = "\t" if sample.count("\t") >= sample.count(",") else ","
    return list(csv.DictReader(io.StringIO(raw), delimiter=delim))


def _pick(headers, *needles):
    for h in headers:
        hl = h.lower()
        if any(n in hl for n in needles):
            return h
    return None


def build(rows) -> dict:
    if not rows:
        raise SystemExit("the LongevityMap table is empty")
    headers = list(rows[0].keys())
    col_gene = _pick(headers, "gene", "symbol")
    col_var = _pick(headers, "variant", "rsid", "rs id", "snp", "polymorph")
    col_pop = _pick(headers, "population", "ethnic", "cohort")
    col_assoc = _pick(headers, "association", "significan", "conclusion", "result")
    col_pmid = _pick(headers, "pubmed", "pmid", "reference")
    col_id = _pick(headers, "id")
    print(f"  columns: gene={col_gene} var={col_var} pop={col_pop} assoc={col_assoc} pmid={col_pmid}")

    variants: dict[str, dict] = {}
    genes: dict[str, set] = {}
    n_assoc_total = 0
    for row in rows:
        blob = " ".join(str(v) for v in row.values() if v)
        rsids = set(m.group(0).lower() for m in RS.finditer((row.get(col_var) or "") if col_var else "")) \
            or set(m.group(0).lower() for m in RS.finditer(blob))
        gene = (row.get(col_gene) or "").strip() if col_gene else ""
        pop = (row.get(col_pop) or "").strip() if col_pop else ""
        assoc = (row.get(col_assoc) or "").strip() if col_assoc else ""
        pmids = set(PMID.findall((row.get(col_pmid) or "")) if col_pmid else [])
        if not rsids:
            # a record without an rsID (e.g. gene only) — kept in the gene index
            if gene:
                genes.setdefault(gene, set())
            continue
        n_assoc_total += 1
        for rs in rsids:
            v = variants.setdefault(rs, {"gene": gene, "populations": set(),
                                         "associations": set(), "pmids": set(), "studies": 0})
            if gene and not v["gene"]:
                v["gene"] = gene
            if pop:
                v["populations"].add(pop)
            if assoc:
                v["associations"].add(assoc)
            v["pmids"].update(pmids)
            v["studies"] += 1
            if gene:
                genes.setdefault(gene, set()).add(rs)

    # serialise the sets
    var_out = {}
    for rs, v in sorted(variants.items()):
        var_out[rs] = {
            "gene": v["gene"],
            "populations": sorted(v["populations"]),
            "associations": sorted(v["associations"]),
            "pmids": sorted(v["pmids"]),
            "studies": v["studies"],
        }
    gene_out = {g: sorted(rs) for g, rs in sorted(genes.items()) if rs}

    return {
        "_meta": {
            "source": "LongevityMap (HAGR) — genomics.senescence.info/longevity",
            "license": "HAGR free for all purposes (genomics.senescence.info/legal.html)",
            "purpose": ("A SHARED PUBLIC catalogue of variants associated with longevity "
                        "(rsID → gene/population/association/PMID). It contains nobody's genotypes. "
                        "It is applied to a personal VCF by rsID, like loci.json."),
            "note": ("The associations from the literature are of varying strength; many have not "
                     "been reproduced and depend on the population. Use it as a research layer "
                     "with caveats, not as a diagnosis."),
            "variant_count": len(var_out),
            "gene_count": len(gene_out),
            "association_records": n_assoc_total,
        },
        "variants": var_out,
        "genes": gene_out,
    }


def main():
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        raw = p.read_bytes()
        rows = _rows_from_zip(raw) if p.suffix.lower() == ".zip" else _parse_table(raw.decode("utf-8", "replace"))
    else:
        rows = _rows_from_zip(_download())
    cat = build(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    m = cat["_meta"]
    print(f"✓ {OUT}")
    print(f"  variants: {m['variant_count']}, genes: {m['gene_count']}, association records: {m['association_records']}")


if __name__ == "__main__":
    main()
