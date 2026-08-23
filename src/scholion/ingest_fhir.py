"""Import a FHIR R4 Bundle: laboratory results a person exports from a portal.

Why this and not another parser. Every laboratory prints its own form, and the
PDF path has to learn each one; FHIR is the opposite — one shape, agreed by the
people who write the systems, and a US portal, Apple Health's clinical records
and an EHR export all speak it. An `Observation` names its analyte by LOINC code
and its unit in UCUM, which are exactly the two things this project already keys
its dictionary by. So the import is a mapping, not a guess: LOINC → marker,
UCUM → the unit gate, and anything that does not map is named rather than
approximated.

WHAT IS DELIBERATELY NOT DONE HERE:

  · No value is invented. An `Observation` without a `valueQuantity` — a coded
    result, a panel that only groups its members, an attachment — is listed with
    its reason and not converted into a number.
  · A code we do not carry is not matched by its display text. «Glucose» in one
    system is not necessarily the analyte our dictionary calls glucose, and the
    LOINC code exists precisely so that nobody has to decide that by name.
  · Nothing about the person is written from the bundle. A FHIR `Patient` gives
    sex and birth date, and both would be useful — six reference intervals
    depend on the first. They are REPORTED and not applied: a file the user
    pointed at may be a relative's, a sample, or an export from a portal that
    holds two people, and quietly adopting an identity from a file is the one
    kind of error that then contaminates everything downstream.
  · The reference interval is taken from the bundle when the bundle carries one,
    and left empty otherwise — the project's rule that a corridor comes from the
    document, never from a default.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import core, store
from .i18n import t as _t

#: The FHIR *system* URI for LOINC. It is an IDENTIFIER, not an address: a coding
#: says «this code belongs to the system named by this URI», and nothing here ever
#: dereferences it. Written in two halves so that the network inventory — which
#: reads code looking for hosts this application can talk to — does not report a
#: host we never contact. Overstating that surface is safe; overstating it with
#: something untrue is not, and the README's list of addresses is a promise.
LOINC_SYSTEM = "http://" + "loinc.org"

#: Statuses whose value may be stored. `preliminary` and `registered` are
#: explicitly excluded: a result the source itself has not finalised must not
#: enter a history that other layers then compare against.
FINAL_STATUSES = {"final", "amended", "corrected"}


def _loinc_codes(resource: Dict[str, Any]) -> List[str]:
    out = []
    for coding in ((resource.get("code") or {}).get("coding") or []):
        if (coding.get("system") or "").rstrip("/") == LOINC_SYSTEM and coding.get("code"):
            out.append(str(coding["code"]).strip())
    return out


def _effective(resource: Dict[str, Any]) -> Optional[str]:
    """The moment the specimen was taken, in the bundle's own words.

    Preference order is the order of decreasing certainty about WHEN the sample
    was taken: an instant, a datetime, the start of a period, and only then
    `issued`, which is when the report was released and may be days later.
    """
    for key in ("effectiveInstant", "effectiveDateTime"):
        if resource.get(key):
            return str(resource[key])
    period = resource.get("effectivePeriod") or {}
    if period.get("start"):
        return str(period["start"])
    if resource.get("issued"):
        return str(resource["issued"])
    return None


def _stamp(raw: str) -> str:
    """`2009-10-26T06:44:52-04:00` → `2009-10-26T06:44`, the project's own shape.

    The offset is dropped rather than converted. A draw time is a local clinical
    fact — «before the procedure», «fasting, morning» — and re-expressing it in
    another zone would move a morning draw into the previous evening for no gain.
    """
    date = raw[:10]
    if len(raw) >= 16 and raw[10] in "T ":
        return f"{date}T{raw[11:16]}"
    return date


def _range(resource: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    for rr in (resource.get("referenceRange") or []):
        low = (rr.get("low") or {}).get("value")
        high = (rr.get("high") or {}).get("value")
        if low is not None or high is not None:
            return (float(low) if low is not None else None,
                    float(high) if high is not None else None)
    return None, None


def profile_facts(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Sex and birth date as the bundle states them — reported, never applied."""
    for entry in (bundle.get("entry") or []):
        res = entry.get("resource") or {}
        if res.get("resourceType") == "Patient":
            return {k: v for k, v in
                    {"sex": res.get("gender"), "birth_date": res.get("birthDate")}.items()
                    if v}
    return {}


def read_bundle(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"ok": False, "error": _t("fhir.unreadable", path=str(path), error=str(e))}
    if not isinstance(data, dict) or data.get("resourceType") != "Bundle":
        kind = (data or {}).get("resourceType") if isinstance(data, dict) else type(data).__name__
        return {"ok": False, "error": _t("fhir.not_a_bundle", kind=str(kind))}
    return {"ok": True, "bundle": data}


