#!/usr/bin/env python3
"""Checklist for the next blood draw — one artefact from four sources in the project.

It invents nothing new: it brings together what already lies in the project and
turns it into a list one can take to the laboratory.

Sources:
  1) DRUG MONITORING — the active entries of medications.json → classes
     (med_classes.json) → the control tests and the "why" (drug_lab_monitoring.json);
  2) COMPLETENESS OF THE PhenoAge PANEL — which of the 9 markers were missing in the
     recent panels; without them biological age is not computed and no series is built
     (project rule: substituting markers from other draws is forbidden);
  3) AGREED WITH THE DOCTOR — planned_labs from medications.json (window, conditions);
  4) CLINICAL THRESHOLDS ALREADY CROSSED — clinical_thresholds.json against the latest
     values in labs.json: what is past the action threshold and asks to be tracked.

Output: profile/next_draw_checklist.md (print it and take it along) + .json (for the engine).
Personal — stays in profile/.

Run:  python3 src/ingest/draw_checklist.py
Not a prescription and not a diagnosis: a list for discussion with a doctor.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    from scholion import core, i18n, phenoage
except Exception as e:                                    # noqa: BLE001
    sys.exit(f"❌ cannot import the scholion package: {e}")

OUT_MD = Path(core.profile_dir()) / "next_draw_checklist.md"
OUT_JSON = Path(core.profile_dir()) / "next_draw_checklist.json"

TEST_META_PATH = ROOT / "src/scholion/knowledge/lab_test_meta.json"
try:
    TEST_META = json.loads(TEST_META_PATH.read_text(encoding="utf-8")).get("tests", {})
except Exception:                                          # noqa: BLE001
    TEST_META = {}

ACTIVE_PREFIXES = ("active", "course")          # course_postponed is cut off explicitly below
DEFERRED = {"course_postponed", "paused", "not_started", "planned_no_dose"}


# --------------------------------------------------------------------------- utilities
def _text(value) -> str:
    """A curated field of a knowledge file → one string.

    Printed fields in knowledge/*.json are per-language maps ({"en": …, "ru": …}).
    lab_test_meta.json is read here directly, past core's resolver, so the map has
    to be collapsed — otherwise the checklist prints a raw dict. The checklist is
    written in English, so English is taken where it exists.
    """
    if isinstance(value, dict):
        return value.get("en") or value.get("ru") or next(iter(value.values()), "")
    return value or ""


def _marker_label(key: str) -> str:
    """The marker's name: first from the profile itself (where it is already human and
    correctly cased), then from the recognition dictionary, otherwise the key itself."""
    prof = core.labs().get("markers", {}).get(key)
    if isinstance(prof, dict) and prof.get("name"):
        return str(prof["name"])
    fn = getattr(core, "lab_markers", None)
    if callable(fn):
        m = fn().get("markers", {}).get(key)
        if isinstance(m, dict):
            # The display label first, in the output language; the recognition
            # substrings only as a last resort — they are lower-case fragments
            # («(алт», «25-он витамин d») and were never meant for a screen.
            shown = core.marker_display(m, i18n.lang())
            if shown:
                return shown
            names = core.marker_rules(m, "names")
            if names:
                return str(names[0])
    return key


def _latest_point(key: str):
    """(value, date) of the marker's latest point, or (None, None)."""
    series = core.labs().get("markers", {}).get(key, {}).get("series", []) or []
    best_v = best_d = None
    for pt in series:
        v, d = pt.get("value"), str(pt.get("date", ""))
        if v is None or not d:
            continue
        if best_d is None or d > best_d:
            best_v, best_d = v, d
    return best_v, best_d


def _freshness(key: str, fresh_days: int = 90):
    """(date of the last value, days ago, whether it is fresh). Without this the checklist
    is a dump: half the entries were taken at the last draw and there is no point repeating them."""
    val, dt = _latest_point(key)
    if not dt:
        return None, None, False
    s = str(dt)[:10]
    if len(s) == 7:          # dates in the profile are monthly (YYYY-MM) — take the 1st
        s += "-01"
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return dt, None, False
    days = (date.today() - d).days
    return dt, days, days <= fresh_days


def _classes_for(name: str):
    """The drug's classes: through the engine if it can do it, otherwise the dictionary directly."""
    fn = getattr(core, "classify_drug", None)
    if callable(fn):
        try:
            res = fn(name)
            if isinstance(res, (list, tuple, set)):
                return list(res)
            if isinstance(res, str):
                return [res]
        except Exception:                                  # noqa: BLE001
            pass
    out = []
    for cls, spec in core.med_classes().get("classes", {}).items():
        for cname in spec.get("names", []):
            c, n = cname.lower(), name.lower()
            if c and (c in n or n in c):
                out.append(cls)
                break
    return out


# --------------------------------------------------------------------------- sources
def from_medications():
    """[(test_key, reason)], plus the list of deferred entries for the footnote."""
    mon = core.drug_lab_monitoring().get("classes", {})
    meds = core.medications_json().get("medications", []) or []
    items, deferred = [], []
    for m in meds:
        name, status = str(m.get("name", "")), str(m.get("status", ""))
        if not name:
            continue
        if status in DEFERRED or not status.startswith(ACTIVE_PREFIXES):
            classes = [c for c in _classes_for(name) if c in mon]
            if classes and status in DEFERRED:
                deferred.append((name, status, classes))
            continue
        for cls in _classes_for(name):
            spec = mon.get(cls)
            if not spec:
                continue
            why = spec.get("why", "")
            for lab in spec.get("labs", []) or []:
                items.append((lab, f"{name} (class {cls}){' — ' + why if why else ''}"))
    return items, deferred


def from_phenoage(lookback: int = 3):
    """What is missing for the next PhenoAge panel to come out complete."""
    try:
        ov = phenoage.panels_overview()
    except Exception as e:                                 # noqa: BLE001
        return {"error": str(e)}, []
    panels = ov.get("panels", []) or []
    complete = ov.get("complete", []) or []
    recent = panels[-lookback:] if panels else []
    # union of what is missing across the recent panels: what systematically drops out
    union, seen = [], set()
    for p in recent:
        for m in p.get("missing", []) or []:
            if m not in seen:
                seen.add(m)
                union.append(m)
    items = [(phenoage.LABS_KEYS[m][0], f"completeness of the PhenoAge panel (without it biological age is not computed)")
             for m in union]
    info = {
        "panels_total": len(panels),
        "complete_panels": complete,
        "latest_panel": panels[-1]["panel"] if panels else None,
        "latest_missing_ru": panels[-1].get("missing_ru", []) if panels else [],
        "union_missing_ru": [phenoage.marker_name(m) for m in union],
        "trend_possible": len(complete) >= 2,
        "note": ("the biological-age trend is built from complete panels only; "
                 f"complete ones so far: {len(complete)} — "
                 + ("a series is already possible" if len(complete) >= 2
                    else "a slope is not computed from a single point")),
    }
    return info, items


def from_planned_labs():
    pl = core.medications_json().get("planned_labs", []) or []
    out = []
    for p in pl:
        out.append({
            "window": p.get("window", ""),
            "tests": p.get("tests", []) or [],
            "conditions": p.get("conditions", ""),
            "agreed": bool(p.get("agreed_with_doctor")),
            "caveat": p.get("caveat", ""),
        })
    return out


def from_thresholds():
    """Markers whose latest value is already past the clinical action threshold."""
    th = core.clinical_thresholds().get("markers", {}) if hasattr(core, "clinical_thresholds") else {}
    if not th:
        try:
            th = json.loads((ROOT / "src/scholion/knowledge/clinical_thresholds.json")
                            .read_text(encoding="utf-8")).get("markers", {})
        except Exception:                                  # noqa: BLE001
            return []
    out = []
    for key, rules in th.items():
        val, dt = _latest_point(key)
        if val is None:
            continue
        crossed = []
        for r in rules or []:
            thr, side = r.get("value"), r.get("side", "high")
            if thr is None:
                continue
            if (side == "high" and val >= thr) or (side == "low" and val <= thr):
                crossed.append(r)
        if not crossed:
            continue
        worst = max(crossed, key=lambda r: abs(float(r.get("value", 0)) - 0)) if crossed else None
        label = _text(worst.get("label")) if worst else ""
        out.append((key, f"clinical threshold «{label}» crossed (latest value {val} of {dt}) — track the dynamics"))
    return out


# --------------------------------------------------------------------------- assembly
def main() -> int:
    med_items, deferred = from_medications()
    ph_info, ph_items = from_phenoage()
    thr_items = from_thresholds()
    planned = from_planned_labs()

    merged: dict[str, dict] = {}
    for key, reason in med_items + ph_items + thr_items:
        label = _marker_label(key)
        e = merged.setdefault(key, {"key": key, "test": label[:1].upper() + label[1:],
                                    "reasons": []})   # case fixed in case the name came from the dictionary
        if reason not in e["reasons"]:
            e["reasons"].append(reason)
    # Computed markers are NOT ORDERED as a separate entry — their components go on the
    # form instead. This does NOT mean the index's value is ignored: if the laboratory
    # computed and printed it, it sits in labs.json and takes part in trends, thresholds
    # and the analysis, as before. What is decided here is only the content of the form.
    computed_dissolved = []
    for key in list(merged):
        meta = TEST_META.get(key, {})
        if meta.get("computed"):
            src = merged.pop(key)
            last_v, last_d = _latest_point(key)
            computed_dissolved.append({
                "key": key, "test": src["test"],
                "requires": meta.get("requires", []),
                "last_value": last_v, "last_date": last_d,
                "note": "not ordered separately; the value printed on the form is stored and used",
            })
            for dep in meta.get("requires", []):
                d = merged.setdefault(dep, {"key": dep, "test": _marker_label(dep), "reasons": []})
                r = (f"needed to compute «{src['test']}» ({_text(meta.get('note'))})".strip()
                     .replace(" ()", ""))
                if r not in d["reasons"]:
                    d["reasons"].append(r)
    for e in merged.values():
        dt, days, fresh = _freshness(e["key"])
        e["last_date"], e["days_ago"], e["fresh"] = dt, days, fresh
        meta = TEST_META.get(e["key"], {})
        # a silent default is inadmissible here: "properties unknown" is a gap in the
        # map that has to be seen, not an invented tier 2
        e["meta_known"] = bool(meta)
        e["tier"] = meta.get("tier", 9)
        e["biomaterial"] = meta.get("biomaterial", "")
        e["fasting"] = bool(meta.get("fasting"))
        e["note"] = _text(meta.get("note"))
        # a tier 3 test is proposed only if its prerequisites already have fresh values
        miss = [d for d in meta.get("requires", []) if not _freshness(d)[2]]
        e["blocked_by"] = miss if (e["tier"] >= 3 and miss) else []
    # first what is missing or long stale; within that — by the number of reasons
    items = sorted(merged.values(),
                   key=lambda e: (e["fresh"], e["tier"], -(e["days_ago"] or 10 ** 4),
                                  -len(e["reasons"])))
    need = [e for e in items if not e["fresh"] and not e["blocked_by"]]
    later = [e for e in items if not e["fresh"] and e["blocked_by"]]
    have = [e for e in items if e["fresh"]]

    data = {
        "_meta": {
            "generated": str(date.today()),
            "purpose": "Checklist for the next draw: drug monitoring, completeness of the "
                       "PhenoAge panel, tests agreed with the doctor and clinical "
                       "thresholds already crossed, brought together.",
            "disclaimer": "Not a prescription and not a diagnosis — a list for discussion with a "
                          "doctor. The final content of the draw is decided by the doctor.",
        },
        "items": items,
        "need_now": [e["key"] for e in need],
        "deferred_until_prereq": [e["key"] for e in later],
        "computed_not_ordered": computed_dissolved,
        "phenoage": ph_info,
        "planned_labs": planned,
        "deferred_meds": [{"name": n, "status": s, "classes": c} for n, s, c in deferred],
    }
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- printable form
    L = [f"# Checklist for the next draw · {date.today()}", "",
         "_Not a prescription and not a diagnosis: a list for discussion with a doctor._", ""]
    if planned:
        L += ["## Agreed with the doctor", ""]
        for p in planned:
            mark = "✔" if p["agreed"] else "•"
            L.append(f"{mark} **{p['window']}** — {', '.join(p['tests'])}")
            if p["conditions"]:
                L.append(f"  · conditions: {p['conditions']}")
            if p["caveat"]:
                L.append(f"  · caveat: {p['caveat']}")
        L.append("")
    def _block(title, rows, note=""):
        if not rows:
            return
        L.append(f"## {title}")
        if note:
            L.append("")
            L.append(note)
        L.append("")
        BIO = {"serum": "serum", "edta_whole_blood": "EDTA (CBC tube)",
               "serum_special": "serum, special conditions", "urine": "urine"}
        for e in rows:
            when = (f"last taken {e['last_date']}, {e['days_ago']} d. ago"
                    if e["last_date"] else "no value at all in the profile")
            tags = ([f"tier {e['tier']}", BIO.get(e["biomaterial"], e["biomaterial"])]
                    if e.get("meta_known") else ["the test's properties are not described in lab_test_meta.json"])
            if e["fasting"]:
                tags.append("fasting")
            L.append(f"- [ ] **{e['test']}** — _{when}_  ({'; '.join(tags)})")
            if e.get("note"):
                L.append(f"      · condition: {e['note']}")
            for r in e["reasons"]:
                L.append(f"      · {r}")
        L.append("")

    _block("To add — no fresh value", need,
           "Never measured, or older than 90 days. The order is by tier: "
           "basic screening first, the expensive ones below.")
    if later:
        L.append("## Postpone to the next round")
        L.append("")
        L.append("Expert tests whose prerequisites are not fresh — taking them now "
                 "means paying for an uninterpretable result.")
        L.append("")
        for e in later:
            dep = ", ".join(_marker_label(d) for d in e["blocked_by"])
            L.append(f"- **{e['test']}** (tier {e['tier']}) — these are needed first: {dep}")
        L.append("")
    _block("A fresh value already exists — repeat at the doctor's discretion", have,
           "Taken within 90 days; they go on the form only if the doctor wants the dynamics.")
    if ph_info.get("union_missing_ru") or ph_info.get("latest_panel"):
        latest_missing = ph_info.get("latest_missing_ru") or []
        L += ["## Biological age (PhenoAge)", "",
              f"Complete panels: {len(ph_info.get('complete_panels', []))}"
              f" (the latest panel — {ph_info.get('latest_panel')}). {ph_info.get('note','')}", ""]
        if latest_missing:
            L.append("Missing from the latest panel: " + ", ".join(latest_missing) + ".")
        else:
            L.append("The latest panel is complete — biological age has been computed from it.")
        if ph_info.get("union_missing_ru"):
            L += ["",
                  "Systematically dropped from the draws (make sure they get into the next one): "
                  + ", ".join(ph_info["union_missing_ru"]) + ".",
                  "",
                  "_Every complete panel is one point of the series. While there are fewer than "
                  "two, the pace of ageing is not computed: a slope through one point does not exist._"]
        L.append("")
    if computed_dissolved:
        L += ["## Computed indices — do not put them on the form", "",
              "They are computed from other markers. If the laboratory prints them itself — "
              "good, the value is stored and used; there is nothing to order as a separate "
              "line.", ""]
        for c in computed_dissolved:
            dep = ", ".join(_marker_label(d) for d in c["requires"])
            val = (f"latest value {c['last_value']} ({c['last_date']})"
                   if c["last_value"] is not None else "no values in the profile")
            L.append(f"- **{c['test']}** ← {dep}; {val}")
        L.append("")

    if deferred:
        L += ["## Deferred items of the regimen (no monitoring needed for now)", ""]
        for n, s, c in deferred:
            L.append(f"- {n} — status `{s}`; if it comes back, monitoring for class {', '.join(c)} will be needed")
        L.append("")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"✓ {OUT_MD}")
    print(f"✓ {OUT_JSON}")
    for c in computed_dissolved:
        have_v = (f"latest value {c['last_value']} of {c['last_date']} — "
                  f"stored and used" if c["last_value"] is not None
                  else "no values in the profile")
        print(f"\n  {c['test']}: a computed index, not ordered as a separate item "
              f"(what goes on the form: {', '.join(_marker_label(d) for d in c['requires'])}); "
              f"{have_v}")
    unknown = [e["test"] for e in items if not e.get("meta_known")]
    if unknown:
        print(f"\n⚠ properties are not described for {len(unknown)} tests "
              f"(tier/tube unknown): {', '.join(unknown[:8])}"
              + (" …" if len(unknown) > 8 else ""))
    print(f"\nWithout a fresh value: {len(need)}; postponed until prerequisites: {len(later)}; "
          f"already taken within 90 days: {len(have)}; "
          f"agreed with the doctor: {len(planned)}; deferred drugs: {len(deferred)}")
    print("\nTo add (no fresh value):")
    for e in need[:15]:
        when = f"{e['days_ago']} d." if e["days_ago"] is not None else "never"
        tier = f"t.{e['tier']}" if e.get("meta_known") else "t.?"
        print(f"  · [{tier:5}] {e['test']:30} [{when:>8}] {e['reasons'][0][:60]}")
    if ph_info.get("union_missing_ru"):
        print(f"\n  PhenoAge — add to the draw: {', '.join(ph_info['union_missing_ru'])}")
        print(f"  {ph_info.get('note','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
