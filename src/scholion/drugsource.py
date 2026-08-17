"""Online resolution of a drug when it is not in the project's local database.

The source is the open international NLM databases (RxNorm + RxClass), without a key and
without patient data (only the drug name goes out — a public query). Cache in .cache/drug_cache.json.

The logic: name → RxCUI (normalisation, including approximate) → ATC class(es) → mapping onto
the project's internal classes (for interaction and pharmacogenetics checks). Russian names are
transliterated into Latin and looked up by RxNorm approximate search (Cyrillic «varfarin» → warfarin).

In the cloud sandbox the network is closed (403) — the path works on the user's machine (a Mac
with internet), as does live rsID resolution. Offline/error → None (then honestly «not found online»).
"""
from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core, net
from .i18n import t as _t

_RX_BYNAME = "https://rxnav.nlm.nih.gov/REST/rxcui.json?name={}&search=2"
_RX_APPROX = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={}&maxEntries=3"
_RX_NAMEPROP = "https://rxnav.nlm.nih.gov/REST/rxcui/{}/property.json?propName=RxNorm%20Name"
_RX_ATC = "https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={}&relaSource=ATC"
_RXNAV_UI = "https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={}"

# free translators without a key (for Russian names: brands do not transliterate, they must be translated)
_MYMEMORY = "https://api.mymemory.translated.net/get?q={}&langpair=ru|en"
_GTX = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ru&tl=en&dt=t&q={}"

# The transliteration table and the Cyrillic test below are INPUT handling: a drug name
# typed in Russian is turned into something RxNorm can be asked about. Nothing here is
# printed, and moving it into the catalogue would translate a lookup key.
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit(s: str) -> str:
    return "".join(_TRANSLIT.get(ch, _TRANSLIT.get(ch.lower(), ch)) for ch in s)


def _has_cyrillic(s: str) -> bool:
    return any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in s)


def _has_latin(s: str) -> bool:
    return any("a" <= ch.lower() <= "z" for ch in s)


# ATC prefix → the project's internal class (matches med_classes.json)
_ATC_TO_CLASS: List[tuple] = [
    ("C10AA", "statin"), ("C10AB", "fibrate"),
    ("B01AA", "anticoagulant_vka"),
    ("B01AF", "doac"), ("B01AE", "doac"),
    ("B01AC04", "antiplatelet_p2y12"), ("B01AC22", "antiplatelet_p2y12"), ("B01AC24", "antiplatelet_p2y12"),
    ("B01AC06", "nsaid"),
    ("M01A", "nsaid"), ("N02BA", "nsaid"),
    ("N06AB", "ssri_snri"), ("N06AX16", "ssri_snri"), ("N06AX21", "ssri_snri"),
    ("A02BC", "ppi"),
    ("J01FA", "macrolide"),
    ("J02AC", "azole_antifungal"), ("D01BA02", "azole_antifungal"),
    ("N02AA", "opioid_codeine"), ("R05DA04", "opioid_codeine"), ("N02AX02", "opioid_codeine"),
    ("H03AA", "thyroid_hormone"),
    ("L04AX01", "thiopurine"), ("L01BB02", "thiopurine"),
    ("G03BA", "testosterone_replacement"),
    ("A10BA", "biguanide"), ("A10BD", "biguanide"),
    ("A10BB", "sulfonylurea"),
    ("A10BK", "sglt2"),
    ("A10BJ", "glp1"),
    ("A10BH", "dpp4"),
    ("C09A", "ace_inhibitor"), ("C09B", "ace_inhibitor"),
    ("C09C", "arb"), ("C09D", "arb"),
    ("C07", "beta_blocker"),
    ("C08", "ccb"),
    ("C03A", "thiazide"), ("C03B", "thiazide"),
    ("C03C", "loop_diuretic"),
    ("A02BA", "h2_blocker"),
]

# class → gene (for the pharmacogenetics of a drug found online). The reason is printed
# into the report, so it lives in the catalogue; the class and the gene are identifiers.
_CLASS_GENE = {
    "statin": "SLCO1B1",
    "anticoagulant_vka": "VKORC1",
    "antiplatelet_p2y12": "CYP2C19",
    "ppi": "CYP2C19",
    "thiopurine": "TPMT",
    "opioid_codeine": "CYP2D6",
}


def _cache_file() -> Path:
    p = core.mkdir_private(core.cache_dir())
    return p / "drug_cache.json"


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


def _get(url: str) -> Optional[Any]:
    return net.get_json(url)


