"""reconcile.py — an audit of the completeness of labs.json against the source PDFs (READ ONLY).

Why: the main lesson is that a form can lie in the folder while its data never reaches the
structured profile (labs.json), and nobody finds out. Especially when the PDF is a scan
without a text layer or an iCloud «placeholder» that cannot be read. `ingest-labs` skips
such files silently and marks them processed. reconcile closes that hole.

What it does:
  - walks ALL PDFs in the folder (no skip manifest — it always re-reads everything);
  - extracts markers with the same dictionary knowledge/lab_markers.json;
  - checks them against labs.json and sorts them into:
      missing    — the value is in the PDF but not in the profile (a candidate for entry);
      mismatch   — the date matches but the value diverges (an error / a unit conflict → manual check);
      unreadable — the PDF gave up no text (a scan / a placeholder) — EXPLICITLY, not silently;
      covered    — matched the profile (a self-check: trust in the extraction of that marker);
  - writes the provenance profile/labs_coverage.json (marker → date → source file).

Writes NOTHING into labs.json. Run: python -m scholion reconcile [--lab-dir PATH] [--json]
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core, ingest_labs
from .i18n import t as _t

_MIN_TEXT = 200  # less than this counts as «no text layer» (a scan / a placeholder)


_LAB_FOLDER_NAMES = ("Лабораторные исследования", "Лабораторные_исследования")
# The candidate names are PATHS on somebody's disk, not text: they are what the
# folder is actually called, and renaming them in a translation would stop it
# being found.


def _default_lab_dir() -> Optional[Path]:
    """Where the PDF forms are, when nobody said. Never outside the data directory.

    This function used to look at `repo_dir().parent` — one directory ABOVE the
    project. It was harmless while the delivery had a container level, whose
    parent held nothing but the delivery. When v2.6.0 removed that level "so that
    the build root is the project", the package moved one directory up and its
    parent became the folder where the owner keeps everything, the real forms
    included. An unpacked package, exercised in place, read 570 KB of one
    person's lab history and wrote the provenance back inside itself.

    The first repair gated the outside search on "does this profile hold real
    data", and the next run leaked again — into `demo/profile/`, because the demo
    profile is synthetic AND filled, so the heuristic said yes. That second
    failure is the useful one: the fault was never the condition, it was having a
    condition at all. A guess about somebody's disk that ends in reading medical
    documents cannot be made safe by making it cleverer.

    So there is no guess. Outside the data directory requires an answer:
    `--lab-dir`, `SCHOLION_LABS_DIR`, or putting the forms in `raw/lab/`, which
    is the slot the data layout declares for exactly this. What is lost is one
    convenience for one existing setup; `selfcheck` names the candidate it can
    see and asks, instead of reading it.

      1. `SCHOLION_LABS_DIR` — always honoured, it is a decision;
      2. `profile/sources.json` — the person's own permanent setting;
      3. `raw/lab/` — the declared slot, wherever that slot points;
      4. a folder by name INSIDE the data directory.

    Step 2 is what makes the refusal usable rather than merely safe. `set-folder
    labs_docs` already existed and was already honoured by `ingest-labs` — but
    not here, so the first version of this repair left `reconcile` and
    `selfcheck` with no way at all to be told where the forms are. Removing a
    guess without leaving an answer in its place is not a fix, it is a smaller
    product.
    """
    import os
    env = os.environ.get("SCHOLION_LABS_DIR")
    if env and Path(env).expanduser().is_dir():
        return Path(env).expanduser()

    chosen = core.source_config().get("labs_docs")
    if chosen and Path(chosen).expanduser().is_dir():
        return Path(chosen).expanduser()

    lab_slot = core.raw_dir("lab")
    if lab_slot.is_dir() and any(lab_slot.iterdir()):
        return lab_slot

    data = core.repo_dir()
    for name in _LAB_FOLDER_NAMES:
        cand = data / name
        if cand.is_dir():
            return cand
    return None


def nearby_candidate() -> Optional[Path]:
    """A folder of forms that is visible but will NOT be read without being named.

    Kept apart from `_default_lab_dir` on purpose: this one only ever produces a
    sentence for a person to read, never a path the code opens. That separation
    is the whole point — the discoverability survives, the automatic reading does
    not.
    """
    parent = core.repo_dir().parent
    for name in _LAB_FOLDER_NAMES:
        cand = parent / name
        if cand.is_dir():
            return cand
    return None


def _ym(date: Optional[str]) -> Optional[str]:
    """YYYY-MM-DD | YYYY-MM -> YYYY-MM (the granularity of the profile)."""
    if not date:
        return None
    m = re.match(r"(\d{4})-(\d{2})", date)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.05, abs(b) * 0.02)


def reconcile(lab_dir: Optional[str] = None, ocr: bool = False) -> Dict[str, Any]:
    root = Path(lab_dir).expanduser() if lab_dir else _default_lab_dir()
    if not root or not root.is_dir():
        # A folder that is visible but was not named is reported, not opened.
        # Naming it costs the reader one command and buys the guarantee that
        # nothing is read on a guess.
        hint = nearby_candidate()
        return {"ok": False,
                "error": _t("reconcile.no_folder",
                            path=root or _t("reconcile.autodetect_failed")),
                "candidate": str(hint) if hint else None,
                "candidate_hint": _t("reconcile.candidate_hint", path=hint) if hint else None}
    markers = core.lab_markers().get("markers", {})
    labs = core.labs().get("markers", {})
    # the profile index: marker -> {ym -> value}
    prof: Dict[str, Dict[str, float]] = {}
    for k, m in labs.items():
        prof[k] = {p["date"]: p["value"] for p in m.get("series", []) if "date" in p}

    files = sorted(root.rglob("*.pdf"))
    unreadable: List[Dict[str, Any]] = []
    non_lab = 0
    missing: List[Dict[str, Any]] = []
    mismatch: List[Dict[str, Any]] = []
    alt_method: List[Dict[str, Any]] = []
    covered = 0
    coverage: Dict[str, Dict[str, Dict[str, str]]] = {}
    seen_markers: set = set()

    for f in files:
        try:
            size = f.stat().st_size
        except Exception:
            size = 0
        text = ingest_labs._read_pdf(f)
        if text is None:
            text = ""
        if len(text.strip()) < _MIN_TEXT:
            if ocr:
                text = _ocr(f) or text
            if len(text.strip()) < _MIN_TEXT:
                reason = _t("reconcile.no_text_layer" if size > 0 else "reconcile.empty_file")
                unreadable.append({"file": _rel(f, root), "reason": reason, "bytes": size})
                continue
        if not (ingest_labs._DATE.search(text) or ingest_labs._DATE_FALLBACK.search(text)):
            non_lab += 1
            continue
        low = text.lower()
        # There used to be a rejection of a «genetic report» here by the words «полиморфизм /
        # nm_0 / генетическ» BEFORE parsing. It broke HYBRID forms: «Гормоны мочи» (estrogen
        # metabolites) print both a table of measurements and a section of COMT/CYP1B1
        # polymorphisms — the file was discarded whole, and its est_* points were invisible to
        # both reconciliations (in reconcile they fell neither into covered nor into missing;
        # in the provenance they hung as «manual»). The rejection is not needed: a purely
        # genetic report yields no marker at all and is cut off by the `not found` check below.
        date, found = ingest_labs.parse_report(text, markers, source=str(f))
        ym = _ym(date)
        if not ym or not found:
            non_lab += 1
            continue
        for key, v in found.items():
            seen_markers.add(key)
            val = v["value"]
            slot = coverage.setdefault(key, {}).setdefault(
                ym, {"file": _rel(f, root), "draw_date": date, "value": val, "sources": []})
            # ALL sources for a (marker, month), not just the first: otherwise the reverse check
            # falsely complains about the second method of the same draw (LC-MS vs immunoassay).
            src = {"file": _rel(f, root), "draw_date": date, "value": val,
                   "form": _form_of(_rel(f, root), low)}
            if src not in slot["sources"]:
                slot["sources"].append(src)
            if key not in prof:
                missing.append({"marker": key, "date": ym, "value": val,
                                "unit": markers[key].get("unit"), "file": _rel(f, root),
                                "reason": _t("reconcile.marker_absent")})
            elif ym not in prof[key]:
                missing.append({"marker": key, "date": ym, "value": val,
                                "unit": markers[key].get("unit"), "file": _rel(f, root),
                                "reason": _t("reconcile.point_absent")})
            elif not _close(val, prof[key][ym]):
                # Not a divergence but the second method of the same draw: the marker has a
                # preferred form declared (prefer_form, e.g. the LC-MS steroid profile), and
                # the profile holds the value from exactly that one. Otherwise such pairs hang
                # in «divergences» forever and screen off the real omissions.
                pf = [x.lower() for x in core.marker_rules(markers[key], "prefer_form")]
                if pf and not any(x in low for x in pf):
                    alt_method.append({"marker": key, "date": ym, "pdf": val,
                                       "profile": prof[key][ym], "file": _rel(f, root)})
                else:
                    mismatch.append({"marker": key, "date": ym, "pdf": val,
                                     "profile": prof[key][ym], "file": _rel(f, root)})
            else:
                covered += 1

    # The provenance goes to the PROFILE directory, which is where the profile
    # lives. It used to be written to `repo_dir()/profile` — a path built from
    # where the CODE is, so `SCHOLION_PROFILE_DIR` had no say over it. That is
    # why the test suite, whose whole isolation model is that variable, could not
    # protect against this file: the tests pointed the profile at a fixture and
    # the write went somewhere else entirely, into the source tree or into an
    # unpacked package. For an ordinary setup the two paths are the same folder,
    # so nothing moves; they differ exactly where it matters.
    cov_path = core.profile_dir() / "labs_coverage.json"
    try:
        core.write_json(cov_path,
            {"_meta": {"generated_by": "scholion reconcile", "lab_dir": str(root),
                       "note": _t("reconcile.coverage_note")},
             "coverage": coverage}, indent=1)
        cov_written = str(cov_path)
    except Exception as e:
        cov_written = _t("reconcile.coverage_not_written", error=e)

    # make missing unique by (marker,date)
    seen = set(); miss_u = []
    for r in missing:
        k = (r["marker"], r["date"])
        if k in seen:
            continue
        seen.add(k); miss_u.append(r)
    miss_u.sort(key=lambda r: (r["marker"], r["date"]))
    mismatch.sort(key=lambda r: (r["marker"], r["date"]))
    alt_method.sort(key=lambda r: (r["marker"], r["date"]))

    return {"ok": True, "lab_dir": str(root),
            "files_total": len(files), "files_non_lab": non_lab,
            "unreadable": unreadable, "missing": miss_u, "mismatch": mismatch, "alt_method": alt_method,
            "covered_points": covered, "markers_seen": sorted(seen_markers),
            "coverage_path": cov_written, "disclaimer": core.labs().get("_meta", {}).get("note", "")[:0]}


# The first element is a catalogue key — the assay method, printed next to a value in the
# reverse check. The rest are the Russian substrings SEARCHED FOR in the form itself: input,
# not output, and therefore not translated.
_FORMS = (("form.lcms", ("жх-мс", "лх-мс", "(ответ мс)", "масс-спектром")),
          ("form.clia", ("ихла", "иммунохим", "иммунохемилюм")),
          ("form.elisa", ("иммунофермент",)),
          ("form.icpms", ("исп-мс",)),
          ("form.biochemistry", ("биохим", "клиническая химия")),
          ("form.cbc", ("общий анализ крови", "гематолог")),
          ("form.urine", ("моча", "мочи")))


def _form_of(rel: str, low: str) -> str:
    """The method/form of the source — so the reverse check tells a second method from an error."""
    hay = (rel + " " + low[:4000]).lower()
    for key, needles in _FORMS:
        if any(k in hay for k in needles):
            return _t(key)
    return "—"


def _rel(f: Path, root: Path) -> str:
    try:
        return str(f.relative_to(root))
    except Exception:
        return f.name


def _ocr(path: Path) -> Optional[str]:
    """OCR as a last resort (needs pdftoppm + tesseract with rus)."""
    import shutil, subprocess, tempfile, os
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["pdftoppm", "-r", "200", "-png", str(path), os.path.join(td, "p")],
                           timeout=120, capture_output=True)
            out = []
            for png in sorted(Path(td).glob("p*.png")):
                r = subprocess.run(["tesseract", str(png), "stdout", "-l", "rus"],
                                   timeout=120, capture_output=True, text=True)
                out.append(r.stdout)
            return "\n".join(out)
    except Exception:
        return None


def selfcheck_summary(res: Dict[str, Any]) -> str:
    """A short self-check banner for the start of the application or a session.
    PASS/FAIL is tied to unreadable — it is unreadable forms that lose data silently.
    missing/mismatch are informational (a manual check), they do not turn the status red."""
    if not res.get("ok"):
        return _t("selfcheck.failed", error=res.get("error", ""))
    un = res.get("unreadable", [])
    miss = res.get("missing", [])
    mm = res.get("mismatch", [])
    lines = []
    if un:
        lines.append(_t("selfcheck.unreadable", n=len(un)))
        for u in un[:12]:
            lines.append(f"   🔴 {u['file']} — {u['reason']}")
        lines.append(_t("selfcheck.unreadable_hint"))
    else:
        lines.append(_t("selfcheck.ok"))
    lines.append(_t("selfcheck.counters", files=res.get("files_total"),
                    covered=res.get("covered_points"), missing=len(miss), mismatch=len(mm)))
    return "\n".join(lines)
