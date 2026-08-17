"""Deterministic logic (a hybrid: the code computes facts and flags, the LLM words them).

Three MVP tools:
  - check_drug_gene(drug)  : checking a prescription against pharmacogenetics
  - analyze_labs(markers)  : deviation flags + trends + the link to the genome
  - suggest_tests()        : which lab tests it makes sense to take (rules)

All functions return a STRUCTURE (dict/list) — not text. Formatting into a string for
the tools/CLI is in format.py. That way one logic feeds both the Claude skill and Ouroboros.
"""
from __future__ import annotations
import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from .i18n import lang as _lang, plural as _plural, t as _t


def _recent(date_str: str, months: int = 12) -> bool:
    """A date (YYYY-MM / YYYY-MM-DD) no older than `months` from today (sliding window).
    Unrecognised dates are not hidden (True is returned)."""
    if not date_str:
        return False
    try:
        parts = str(date_str).split("-")
        y, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
    except Exception:
        return True
    today = datetime.date.today()
    cy, cm = today.year, today.month - months
    while cm <= 0:
        cm += 12
        cy -= 1
    return (y, m) >= (cy, cm)

def DISCLAIMER() -> str:
    """The standing caveat under every report.

    A function and not a constant: the language is chosen when the report is built,
    and the web server builds two reports in two languages at the same time.
    """
    return _t("disclaimer.general")


# ==========================================================================
# 1. Checking a prescription against pharmacogenetics
# ==========================================================================
def _match_count(count: int, expr: str) -> bool:
    """Check of a condition of the form '>=2' / '==1' against the number of allele copies."""
    for op in (">=", "<=", "==", ">", "<"):
        if expr.startswith(op):
            return _OPS[op](count, int(expr[len(op):]))
    return count == int(expr)