def _translate_ru_en(text: str) -> Optional[str]:
    """Translate a Russian drug name into English (INN/brand). Without a key.

    Brands written in Cyrillic (such as Glucophage) are not recovered by transliteration —
    they have to be translated (MyMemory → Glucophage). We try MyMemory, then the unofficial
    Google. On a Mac urllib works; in the cloud sandbox the network is closed."""
    q = urllib.parse.quote(text)
    # 1) MyMemory
    data = _get(_MYMEMORY.format(q))
    tr = (((data or {}).get("responseData") or {}).get("translatedText") or "").strip()
    bad = ("PLEASE SELECT", "INVALID", "QUERY LENGTH")
    if tr and tr.lower() != text.lower() and not any(b in tr.upper() for b in bad):
        return tr
    # 2) Google (gtx) — returns a nested array
    raw = net.get_json(_GTX.format(q), headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        seg = raw[0] if isinstance(raw, list) else None
        if seg:
            out = "".join(s[0] for s in seg if s and s[0]).strip()
            if out and out.lower() != text.lower():
                return out
    except Exception:
        pass
    return None


def _rxcui_for(term: str, approx: bool = True) -> Optional[str]:
    data = _get(_RX_BYNAME.format(urllib.parse.quote(term)))
    ids = (((data or {}).get("idGroup") or {}).get("rxnormId")) or []
    if ids:
        return str(ids[0])
    # Approximate search — ONLY for Latin script (on Cyrillic it gives junk matches: the
    # Cyrillic spelling of «metformin» resolves to «citrate»). Russian words are translated
    # or transliterated first.
    if not approx:
        return None
    data = _get(_RX_APPROX.format(urllib.parse.quote(term)))
    cands = (((data or {}).get("approximateGroup") or {}).get("candidate")) or []
    for c in cands:
        if c.get("rxcui"):
            return str(c["rxcui"])
    return None


def _atc_info(rxcui: str) -> Dict[str, Any]:
    """ATC classes + the active substance (ingredient) for an rxcui (including a brand)."""
    data = _get(_RX_ATC.format(rxcui))
    out, seen, ingredient = [], set(), None
    for info in (((data or {}).get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []:
        mc = info.get("minConcept") or {}
        if mc.get("tty") == "IN" and not ingredient:
            ingredient = mc.get("name")
        item = info.get("rxclassMinConceptItem") or {}
        code, name = item.get("classId"), item.get("className")
        if code and code not in seen:
            seen.add(code)
            out.append({"code": code, "name": name})
    return {"classes": out, "ingredient": ingredient}


def _map_internal_class(atc: List[Dict[str, str]]) -> Optional[str]:
    for a in atc:
        code = a.get("code", "")
        for prefix, cls in _ATC_TO_CLASS:
            if code.startswith(prefix):
                return cls
    return None


def class_gene(cls: Optional[str]):
    """(gene, why it matters) for a drug class, or None. The reason is already in words."""
    gene = _CLASS_GENE.get(cls or "")
    return (gene, _t(f"gene_why.{cls}")) if gene else None


_CPIC_PAIR = "https://api.cpicpgx.org/v1/pair?drugid=eq.RxNorm:{}&select=genesymbol,cpiclevel,pgxtesting"


def cpic_lookup(rxcui: str, allow_network: bool = True) -> Dict[str, Any]:
    """Pharmacogenes for a drug from the international CPIC database (by rxcui).

    Returns `{"genes": [...], "asked": bool, "reason": str|None}` — and the
    second field is the point of this function.

    What used to be here returned a bare list and answered `[]` in three
    different situations: the database said this drug has no meaningful
    pharmacogenetics; the network was switched off; the request failed.
    `net.get_json` turns every exception into `None`, so those last two are
    indistinguishable from the inside. Downstream, an empty list printed «no
    genes affecting the dose or the effect were found» — a statement about a
    database that had never been reached, made with the same confidence as one
    that had. Verified offline on amiodarone, where the verdict came out green.

    `asked` is true only when CPIC actually answered. Nothing may make a
    negative statement about pharmacogenetics without it. `reason` says why not:
    `no_rxcui` (the drug was never identified, so there was no key to ask by),
    `offline`, `unreachable`.
    """
    if not rxcui:
        return {"genes": [], "asked": False, "reason": "not_identified"}
    cache = _load_cache()
    key = "cpic:" + str(rxcui)
    if key in cache and cache[key] is not None:
        return {"genes": cache[key], "asked": True, "reason": None}
    if not allow_network or net.offline():
        return {"genes": [], "asked": False, "reason": "offline"}
    data = net.get_json(_CPIC_PAIR.format(rxcui))
    if data is None:
        return {"genes": [], "asked": False, "reason": "unreachable"}
    out = []
    for r in data:
        lvl = (r.get("cpiclevel") or "").upper()
        gene = r.get("genesymbol")
        if not gene:
            continue
        out.append({"gene": gene, "level": lvl,
                    "actionable": r.get("pgxtesting") == "Actionable PGx" or lvl in ("A", "B")})
    # actionable ones first
    out.sort(key=lambda g: (not g["actionable"], g["level"]))
    cache[key] = out
    _save_cache(cache)
    return {"genes": out, "asked": True, "reason": None}


def resolve_drug(name: str, allow_network: bool = True) -> Optional[Dict[str, Any]]:
    """Find a drug in RxNorm/RxClass. Returns {rxcui, name, atc[], internal_class, url}
    or None (offline/not found). Cached by the normalised query."""
    q = (name or "").strip()
    if not q:
        return None
    cache = _load_cache()
    key = q.lower()
    if cache.get(key):          # positive entries only (None entries are ignored and the network retried)
        return cache[key]
    if not allow_network:
        return None
    # Order for Russian words: the LATIN variants first (translation → transliteration),
    # they allow approximate search; the Cyrillic original goes last and only exact.
    translated = None
    if _has_cyrillic(q):
        translated = _translate_ru_en(q)
        terms = ([translated] if translated else []) + [_translit(q), q]
    else:
        terms = [q]
    rxcui, matched = None, None
    for t in terms:
        rxcui = _rxcui_for(t, approx=_has_latin(t))
        if rxcui:
            matched = t
            break
    if not rxcui:
        return None  # do NOT cache a negative result (the network failure may have been temporary)
    prop = _get(_RX_NAMEPROP.format(rxcui))
    rxname = (((prop or {}).get("propConceptGroup") or {}).get("propConcept") or [{}])[0].get("propValue")
    info = _atc_info(rxcui)
    atc = info["classes"]
    rec = {"rxcui": rxcui, "name": rxname or matched or q, "ingredient": info.get("ingredient"),
           "atc": atc, "internal_class": _map_internal_class(atc), "url": _RXNAV_UI.format(rxcui),
           "translated": translated, "matched_term": matched, "source": "rxnorm"}
    cache[key] = rec
    _save_cache(cache)
    return rec