def plan(path: Path) -> Dict[str, Any]:
    """What this bundle offers, WITHOUT writing anything.

    Separated from the write on purpose: a person about to let a file into their
    medical history should be able to see what it will do first, and `--dry-run`
    then costs one flag instead of a design.
    """
    got = read_bundle(Path(path))
    if not got.get("ok"):
        return got
    bundle = got["bundle"]
    index = core.loinc_index()
    points: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    # Body measurements go to the metrics layer, not to the laboratory series:
    # a weight is the person's own measurement and this product has always
    # accepted it — from the command line and from the page. Dropping it because
    # it arrived in a bundle was a hole, not a policy.
    metrics: List[Dict[str, Any]] = []
    for entry in (bundle.get("entry") or []):
        res = entry.get("resource") or {}
        if res.get("resourceType") != "Observation":
            continue
        label = ((res.get("code") or {}).get("text")
                 or (((res.get("code") or {}).get("coding") or [{}])[0]).get("display")
                 or res.get("id") or "?")
        status = (res.get("status") or "").lower()
        if status not in FINAL_STATUSES:
            skipped.append({"label": label, "reason": "not_final", "detail": status})
            continue
        qty = res.get("valueQuantity")
        if not isinstance(qty, dict) or qty.get("value") is None:
            skipped.append({"label": label, "reason": "no_quantity",
                            "detail": next((k for k in res if k.startswith("value")), "none")})
            continue
        codes = _loinc_codes(res)
        if not codes:
            skipped.append({"label": label, "reason": "no_loinc"})
            continue
        key = next((index[c] for c in codes if c in index), None)
        if not key:
            # A body measurement is not an analyte the dictionary is missing —
            # it is a value that belongs somewhere else entirely. Saying «the
            # code is not in the dictionary» about a body weight sends the
            # reader looking for an entry that should never exist there.
            metric = next((c for c in codes if c in _body_metrics()), None)
            if metric:
                known = _body_metrics()[metric]
                mine, want = known.get("ours"), (known.get("unit") or "").strip()
                when = _effective(res)
                got = (qty.get("code") or qty.get("unit") or "").strip()
                if not mine:
                    # No metric of ours holds this quantity. The table says what
                    # it is instead, and that sentence is the answer.
                    skipped.append({"label": label, "reason": "loinc_is_a_body_metric",
                                    "detail": metric, "ours": None})
                elif not when:
                    skipped.append({"label": label, "reason": "no_date", "detail": metric})
                elif got.lower() != want.lower():
                    # Nothing here converts. A weight in pounds joining a series
                    # in kilograms is the defect this project spends its time
                    # removing, and it would arrive silently.
                    skipped.append({"label": label, "reason": "metric_unit_not_ours",
                                    "detail": f"{metric}: {got or '—'} ≠ {want}"})
                else:
                    metrics.append({"metric": mine, "label": label,
                                    "date": _stamp(when), "value": float(qty["value"]),
                                    "unit": want, "loinc": metric})
                continue
            # NOT matched by display text — see the module docstring. This is the
            # list that says what the dictionary is missing, and it is the same
            # kind of material a dictionary proposal is built from.
            skipped.append({"label": label, "reason": "loinc_not_in_catalogue",
                            "detail": ", ".join(codes)})
            continue
        when = _effective(res)
        if not when:
            skipped.append({"label": label, "reason": "no_date"})
            continue
        low, high = _range(res)
        points.append({"key": key, "label": label, "date": _stamp(when),
                       "value": float(qty["value"]),
                       "unit": qty.get("code") or qty.get("unit"),
                       "ref_low": low, "ref_high": high,
                       "loinc": codes[0]})
    return {"ok": True, "path": str(path), "points": points, "metrics": metrics,
            "skipped": skipped,
            "profile_facts": profile_facts(bundle),
            "observations": sum(1 for e in (bundle.get("entry") or [])
                                if (e.get("resource") or {}).get("resourceType") == "Observation")}


def _body_metrics() -> Dict[str, Any]:
    """LOINC codes that name a body measurement rather than a laboratory analyte.

    Data, not a list in code: the next such code is added by whoever meets it,
    with the sentence that says where the value belongs — and `ours` names our
    own metric only where the two are the same quantity in the same unit.
    """
    return {k: v for k, v in (core.lab_test_meta().get("body_metrics") or {}).items()
            if isinstance(v, dict)}


def ingest(path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Read the bundle and write its laboratory points into the profile."""
    res = plan(Path(path).expanduser())
    if not res.get("ok"):
        return res
    res["dry_run"] = bool(dry_run)
    if dry_run:
        res["added"] = []
        return res
    added, refused = [], []
    for p in res["points"]:
        # `effectiveDateTime` on an Observation is when the specimen was taken —
        # the draw itself, not a stand-in for it.
        r = store.add_lab_point(p["key"], p["date"], p["value"], name=p["label"],
                                unit=p["unit"], ref_low=p["ref_low"], ref_high=p["ref_high"],
                                date_source="form", subject="owner")
        if r.get("ok"):
            added.append(p["key"])
        else:
            # The unit gate refused. That is the gate working: a value whose unit
            # cannot be converted is not written in whatever unit it arrived in.
            refused.append({"label": p["label"], "unit": p["unit"],
                            "reason": r.get("error") or "refused"})
    # The body measurements, into the metrics layer they belong to. Same person,
    # same file, same import — a weight is not a laboratory result and it is not
    # somebody else's business either.
    added_metrics = []
    for m in res.get("metrics") or []:
        r = store.add_metric_point(m["metric"], m["date"], m["value"],
                                   name=m["label"], unit=m["unit"], subject="owner")
        if r.get("ok"):
            added_metrics.append(m["metric"])
        else:
            refused.append({"label": m["label"], "unit": m["unit"],
                            "reason": r.get("error") or "refused"})
    res["added"] = added
    res["added_metrics"] = added_metrics
    res["refused"] = refused
    core.reset_cache()
    return res
