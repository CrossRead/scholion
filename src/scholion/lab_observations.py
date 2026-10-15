"""Printed non-scalar lab observations, kept outside numeric marker series.

An absent analyte is not zero, a microscopy interval is not its midpoint, and
negative PCR targets must not become blood measurements. Recognition is proposed;
references are transcribed, never invented or clinically graded here.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from . import core, i18n


def _catalogue() -> dict:
    return json.loads(core.knowledge_path("lab_observations.json").read_text(encoding="utf-8"))


def _names(spec: dict) -> list:
    return [n for label in spec.get("labels", {}).values() for n in label.get("names", [])]


def _label_hit(line: str, spec: dict):
    for name in sorted(_names(spec), key=len, reverse=True):
        if line.casefold().startswith(name.casefold()):
            end = len(name)
            if end == len(line) or not line[end].isalnum():
                return name
    return None


def _result(tail: str, vocabulary: list, allow_interval: bool, unit_names: list):
    candidates = []
    for entry in vocabulary:
        for name in _names(entry):
            m = re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", tail, re.I)
            if m:
                candidates.append((m.start(), -len(name), m, entry["code"]))
    if allow_interval:
        scalar = re.match(r"^(\d+(?:[.,]\d+)?)(?=\s|$)", tail)
        if scalar:
            candidates.append((0, -len(scalar.group()), scalar, "count"))
        m = re.search(r"(?<![\w.,])\d+(?:[.,]\d+)?\s*[-–—]\s*\d+(?:[.,]\d+)?(?![\w.,])", tail)
        if m:
            candidates.append((m.start(), -len(m.group()), m, "interval"))
    if not candidates:
        return None
    _, _, match, code = min(candidates, key=lambda x: x[:2])
    if allow_interval and match.start() != 0:
        return None  # Never take a reference after an unrecognised result.
    out: Dict[str, Any] = {"kind": code if code in ("interval", "count") else "qualitative",
                           "result_text": match.group(), "code": code}
    if code == "count":
        out["value"] = float(match.group().replace(",", "."))
    if code == "interval":
        low, high = re.split(r"\s*[-–—]\s*", match.group())
        out["low"], out["high"] = float(low.replace(",", ".")), float(high.replace(",", "."))
        if out["low"] > out["high"]:
            return None
    rest = tail[match.end():].strip()
    # Unit spellings are input data, not assumed canonical units.
    for unit in sorted(unit_names, key=len, reverse=True):
        if rest.casefold().startswith(unit.casefold()):
            out["unit"] = rest[:len(unit)]
            rest = rest[len(unit):].strip()
            break
        if rest.casefold().endswith(" " + unit.casefold()):
            out["unit"] = rest[-len(unit):]
            rest = rest[:-len(unit)].strip()
            break
    # A row can have no reference. The unparsed prefix is the wrapped assay
    # name, not a reference; only text AFTER the observed result is retained.
    out["reference_text"] = rest
    return out


def parse_observations(text: str) -> List[dict]:
    """Read bounded result rows; repeated bilingual printouts are one observation."""
    cat = _catalogue()
    specs = cat["markers"]
    lines = [" ".join(s.split()) for s in text.splitlines() if s.strip()]
    lower = text.casefold()
    specs = {key: spec for key, spec in specs.items()
             if any(token.casefold() in lower for label in spec["labels"].values()
                    for token in label.get("form_require", []))}
    out: List[dict] = []
    for i, line in enumerate(lines):
        for key, spec in specs.items():
            label = _label_hit(line, spec)
            if not label:
                continue
            segment = line[len(label):].strip()
            # PCR names can wrap on both sides of the result. Stop at another
            # assay; never borrow its result for an empty row.
            for following in lines[i + 1:i + 4]:
                if any(_label_hit(following, s) for s in specs.values()):
                    break
                if _result(segment, cat["results"], spec.get("allow_interval", False), cat.get("synonyms", [])):
                    break
                continuation_result = _result(following, cat["results"], False, cat.get("synonyms", []))
                if not following.startswith("(") and not (continuation_result and
                        following.startswith(continuation_result["result_text"])):
                    break
                segment += " " + following
            result = _result(segment, cat["results"], spec.get("allow_interval", False), cat.get("synonyms", []))
            if not result:
                continue
            if result["reference_text"].endswith(",") and i + 1 < len(lines):
                continuation = lines[i + 1]
                if _result(continuation, cat["results"], False, cat.get("synonyms", [])) and not any(
                        _label_hit(continuation, s) for s in specs.values()):
                    result["reference_text"] += " " + continuation
            if key == "urinalysis_color" and not result["reference_text"]:
                fragments = []
                for offset in (-1, 1):
                    if not 0 <= i + offset < len(lines):
                        continue
                    fragment = lines[i + offset]
                    colour = _result(fragment, cat["results"], False, cat.get("synonyms", []))
                    if colour and colour["code"] in ("dark_yellow", "straw_yellow", "light_yellow", "yellow") and (
                            fragment.rstrip(",") == colour["result_text"]):
                        fragments.append(fragment)
                result["reference_text"] = " ".join(fragments)
            specimen = spec["specimen"]
            if spec.get("specimen_from_form"):
                specimen = next((kind for kind, rule in cat.get("specimen_rules", {}).items()
                                 if any(ln.casefold().startswith(prefix.casefold())
                                        for prefix in _names(rule) for ln in lines)), "unknown")
            item = dict(result, key=key, label=line[:len(label)], specimen=specimen,
                        method=spec["method"], proposed_rule=True)
            # No result text, reference or number is sourced from the dictionary.
            # The raw row is bounded, so patient headers/comments are not copied.
            item["source_row"] = line + (" " + segment if segment != line[len(label):].strip() else "")
            if not any(x["key"] == key and equivalent(x, item) for x in out):
                out.append(item)
    return out


def equivalent(a: dict, b: dict) -> bool:
    """Semantic equality ignores translated wording, not intervals or units."""
    return all(a.get(k) == b.get(k) for k in ("kind", "code", "low", "high", "value", "unit", "specimen", "method"))


def view(markers=None) -> List[dict]:
    """One latest record per observation key plus complete provenance/history."""
    specs = _catalogue()["markers"]
    out: List[dict] = []
    for key, observation in core.labs().get("observations", {}).items():
        if markers and key not in markers:
            continue
        series = sorted(observation.get("series", []), key=lambda p: p["date"])
        if not series:
            continue
        spec = specs.get(key, {})
        label = spec.get("labels", {}).get(i18n.lang(), {})
        name = label.get("display") or (label.get("names") or [observation.get("name", key)])[0]
        out.append({"key": key, "name": name, **series[-1], "series": series,
                    "proposed_rule": True})
    return out
