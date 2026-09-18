#!/usr/bin/env python3
"""The monogenic half of a system panel, taken from a base that has a version.

    python3 src/tools/fetch_gencc.py --list                 # what it would fetch; fetches nothing
    python3 src/tools/fetch_gencc.py                        # download, filter, write the knowledge file
    python3 src/tools/fetch_gencc.py --save-raw <file.tsv>  # the same, keeping the export beside it
    python3 src/tools/fetch_gencc.py --from <file.tsv>      # read a saved export, no network at all
    python3 src/tools/fetch_gencc.py --age [--max-days N]   # how old the shipped file is; no network

GenCC — the Gene Curation Coalition — aggregates gene↔disease validity assertions
from ClinGen, Genomics England PanelApp, PanelApp Australia, Gene2Phenotype,
Orphanet, laboratories and others. Each row is one submitter's assertion: a
gene, a disease, a classification (Definitive … Refuted) and a MODE OF
INHERITANCE. That last field is the reason this tool exists. A panel written by
hand says «risk allele found, heterozygous» about a gene it does not know to be
recessive; the base says the gene is recessive, and then the heterozygote is a
carrier, not a person at risk. The field arrives with the gene, machine-readable,
and a list that comes from the base carries it for free.

**What this tool writes.** `knowledge/gencc_gene_disease.json`: the GenCC rows
for the genes whose disease names match a system's filter in
`knowledge/system_disease_terms.json`, grouped by system and by gene. Every
submitter's row is kept — GenCC does not re-check its submitters, and when five
of them disagree about one gene the disagreement is the finding, not something
to average away. Every classification is kept too, `Limited` and `Refuted`
included: which of them may be printed as a finding is the engine's decision,
and a base that had already made it would be a base nobody could check. Each row
is marked `mode: monogenic`, because a gene↔disease assertion must never be
printed in the same shape as a polygenic score or a pharmacogenetic phenotype.

**Address and terms, verified 12.09.2026.** The export lives at
https://thegencc.org/download/action/submissions-export-tsv?format=new
(the older `search.thegencc.org` host answers with a redirect to it, which this
tool refuses to follow — see `_NoRedirect`). The site states on every page that
«The GenCC data are available free of restriction under a CC0 1.0 Universal
(CC0 1.0) Public Domain Dedication» and asks for attribution to GenCC and the
contributing sources; that is compatible with the repository's Apache-2.0 code
and CC BY 4.0 knowledge base, so the filtered file may ship. Downloads count
against a per-address quota of 20 a day; HEAD requests and 304 answers do not,
so `--list` asks with HEAD and a download sends the ETag it last saw. The export
is refreshed weekly; the file records the export's own `Last-Modified` date, and
`--age` says how far behind the shipped copy is. The «new format» is the one to
use — the legacy format is withdrawn after 30.09.2026.

**With `SCHOLION_OFFLINE=1` this refuses before opening a socket.** `--from` and
`--age` make no request and work in that mode; nothing else does.

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "src" / "scholion" / "knowledge"
FILTER_FILE = KNOWLEDGE / "system_disease_terms.json"
OUT_FILE = KNOWLEDGE / "gencc_gene_disease.json"

HOST = "https://thegencc.org"
#: Verified 12.09.2026 with a HEAD request: 200, text/tab-separated-values,
#: 24 959 340 bytes, Last-Modified Sun, 06 Sep 2026, ETag an MD5 of the file.
URL = HOST + "/download/action/submissions-export-tsv?format=new"
LICENSE = ("CC0 1.0 Universal (CC0 1.0) Public Domain Dedication; GenCC requests "
           "attribution to GenCC and the contributing sources whenever possible")
#: The form the site's Terms of Use ask for, verbatim; the date accessed is the
#: `downloaded` field beside it. A journal reference is deliberately not written
#: here from memory — it would be a number about the outside world with no
#: record of how it was obtained.
CITATION = "The Gene Curation Coalition. https://thegencc.org [date accessed: see `downloaded`]"
USER_AGENT = "scholion-fetch-gencc"

#: The shipped snapshot is «stale» past this many days. GenCC refreshes weekly,
#: but a classification changes rarely and a panel is read for months; a quarter
#: plus the time a release takes to travel is when the difference starts to
#: matter to a reader. `--max-days` overrides it.
DEFAULT_MAX_DAYS = 120

#: Mode of inheritance as GenCC spells it, in the eight-letter alphabet the engine
#: reads. The HPO curie is preferred — it is what the submitter chose from a
#: list — and the title is the fallback for a row that has no curie. Anything
#: outside the alphabet (Y-linked, digenic, somatic) stays «unknown» here and
#: keeps its original spelling beside it, so the reader is told less, never
#: something wrong.
_MOI_BY_CURIE = {
    "HP:0000006": "AD",
    "HP:0000007": "AR",
    "HP:0001417": "XL",
    "HP:0001419": "XLR",
    "HP:0001423": "XLD",
    "HP:0001427": "MT",
    "HP:0032113": "SD",
    "HP:0000005": "unknown",
}
_MOI_BY_TITLE = (
    ("autosomal dominant", "AD"),
    ("autosomal recessive", "AR"),
    ("x-linked recessive", "XLR"),
    ("x-linked dominant", "XLD"),
    ("x-linked", "XL"),
    ("mitochondrial", "MT"),
    ("semidominant", "SD"),
)

#: Column names of the export, by role. The new format puts a submission id and
#: its version first; the legacy one a composite uuid. Everything this tool
#: needs is looked up BY NAME, so a column moving does not move the meaning —
#: and a column missing is refused by name (see `_columns`), not read as empty.
_COLS = {
    "gene": "gene_symbol",
    "hgnc": "gene_curie",
    "disease": "disease_title",
    "disease_id": "disease_curie",
    "disease_original": "disease_original_title",
    "classification": "classification_title",
    "moi_title": "moi_title",
    "moi_curie": "moi_curie",
    "submitter": "submitter_title",
    "curated_on": "submitted_as_date",
}
_OPTIONAL = {"disease_original", "moi_curie", "hgnc"}
_REQUIRED = [v for k, v in _COLS.items() if k not in _OPTIONAL]


def offline() -> bool:
    return os.environ.get("SCHOLION_OFFLINE", "").strip() in ("1", "true", "yes")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect. The host is checked once, when the address is
    written down here; `urlopen` follows 3xx by default, and a checked host
    answering with one would land the download on a host nobody checked. The
    same reasoning as in the product's network layer and in the demo-genome
    fetcher, written down there first."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _opener() -> "urllib.request.OpenerDirector":
    return urllib.request.build_opener(_NoRedirect())


def _checked(url: str) -> str:
    if not url.startswith(HOST + "/"):
        raise SystemExit(f"! refusing to fetch from {url} — it is not under {HOST}.")
    return url


def _head(url: str) -> Dict[str, Any]:
    """Size, date and ETag of the export, asked without spending the quota."""
    req = urllib.request.Request(_checked(url), method="HEAD", headers={"User-Agent": USER_AGENT})
    with _opener().open(req, timeout=30) as r:                                    # noqa: S310
        h = r.headers
        return {"status": getattr(r, "status", 200),
                "size": int(h.get("Content-Length") or 0) or None,
                "last_modified": h.get("Last-Modified"),
                "etag": h.get("ETag"),
                "content_type": h.get("Content-Type")}


def _get(url: str, etag: Optional[str] = None) -> Tuple[Optional[bytes], Dict[str, Any]]:
    """The export itself. With an ETag from a previous pull the request is
    conditional, and a 304 — which the quota does not count — comes back as
    `(None, headers)` so the caller keeps what it has."""
    headers = {"User-Agent": USER_AGENT}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(_checked(url), headers=headers)
    try:
        with _opener().open(req, timeout=300) as r:                                # noqa: S310
            h = r.headers
            return r.read(), {"last_modified": h.get("Last-Modified"), "etag": h.get("ETag")}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, {"last_modified": e.headers.get("Last-Modified"), "etag": e.headers.get("ETag")}
        raise


def _http_date(value: Optional[str]) -> Optional[str]:
    """`Sun, 06 Sep 2026 06:01:23 GMT` → `2026-09-06`. A date the reader can
    compare with a calendar; the raw header is kept beside it."""
    if not value:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return None


# ── the filter ────────────────────────────────────────────────────────────

def load_filter(path: Path = FILTER_FILE) -> Dict[str, Any]:
    d = json.loads(path.read_text(encoding="utf-8"))
    systems = d.get("systems") or {}
    if not isinstance(systems, dict):
        raise SystemExit(f"! {path.name}: `systems` must be an object keyed by radar domain")
    return d


def active_systems(filt: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """The systems whose filter says something. An entry with no terms and no
    ids is a system nobody has curated yet, and it stays out of the output
    rather than appearing with zero genes — «no list» and «a list with no
    genes» are different states and the file must not blur them."""
    out = {}
    for key, spec in (filt.get("systems") or {}).items():
        terms = [t.strip().lower() for t in (spec.get("terms") or []) if t and t.strip()]
        ids = [i.strip() for i in (spec.get("mondo_ids") or []) if i and i.strip()]
        # A substring that must NOT be in the title: `cystinuria` is inside
        # `homocystinuria` and `gout` inside `Aicardi-Goutieres`, and no choice
        # of positive terms separates them (added 13.09.2026, composing the
        # ten remaining systems).
        exclude = [e.strip().lower() for e in (spec.get("exclude") or []) if e and e.strip()]
        if terms or ids:
            if not spec.get("source"):
                raise SystemExit(f"! {key}: a filter with terms must name its `source`; "
                                 "a list with no provenance is an opinion.")
            out[key] = {"terms": terms, "ids": set(ids), "source": spec["source"],
                        "exclude": exclude}
    return out


def match(spec: Dict[str, Any], row: Dict[str, str]) -> Optional[str]:
    """Which term (or id) of a system's filter this row satisfies, if any.
    Substrings, case-insensitive, against the harmonised disease title and the
    submitter's original title — the two can differ, and a filter written from
    one spelling should not miss the other."""
    ids = spec["ids"]
    if ids and row.get("disease_id") in ids:
        return row["disease_id"]
    names = [(row.get("disease") or "").lower(), (row.get("disease_original") or "").lower()]
    if any(e in n for e in spec.get("exclude") or [] for n in names):
        return None
    for term in spec["terms"]:
        for name in names:
            if term in name:
                return term
    return None


# ── the export ────────────────────────────────────────────────────────────

def _columns(header: List[str]) -> Dict[str, int]:
    """The index of each column this tool reads. A required column that is not
    in the header stops the run by name: an export whose layout changed must be
    looked at, not read through a hole."""
    idx = {name: i for i, name in enumerate(header)}
    missing = [c for c in _REQUIRED if c not in idx]
    if missing:
        raise SystemExit("! the export does not carry the column(s) this tool reads: "
                         f"{', '.join(missing)}. Its header is: {', '.join(header[:12])} …\n"
                         "  The layout has changed; nothing was written.")
    return {role: idx[col] for role, col in _COLS.items() if col in idx}


def normalise_moi(curie: str, title: str) -> str:
    code = _MOI_BY_CURIE.get((curie or "").strip())
    if code:
        return code
    low = (title or "").strip().lower()
    for prefix, code in _MOI_BY_TITLE:
        if low.startswith(prefix):
            return code
    return "unknown"


def parse_rows(text: str) -> Iterable[Dict[str, str]]:
    """The export as plain dicts, one per submission, by role name."""
    reader = csv.reader(io.StringIO(text), delimiter="\t", quotechar='"')
    header = next(reader, None)
    if not header:
        raise SystemExit("! the export is empty.")
    cols = _columns([h.strip() for h in header])
    # The new format's first two columns identify the submission and its version;
    # kept under a neutral name so the engine can cite a row exactly.
    id_col = 0 if header[0].strip() not in _COLS.values() else None
    for raw in reader:
        if not raw or all(not c.strip() for c in raw):
            continue
        row = {role: (raw[i].strip() if i < len(raw) else "") for role, i in cols.items()}
        if id_col is not None:
            row["submission_id"] = raw[id_col].strip()
            if len(header) > 1 and "version" in header[1].strip().lower():
                row["submission_version"] = raw[1].strip() if len(raw) > 1 else ""
        yield row


def compose(rows: Iterable[Dict[str, str]], systems: Dict[str, Dict[str, Any]],
            export_date: Optional[str]) -> Tuple[Dict[str, Any], int]:
    """Group the matching rows by system and gene. Returns the `systems` block
    and the number of export rows read."""
    out: Dict[str, Any] = {k: {"source": v["source"], "genes": {}} for k, v in systems.items()}
    total = 0
    for row in rows:
        total += 1
        for key, spec in systems.items():
            hit = match(spec, row)
            if hit is None:
                continue
            gene = row.get("gene") or ""
            if not gene:
                continue
            entry = out[key]["genes"].setdefault(gene, {"hgnc_id": row.get("hgnc") or None,
                                                        "submissions": []})
            item = {
                "disease": row.get("disease") or "",
                "disease_id": row.get("disease_id") or "",
                "classification": row.get("classification") or "",
                "moi": row.get("moi_title") or "",
                "moi_code": normalise_moi(row.get("moi_curie") or "", row.get("moi_title") or ""),
                "submitter": row.get("submitter") or "",
                "curated_on": row.get("curated_on") or "",
                "gencc_version_or_date": export_date,
                "mode": "monogenic",
                "matched": hit,
            }
            if row.get("submission_id"):
                item["submission_id"] = row["submission_id"]
                if row.get("submission_version"):
                    item["submission_version"] = row["submission_version"]
            entry["submissions"].append(item)
    for key in list(out):
        genes = out[key]["genes"]
        if not genes:
            # A filter that matched nothing in THIS export is left out, as the
            # filter file promises: «no list» and «a list with no genes» must
            # stay different on the screen (a system with zero genes was
            # written until 13.09.2026, when every system got a filter and a
            # small export showed it).
            del out[key]
            continue
        out[key]["genes"] = {g: genes[g] for g in sorted(genes)}
        out[key]["gene_count"] = len(genes)
    return out, total


def build(text: str, filt: Dict[str, Any], *, export_date: Optional[str],
          export_meta: Dict[str, Any], downloaded: str, origin: str) -> Dict[str, Any]:
    systems = active_systems(filt)
    if not systems:
        raise SystemExit("! no system in the filter file names a single term; nothing to compose.")
    block, total = compose(parse_rows(text), systems, export_date)
    fmeta = filt.get("_meta") or {}
    meta = {
        "purpose": ("A SHARED PUBLIC LAYER. Gene↔disease validity assertions from GenCC for the "
                    "genes whose disease names match a system's filter — the monogenic half of a "
                    "system panel, generated from a base with a version rather than written by "
                    "hand. Nobody's genotypes are here."),
        "source": "GenCC — the Gene Curation Coalition, submissions export (TSV, new format)",
        "source_url": URL,
        "license": LICENSE,
        "citation": CITATION,
        "downloaded": downloaded,
        # The stamp the local-refresh comparison reads (core.knowledge_precedence).
        # It used to be added by hand after each run, and a run that forgot left
        # the bundled file with no date to compare a local copy against.
        "updated": _dt.date.today().isoformat(),
        "origin": origin,
        "export_last_modified": export_date,
        "export_last_modified_header": export_meta.get("last_modified"),
        "export_etag": export_meta.get("etag"),
        "export_rows_read": total,
        "filter_file": FILTER_FILE.name,
        "filter_version": fmeta.get("version"),
        "mode": "monogenic",
        "kept": ("Every submitter's row and every classification, Limited/Disputed/Refuted "
                 "included. GenCC does not re-check its submitters; a disagreement between two "
                 "of them is shown, never averaged. Which classifications may be printed as a "
                 "finding is decided by the engine, not here."),
        "moi_code": ("Normalised mode of inheritance: AD, AR, XL, XLR, XLD, MT, SD or unknown. "
                     "`moi` beside it is GenCC's own spelling; a mode outside this alphabet "
                     "stays unknown here and keeps its spelling."),
        "schema": ("systems: { <radar domain key>: { source, gene_count, genes: { SYMBOL: { hgnc_id, "
                   "submissions: [ { disease, disease_id, classification, moi, moi_code, submitter, "
                   "curated_on, gencc_version_or_date, mode, matched, submission_id?, "
                   "submission_version? } ] } } } }"),
        "caveats": ("An aggregator's export, not a diagnosis: a gene here is a gene for which "
                    "somebody has asserted a link to a disease of the system, with the strength "
                    "they asserted. A substring filter over disease names misses a syndrome named "
                    "after a person; add its MONDO id to the filter rather than widening a term."),
        "source_tier": "guideline_verbatim",
        "source_tier_note": ("The rows are GenCC's submissions verbatim — disease, classification, "
                             "inheritance, submitter and date as exported. Only `moi_code`, `mode`, "
                             "`matched` and the grouping by system are this project's."),
        "regenerate": "python3 src/tools/fetch_gencc.py",
    }
    return {"_meta": meta, "systems": block}


def write(doc: Dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ── freshness ─────────────────────────────────────────────────────────────

def age(out: Path = OUT_FILE, today: Optional[_dt.date] = None) -> Dict[str, Any]:
    """How old the shipped file is, by the two dates it records: when it was
    pulled and when GenCC last refreshed the export it was pulled from. The
    second is the one that matters — a pull made yesterday of an export
    refreshed in March is a March file."""
    if not out.exists():
        return {"present": False, "file": str(out)}
    meta = (json.loads(out.read_text(encoding="utf-8")).get("_meta") or {})
    today = today or _dt.date.today()
    rep: Dict[str, Any] = {"present": True, "file": str(out),
                           "downloaded": meta.get("downloaded"),
                           "export_last_modified": meta.get("export_last_modified"),
                           "filter_version": meta.get("filter_version")}
    for k in ("downloaded", "export_last_modified"):
        v = meta.get(k)
        try:
            rep[k + "_days"] = (today - _dt.date.fromisoformat(v)).days if v else None
        except ValueError:
            rep[k + "_days"] = None
    return rep


def _print_age(rep: Dict[str, Any], max_days: int) -> int:
    if not rep["present"]:
        print(f"no shipped file at {rep['file']} — the monogenic half is authored by hand until "
              "one is fetched.")
        return 1
    print(f"{Path(rep['file']).name}: pulled {rep['downloaded']} "
          f"({rep['downloaded_days']} days ago), export dated {rep['export_last_modified']} "
          f"({rep['export_last_modified_days']} days ago), filter version {rep['filter_version']}")
    d = rep.get("export_last_modified_days")
    if d is None:
        print("  ! the file does not say when its export was refreshed — treat as stale.")
        return 1
    if d > max_days:
        print(f"  ! older than {max_days} days. GenCC refreshes weekly: python3 src/tools/fetch_gencc.py")
        return 1
    print(f"  fresh enough (limit {max_days} days).")
    return 0


# ── main ──────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="say what would be fetched; fetch nothing")
    ap.add_argument("--from", dest="from_file", default=None,
                    help="read a saved export instead of the network")
    ap.add_argument("--export-date", default=None,
                    help="with --from: the export's own date (YYYY-MM-DD); default: the file's mtime")
    ap.add_argument("--etag", default=None,
                    help="with --from: the ETag the export was served with, so the next "
                         "download can be conditional and cost no quota")
    ap.add_argument("--save-raw", default=None, help="keep the downloaded export at this path")
    ap.add_argument("--filter", default=str(FILTER_FILE), help="the per-system filter file")
    ap.add_argument("--out", default=str(OUT_FILE), help="where to write the composed file")
    ap.add_argument("--age", action="store_true", help="report how old the shipped file is; no network")
    ap.add_argument("--max-days", type=int, default=DEFAULT_MAX_DAYS,
                    help=f"with --age: exit 1 past this many days (default {DEFAULT_MAX_DAYS})")
    a = ap.parse_args(argv)

    out = Path(a.out).expanduser()
    if a.age:
        return _print_age(age(out), a.max_days)

    filt = load_filter(Path(a.filter).expanduser())
    today = _dt.date.today().isoformat()

    if a.from_file:
        src = Path(a.from_file).expanduser()
        text = src.read_text(encoding="utf-8")
        export_date = a.export_date or _dt.date.fromtimestamp(src.stat().st_mtime).isoformat()
        doc = build(text, filt, export_date=export_date,
                    export_meta={"etag": a.etag, "last_modified": None},
                    downloaded=today, origin=f"--from {src.name}, a saved copy of {URL}")
        write(doc, out)
        _report(doc, out)
        return 0

    # Everything past this line talks to the network, and --list is not exempt:
    # a HEAD is a request too. The refusal comes BEFORE a socket is opened.
    if offline():
        print("SCHOLION_OFFLINE=1 is set. This tool downloads on purpose, so it stops here; "
              "use --from <saved export> or --age, which need no network. Nothing was fetched.")
        return 1

    print(f"GenCC submissions export — {LICENSE}")
    print(f"  {URL}")
    try:
        h = _head(URL)
    except (urllib.error.URLError, OSError) as e:
        print(f"  ! the server did not answer a HEAD request: {e}")
        if a.list:
            return 1
        h = {}
    if h:
        size = h.get("size")
        print(f"  {size / (1 << 20):.1f} MB" if size else "  the server did not say how big it is",
              f"· export dated {h.get('last_modified') or '?'} · ETag {h.get('etag') or '?'}")
    if a.list:
        print("\n(--list: nothing was downloaded; a HEAD request does not count against the quota)")
        return 0

    # A previous pull's ETag makes the request conditional: an unchanged export
    # answers 304, costs no quota, and the file on disk is left as it is.
    prev_etag = None
    if out.exists():
        try:
            prev_etag = (json.loads(out.read_text(encoding="utf-8")).get("_meta") or {}).get("export_etag")
        except (OSError, ValueError):
            prev_etag = None
    data, meta = _get(URL, etag=prev_etag)
    if data is None:
        print(f"  the export has not changed since the shipped file was pulled (ETag {prev_etag}); "
              "nothing was rewritten.")
        return 0
    print(f"  downloaded {len(data) / (1 << 20):.1f} MB")
    if a.save_raw:
        raw = Path(a.save_raw).expanduser()
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(data)
        print(f"  raw export kept at {raw}")
    text = data.decode("utf-8", "replace")
    doc = build(text, filt, export_date=_http_date(meta.get("last_modified")),
                export_meta=meta, downloaded=today, origin=URL)
    write(doc, out)
    _report(doc, out)
    return 0


def _report(doc: Dict[str, Any], out: Path) -> None:
    m = doc["_meta"]
    print(f"\n  wrote {out} ({out.stat().st_size // 1024} KB) — {m['export_rows_read']} export rows read,"
          f" export dated {m['export_last_modified']}, filter version {m['filter_version']}")
    for key, sysblock in doc["systems"].items():
        n = sum(len(g["submissions"]) for g in sysblock["genes"].values())
        print(f"    {key}: {sysblock['gene_count']} genes, {n} submissions")


if __name__ == "__main__":
    raise SystemExit(main())