def _basis(gene: str, gdef: Dict[str, Any], found: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What was read for this gene, what was not, and whether the gap can be closed.

    Exists because "unknown" on its own is a dead end for the reader. Knowing that
    a phenotype was not determined tells nobody what to do; knowing that one of
    two markers was read, that the missing one is rs12248560 (*17), and that its
    coordinates are in the locus catalogue so a full VCF closes it — that is an
    instruction. The same structure decides whether an answer may be called
    ASSUMED rather than refused: a partial panel still carries information, and
    throwing it away is its own kind of dishonesty.
    """
    model = gdef.get("markers", []) if gdef else []
    read = {f["rsid"] for f in found}
    from . import genome as _genome          # lazy: genome imports core, core imports nothing back
    try:
        catalogue = _genome.loci().get("loci", {}) or {}
    except Exception:                                            # noqa: BLE001
        catalogue = {}
    missing = []
    for m in model:
        if m["rsid"] in read:
            continue
        missing.append({"rsid": m["rsid"], "star": m.get("star", ""),
                        "function": m.get("function", ""),
                        "obtainable": m["rsid"] in catalogue})
    # Deficient alleles the project's own catalogue knows and this gene's model does
    # not. Named because a reader is entitled to know that the panel is narrower
    # than the data the project already ships.
    modelled = {m["rsid"] for m in model}
    not_modelled = [r for r, e in catalogue.items()
                    if e.get("gene") == gene and r not in modelled]
    return {"read": sorted(read), "total": len(model),
            "missing": missing, "not_modelled": sorted(not_modelled)}


def _basis_note(gene: str, basis: Dict[str, Any]) -> str:
    """One sentence: what is there, what is missing, and what would close it."""
    parts = []
    read, total = len(basis["read"]), basis["total"]
    if total:
        parts.append(_t("basis.read", read=read, total=total))
    miss = basis["missing"]
    if miss:
        names = ", ".join(f"{m['rsid']}{(' (' + m['star'] + ')') if m['star'] else ''}"
                          for m in miss)
        parts.append(_t("basis.missing", names=names))
        # "Build a VCF" is the wrong instruction when the VCF is already there and
        # these very positions carry no row in it. The remedy then is to genotype
        # them from the BAM, and `basis.not_called` says so a line below; offering
        # both would be advice that argues with itself.
        not_called = set(basis.get("not_called") or [])
        outstanding = [m for m in miss if m["rsid"] not in not_called]
        if outstanding:
            if any(m["obtainable"] for m in outstanding):
                parts.append(_t("basis.obtainable"))
            else:
                parts.append(_t("basis.not_in_catalogue"))
    if basis.get("not_called"):
        # A different remedy from "you have no VCF": the file is there, these
        # positions simply carry no row, so the answer is to genotype them from
        # the BAM rather than to build a VCF.
        parts.append(_t("basis.not_called", names=", ".join(basis["not_called"])))
    if basis["not_modelled"]:
        parts.append(_t("basis.not_modelled", names=", ".join(basis["not_modelled"])))
    return " ".join(parts)


def compute_phenotype(gene: str) -> Dict[str, Any]:
    """The patient's phenotype for a gene, WITH the basis it rests on.

    Returns {phenotype, label, found, certainty, basis, basis_note}.

    `certainty` is the part that matters: `determined` when every marker of the
    model was read, `assumed` when only some were, `unknown` when none were. An
    assumed phenotype is still printed — it carries real information — but it is
    labelled as assumed and says what would make it certain. Refusing to answer
    from a partial panel and asserting a phenotype from one are both wrong; the
    honest third option is to answer and mark the answer.
    """
    kb = core.cpic_kb()
    gdef = (kb.get("genes", {}) or {}).get(gene)
    if gene in core.genome_gaps():
        basis = _basis(gene, gdef, [])
        # Which of them are unread because the file has no row there, as opposed
        # to there being no file: the two need different instructions, and the
        # gene being in the gap list does not say which case this is.
        not_called = [m["rsid"] for m in basis["missing"]
                      if (core.genotype_status(m["rsid"]) or {}).get("confidence") == "assumed_ref"]
        if not_called:
            basis["not_called"] = not_called
        return {"phenotype": "unknown", "label": _t("phenotype.not_covered"),
                "found": core.markers_for_gene(gene), "certainty": "unknown",
                "basis": basis, "basis_note": _basis_note(gene, basis)}
    if not gdef:
        markers = core.markers_for_gene(gene)
        basis = _basis(gene, None, [])
        return {"phenotype": "unknown" if not markers else "reported",
                "label": _t("phenotype.no_model"), "found": markers,
                "certainty": "unknown" if not markers else "assumed",
                "basis": basis, "basis_note": _basis_note(gene, basis)}

    func_counts: Dict[str, int] = {}
    found: List[Dict[str, Any]] = []
    unread: List[str] = []
    for m in gdef.get("markers", []):
        st = core.genotype_status(m["rsid"])
        if not st or not st.get("genotype"):
            continue
        # `assumed_ref` is not a reading. It means the position has no row in the
        # variant VCF, which is either the reference OR no coverage there, and the
        # two are indistinguishable from the file alone. Counting it as zero
        # variant copies is what made a connected genome produce a LESS cautious
        # answer than no genome at all: the string said "CC", the phenotype came
        # out normal, and a possible carrier read it as permission.
        if st.get("confidence") == "assumed_ref":
            unread.append(m["rsid"])
            continue
        gt = st["genotype"]
        copies = gt.upper().count(m["variant_allele"].upper())
        func_counts[m["function"]] = func_counts.get(m["function"], 0) + copies
        found.append({"rsid": m["rsid"], "star": m.get("star", ""), "genotype": gt,
                      "copies": copies, "function": m["function"],
                      "confidence": st.get("confidence"), "depth": st.get("depth")})

    basis = _basis(gene, gdef, found)
    if unread:
        basis["not_called"] = unread
    note = _basis_note(gene, basis)
    if not found:
        return {"phenotype": "unknown", "label": _t("phenotype.no_markers"), "found": [],
                "certainty": "unknown", "basis": basis, "basis_note": note}

    certainty = "determined" if not basis["missing"] else "assumed"
    phen, label = "NM", _t("phenotype.normal_default")
    for rule in gdef.get("phenotype_rules", []):
        if rule.get("default") or all(_match_count(func_counts.get(fn, 0), expr)
                                      for fn, expr in rule["when"].items()):
            phen, label = rule["phenotype"], rule.get("label", "")
            break
    if certainty == "assumed":
        label = _t("phenotype.assumed", label=label)
    return {"phenotype": phen, "label": label, "found": found,
            "certainty": certainty, "basis": basis, "basis_note": note}


def check_drug_gene(drug: str) -> Dict[str, Any]:
    q = (drug or "").strip().lower()
    if not q:
        return {"status": "error", "message": _t("drug.no_name"), "disclaimer": DISCLAIMER()}

    kb = core.cpic_kb()
    match = None
    for entry in kb.get("drugs", []):
        for name in entry.get("names", []):
            if q == name or q in name or name in q:
                match = entry
                break
        if match:
            break

    if not match:
        return _check_drug_online(drug)

    gene = match["gene"]
    ph = compute_phenotype(gene)
    phenotype = ph["phenotype"]
    guidance = match.get("guidance", {})

    # A determined phenotype with no entry of its own must not be answered out of
    # `default`. Voriconazole's table has keys for UM, RM, PM and default — but
    # none for IM, NM or unknown, so a carrier of a loss-of-function allele, a
    # normal metaboliser and a person with no data at all were given the same
    # sentence: "no features have been found by the markers". The catalogue's
    # silence about a phenotype was printed as a statement about the patient.
    #
    # `default` keeps its meaning — a rule that applies whatever the phenotype —
    # but only where the phenotype was never determined. Where it WAS determined
    # and the catalogue has nothing to say, that is what the answer says, and the
    # gap is machine-readable in `guidance_gap` rather than only in the prose.
    explicit = guidance.get(phenotype)
    gap = False
    if explicit:
        flag = explicit
    elif phenotype in ("unknown", "reported") or not guidance:
        flag = guidance.get("default") or {
            "level": "unknown" if phenotype == "unknown" else "low",
            "note": _t("drug.nothing_notable")}
    else:
        gap = True
        flag = {"level": "unknown",
                "note": _t("drug.no_guidance_for_phenotype", phenotype=phenotype, gene=gene)}

    # An undetermined phenotype cannot yield a reassuring level, whatever the
    # catalogue's `default` says. Five drugs had `default.level = "low"`, so a
    # person with no genotype at all was told the drug was fine on this gene —
    # azathioprine among them.
    #
    # The text is led, not replaced. A `default` note is often good advice
    # ("assess the TPMT status before prescribing") and worth keeping — but some
    # of them are claims about the patient: voriconazole's reads "no features
    # have been found by the markers", which, said to a person whose markers were
    # never read, is the same defect one layer down. Lifting the level and
    # leaving that sentence would have been the mirror of what this change is
    # for. So the answer opens by saying the phenotype was not determined, and
    # whatever the catalogue advises follows that.
    if phenotype == "unknown":
        # "Not determined" alone is a dead end. What follows it is the basis: how
        # many markers of the model were read, which were not, and whether the
        # gap is closable from the person's own data or needs a laboratory. A
        # reader can act on that; they cannot act on the absence of a word.
        lead = _t("drug.phenotype_not_determined", gene=gene)
        parts = [lead, ph.get("basis_note") or "", flag.get("note") or ""]
        flag = {**flag,
                "level": "unknown" if flag.get("level") in ("low", None) else flag["level"],
                "note": " ".join(x for x in parts if x)}
    elif ph.get("certainty") == "assumed":
        # An assumed phenotype keeps its recommendation — the information is real
        # — and carries what would make it certain, in the same sentence.
        flag = {**flag, "note": " ".join(x for x in (flag.get("note") or "",
                                                     ph.get("basis_note") or "") if x)}
    return {
        "status": "ok",
        "drug": drug,
        "gene": gene,
        "drug_class": match.get("class", ""),
        "why": match.get("why", ""),
        "phenotype": phenotype,
        "phenotype_label": ph.get("label", ""),
        "certainty": ph.get("certainty"),
        "basis": ph.get("basis"),
        "level": flag["level"],
        "guidance_gap": gap,
        "recommendation": flag["note"],
        "markers_found": ph.get("found") or core.markers_for_gene(gene),
        "clinvar": clinvar_for_drug(drug, {"genes": [{"gene": gene}]}),
        "disclaimer": DISCLAIMER(),
    }


# ==========================================================================
# 2. Analysis of the lab results: flags + trends
# ==========================================================================
def _latest(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return sorted(series, key=lambda p: p["date"])[-1] if series else None


def _flag_value(m: Dict[str, Any], value: float, censored: Optional[str] = None) -> str:
    """Flag of a marker relative to the reference interval.

    censored — the sign from the lab form when a bound is printed instead of a number ("<" / ">").
    The value is stored at the bound, so an ordinary comparison lies exactly at the edge: a result of
    "less than 10^5" with a lower bound of 10^5 is strictly BELOW the reference, although
    value == ref_low. Likewise "more than 10^8" with an upper bound of 10^8 is strictly above.
    """
    lo, hi = m.get("ref_low"), m.get("ref_high")
    if censored == "<" and lo is not None and value <= lo:
        return "low"
    if censored == ">" and hi is not None and value >= hi:
        return "high"
    if hi is not None and value > hi:
        return "high"
    if lo is not None and value < lo:
        return "low"
    if lo is None and hi is None:
        # No corridor at all — and «ok» here would be a claim, not an absence of
        # one. A green tick beside a number nobody has anything to compare with
        # reads as «this is fine», which is exactly what cannot be said; the very
        # first marker a new user enters by hand has no bounds, so this is the
        # first screen of every person who starts without a lab form.
        return "norange"
    return "ok"


MOVE_MIN_PCT = 10.0          # below this, a shift from the personal baseline is treated as noise
MOVE_MIN_SD = 1.5            # or this many personal standard deviations


def _personal_move(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Shift of the last point relative to the marker's OWN history.

    Why: the position inside the reference corridor is nearly uninterpretable for an individual
    person. The corridor is the central 95 % of a healthy population, so any healthy person lands
    in the outer 10–13 % of its width in about 5 % of cases at each edge by construction alone.
    For most analytes the index of individuality is below 0.6, that is, the population interval
    senses the changes of a particular person poorly, and what has to be watched is the deviation
    from that person's own level.

    A shift counts as significant when it exceeds BOTH 10 % of the personal baseline AND one and
    a half personal standard deviations (when there is enough history to estimate the scatter)."""
    if not series or len(series) < 2:
        return None
    s = sorted(series, key=lambda p: p["date"])
    prior = [p["value"] for p in s[:-1] if isinstance(p.get("value"), (int, float))]
    v = s[-1].get("value")
    if not prior or not isinstance(v, (int, float)):
        return None
    prior_sorted = sorted(prior)
    n = len(prior_sorted)
    base = (prior_sorted[n // 2] if n % 2 else (prior_sorted[n // 2 - 1] + prior_sorted[n // 2]) / 2)
    if base == 0:
        return None
    delta_pct = (v - base) / abs(base) * 100
    sd = None
    if n >= 3:
        mean = sum(prior) / n
        sd = (sum((x - mean) ** 2 for x in prior) / (n - 1)) ** 0.5
    sig = abs(delta_pct) >= MOVE_MIN_PCT
    if sd is not None and sd > 0:
        sig = sig and abs(v - base) >= MOVE_MIN_SD * sd
    return {"baseline": round(base, 4), "points": n, "delta_pct": round(delta_pct, 1),
            "significant": bool(sig), "direction": "up" if v > base else ("down" if v < base else "flat")}


def _decision_limits(key: str, value: float, active_classes: Optional[set] = None) -> List[Dict[str, Any]]:
    """Clinical action thresholds for a marker: which are crossed and which are not.

    This is a DIFFERENT object from the reference interval: a threshold is derived from
    outcomes, not from the distribution of the healthy. It can lie inside the lab corridor
    (prediabetes at HbA1c 5.7 with a reference up to 6.0) or far outside it (haematocrit 54 %
    on testosterone therapy with a lab ceiling of 49.0)."""
    out = []
    for t in core.clinical_thresholds().get("markers", {}).get(key, []):
        need = t.get("applies_when_class")
        if need and (active_classes is None or need not in active_classes):
            continue
        try:
            crossed = value >= t["value"] if t.get("side") == "high" else value <= t["value"]
        except Exception:
            continue
        out.append({**t, "crossed": bool(crossed),
                    "distance_pct": round((value - t["value"]) / abs(t["value"]) * 100, 1) if t["value"] else None})
    # order: the crossed ones first; among those not crossed — the ones tied to an active
    # drug class (for haematocrit on testosterone therapy the relevant threshold is 54, not
    # the general therapy-start threshold of 50), then the nearest by value
    out.sort(key=lambda x: (not x["crossed"], not x.get("applies_when_class"), x.get("value", 0)))
    return out


NEAR_LIMIT_FRACTION = 0.10   # "at the edge" = the last 10 % before the corridor bound


def _near_limit(m: Dict[str, Any], value: float, flag: str,
                censored: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A marker formally within range, but pressed against the edge of the corridor.

    The threshold is 10 % of the bound value (21.8 against a ceiling of 22.0 → 99 % of the corridor
    and "at the edge"; 98.3 against a ceiling of 106 → 93 % and also "at the edge"). For NARROW
    corridors, where 10 % of the bound would cover half the reference range or more (sodium 130–140,
    say), the zone narrows to half the corridor width — otherwise the whole range would be "at the edge".

    The second condition, when the corridor is two-sided: the value has to lie in the outer quarter of
    the corridor. Without it, "at the edge" would be given to, for instance, HbA1c 5.4 with a reference
    of 4.0–6.0 — that is 10 % off the ceiling, but only 70 % of the corridor width, the middle of the
    range and not its edge.

    Returns None if the marker is already out of range (the ordinary flag works there), if the bound is
    absent or non-positive, and for CENSORED results ("< 1:10", "less than 10^4"): there the value is
    stored at the bound itself, and "0 % to the bound" means a negative result, not an approach to it.

    A value that EXACTLY coincides with the bound does not count as "at the edge" either: almost always it
    is the limit of detection of the method (a hormone at 0.09 with a lower bound of 0.09; lithium at 0.001
    with a bound of 0.001) or a step of a coarse scale (log10 CFU with a corridor of 7.0–8.0, stool-analysis
    scores), and not a marker pressed against the ceiling by the measurement."""
    if flag not in ("ok", "norange") or value is None or censored:
        return None
    lo, hi = m.get("ref_low"), m.get("ref_high")
    width = (hi - lo) if (lo is not None and hi is not None and hi > lo) else None
    outer = 0.25   # what share of the corridor at the edge counts as "the edge"
    try:
        if hi is not None and hi > 0:
            thr = hi * (1 - NEAR_LIMIT_FRACTION)
            if width is not None:
                thr = max(thr, hi - width / 2, hi - width * outer)
            if value >= thr and value < hi:
                return {"side": "high", "bound": hi,
                        "margin_pct": round((hi - value) / hi * 100, 1),
                        "corridor_pct": round((value - lo) / width * 100, 1) if width else None}
        if lo is not None and lo > 0:
            thr = lo * (1 + NEAR_LIMIT_FRACTION)
            if width is not None:
                thr = min(thr, lo + width / 2, lo + width * outer)
            if value <= thr and value > lo:
                return {"side": "low", "bound": lo,
                        "margin_pct": round((value - lo) / lo * 100, 1),
                        "corridor_pct": round((value - lo) / width * 100, 1) if width else None}
    except Exception:
        return None
    return None


def _trend(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(series) < 2:
        return None
    s = sorted(series, key=lambda p: p["date"])
    prev, last = s[-2], s[-1]
    delta = round(last["value"] - prev["value"], 3)
    direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
    pct = round(100.0 * delta / prev["value"], 1) if prev["value"] else None
    return {"from_date": prev["date"], "to_date": last["date"], "delta": delta,
            "direction": direction, "pct": pct}


def analyze_labs(markers: Optional[List[str]] = None) -> Dict[str, Any]:
    data = core.labs().get("markers", {})
    keys = markers or list(data.keys())
    try:
        active_classes = set(_active_names_by_class().keys())
    except Exception:
        active_classes = set()
    results = []
    for k in keys:
        m = data.get(k)
        if not m or not m.get("series"):
            continue
        latest = _latest(m["series"])
        flag = _flag_value(m, latest["value"], latest.get("censored"))
        # for "higher_better" (HDL, testosterone, vitamin D, omega-3) the low flag = worse
        direction_pref = m.get("direction")
        # «norange» is not an abnormality — it is the absence of anything to
        # compare against. Counting it as one turns a first screen with two
        # hand-entered numbers into «2 values out of range», which is alarming and
        # false, and the person has no way to tell which of the two it means.
        abnormal = flag not in ("ok", "norange")
        results.append({
            "key": k, "name": m["name"], "unit": m.get("unit", ""),
            "value": latest["value"], "date": latest["date"],
            "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
            "flag": flag, "abnormal": abnormal, "direction_pref": direction_pref,
            "near_limit": None,   # set below, after the personal shift has been assessed
            "personal_move": None,
            "decisions": _decision_limits(k, latest["value"], active_classes),
            "trend": _trend(m["series"]),
            "series": sorted(m["series"], key=lambda p: p["date"]),
            "genome_link": m.get("genome_link"), "note": m.get("note"),
        })
    # "At the edge" is set only if the marker is MOVING towards that bound relative to its
    # own history. Otherwise the flag catches markers that have stood there all their life:
    # without this condition it fired on markers that were flat or even moving away from the
    # bound — attention without information.
    for r in results:
        raw = data.get(r["key"], {})
        latest_v, cens = r["value"], None
        for p in raw.get("series", []):
            if p.get("date") == r["date"]:
                cens = p.get("censored")
        nl = _near_limit(raw, latest_v, r["flag"], cens)
        if not nl:
            continue
        mv = _personal_move(raw.get("series", []))
        r["personal_move"] = mv
        if mv is None:                       # no history — nothing to judge by, it is kept
            nl["movement"] = _t("near.no_history")
        elif mv["significant"] and ((nl["side"] == "high" and mv["direction"] == "up") or
                                    (nl["side"] == "low" and mv["direction"] == "down")):
            nl["movement"] = _t("near.moved_from_baseline", delta=f"{mv['delta_pct']:+g}",
                                baseline=f"{mv['baseline']:g}")
        else:
            continue                         # stands at the edge but goes nowhere — not flagged
        r["near_limit"] = nl

    # sorting: the abnormal first, then by name
    results.sort(key=lambda r: (not r["abnormal"], r["name"]))
    abnormal = [r for r in results if r["abnormal"]]
    near = [r for r in results if r.get("near_limit")]
    crossed = [r for r in results if any(d["crossed"] for d in r.get("decisions", []))]
    return {"status": "ok", "count": len(results), "abnormal_count": len(abnormal),
            "near_limit_count": len(near), "decision_crossed_count": len(crossed),
            "markers": results, "disclaimer": DISCLAIMER()}


# ==========================================================================
# 3. Suggestion of additional lab tests (rules)
# ==========================================================================
def _latest_value(marker_key: str) -> Optional[float]:
    m = core.labs().get("markers", {}).get(marker_key)
    if not m or not m.get("series"):
        return None
    return _latest(m["series"])["value"]


_OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b}


def _eval_condition(cond: Dict[str, Any]) -> bool:
    if "all" in cond:
        return all(_eval_condition(c) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(c) for c in cond["any"])
    if "marker" in cond and "op" in cond:
        val = _latest_value(cond["marker"])
        if val is None:
            return False
        return _OPS[cond["op"]](val, cond["value"])
    if "trend" in cond:
        m = core.labs().get("markers", {}).get(cond["trend"]["marker"])
        t = _trend(m["series"]) if m and m.get("series") else None
        return bool(t and t["direction"] == cond["trend"]["direction"])
    if "med_contains" in cond:
        q = cond["med_contains"].lower()
        return any(q in mn for mn in core.medication_names())
    if "med_class" in cond:
        return cond["med_class"] in core.active_med_classes()
    if "genome_gap" in cond:
        return cond["genome_gap"] in core.genome_gaps()
    return False


_PRIORITY_ORDER = {"high": 0, "moderate": 1, "low": 2}


def _marker_last_date(keys) -> Optional[str]:
    """The most recent measurement date among the given markers (or None)."""
    mk = core.labs().get("markers", {})
    ds = []
    for k in keys or []:
        m = mk.get(k)
        if m and m.get("series"):
            try:
                ds.append(max(p["date"] for p in m["series"] if p.get("date")))
            except Exception:
                pass
    return max(ds) if ds else None


def suggest_tests() -> Dict[str, Any]:
    """What else to take. A rule with a ``covers`` field (the markers it monitors) is marked
    ``done_recently`` if all of them were measured within the last ``recheck_months``
    (3 by default) — then it is not an extra order but routine monitoring: it goes down the list."""
    triggered = []
    for rule in core.test_rules().get("rules", []):
        try:
            if _eval_condition(rule["when"]):
                item = {k: rule[k] for k in ("id", "suggest", "why", "priority", "specialist") if k in rule}
                covers = rule.get("covers")
                if covers:
                    ld = _marker_last_date(covers)
                    if ld and _recent(ld, rule.get("recheck_months", 3)):
                        item["done_recently"] = True
                        item["last_measured"] = ld
                        item["recheck_months"] = rule.get("recheck_months", 3)
                triggered.append(item)
        except Exception as e:  # a rule must not take the whole tool down
            triggered.append({"id": rule.get("id", "?"), "error": str(e)})
    # recently done monitoring goes to the end; inside the groups — by priority
    triggered.sort(key=lambda r: (bool(r.get("done_recently")),
                                  _PRIORITY_ORDER.get(r.get("priority", "low"), 3)))
    pending = [r for r in triggered if not r.get("done_recently")]
    return {"status": "ok", "count": len(pending), "total": len(triggered),
            "suggestions": triggered, "disclaimer": DISCLAIMER()}


# a convenient aggregate — a snapshot of the profile
def load_profile() -> Dict[str, Any]:
    return {
        "subject_id": core.pharmacogenomics().get("meta", {}).get("subject_id", "?"),
        "genome_gaps": core.genome_gaps(),
        "labs_markers": list(core.labs().get("markers", {}).keys()),
        "pgx_genes": sorted({g.get("gene") for g in core.pharmacogenomics().get("genotypes", [])}),
    }


def overview() -> Dict[str, Any]:
    """Summary for the main screen: red flags, counters, gaps."""
    labs = analyze_labs()
    tests = suggest_tests()
    # The overview is a current snapshot: only the markers measured within the last 12 months
    # (a sliding window from today). Older deviations are not shown on the main screen.
    red = [m for m in labs["markers"] if m["flag"] not in ("ok", "norange") and _recent(m.get("date"))]
    stale = sum(1 for m in labs["markers"] if m["flag"] not in ("ok", "norange") and not _recent(m.get("date")))
    return {
        "subject_id": core.pharmacogenomics().get("meta", {}).get("subject_id", "?"),
        "abnormal_count": len(red),
        "stale_abnormal_count": stale,
        "markers_total": labs["count"],
        "high_flags": [m for m in red if m["flag"] == "high"],
        "watch_flags": [m for m in red if m["flag"] == "low"],
        "suggestions_count": tests["count"],
        "high_suggestions": [s for s in tests["suggestions"]
                             if s.get("priority") == "high" and not s.get("done_recently")],
        "genome_gaps": core.genome_gaps(),
        "genome": genome_status(),
        "medications_count": len(core.medications_json().get("medications", [])),
        "metrics": _metrics_overview(),
        "lifestyle": _lifestyle_overview(),
        "disclaimer": DISCLAIMER(),
    }


def _metrics_overview() -> Dict[str, Any]:
    ms = metrics_summary()
    filled = [m for m in ms["metrics"] if m["value"] is not None]
    watch = [{"name": m["name"], "value": m["value"], "unit": m["unit"], "flag": m["flag"]}
             for m in filled if m["flag"] in ("high", "low")]
    return {"bmi": ms.get("bmi"), "age": ms.get("age"),
            "filled_count": len(filled), "watch": watch}


# "watch" drugs for the second look (clinically frequent + relevant to the profile).
#
# These are QUERIES against the drug dictionary — but unlike a name the person typed,
# they are generated by the system, and `check_drug_gene` echoes its query back as the
# `drug` field of the answer. A fixed Russian list therefore printed Russian drug names
# into the English report: the query language leaked into the output language. Each entry
# is a language map, resolved at call time, so the report names the drug in the language
# it is being read in while the lookup still hits the same dictionary entry.
_WATCHLIST = [
    {"en": "clopidogrel",  "ru": "клопидогрел"},
    {"en": "statin",       "ru": "статин"},
    {"en": "warfarin",     "ru": "варфарин"},
    {"en": "omeprazole",   "ru": "омепразол"},
    {"en": "azathioprine", "ru": "азатиоприн"},
    {"en": "methotrexate", "ru": "метотрексат"},
]


def metrics_summary() -> Dict[str, Any]:
    """Personal health metrics: latest values, trends, flags + the BMI computation."""
    data = core.metrics_json()
    prof = data.get("profile", {})
    out = []
    latest_weight = None
    for k, m in data.get("metrics", {}).items():
        series = m.get("series") or []
        latest = _latest(series) if series else None
        row = {"key": k, "name": m.get("name", k), "unit": m.get("unit", ""),
               "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
               "direction": m.get("direction"),
               "value": latest["value"] if latest else None,
               "date": latest["date"] if latest else None,
               "flag": _flag_value(m, latest["value"], latest.get("censored")) if latest else "unknown",
               "trend": _trend(series), "series": sorted(series, key=lambda p: p["date"])}
        if k == "weight" and latest:
            latest_weight = latest["value"]
        out.append(row)
    out.sort(key=lambda r: (r["value"] is None, r["name"]))
    # BMI from the height + the latest weight
    bmi = None
    h = prof.get("height_cm")
    if h and latest_weight:
        try:
            bmi_val = round(latest_weight / (float(h) / 100) ** 2, 1)
            cat = _t("bmi.under" if bmi_val < 18.5 else "bmi.normal" if bmi_val < 25
                     else "bmi.over" if bmi_val < 30 else "bmi.obese")
            flag = "ok" if 18.5 <= bmi_val < 25 else ("low" if bmi_val < 18.5 else "high")
            bmi = {"value": bmi_val, "category": cat, "flag": flag}
        except Exception:
            bmi = None
    age = None
    if prof.get("birth_year"):
        try:
            from datetime import date
            age = date.today().year - int(prof["birth_year"])
        except Exception:
            age = None
    return {"status": "ok", "profile": prof, "age": age, "bmi": bmi,
            "metrics": out, "disclaimer": DISCLAIMER()}


def genome_lookup(rsid: Optional[str] = None, gene: Optional[str] = None) -> Dict[str, Any]:
    """Lookup of any locus in the personal full VCF (through the coordinate reference)."""
    from . import genome
    r = genome.lookup(rsid=rsid, gene=gene)
    r["disclaimer"] = DISCLAIMER()
    return r


def genome_status() -> Dict[str, Any]:
    from . import genome
    return genome.available()


def clinvar_findings(limit: int = 200) -> Dict[str, Any]:
    """The patient's clinically significant findings (ClinVar × the personal VCF)."""
    from . import genome
    r = genome.clinvar_hits(limit=limit)
    r["disclaimer"] = DISCLAIMER()
    r["penetrance"] = _penetrance_block()
    return r


def _penetrance_block() -> Dict[str, Any]:
    """Penetrance caveats — what a list of pathogenic findings misleads without."""
    from . import genome
    pn = genome.penetrance_notes()
    return {"one_line": pn.get("_meta", {}).get("one_line"),
            "principles": [{"title": p.get("title"), "text": p.get("text"), "source": p.get("source")}
                           for p in pn.get("principles", [])]}


def acmg_findings() -> Dict[str, Any]:
    """ACMG SF secondary findings + the layer of honesty about interpretation."""
    from . import genome
    r = genome.acmg_sf_findings()
    r["disclaimer"] = DISCLAIMER()
    r["penetrance"] = _penetrance_block()
    return r


def apoe() -> Dict[str, Any]:
    from . import genome
    return genome.apoe_status()


# ==========================================================================
# Polygenic risks (PGS) and the longevity layer (LongevityMap)
# ==========================================================================
def PRS_DISCLAIMER() -> str:
    """The caveat specific to polygenic scores — see the note on DISCLAIMER()."""
    return _t("disclaimer.prs")


def _annotate_prs_evidence(traits: List[Dict[str, Any]]) -> None:
    """Set the level of evidence from knowledge/prs_traits.json.

    Without it all 74 traits look equally weighty, and that is not true: coronary
    artery disease and prostate cancer have prospective data, most of the rest have
    only a population association.
    """
    cat = core._read_knowledge("prs_traits.json")
    tiers = (cat.get("_meta") or {}).get("evidence_tiers", {})
    by_term, by_label = {}, {}
    for c in cat.get("traits", []):
        if c.get("term"):
            by_term[c["term"].lower()] = c
        if c.get("label"):
            by_label[c["label"].lower()] = c
    for t in traits:
        src = by_term.get(str(t.get("term", "")).lower()) or by_label.get(str(t.get("label", "")).lower())
        if not src:
            continue
        ev = src.get("evidence")
        if not ev:
            continue
        t["evidence"] = ev
        t["evidence_label"] = (tiers.get(ev) or {}).get("label", ev)
        if src.get("evidence_note"):
            t["evidence_note"] = src["evidence_note"]


def prs_findings() -> Dict[str, Any]:
    """Aggregated polygenic scores (profile/prs_results.json), grouped by category.

    Returns {categories:[{category, traits:[...]}], high[], stats, disclaimer}.
    high — the reliable traits with a percentile ≥80 (what to look at when screening).
    """
    data = core.prs_results()
    traits = data.get("traits", []) if isinstance(data, dict) else []
    if not traits:
        return {"available": False, "disclaimer": PRS_DISCLAIMER(),
                "message": _t("prs.not_computed")}
    for tr in traits:                      # a guard layer: double counting of the input shows at once
        _mr = tr.get("match_rate")
        if isinstance(_mr, (int, float)) and _mr > 1.0001:
            tr["reliable"] = False
            tr["integrity_note"] = _t("prs.integrity_double")
    _annotate_prs_evidence(traits)
    cats: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for t in traits:
        c = t.get("category") or _t("prs.category_other")
        if c not in cats:
            cats[c] = []; order.append(c)
        cats[c].append(t)
    def pnum(t):
        p = t.get("percentile")
        return p if isinstance(p, (int, float)) else -1
    high = sorted([t for t in traits if t.get("reliable") and pnum(t) >= 80],
                  key=lambda t: -pnum(t))
    reliable = [t for t in traits if t.get("reliable")]
    return {
        "available": True,
        "categories": [{"category": c, "traits": cats[c]} for c in order],
        "high": high,
        "stats": {"total": len(traits), "reliable": len(reliable),
                  "high": len(high), "superpopulation": (data.get("_meta") or {}).get("superpopulation", "EUR"),
                  "updated": (data.get("_meta") or {}).get("updated")},
        "disclaimer": PRS_DISCLAIMER(),
    }


def genome_updates() -> Dict[str, Any]:
    """Result of the last check for database updates (genome/whats_new.json).
    Shows what appeared when the genome was checked against a fresh ClinVar."""
    data = core.whats_new()
    if not data or not data.get("clinvar"):
        return {"available": False}
    cv = data.get("clinvar", {})
    return {"available": True, "last_checked": data.get("last_checked"),
            "clinvar": {"release": cv.get("release"), "new": cv.get("new", []),
                        "changed": cv.get("changed", []), "counts": cv.get("counts", {})}}


def longevity_findings() -> Dict[str, Any]:
    """Longevity layer (LongevityMap × the owner's genome, profile/longevity_findings.json).

    Returns {available, apoe, known[], significant_genes[], stats, disclaimer}.
    The key parts are the APOE ε status and the well-studied markers (FOXO3 and so on).
    """
    data = core.longevity_data()
    if not data or not data.get("known"):
        return {"available": False, "disclaimer": DISCLAIMER(),
                "message": _t("longevity.not_built")}
    sig = data.get("significant_by_gene", {}) or {}
    # the famous longevity genes come first
    famous = ["FOXO3", "APOE", "SIRT1", "SIRT3", "CETP", "IL6", "TP53", "KL", "IGF1R",
              "AKT1", "APOC3", "ADIPOQ", "ACE", "TOMM40"]
    genes = sorted(sig.keys(), key=lambda g: (famous.index(g) if g in famous else 999, g))
    sig_genes = [{"gene": g, "variants": sig[g]} for g in genes]
    meta = data.get("_meta", {})
    return {
        "available": True,
        "apoe": data.get("apoe"),
        "known": data.get("known", []),
        "significant_genes": sig_genes,
        "stats": {"genotyped": meta.get("genotyped"), "carriers": meta.get("carriers"),
                  "significant_carriers": meta.get("significant_carriers"),
                  "significant_genes": len(sig_genes)},
        "disclaimer": (meta.get("disclaimer") or "") + " " + DISCLAIMER(),
    }


def _goal_series(ref: str) -> List[Dict[str, Any]]:
    """Resolve a source of the SINGLE data model into a sorted series [{date,value}].

    ref of the form 'lab:<marker>' (labs.json markers[key].series) or
    'wear:<Metric>' (wearable_trends.json metrics[Metric] = {YYYY-MM: value}).
    That way the goal chart feeds on the project's LIVE data and not on a copy of its own.
    """
    if not ref:
        return []
    kind, _, key = ref.partition(":")
    pts: List[Dict[str, Any]] = []
    if kind == "lab":
        m = core.labs().get("markers", {}).get(key) or {}
        for p in m.get("series", []) or []:
            if p.get("value") is not None and p.get("date"):
                pts.append({"date": str(p["date"]), "value": float(p["value"])})
    elif kind == "wear":
        data = core.wearable_trends()
        msrc = data.get("metrics") if isinstance(data.get("metrics"), dict) else data
        sd = (msrc or {}).get(key)
        if isinstance(sd, dict):
            for y, v in sd.items():
                if isinstance(v, (int, float)):
                    pts.append({"date": str(y), "value": float(v)})
    return sorted(pts, key=lambda p: p["date"])


def _goal_lv(ref: str) -> Dict[str, Any]:
    """Series → {l:[dates], v:[values]} for Chart.js."""
    s = _goal_series(ref)
    return {"l": [p["date"] for p in s], "v": [p["value"] for p in s]}


def _goal_merge(ref_a: str, ref_b: str) -> Dict[str, Any]:
    """Two series on a common sorted date axis (gaps = null, spanGaps on the client)."""
    a, b = _goal_series(ref_a), _goal_series(ref_b)
    da = {p["date"]: p["value"] for p in a}
    db = {p["date"]: p["value"] for p in b}
    labels = sorted(set(da) | set(db))
    return {"l": labels,
            "a": [da.get(x) for x in labels],
            "b": [db.get(x) for x in labels]}


def _goal_num(v: Optional[float]) -> str:
    """Number → a string in the Russian style (comma; integers without a fraction)."""
    if v is None:
        return "—"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.1f}".replace(".", ",")


def _goal_now(source: str) -> str:
    """Current value(s) for the source(s). 'lab:a|lab:b' → 'a_last / b_last'."""
    parts = []
    for ref in source.split("|"):
        s = _goal_series(ref.strip())
        parts.append(_goal_num(s[-1]["value"]) if s else "—")
    return " / ".join(parts)


def goal_dashboard() -> Dict[str, Any]:
    """Dashboard of the GOAL ("get the 2021–2022 shape back") on the project's SINGLE data model.

    The curated part (the wording, the anchor points, the reference values, the chart parameters)
    comes from profile/health_goals.json. The current values and all the series are LIVE from
    labs.json and wearable_trends.json (the same sources the rest of the application sees).
    """
    g = core.health_goals()
    if not g or not g.get("targets"):
        return {"available": False, "disclaimer": DISCLAIMER(),
                "message": _t("goal.not_set")}

    targets = [{"label": t["label"], "now": _goal_now(t.get("source", "")),
                "best": t.get("best", ""), "target": t.get("target", "")}
               for t in g.get("targets", [])]

    ch = g.get("charts", {}) or {}
    charts: Dict[str, Any] = {}

    if "weight" in ch:
        c = ch["weight"]
        charts["weight"] = {**{k: c[k] for k in ("title", "cap", "band", "targets", "min", "max") if k in c},
                            **_goal_lv(c.get("source", ""))}
    if "bodycomp" in ch:
        c = ch["bodycomp"]
        m = _goal_merge(c.get("fat", ""), c.get("mus", ""))
        charts["bodycomp"] = {**{k: c[k] for k in ("title", "cap", "targets", "ymin", "ymax", "y2min", "y2max") if k in c},
                              "l": m["l"], "fat": m["a"], "mus": m["b"]}
    if "minis" in ch:
        minis = []
        for c in ch["minis"]:
            minis.append({**{k: c[k] for k in ("id", "title", "cap", "color", "tgt", "tlabel", "min", "max") if k in c},
                          **_goal_lv(c.get("source", ""))})
        charts["minis"] = minis
    for dual in ("fit", "la"):
        if dual in ch:
            c = ch[dual]
            m = _goal_merge(c.get("a", ""), c.get("b", ""))
            charts[dual] = {**{k: c[k] for k in ("title", "cap", "band", "targets", "ymin", "ymax",
                                                 "y2min", "y2max", "a_label", "b_label", "a_color", "b_color") if k in c},
                            "l": m["l"], "a": m["a"], "b": m["b"]}

    return {
        "available": True,
        "title": g.get("title") or _t("goal.title_default"),
        "headline": g.get("headline", ""),
        "as_of": core.file_date(core.profile_dir() / "wearable_trends.json") or g.get("_meta", {}).get("updated"),
        "peaks": g.get("peaks", []),
        "targets": targets,
        "charts": charts,
        "disclaimer": DISCLAIMER(),
    }


def _guidance_for(drug: str, gene: str) -> Dict[str, Any]:
    """The recommendation table for the PAIR (drug, gene), or nothing.

    Matching on the gene alone is what let a proton pump inhibitor be answered
    out of the clopidogrel table. There is no safe fallback here: a table for
    another drug on the same gene is not an approximation, it can be the
    opposite advice. An empty result is handled by the caller as "no specific
    recommendation", which is true.
    """
    q = (drug or "").strip().lower()
    if not q:
        return {}
    for d in core.cpic_kb().get("drugs", []):
        if d.get("gene") != gene:
            continue
        for name in d.get("names", []):
            if q == name or q in name or name in q:
                return d.get("guidance", {}) or {}
    return {}


def _check_drug_online(drug: str) -> Dict[str, Any]:
    """Fallback when the drug is not in the local base: the international RxNorm/RxClass bases are searched."""
    from . import drugsource
    info = drugsource.resolve_drug(drug)
    if not info:
        return {"status": "not_found", "drug": drug, "disclaimer": DISCLAIMER(),
                "message": _t("drug.not_found", drug=drug)}
    cls = info.get("internal_class")
    atc_names = ", ".join(a.get("name", "") for a in info.get("atc", []) if a.get("name"))
    disp = info.get("name") or drug
    ing = info.get("ingredient")
    if ing and ing.lower() not in disp.lower():
        disp = f"{disp} ({ing})"
    gene_hint = drugsource.class_gene(cls)
    if gene_hint:
        gene, why = gene_hint
        ph = compute_phenotype(gene)
        phenotype = ph["phenotype"]
        # The recommendation table belongs to the pair (drug, gene), never to the
        # gene alone. Taking the first record with a matching gene handed a proton
        # pump inhibitor the clopidogrel table — the first CYP2C19 entry in the
        # catalogue — and that table is not merely somebody else's, it is
        # pharmacologically inverted: for a PPI a reduced CYP2C19 function means
        # MORE exposure, not an insufficient effect. The screen said "consider a
        # platelet function test" about omeprazole.
        #
        # If this drug has no table of its own, no table is used. A generic
        # gene-level caution is honest; a specific recommendation borrowed from a
        # different drug is not.
        guidance = _guidance_for(drug, gene)
        flag = guidance.get(phenotype) or {"level": "unknown" if phenotype == "unknown" else "low",
                                           "note": _t("drug.nothing_notable_ask")}
        return {"status": "ok", "drug": disp, "gene": gene,
                "drug_class": atc_names or (cls or ""), "why": why,
                "phenotype": phenotype, "phenotype_label": ph.get("label", ""),
                "level": flag["level"], "recommendation": flag["note"],
                "markers_found": ph.get("found") or core.markers_for_gene(gene),
                "resolved_by": "rxnorm", "reference": info.get("url"),
                "disclaimer": DISCLAIMER()}
    # found online, but there is no pharmacogene for the class — said honestly + the class for interactions
    return {"status": "found_online", "drug": disp,
            "drug_class": atc_names or (cls or _t("drug.class_unknown")),
            "internal_class": cls, "reference": info.get("url"), "disclaimer": DISCLAIMER(),
            "message": _t("drug.online_headline", drug=disp,
                          class_note=_t("drug.online_class_note", classes=atc_names) if atc_names else "",
                          tail=_t("drug.online_check_interactions") if cls
                               else _t("drug.online_ask_doctor"))}


def _classes_for(drug: str) -> List[str]:
    """Classes of a drug: first the local dictionary, then the international base (RxClass ATC)."""
    local = core.classify_drug(drug)
    if local:
        return local
    from . import drugsource
    info = drugsource.resolve_drug(drug)
    cls = info.get("internal_class") if info else None
    return [cls] if cls else []


_SEV_ORDER = {"high": 0, "moderate": 1, "low": 2}


def check_interactions(drug: str) -> Dict[str, Any]:
    """Interactions of a NEW drug with the patient's current prescriptions (by class).
    The class is taken from the local dictionary, and failing that — from the international RxClass base."""
    new_classes = _classes_for(drug)
    active = core.active_med_classes()
    if not new_classes:
        # telling apart: the drug was not found at all vs found online, but its class has no interaction rules
        from . import drugsource
        info = drugsource.resolve_drug(drug)
        if info:
            atc = ", ".join(a.get("name", "") for a in info.get("atc", []) if a.get("name"))
            return {"status": "no_rules", "drug": info.get("name", drug), "new_classes": [],
                    "interactions": [], "atc": atc,
                    "message": _t("interactions.no_rules", atc=atc or _t("common.na"))}
        return {"status": "unknown_class", "drug": drug, "new_classes": [],
                "interactions": [],
                "message": _t("interactions.unknown_drug")}
    hits = []
    names_by_class = _active_names_by_class()
    for rule in core.drug_interactions().get("interactions", []):
        a, b = rule.get("a"), rule.get("b")
        pair = None
        if a in new_classes and b in active:
            pair = b
        elif b in new_classes and a in active:
            pair = a
        if pair:
            hits.append({**rule, "with_class": pair,
                         "with_meds": names_by_class.get(pair, [])})
    hits.sort(key=lambda r: _SEV_ORDER.get(r.get("severity"), 3))
    # `baseline` says WHAT the new drug was compared against. Without it an empty
    # `interactions` list is ambiguous, and the ambiguity falls on the most common
    # state there is: a fresh install before the first `add-med`, where the answer
    # "no interactions found with your current prescriptions" was byte-identical
    # to the answer given to a person on five drugs. Nothing was checked; the
    # sentence claimed it was.
    # …and `unclassified` says what the comparison could NOT see. `empty` covers only
    # the extreme: a profile with no prescriptions at all. A list of two, one of them
    # a name the dictionary does not recognise, gave `empty: False` and the flat
    # sentence "no explicit interactions with the current prescriptions were found" —
    # a negative statement resting on half the list, with the unread half never
    # named. Naming it costs one line and turns a claim into an instruction.
    unrecognised = [m.get("name", "") for m in core.medications_json().get("medications", [])
                    if m.get("name") and not core.classify_drug(m["name"])]
    return {"status": "ok", "drug": drug, "new_classes": new_classes,
            "interactions": hits, "count": len(hits),
            "baseline": {"classes": sorted(active), "count": len(active),
                         "empty": not active, "unclassified": unrecognised}}


def _active_names_by_class() -> Dict[str, List[str]]:
    """Which of the patient's concrete prescriptions fall into each active class."""
    out: Dict[str, List[str]] = {}
    names = core.medications_json().get("medications", [])
    classes = core.med_classes().get("classes", {})
    for m in names:
        nm = m.get("name", "")
        for cls in core.classify_drug(nm):
            out.setdefault(cls, [])
            if nm not in out[cls]:
                out[cls].append(nm)
    return out


def _assess_gene(gene: str) -> Dict[str, Any]:
    """Assessment of a gene by the PATIENT'S DATA: a phenotype (if the gene is modelled and covered)
    or raw variants from the full genome base. Works from the full VCF, not from a fixed list."""
    from . import genome
    kb = core.cpic_kb()
    modelled = gene in kb.get("genes", {})
    covered = gene not in core.genome_gaps()
    if modelled and covered:
        ph = compute_phenotype(gene)
        return {"gene": gene, "computable": True, "phenotype": ph["phenotype"],
                "label": ph.get("label", ""), "markers": ph.get("found", [])}
    markers = core.markers_for_gene(gene)
    ready = genome.available()["ready"]
    for rs, l in genome.loci().get("loci", {}).items():   # the gene loci are taken from the full VCF
        if l.get("gene", "").upper() == gene.upper():
            gt = core.genotype_at(rs)
            if gt and not any(m.get("rsid") == rs for m in markers):
                markers.append({"rsid": rs, "genotype": gt, "interpretation": ""})
    note = _t("gene.covered_by_vcf" if ready else "gene.vcf_pending")
    return {"gene": gene, "computable": False,
            "phenotype": "reported" if markers else "pending",
            "label": note, "markers": markers}


def _genome_for_drug(drug: str, info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Genes important for the drug (the local base + CPIC by rxcui for ANY drug),
    assessed against the patient's genome."""
    from . import genome, drugsource
    genes: Dict[str, Dict[str, Any]] = {}
    q = (drug or "").lower()
    for entry in core.cpic_kb().get("drugs", []):
        if any(q == n or q in n or n in q for n in entry.get("names", [])):
            # The level is a VALUE the code compares — format.py and the web page both
            # test it against this exact word to tell the project's own base from CPIC.
            genes.setdefault(entry["gene"], {"level": "куратор", "actionable": True})
    # Whether the international database was actually reached. An empty answer and
    # an unreachable source are different facts, and only the first of them
    # licenses «this drug has no meaningful pharmacogenetics» downstream.
    cpic = drugsource.cpic_lookup(info["rxcui"]) if (info and info.get("rxcui")) \
        else {"genes": [], "asked": False, "reason": "not_identified"}
    for g in cpic["genes"]:
        if g["actionable"]:          # only the clinically significant ones (CPIC A/B); level D is noise
            genes.setdefault(g["gene"], {"level": g["level"], "actionable": True})
    assessed = []
    for gene, meta in genes.items():
        a = _assess_gene(gene)
        a["cpic_level"], a["actionable"] = meta["level"], meta["actionable"]
        assessed.append(a)
    assessed.sort(key=lambda a: (not a.get("actionable"), not a.get("computable")))
    return {"genes": assessed, "genome_ready": genome.available()["ready"],
            "has_pgx": bool(assessed),
            "cpic": {"asked": cpic.get("asked", False), "reason": cpic.get("reason")}}


def _labs_for_drug(classes: List[str]) -> Dict[str, Any]:
    """Which of YOUR lab tests matter with this drug (by class) and their current state."""
    mon = core.drug_lab_monitoring().get("classes", {})
    by = {m["key"]: m for m in analyze_labs()["markers"]}
    rows, whys, seen = [], [], set()
    for c in classes:
        spec = mon.get(c)
        if not spec:
            continue
        if spec.get("why"):
            whys.append(spec["why"])
        for k in spec.get("labs", []):
            if k in seen:
                continue
            seen.add(k)
            m = by.get(k)
            rows.append({"key": k, "present": m is not None,
                         "name": m["name"] if m else k, "value": m["value"] if m else None,
                         "unit": m["unit"] if m else "", "flag": m["flag"] if m else "nodata",
                         "near_limit": m.get("near_limit") if m else None,
                         "decisions": m.get("decisions") if m else [],
                         "personal_move": m.get("personal_move") if m else None,
                         "ref_low": m.get("ref_low") if m else None, "ref_high": m.get("ref_high") if m else None})
    # Which of the drug's classes the monitoring catalogue actually has a rule for.
    # An empty `markers` used to print «no lab monitoring is required for this
    # class» whether the catalogue said so or simply had no entry — nine of the
    # project's 41 classes have no entry, among them SSRI/SNRI, clopidogrel and
    # amiodarone, all of which need monitoring in real life.
    return {"reason": "; ".join(dict.fromkeys(whys)), "markers": rows,
            "basis": {"classes": list(classes),
                      "with_rules": [c for c in classes if c in mon]},
            "watch": [r for r in rows if r["flag"] in ("high", "low")],
            "near": [r for r in rows if r.get("near_limit")],
            "crossed": [r for r in rows if any(d["crossed"] for d in (r.get("decisions") or []))]}


def _rsids_for_genes(gene_names) -> Dict[str, str]:
    """rsID → gene for the given genes (from the CPIC model and the loci.json catalogue)."""
    from . import genome
    want = {g.upper() for g in gene_names if g}
    out: Dict[str, str] = {}
    for gname, gdef in core.cpic_kb().get("genes", {}).items():
        if gname.upper() in want:
            for m in gdef.get("markers", []):
                if m.get("rsid"):
                    out[m["rsid"]] = gname
    for rs, l in genome.loci().get("loci", {}).items():
        if (l.get("gene", "") or "").upper() in want:
            out.setdefault(rs, l.get("gene"))
    return out


def clinvar_for_drug(drug: str, genome_sec: Dict[str, Any], info=None) -> Dict[str, Any]:
    """Find the patient's ClinVar findings that relate to the drug: by the rsIDs of the drug's genes
    (drug_response/risk/pathogenic) and by a mention of the drug name in the description of a finding.
    Refreshed by the monthly ClinVar check (update_check.sh)."""
    from . import genome as gm
    try:
        cv = gm.clinvar_hits(limit=2000)
    except Exception:  # noqa
        return {"available": False, "hits": []}
    if cv.get("status") != "ok":
        return {"available": False, "status": cv.get("status"), "hits": []}
    gene_names = [g.get("gene") for g in (genome_sec or {}).get("genes", [])]
    rs2gene = _rsids_for_genes(gene_names)
    toks = set()
    for s in (drug or "", (info or {}).get("name") or "", (info or {}).get("ingredient") or ""):
        for t in str(s).lower().replace("/", " ").replace(",", " ").split():
            if len(t) >= 4:
                toks.add(t)
    out, seen = [], set()
    for h in cv.get("hits", []):
        rsid = h.get("rsid", "")
        clndn = (h.get("clndn", "") or "").lower()
        by_gene = rsid in rs2gene
        by_drug = any(t in clndn for t in toks)
        if not (by_gene or by_drug):
            continue
        tier = h.get("tier")
        if by_gene and not by_drug and tier not in ("drug", "risk", "pathogenic"):
            continue
        key = f"{rsid}|{h.get('pos')}"
        if key in seen:
            continue
        seen.add(key)
        out.append({"rsid": rsid, "genotype": h.get("genotype"), "clnsig": h.get("clnsig"),
                    "disease": h.get("disease"), "tier": tier,
                    "gene": rs2gene.get(rsid), "by_drug": by_drug})
    order = {"drug": 0, "pathogenic": 1, "risk": 2, "protective": 3}
    out.sort(key=lambda x: order.get(x["tier"], 5))
    return {"available": True, "count": len(out), "hits": out}


def _dose_context(drug: str, info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dose and critical-claim context of a drug from knowledge/dose_evidence.json.

    The point of the layer: not "drug X worsens Y", but the dose, the effect size with a reference,
    the difference between formulations — and the comparison with the patient's CONCRETE numbers
    (labs.json and, for lifestyle metrics, wearable_trends.json). The search goes by the Russian
    spelling and by the RxNorm ingredient — otherwise two spellings of one drug find different entries.
    """
    names = {(drug or "").strip().lower()}
    if info:
        for k in ("name", "ingredient"):
            if info.get(k):
                names.add(str(info[k]).strip().lower())
    ent = (core.dose_evidence().get("entries") or {})
    hit = None
    for key, spec in ent.items():
        pats = [key] + list(spec.get("match") or [])
        if any(p and p.lower() in n for n in names for p in pats):
            hit = spec
            break
    if not hit:
        return {"matched": False}
    by = {m["key"]: m for m in analyze_labs()["markers"]}
    items = []
    for it in hit.get("critical") or []:
        pts = []
        for key in it.get("compare_marker") or []:
            m = by.get(key)
            if m:
                pts.append({"name": m["name"], "value": m["value"], "unit": m.get("unit", ""),
                            "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
                            "flag": m.get("flag"), "measured": True})
                continue
            lv = _brief_life(key)          # a wearable-device metric, not a lab test
            if lv.get("value") and lv.get("value") != "—":
                # the human-readable name and the units come from the public metrics reference
                meta = (core.wearable_metrics().get("metrics") or {}).get(key) or {}
                unit = meta.get("unit", "")
                if any(ch.isdigit() for ch in unit):   # "0–100" is a scale, not a unit
                    unit = ""
                pts.append({"name": meta.get("label") or key,
                            "value": _brief_num(lv.get("value")), "unit": unit,
                            "flag": None, "measured": True})
            else:
                pts.append({"name": key, "measured": False})
        items.append({**{k: it.get(k) for k in
                         ("claim", "dose_dependent", "effect_size", "low_dose_note", "source")},
                      "patient": pts})
    return {"matched": True,
            "nutritional_dose": hit.get("nutritional_dose"),
            "pharmacologic_dose": hit.get("pharmacologic_dose"),
            "items": items, "forms": hit.get("forms"),
            "verdict_rule": hit.get("verdict_rule"),
            "alternatives": hit.get("alternatives") or [],
            "note": hit.get("note")}


def check_new_prescription(drug: str) -> Dict[str, Any]:
    """SECOND OPINION on a prescription — PERSONAL, relative to the patient's data:
    🧬 their genome (the genes important for the drug per CPIC + their genotypes),
    🧪 their labs (which to monitor and what is already out of range),
    🔗 their current prescriptions (interactions). Works for any drug."""
    drug = (drug or "").strip()
    if not drug:
        return {"status": "error", "message": _t("drug.no_name"), "disclaimer": DISCLAIMER()}
    from . import drugsource
    pgx = check_drug_gene(drug)
    info = drugsource.resolve_drug(drug)
    classes = _classes_for(drug)
    genome_sec = _genome_for_drug(drug, info)
    labs_sec = _labs_for_drug(classes)
    inter = check_interactions(drug)
    clinvar_sec = clinvar_for_drug(drug, genome_sec, info)

    atc = ", ".join(a.get("name", "") for a in (info.get("atc") if info else []) if a.get("name"))
    labels = core.med_classes().get("classes", {})
    class_display = (", ".join(labels.get(c, {}).get("label", c) for c in classes) if classes
                     else atc or pgx.get("drug_class") or _t("prescription.class_undefined"))
    disp = (info.get("name") if info else None) or (
        pgx.get("drug") if pgx.get("status") in ("ok", "found_online") else drug)
    ing = info.get("ingredient") if info else None
    if ing and disp and ing.lower() not in disp.lower():
        disp = f"{disp} ({ing})"

    # The verdict, and what could not be determined for it.
    #
    # This used to read `if pgx.get("level") in ("high", "moderate")`, so an
    # `unknown` pharmacogenetic status contributed nothing and the answer came
    # out green. That one condition was the common denominator of five of the six
    # clinical failures found in the audit: the strongest of them was that
    # CONNECTING A GENOME made the answer less cautious than having none, because
    # an unread position turns "no data" into a confident phenotype downstream.
    #
    # An undetermined input now lifts the verdict off `low`, and — separately —
    # it is named. Both halves matter. Escalating without naming leaves the
    # reader guessing which of several inputs is missing; naming without
    # escalating is exactly the defect this project keeps finding in itself:
    # honest prose beside a green machine-readable field.
    concerns, unresolved = [], []
    if pgx.get("status") == "ok":
        # A graded concern and an unresolved input are not alternatives. Clopidogrel
        # with no genotype at all returns `moderate` from its catalogue default —
        # a real recommendation — and the phenotype is still unknown. Treating the
        # two as one branch meant the answer raised the verdict for the right
        # reason and then said nothing about the missing genotype, which is the
        # very thing the reader could act on.
        if pgx.get("level") in ("high", "moderate"):
            concerns.append(pgx["level"])
        if (pgx.get("level") == "unknown" or pgx.get("phenotype") == "unknown"
                or pgx.get("certainty") == "assumed"):
            # The detail names what is missing and what would close it, not just
            # that something is. A verdict raised without an instruction is only
            # half an answer.
            basis = pgx.get("basis") or {}
            miss = ", ".join(f"{m['rsid']}{(' (' + m['star'] + ')') if m.get('star') else ''}"
                             for m in basis.get("missing", []))
            unresolved.append({"what": "pharmacogenetics", "gene": pgx.get("gene"),
                               "missing": [m["rsid"] for m in basis.get("missing", [])],
                               "closable": any(m.get("obtainable")
                                               for m in basis.get("missing", [])),
                               "detail": _t("unresolved.pgx", names=miss)
                                         if miss else (pgx.get("phenotype_label") or "")})
    for it in inter.get("interactions", []):
        concerns.append(it["severity"])
    if inter.get("status") in ("unknown_class", "no_rules"):
        unresolved.append({"what": "interactions", "gene": None,
                           "detail": _t("unresolved.drug_not_classified")})
    elif (inter.get("baseline") or {}).get("empty"):
        unresolved.append({"what": "interactions", "gene": None,
                           "detail": _t("unresolved.no_baseline")})
    elif (inter.get("baseline") or {}).get("unclassified"):
        unresolved.append({"what": "interactions", "gene": None,
                           "detail": _t("unresolved.baseline_partial",
                                        names=", ".join((inter["baseline"]["unclassified"])[:6]))})
    # A source that was never reached cannot license a negative statement. Both of
    # these print as absence — «no pharmacogenetics», «no monitoring required» —
    # and absence of an answer is not absence of a finding.
    cp = genome_sec.get("cpic") or {}
    if not genome_sec.get("genes") and not cp.get("asked"):
        unresolved.append({"what": "pharmacogenetics", "gene": None,
                           "detail": _t("unresolved.pgx_source",
                                        why=_t("pgx_unchecked." + (cp.get("reason")
                                                                   or "unreachable")))})
    lbasis = labs_sec.get("basis") or {}
    if not labs_sec["markers"] and lbasis.get("classes") and not lbasis.get("with_rules"):
        unresolved.append({"what": "monitoring", "gene": None,
                           "detail": _t("unresolved.labs_no_rule", classes=class_display)})
    if labs_sec["watch"]:
        concerns.append("moderate")
    if unresolved:
        concerns.append("moderate")     # not green; the reason travels in `unresolved`
    overall = "high" if "high" in concerns else ("moderate" if "moderate" in concerns else "low")

    return {
        "status": "ok",
        "drug": disp or drug,
        "overall": overall,
        "unresolved": unresolved,
        "class_display": class_display,
        "classes": classes,
        "identified": {"name": disp, "atc": atc,
                       "rxcui": info.get("rxcui") if info else None,
                       "reference": info.get("url") if info else None,
                       "source": "rxnorm" if info else ("local" if pgx.get("status") == "ok" else "none")},
        "genome": genome_sec,
        "labs": labs_sec,
        "interactions": inter,
        "pharmacogenetics": pgx,
        "clinvar": clinvar_sec,
        "dose_context": _dose_context(drug, info),
        "disclaimer": DISCLAIMER(),
    }


def _monitoring_for(drug: str, classes: List[str]) -> List[str]:
    """Short monitoring hints for the class of the new drug."""
    classes_with_tips = ("statin", "anticoagulant_vka", "doac", "thiopurine",
                         "testosterone_replacement", "thyroid_hormone", "ppi",
                         "antiplatelet_p2y12")
    return [_t(f"monitor.{c}") for c in classes_with_tips if c in classes]


def provenance() -> Dict[str, Any]:
    """Origin and freshness of the data by domain — for the "source/updated" marks on the tabs.

    kind: 'local' — personal files on the owner's machine; 'public' — open international
    bases / curated references. updated — the _meta.updated date or the mtime.
    """
    from . import genome
    prof = core.profile_dir()
    kn = core._KNOWLEDGE_DIR

    cfg = core.source_config()

    def loc(name: str, label: str, domain: str) -> Dict[str, Any]:
        p = core.source_path(domain)
        folder = cfg.get(domain)
        origin = (_t("sources.chosen_folder", path=folder) if folder
                  else _t("sources.local_folder", path=f"profile/{name}"))
        return {"kind": "local", "label": label, "origin": origin, "domain": domain,
                "folder": folder, "custom": bool(folder),
                "updated": core.json_updated(p) or core.file_date(p), "present": p.exists()}

    def pub(name: str, label: str, origin: str) -> Dict[str, Any]:
        p = kn / name
        return {"kind": "public", "label": label, "origin": origin,
                "updated": core.json_updated(p) or core.file_date(p), "present": p.exists()}

    # the genome (full VCF) — local
    vp = genome.vcf_path()
    gfolder = cfg.get("genome")
    genome_vcf = {"kind": "local", "label": _t("sources.genome_vcf"), "domain": "genome",
                  "folder": gfolder, "custom": bool(gfolder),
                  "origin": (_t("sources.chosen_folder", path=gfolder) if gfolder
                             else _t("sources.local_folder",
                                     path=vp.parent if vp else "genome/*.vcf.gz")),
                  "updated": core.file_date(vp) if vp else None, "present": vp is not None}

    # ClinVar findings — an international base (NCBI), synchronisation = the mtime of the file/meta
    cv_meta = None
    for base in core.genome_bases():
        mf = base / "clinvar_meta.json"
        hf = base / "clinvar_hits.tsv"
        if mf.exists():
            try:
                cv_meta = core._read_json(mf)
            except Exception:
                cv_meta = None
        if hf.exists():
            clinvar_synced = core.file_date(hf)
            break
    else:
        hf = None
        clinvar_synced = None
    clinvar = {"kind": "public", "label": _t("sources.clinvar"),
               "origin": _t("sources.clinvar_origin"),
               "release": (cv_meta or {}).get("clinvar_date"),
               "updated": (cv_meta or {}).get("synced") or clinvar_synced,
               "present": hf is not None and (hf.exists() if hf else False)}

    # live resolution of rsIDs — Ensembl REST
    cache = core.cache_dir() / "rsid_cache.json"
    ensembl = {"kind": "public", "label": _t("sources.ensembl"),
               "origin": _t("sources.ensembl_origin"),
               "updated": core.file_date(cache), "present": cache.exists()}

    p_life = prof / "wearable_trends.json"
    lifestyle_src = {"kind": "local", "label": _t("sources.lifestyle"),
                     "origin": _t("sources.local_folder",
                                  path="profile/wearable_trends.json"),
                     "updated": core.file_date(p_life), "present": p_life.exists()}
    return {
        "labs": loc("labs.json", _t("sources.labs"), "labs"),
        "medications": loc("medications.json", _t("sources.medications"), "medications"),
        "metrics": loc("metrics.json", _t("sources.metrics"), "metrics"),
        "lifestyle": lifestyle_src,
        "pgx": pub("cpic_drug_gene.json", _t("sources.pgx"), _t("sources.pgx_origin")),
        "interactions": pub("drug_interactions.json", _t("sources.interactions"),
                            _t("sources.interactions_origin")),
        "catalog": pub("loci.json", _t("sources.catalog"), _t("sources.catalog_origin")),
        "test_rules": pub("test_rules.json", _t("sources.test_rules"),
                          _t("sources.test_rules_origin")),
        "genome_vcf": genome_vcf,
        "clinvar": clinvar,
        "ensembl": ensembl,
    }


# The label is a catalogue key, resolved when the radar is built: the key identifies the
# body system, the phrase names it in the reader's language.
_RADAR_DOMAINS = [
    ("lipids", ["cholesterol_total", "ldl", "hdl", "triglycerides"]),
    ("glucose", ["glucose", "hba1c", "homa_ir", "insulin"]),
    ("inflammation", ["crp_hs", "rheumatoid_factor", "homocysteine"]),
    ("hormones", ["testosterone", "igf1", "tsh"]),
    ("liver", ["alt", "ast", "ggt"]),
    ("micronutrients", ["vitamin_d", "omega3_index", "vitamin_b12", "ferritin"]),
    ("renal", ["uric_acid", "creatinine"]),
]


def _wear_status(latest: float, meta: Dict[str, Any]):
    """Status of a lifestyle metric vs the target. Returns (status, score 0–100 or None)."""
    d, tl, th = meta.get("direction"), meta.get("target_low"), meta.get("target_high")
    if d == "higher_better" and tl is not None:
        if latest >= tl:
            return "ok", 100
        if latest >= 0.8 * tl:
            return "warn", 70
        if latest >= 0.6 * tl:
            return "bad", 45
        return "bad", 25
    if d == "lower_better" and th is not None:
        if latest <= th:
            return "ok", 100
        if latest <= 1.2 * th:
            return "warn", 70
        if latest <= 1.5 * th:
            return "bad", 45
        return "bad", 25
    return "none", None


def lifestyle() -> Dict[str, Any]:
    """Historical lifestyle data (wearable devices): trends by year, status vs the target,
    improvement/worsening, a workout summary and an integral fitness score (for the radar/analysis)."""
    data = core.wearable_trends()
    meta = core.wearable_metrics()
    mm = meta.get("metrics", {})
    # Garmin schema: the metrics are in data["metrics"]; the old Apple schema — flat in data.
    msrc = data.get("metrics") if isinstance(data.get("metrics"), dict) else data
    def _life_metric(key, info, sd, since=None):
        """A metric from a monthly series {YYYY-MM: value}: 3-month smoothing, trend, status.

        `since` is the month from which the series is COMPARABLE WITH ITSELF. A change of
        device tears the series: an older watch counted time in bed as sleep and reported
        well over an hour more per night than the current one. Taking the "first value"
        over such a series, the application confidently reports that sleep has got worse
        by that difference — comparing two devices, not sleep. The baseline and the
        conclusion about improvement are taken from `since`; the series itself is returned
        whole, so the chart does not lie by default, but the point of reference is honest.
        """
        pts_all = sorted(({"date": y, "value": float(v)} for y, v in sd.items()), key=lambda p: p["date"])
        pts = [p for p in pts_all if p["date"] >= since] if since else pts_all
        if not pts:                       # the cut-off ate the whole series — so it is wrong
            pts, since = pts_all, None
        vals = [p["value"] for p in pts]
        smooth = [{"date": pts[i]["date"],
                   "value": round(sum(vals[max(0, i - 2):i + 1]) / len(vals[max(0, i - 2):i + 1]), 2)}
                  for i in range(len(pts))]
        latest = pts[-1]["value"]
        latest_sm, first_sm = smooth[-1]["value"], smooth[0]["value"]
        rec = None
        if len(smooth) >= 2:
            a, b = smooth[max(0, len(smooth) - 4)], smooth[-1]
            dv = round(b["value"] - a["value"], 2)
            rec = {"from": a["date"], "to": b["date"], "delta": dv,
                   "direction": "up" if dv > 0 else ("down" if dv < 0 else "flat")}
        st, score = _wear_status(latest_sm, info)
        d = info.get("direction")
        improving = (latest_sm > first_sm) if d == "higher_better" else ((latest_sm < first_sm) if d == "lower_better" else None)
        trend_good = None
        if rec and rec["direction"] != "flat" and d in ("higher_better", "lower_better"):
            up = rec["direction"] == "up"
            trend_good = up if d == "higher_better" else (not up)
        return {"key": key, "label": info.get("label", key), "unit": info.get("unit", ""),
                "comparable_from": since,
                "series_full": pts_all if since else None,
                "direction": d, "group": info.get("group", "activity"), "why": info.get("why", ""),
                "target_low": info.get("target_low"), "target_high": info.get("target_high"),
                "value": round(latest, 1), "value_smooth": latest_sm, "date": pts[-1]["date"],
                "first": round(first_sm, 1), "first_date": pts[0]["date"],
                "overall_delta": round(latest_sm - first_sm, 2),
                "improving": improving, "trend_good": trend_good, "status": st, "score": score,
                "trend": rec, "series": pts, "smooth": smooth}

    # The month from which each series is comparable with itself. It lives in the profile
    # and not in the public metrics reference: the date a device was changed is a fact of
    # the owner's biography, not a property of the metric. No key — previous behaviour.
    cmp_from = (data.get("_meta") or {}).get("comparable_from") or {}
    out = []
    for key in meta.get("order", list(mm.keys())):
        sd = msrc.get(key)
        if isinstance(sd, dict) and sd:
            out.append(_life_metric(key, mm.get(key, {"label": key}), sd, cmp_from.get(key)))
    # manual markers from metrics.json that are NOT in Garmin (e.g. waist/measurements) — also with a trend
    _SKIP = {"weight", "steps", "resting_hr", "sleep_hours", "activity_min"}   # covered by Garmin
    for mk, marker in (core.metrics_json().get("metrics", {}) or {}).items():
        if mk in _SKIP or not marker.get("series"):
            continue
        buckets: Dict[str, List[float]] = {}
        for p in marker["series"]:
            mo = str(p.get("date", ""))[:7]
            if len(mo) == 7 and isinstance(p.get("value"), (int, float)):
                buckets.setdefault(mo, []).append(p["value"])
        monthly = {mo: round(sum(v) / len(v), 1) for mo, v in buckets.items()}
        if not monthly:
            continue
        direction = marker.get("direction") or ("lower_better" if marker.get("ref_high")
                                                else ("higher_better" if marker.get("ref_low") else None))
        info = {"label": marker.get("name", mk), "unit": marker.get("unit", ""),
                "direction": direction, "group": "anthro", "why": marker.get("note", ""),
                "target_high": marker.get("ref_high"), "target_low": marker.get("ref_low")}
        out.append(_life_metric(mk, info, monthly))
    # workouts: totals by type + the last active year
    workouts = []
    wnew = data.get("workouts")
    wold = data.get("Workouts")
    if isinstance(wnew, dict):
        # Garmin: {year: {label: {count, hours}}} → aggregated by label
        agg: Dict[str, Dict[str, Any]] = {}
        for yr, types in wnew.items():
            if not isinstance(types, dict):
                continue
            for typ, v in types.items():
                cnt = (v.get("count", 0) if isinstance(v, dict) else v) or 0
                hrs = (v.get("hours", 0) if isinstance(v, dict) else 0) or 0
                a = agg.setdefault(typ, {"total": 0, "hours": 0.0, "last_year": yr, "last_count": 0})
                a["total"] += cnt; a["hours"] += hrs
                if yr >= a["last_year"]:
                    a["last_year"] = yr; a["last_count"] = cnt
        for typ, a in agg.items():
            workouts.append({"type": typ, "total": a["total"], "hours": round(a["hours"], 1),
                             "last_year": a["last_year"], "last_count": a["last_count"]})
        workouts.sort(key=lambda x: -x["total"])
    elif isinstance(wold, dict):
        # the old Apple schema: {type: {year: count}}
        for typ, yrs in wold.items():
            if not isinstance(yrs, dict) or not yrs:
                continue
            ly = max(yrs.keys())
            workouts.append({"type": typ, "total": sum(yrs.values()), "last_year": ly, "last_count": yrs.get(ly)})
        workouts.sort(key=lambda x: -x["total"])
    scored = [m["score"] for m in out if m.get("score") is not None]
    fitness = round(sum(scored) / len(scored)) if scored else None

    # conclusions for the strategy (metabolic syndrome: bring weight/fat down, raise activity,
    # keep muscle, improve recovery) — from the 3-month trend of the key metrics
    _KEY = ("Weight", "BodyFat", "MuscleMass", "VO2Max", "IntensityMinutesDaily",
            "StepsDaily", "HRV", "BodyBatteryHigh", "RestingHeartRate")
    by_key = {m["key"]: m for m in out}
    good, watch = [], []
    for k in _KEY:
        lbl = _t(f"lifestyle.metric.{k}")
        m = by_key.get(k)
        if not m or not m.get("trend") or m["trend"]["direction"] == "flat":
            continue
        arrow = "↑" if m["trend"]["direction"] == "up" else "↓"
        item = {"label": lbl, "value": m["value"], "unit": m["unit"],
                "delta": m["trend"]["delta"], "arrow": arrow}
        if m.get("trend_good") is True:
            good.append(item)
        elif m.get("trend_good") is False:
            watch.append(item)
    conclusions = {"good": good, "watch": watch}
    return {"metrics": out, "workouts": workouts[:14], "fitness_score": fitness,
            "conclusions": conclusions, "disclaimer": DISCLAIMER()}


def _prev_point(series) -> Optional[Dict[str, Any]]:
    """The next-to-last point of a series (the previous measurement) or None."""
    if not series or len(series) < 2:
        return None
    return sorted(series, key=lambda p: p["date"])[-2]


def _marker_health_at(key: str, point: Optional[Dict[str, Any]]) -> Optional[int]:
    """Health score of a marker computed at an ARBITRARY point of the series (usually the previous one)."""
    raw = core.labs().get("markers", {}).get(key)
    if not raw or not point:
        return None
    flag = _flag_value(raw, point["value"], point.get("censored"))
    return _marker_health({"flag": flag, "value": point["value"],
                           "ref_low": raw.get("ref_low"), "ref_high": raw.get("ref_high")})


def _marker_health(m: Dict[str, Any]) -> int:
    """A 0–100 score for one marker: 100 within range, less — by the DEGREE of deviation.
    That way the radar becomes selective (it does not collapse to 0), and a mild deviation
    differs from a severe one."""
    if m.get("flag") == "ok":
        return 100
    v = m.get("value")
    lo, hi = m.get("ref_low"), m.get("ref_high")
    frac = None  # the relative excess over the bound
    try:
        if m.get("flag") == "high" and hi:
            frac = (v - hi) / abs(hi)
        elif m.get("flag") == "low" and lo:
            frac = (lo - v) / abs(lo)
    except Exception:
        frac = None
    if frac is None:
        return 55  # there is a deviation, but its scale cannot be assessed
    frac = max(frac, 0.0)
    # gradation by the size of the deviation from the reference bound
    if frac <= 0.15:
        return 75
    if frac <= 0.40:
        return 60
    if frac <= 0.90:
        return 45
    if frac <= 2.0:
        return 30
    return 15


def health_radar() -> Dict[str, Any]:
    """Assessment by body system (for the radar): 0–100 as the MEAN health score of the
    system's markers, accounting for the degree of deviation (and not for the share within range)."""
    labs = analyze_labs()
    by_key = {m["key"]: m for m in labs["markers"]}
    domains = []
    for key, keys in _RADAR_DOMAINS:
        label = _t(f"radar.domain.{key}")
        present = [by_key[k] for k in keys if k in by_key]
        if not present:
            domains.append({"key": key, "label": label, "score": None, "status": "nodata",
                            "prev_score": None, "compared_score": None, "delta": None,
                            "prev_date": None, "compared": 0, "moved": [],
                            "total": len(keys), "measured": 0, "missing": list(keys),
                            "ok": 0, "abnormal": []})
            continue
        scores = [_marker_health(m) for m in present]
        abn = [m for m in present if m["flag"] != "ok"]
        score = round(sum(scores) / len(scores))
        status = "good" if score >= 80 else ("warning" if score >= 55 else "critical")
        # --- dynamics: ONLY the markers that have a previous point are compared,
        # otherwise the means would be computed over different sets of markers ---
        comp = []
        for m in present:
            raw = core.labs().get("markers", {}).get(m["key"], {})
            pp = _prev_point(raw.get("series"))
            ph = _marker_health_at(m["key"], pp)
            if ph is None:
                continue
            comp.append({"key": m["key"], "name": m["name"], "unit": m.get("unit", ""),
                         "cur": _marker_health(m), "prev": ph,
                         "from_date": pp["date"], "to_date": m.get("date"),
                         "from_value": pp["value"], "to_value": m.get("value")})
        prev_score = delta = prev_date = compared_score = None
        moved = []
        if comp:
            # Both ends of the comparison are means over the SAME markers — the ones
            # that actually have a previous point. What stood here was
            # `max(0, min(100, score - delta))`: the domain's current score, computed
            # over every measured marker, minus a delta computed over the smaller
            # compared subset. The result was a number nobody had measured, printed
            # with a date beside it — «in January the index was 100/100» out of the
            # movement of a single marker.
            cur_c = sum(c["cur"] for c in comp) / len(comp)
            prev_c = sum(c["prev"] for c in comp) / len(comp)
            delta = round(cur_c - prev_c)
            prev_score = round(prev_c)
            compared_score = round(cur_c)
            prev_date = max(c["from_date"] for c in comp)
            moved = sorted([c for c in comp if c["cur"] != c["prev"]],
                           key=lambda c: -abs(c["cur"] - c["prev"]))[:4]
        domains.append({
            "key": key, "label": label, "score": score, "status": status,
            "prev_score": prev_score, "compared_score": compared_score,
            "delta": delta, "prev_date": prev_date,
            "compared": len(comp), "moved": moved,
            # `total` is the panel the domain DECLARES, not the part of it that
            # happens to be measured. With `len(present)` a domain announced by four
            # markers, of which one had ever been drawn, printed «🟢 100/100, 0 out
            # of range of 1» — a statement about a body system made from a quarter
            # of it. The declared size is the denominator; `measured` says how much
            # of it the statement actually rests on.
            "total": len(keys), "measured": len(present),
            "missing": [k for k in keys if k not in by_key],
            "ok": len(present) - len(abn),
            "abnormal": [{"key": m["key"], "name": m["name"], "value": m["value"], "unit": m["unit"],
                          "flag": m["flag"], "ref_low": m["ref_low"], "ref_high": m["ref_high"],
                          "date": m.get("date"), "stale": not _recent(m.get("date"), 18),
                          "note": m.get("note"), "genome_link": m.get("genome_link")}
                         for m in abn],
        })
    # + the "Fitness" domain from lifestyle (wearable devices) — so that it counts in the analysis
    try:
        ls = lifestyle()
        if ls.get("fitness_score") is not None:
            sc = ls["fitness_score"]
            fstatus = "good" if sc >= 80 else ("warning" if sc >= 55 else "critical")
            fab = []
            for m in ls["metrics"]:
                if m.get("status") in ("warn", "bad"):
                    flag = "high" if m.get("direction") == "lower_better" else "low"
                    fab.append({"key": m["key"], "name": m["label"], "value": m["value"], "unit": m["unit"],
                                "flag": flag, "ref_low": None, "ref_high": None, "stale": False,
                                "note": m.get("why"), "genome_link": None})
            fcomp = []
            for m in ls["metrics"]:
                sm = m.get("smooth") or []
                if len(sm) < 2 or m.get("score") is None:
                    continue
                _st, ps = _wear_status(sm[-2]["value"], m)
                if ps is None:
                    continue
                fcomp.append({"key": m["key"], "name": m["label"], "unit": m.get("unit", ""),
                              "cur": m["score"], "prev": ps,
                              "from_date": sm[-2]["date"], "to_date": sm[-1]["date"],
                              "from_value": sm[-2]["value"], "to_value": sm[-1]["value"]})
            fprev = fdelta = fpdate = fcur = None
            fmoved = []
            if fcomp:
                cur_c = sum(c["cur"] for c in fcomp) / len(fcomp)
                prev_c = sum(c["prev"] for c in fcomp) / len(fcomp)
                fdelta = round(cur_c - prev_c)
                fprev = round(prev_c)          # measured, over the same metrics as the delta
                fcur = round(cur_c)
                fpdate = max(c["from_date"] for c in fcomp)
                fmoved = sorted([c for c in fcomp if c["cur"] != c["prev"]],
                                key=lambda c: -abs(c["cur"] - c["prev"]))[:4]
            domains.append({"key": "fitness", "label": _t("radar.domain.fitness"),
                            "score": sc, "status": fstatus,
                            "prev_score": fprev, "compared_score": fcur,
                            "delta": fdelta, "prev_date": fpdate,
                            "compared": len(fcomp), "moved": fmoved,
                            # every wearable metric of the domain is measured by
                            # construction — there is no unmeasured remainder here
                            "total": len(ls["metrics"]), "measured": len(ls["metrics"]),
                            "missing": [],
                            "ok": sum(1 for m in ls["metrics"] if m.get("status") == "ok"), "abnormal": fab})
    except Exception:
        pass

    scored = [d for d in domains if d["score"] is not None]
    overall = round(sum(d["score"] for d in scored) / len(scored)) if scored else None
    withprev = [d for d in scored if d.get("prev_score") is not None]
    prev_overall = overall_delta = prev_date = None
    if withprev and overall is not None:
        # Same rule one level up: both ends over the same domains.
        overall_delta = round(sum(d["compared_score"] for d in withprev) / len(withprev)
                              - sum(d["prev_score"] for d in withprev) / len(withprev))
        prev_overall = round(sum(d["prev_score"] for d in withprev) / len(withprev))
        prev_date = max(d["prev_date"] for d in withprev if d.get("prev_date"))
    return {"domains": domains, "overall": overall, "prev_overall": prev_overall,
            "overall_delta": overall_delta, "prev_date": prev_date,
            "disclaimer": DISCLAIMER()}


def _lifestyle_overview() -> Optional[Dict[str, Any]]:
    try:
        ls = lifestyle()
    except Exception:
        return None
    if not ls.get("metrics"):
        return None
    watch = [{"label": m["label"], "value": m["value"], "unit": m["unit"], "status": m["status"]}
             for m in ls["metrics"] if m.get("status") == "bad"]
    return {"fitness_score": ls.get("fitness_score"), "watch": watch[:4]}


def second_opinion() -> Dict[str, Any]:
    """Composition: the labs (red) + the pharmacogenetics watchlist + the suggested tests."""
    labs = analyze_labs()
    drugs = [check_drug_gene(core._localized(d, _lang())) for d in _WATCHLIST]
    flagged_drugs = [d for d in drugs if d.get("status") == "ok" and d.get("level") in ("high", "moderate", "unknown")]
    tests = suggest_tests()
    return {
        "red_labs": [m for m in labs["markers"] if m["flag"] != "ok"],
        "drug_flags": flagged_drugs,
        "suggestions": tests["suggestions"],
        "disclaimer": DISCLAIMER(),
    }


# ============================ Lifestyle brief ================================
# A hybrid: the numbers come from live data (tokens), the wording from profile/lifestyle_brief.json,
# the freshness is computed from the watch lists. For details see SKILL.md, scenario E.

_BRIEF_TOKEN = __import__("re").compile(r"\[\[(lab|life|goal):([A-Za-z0-9_.\- ]+)\]\]")


def _brief_num(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return str(v)


def _brief_lab(key: str) -> Dict[str, Any]:
    m = (core.labs().get("markers") or {}).get(key)
    if not m:
        return {"text": _t("brief.no_marker", key=key), "date": None, "status": "missing"}
    pt = _latest(m.get("series") or [])
    if not pt:
        return {"text": _t("brief.no_data"), "date": None, "status": "missing"}
    val, unit = pt.get("value"), (m.get("unit") or "")
    lo, hi = m.get("ref_low"), m.get("ref_high")
    status = "ok"
    try:
        if lo is not None and float(val) < float(lo):
            status = "low"
        elif hi is not None and float(val) > float(hi):
            status = "high"
    except (TypeError, ValueError):
        status = "unknown"
    if lo is not None and hi is not None:
        ref = _t("brief.ref_range", low=_brief_num(lo), high=_brief_num(hi))
    elif hi is not None:
        ref = _t("brief.ref_max", high=_brief_num(hi))
    elif lo is not None:
        ref = _t("brief.ref_min", low=_brief_num(lo))
    else:
        ref = ""
    return {"text": f"{_brief_num(val)} {unit}{ref}".strip(), "value": val,
            "date": pt.get("date"), "name": m.get("name") or key, "status": status}


def _brief_life(key: str) -> Dict[str, Any]:
    try:
        ls = lifestyle()
    except Exception:                                            # noqa: BLE001
        return {"text": _t("brief.no_metric", key=key), "date": None, "status": "missing"}
    for m in ls.get("metrics", []):
        if m.get("key") == key or m.get("label") == key:
            return {"text": f"{_brief_num(m.get('value'))} {m.get('unit') or ''}".strip(),
                    "value": m.get("value"), "date": m.get("date"),
                    "status": m.get("status") or "ok"}
    return {"text": _t("brief.no_metric", key=key), "date": None, "status": "missing"}


def _brief_goal(label: str) -> Dict[str, Any]:
    try:
        g = goal_dashboard()
    except Exception:                                            # noqa: BLE001
        return {"text": "—", "date": None, "status": "missing"}
    for t in g.get("targets", []):
        if str(t.get("label", "")).lower().startswith(label.lower()):
            return {"text": _t("brief.goal_now", now=t.get('now'), target=t.get('target')),
                    "value": t.get("now"), "date": g.get("as_of"), "status": "ok"}
    return {"text": "—", "date": None, "status": "missing"}


def _brief_resolve(text: str) -> Dict[str, Any]:
    used: List[Dict[str, Any]] = []
    fn = {"lab": _brief_lab, "life": _brief_life, "goal": _brief_goal}

    def sub(m):
        kind, key = m.group(1), m.group(2)
        d = fn[kind](key)
        used.append({"kind": kind, "key": key, "date": d.get("date"),
                     "status": d.get("status"), "value": d.get("text")})
        return d["text"]

    return {"text": _BRIEF_TOKEN.sub(sub, text or ""), "used": used}


def _brief_newest(watch: List[Dict[str, Any]]) -> Optional[str]:
    """The most recent date among the block's watched markers."""
    markers = core.labs().get("markers") or {}
    best = None
    for w in watch or []:
        if w.get("kind") not in (None, "lab"):
            continue
        pt = _latest((markers.get(w.get("key")) or {}).get("series") or [])
        d = (pt or {}).get("date")
        if d and (best is None or d > best):
            best = d
    return best


def _brief_snapshot_item(s: Dict[str, Any]) -> Dict[str, Any]:
    """A snapshot row "now → goal": the text + the NUMBER and the scale for the bullet bar.

    The numeric value is obtained by the same resolver as the text — there is one source,
    so a discrepancy between the caption and the bar is impossible.
    """
    tok = s.get("token") or ""
    r = _brief_resolve(tok)
    used = (r["used"] or [{}])[0]
    kind, key = used.get("kind"), used.get("key")
    raw = None
    if kind == "lab":
        raw = _brief_lab(key).get("value")
    elif kind == "life":
        raw = _brief_life(key).get("value")
    try:
        raw = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        raw = None
    return {"label": s.get("label"), "value": r["text"], "raw": raw,
            "unit": s.get("unit") or "", "min": s.get("min"), "max": s.get("max"),
            "target_value": s.get("target_value"), "dir": s.get("dir") or "lower",
            "date": used.get("date"), "status": used.get("status"),
            "target": s.get("target") or "", "tone": s.get("tone") or "muted",
            "source": s.get("source"), "note": s.get("note") or ""}


def lifestyle_brief() -> Dict[str, Any]:
    """Lifestyle brief: live numbers + curated wording + a freshness flag."""
    src = core.lifestyle_brief_src() or {}
    blocks_in = src.get("blocks") or []
    if not blocks_in:
        return {"available": False,
                "reason": _t("brief.not_available")}
    order = src.get("sections") or []
    sections: Dict[str, Dict[str, Any]] = {
        s["id"]: {"id": s["id"], "title": s.get("title") or s["id"],
                  "lead": s.get("lead") or "", "blocks": []} for s in order}
    stale: List[Dict[str, Any]] = []
    for b in blocks_in:
        r = _brief_resolve(b.get("body") or "")
        newest = _brief_newest(b.get("watch") or [])
        reviewed = b.get("reviewed")
        is_stale = bool(newest and reviewed and newest > reviewed)
        item = {"id": b.get("id"), "title": b.get("title") or "", "body": r["text"],
                "sources": r["used"], "watch": b.get("watch") or [], "reviewed": reviewed,
                "newest_data": newest, "stale": is_stale,
                "review_hint": b.get("review_hint") or "", "weight": b.get("weight", 5)}
        if is_stale:
            stale.append({"id": b.get("id"), "title": b.get("title"),
                          "reviewed": reviewed, "newest_data": newest,
                          "review_hint": b.get("review_hint") or ""})
        sec = sections.setdefault(b.get("section") or "other",
                                  {"id": b.get("section") or "other",
                                   "title": _t("brief.section_other"), "lead": "", "blocks": []})
        sec["blocks"].append(item)
    for s in sections.values():
        s["blocks"].sort(key=lambda x: -x.get("weight", 5))
    ordered = [sections[s["id"]] for s in order if s["id"] in sections]
    ordered += [v for k, v in sections.items() if k not in {s["id"] for s in order}]
    return {"available": True,
            "title": src.get("title") or _t("brief.title_default"),
            "subtitle": _brief_resolve(src.get("subtitle") or "")["text"],
            "compiled": src.get("compiled"),
            "disclaimer": src.get("disclaimer") or _t("disclaimer.short"),
            "snapshot": [_brief_snapshot_item(s) for s in (src.get("snapshot") or [])],
            "sections": [s for s in ordered if s["blocks"]],
            "actions": [_brief_resolve(a)["text"] for a in (src.get("actions") or [])],
            "dropped": src.get("dropped") or [],
            "stale_blocks": stale,
            "needs_review": bool(stale)}


# ============================ FOCUS OF ATTENTION =============================
# The one task the owner is concentrated on right now. The curated part lies in
# profile/focus.json; the LIVE numbers are computed here: where the metric is now,
# what happens with the levers over the last window and what the episode journal gives.
# It prescribes nothing: the levers are observations on one's own data, questions go to the doctor.

def _focus_nights(days: Optional[int] = None) -> List[Dict[str, Any]]:
    """Per-night records with phases, newer than PHASES_FROM, and if required — the last `days`."""
    nights = [n for n in (core.sleep_nightly().get("nights") or [])
              if (n.get("date") or "") >= "2022-01-01" and n.get("deep_min")]
    nights.sort(key=lambda n: n["date"])
    if days and nights:
        import datetime as _d
        try:
            edge = (_d.date.fromisoformat(nights[-1]["date"]) - _d.timedelta(days=days)).isoformat()
            nights = [n for n in nights if n["date"] >= edge]
        except ValueError:
            pass
    return nights


def _focus_mean(xs) -> Optional[float]:
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 1) if xs else None


def _focus_metric(metric: Dict[str, Any]) -> Dict[str, Any]:
    """Where the metric is now: the latest monthly value + the mean over 30/90 nights."""
    key = metric.get("key") or ""
    cur = _brief_life(key) if metric.get("kind") == "life" else _brief_lab(key)
    n30, n90 = _focus_nights(30), _focus_nights(90)
    field = "deep_min" if key == "DeepSleepMin" else None
    out = {"label": metric.get("label"), "unit": metric.get("unit"),
           "dir": metric.get("dir", "higher"),
           "value": cur.get("value"), "raw": cur.get("raw"), "as_of": cur.get("date"),
           "baseline": metric.get("baseline"), "baseline_note": metric.get("baseline_note"),
           "target": metric.get("target"), "target_source": metric.get("target_source"),
           "target_note": metric.get("target_note"),
           "mean_30": _focus_mean([n.get(field) for n in n30]) if field else None,
           "mean_90": _focus_mean([n.get(field) for n in n90]) if field else None,
           "nights_30": len(n30), "nights_90": len(n90),
           # The window bounds matter: the Garmin export is static, so "the last 30 nights"
           # means the last 30 nights OF THE EXPORT, not the last 30 calendar days.
           "window_from": n30[0]["date"] if n30 else None,
           "window_to": n30[-1]["date"] if n30 else None}
    # The numbers are shown in the Russian notation (comma), as everywhere in the application.
    out["mean_30_txt"] = _brief_num(out["mean_30"])
    out["mean_90_txt"] = _brief_num(out["mean_90"])
    out["baseline_txt"] = _brief_num(out["baseline"])
    out["target_txt"] = _brief_num(out["target"])
    base, m30 = out["baseline"], out["mean_30"]
    if isinstance(base, (int, float)) and isinstance(m30, (int, float)):
        out["delta"] = round(m30 - base, 1)
        out["delta_txt"] = ("+" if out["delta"] > 0 else "") + _brief_num(out["delta"])
        # The 2-minute threshold is not statistics but an honest limit of discernibility:
        # deep sleep scatters by ±15 min between nights, a monthly mean over 30 nights is noisy at units.
        out["direction"] = _t("focus.direction.up" if out["delta"] >= 2 else
                              "focus.direction.down" if out["delta"] <= -2
                              else "focus.direction.flat")
    return out


def _focus_lever_check(check: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """A live measurement of a lever over the observation window. None — the lever is not measured automatically."""
    if not check:
        return None
    if not isinstance(check, dict):
        # The profile is edited by hand. A string instead of an object is no reason to
        # take the whole tab down: the lever is then not measured automatically.
        return None
    kind = check.get("kind")
    win = int(check.get("window") or 30)
    nights = _focus_nights(win)
    if not nights:
        return None
    if kind == "bedtime_share":
        thr = float(check.get("threshold") or 310)
        vals = [n.get("bedtime_min_from_20") for n in nights
                if isinstance(n.get("bedtime_min_from_20"), (int, float))]
        if not vals:
            return None
        share = round(100 * sum(1 for v in vals if v <= thr) / len(vals))
        avg = _focus_mean(vals)
        return {"text": _t("focus.bedtime_share", n=len(vals), share=share,
                           clock=_focus_clock(avg)),
                "share": share, "mean": avg, "n": len(vals)}
    if kind == "awake_mean":
        vals = [n.get("awake_min") for n in nights if isinstance(n.get("awake_min"), (int, float))]
        if not vals:
            return None
        return {"text": _t("focus.awake_mean", n=len(vals),
                           mean=_brief_num(_focus_mean(vals))),
                "mean": _focus_mean(vals), "n": len(vals)}
    if kind == "journal_alcohol":
        return _focus_journal_split(win)
    return None


def _focus_clock(mins: Optional[float]) -> str:
    """Minutes from 20:00 → hours:minutes of local time."""
    if not isinstance(mins, (int, float)):
        return "—"
    total = (20 * 60 + int(round(mins))) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _focus_journal_split(window: int = 120) -> Dict[str, Any]:
    """Separate the superimposed factors with the journal: clean / alcohol / alcohol + atenolol.

    The point of this computation is not to "prove harm" but to SEPARATE what is inseparable
    in passive data: the drug is taken on exactly the evenings when there is alcohol.
    While the episodes are few, "not enough data" is returned honestly instead of a number.
    """
    entries = {e.get("date"): e for e in (core.focus_log().get("entries") or []) if e.get("date")}
    nights = {n["date"]: n for n in _focus_nights(window)}
    groups: Dict[str, List[float]] = {"clean": [], "alcohol": [], "alcohol_atenolol": []}
    for date, n in nights.items():
        e = entries.get(date) or {}
        alc = bool(e.get("alcohol"))
        aten = bool(e.get("atenolol"))
        key = "alcohol_atenolol" if (alc and aten) else "alcohol" if alc else "clean"
        groups[key].append(n["deep_min"])
    logged = sum(1 for d in entries if d in nights)
    res = {"kind": "journal", "window": window, "logged_nights": logged,
           "groups": [{"id": k, "n": len(v), "mean": _focus_mean(v)} for k, v in groups.items()]}
    need = 8
    if len(groups["alcohol"]) < need or len(groups["alcohol_atenolol"]) < need:
        res["ready"] = False
        res["text"] = _t("focus.journal_not_ready",
                         nights=_plural(logged, "count.nights"), need=need,
                         a=len(groups['alcohol']), b=len(groups['alcohol_atenolol']))
    else:
        res["ready"] = True
        a, b = _focus_mean(groups["alcohol"]), _focus_mean(groups["alcohol_atenolol"])
        res["text"] = _t("focus.journal_split", a=a, b=b,
                         delta=round((b or 0) - (a or 0), 1))
    return res


def _focus_evidence() -> Dict[str, Any]:
    """What has ALREADY been done instrumentally on the focus topic — and what is left open.

    It is needed exactly so as not to suggest a study that is already in the profile.
    The assistant reads prose selectively; the engine reads it always.
    """
    st = (core.studies().get("studies") or [])
    done, open_items = [], []
    for s in st:
        done.append({"date": s.get("date"), "kind": s.get("kind"),
                     "conclusion": s.get("conclusion"),
                     "answers": s.get("answers") or [],
                     "does_not_answer": s.get("does_not_answer") or [],
                     "source": s.get("source")})
        for o in s.get("open") or []:
            open_items.append({"from": s.get("kind"), "date": s.get("date"),
                               "what": o.get("what"), "note": o.get("note")})
    return {"studies": done, "open": open_items, "count": len(done)}


def focus_dashboard() -> Dict[str, Any]:
    """Focus of attention: the goal, the live metric, the state of the levers, the journal, the questions."""
    src = core.focus_src() or {}
    f = src.get("focus") or {}
    if not f:
        return {"available": False,
                "reason": _t("focus.not_set_reason")}
    levers = []
    for lv in f.get("levers") or []:
        levers.append({"id": lv.get("id"), "title": lv.get("title"),
                       "status": lv.get("status") or "secondary",
                       "expected": lv.get("expected") or "",
                       "evidence": lv.get("evidence") or "",
                       "now": _focus_lever_check(lv.get("check"))})
    jr = f.get("journal") or {}
    split = _focus_journal_split(int(jr.get("window") or 120))
    return {"available": True,
            "id": f.get("id"), "title": f.get("title"), "started": f.get("started"),
            "why": f.get("why") or "",
            "metric": _focus_metric(f.get("metric") or {}),
            "levers": levers,
            "journal": {**jr, "state": split},
            "questions": f.get("questions") or [],
            "evidence": _focus_evidence(),
            # The owner's four goals (2026-08-14). The main task stays in `focus`,
            # but the list of goals is wider, and it must not be lost.
            "tracks": src.get("tracks") or [],
            "done": f.get("done") or [],
            "updated": (src.get("_meta") or {}).get("updated"),
            "disclaimer": (src.get("_meta") or {}).get("disclaimer") or _t("disclaimer.short")}
