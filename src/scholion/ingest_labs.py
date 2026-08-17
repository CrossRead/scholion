"""Automatic ingest of lab PDFs from a folder (e.g. «Лабораторные исследования») → labs.json.

Reads text from the PDF, finds the draw date («Дата взятия биоматериала») and known markers
(dictionary knowledge/lab_markers.json), adds points to labs.json. Incremental: the manifest
remembers processed files (by path+mtime), a repeated run takes only new or changed ones.

Value = the first «clean» number after the marker name (digits inside names such as D3,
HbA1c, B12 are cut off by the boundary check). Idempotent: a point of the same date is replaced.

Text extraction: pdfplumber → pdftotext (poppler) → pdfminer; if none is available, it tries
to install pdfplumber via pip. Scanned PDFs (no text layer) are not supported without OCR.
"""
from __future__ import annotations
import json
import os
import re
import unicodedata
import shutil
import subprocess
import sys
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from . import core, i18n, store
from .i18n import t as _t

_NUM = r"\d+(?:[.,]\d+)?"
_CLEAN = re.compile(r"(?<![0-9A-Za-zА-Яа-яЁё])(" + _NUM + r")(?![0-9A-Za-zА-Яа-яЁё])")
_RANGE = re.compile(r"(" + _NUM + r")\s*[-–—]\s*(" + _NUM + r")")
# A reference range whose thousands digit is separated by a SPACE: «197,0 - 1 500,0»,
# «560 - 2 500», «3 000,0 - 27 000,0». The former _RANGE cut the number at the space and gave
# an upper bound of 1,0 / 2,0 / 27,0 — vitamin B12 «197,0 - 1 500,0» became 197–1, and a result
# well inside the true range fell into «above normal». Digits split by a space cannot be glued
# blindly: «Трансферрин 228 200 - 360 мг/дл» is a result of 228 against a range of 200-360, not
# 228200. So the glue is accepted only when it FIXES the order of the bounds (low ≤ high).
_NUM_TH = r"\d{1,3}(?:[ \u00A0\u202F\u2009]\d{3})+(?:[.,]\d+)?"
_NUM_ANY = r"(?:" + _NUM_TH + r"|" + _NUM + r")"
_RANGE_TH = re.compile(r"(" + _NUM_ANY + r")\s*[-–—]\s*(" + _NUM_ANY + r")")
_TAIL3 = re.compile(r"\d{3}(?:[.,]\d+)?$")
# Rows of a multi-line reference block: «Мужчины (старше 18): < 4,20», «Взрослые: < 1,24»,
# «Новорожденные (до 7 дней): 1,20 - 7,80». The lab prints the block under the result row, and
# the parser took the FIRST row of the block — for an adult male that could be a paediatric or
# a female range (17-OH-progesterone took «Новорожденные», 17-OH-pregnenolone — «Женщины»).
_ROW_LABEL = re.compile(r"^\s*(?:взрослые|мужчин|женщин|новорожд|дети|детск|девочк|мальчик|"
                        r"подростк|беремен|терапевтическ|шкала|до\s+полудня|после\s+полудня|"
                        r"при\s+ходьбе|в\s+покое)", re.IGNORECASE)
_ROW_ALIEN = re.compile(r"новорожд|девочк|мальчик|детск|дети|подростк|беремен|пуповин|"
                        r"терапевтическ|шкала\s+таннер", re.IGNORECASE)
_ROW_FEM = re.compile(r"женщин|девушк", re.IGNORECASE)
_ROW_BAND = re.compile(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*(?:лет\b|год\w*|г\s*[):])", re.IGNORECASE)
_ROW_OVER = re.compile(r"старше\s*(\d{1,2})|>\s*(\d{1,2})\s*(?:лет|год\w*)", re.IGNORECASE)
_ROW_UNDER = re.compile(r"до\s*(\d{1,2})\s*(?:лет|год\w*)\b", re.IGNORECASE)
_ROW_UPPER = re.compile(r"(?:<|\bдо\b|\bменее\b)\s*(" + _NUM_ANY + r")", re.IGNORECASE)
_ROW_LOWER = re.compile(r"(?:>|\bболее\b)\s*(" + _NUM_ANY + r")", re.IGNORECASE)
# Different labs label the draw date differently: «Дата взятия биоматериала»
# (Invitro/Medgorod), «Взятие биоматериала: DD.MM.YYYY HH:MM» (DNKOM/Gemotest).
# If it goes unrecognised, the form silently drops out of both ingest and reconcile.
_DATE = re.compile(r"(?:Дата\s+взятия|Взятие\s+биоматериала|Дата\s+забора|Забор\s+биоматериала)[^\d]*(\d{2})\.(\d{2})\.(\d{4})", re.IGNORECASE)
_DATE_FALLBACK = re.compile(r"Регистрация\s+биоматериала[^\d]*(\d{2})\.(\d{2})\.(\d{4})", re.IGNORECASE)
# The same date on an English form — and ONLY in ISO order, deliberately.
# «03/04/2024» is the fourth of March in the United States and the third of April
# almost everywhere else, and nothing in the row says which lab wrote it. A parser
# that guesses is right about half the time and silent about the other half, and a
# lab point filed under the wrong month is worse than a lab point not filed: it
# joins a series and moves a trend. So an unambiguous date is read and an
# ambiguous one is left for the person to enter, with the file skipped as «not a
# report» exactly as before.
_DATE_EN = re.compile(r"(?:collected|collection\s+date|date\s+of\s+collection|specimen\s+collected|"
                      r"drawn|draw\s+date|sample\s+date|date\s+drawn)[^\d]{0,20}"
                      r"(\d{4})-(\d{2})-(\d{2})", re.IGNORECASE)
# Paediatric/female references that land on the same row as the name:
# «Фолликулостимулирующий гормон   Девочки (12-13лет): 1,29 - 8,74» — numbers from here must
# not be taken. The segment carries only PAEDIATRIC/female references, not a result.
# The pattern used to be `лет\)`, and it caught the ADULT range as well: a row like
# «Дегидроэпиандростерон (ДГЭА) … Взрослые (18-40 лет): 4,60 - 27,00 нмоль/л» was discarded
# whole, and DHEA was extracted from no LC-MS form. Only genuinely paediatric words remain.
_PEDI = re.compile(r"девочк|мальчик|детск|подростк|дети\s*\(", re.IGNORECASE)
# Numbers belonging to the UNIT, not to the result: «10^9/л», «109/л», «10*12/л»,
# «10 9/л» — and the same in Latin, «10^9/L», «10*12/L», «10⁹/L», «K/uL», «M/uL».
# Without the Latin half an English blood count returns 10 as the neutrophil count:
# the ten of the unit, taken as the result, and 10 is a plausible enough number for
# nothing downstream to notice.
_UNITNUM = re.compile(r"10\s*[\^*]?\s*(?:9|12|3|6)\s*/\s*[лl]|10[⁹¹²³⁶]+\s*/\s*[лl]|"
                      r"\b[KM]\s*/\s*[uµ]?[lL]\b", re.IGNORECASE)
# Numbers that belong to the NAME of the analyte rather than to its value:
# «Vitamin D (25-OH)», «25(OH)D», «1,25-dihydroxyvitamin D». The Russian dictionary
# never met this because there the digits stand BEFORE the name — «25-ОН витамин D»
# — and the segment searched for the value starts after the name. In English the
# qualifier trails it, and the parser read 25 as the result: 25 nmol/L converted to
# 10 ng/mL, a deficiency reported for a person whose actual value was normal.
_NAMENUM = re.compile(r"\(?\s*1?,?2?5\s*[-–(]?\s*(?:OH|ОН)\s*\)?\s*[-–]?\s*D?\s*\)?",
                      re.IGNORECASE)
# An age span inside the reference text: «Взрослые (18-40 лет): 4,60 - 27,00 нмоль/л».
# Without masking, _RANGE catches «18-40» as the marker's range, and a DHEA result whose
# true range is 4,60-27,00 would be highlighted as «below 18».
_AGERANGE = re.compile(r"\(?\s*\d+\s*[-–—]\s*\d+\s*(?:лет|год|года|мес)[^)]*\)?", re.IGNORECASE)
# A LEGEND row rather than a result: «<0.01 МЕ/мл Иммунитет отсутствует, требуется
# вакцинация.» Such rows come as a list under a marker name that ends with a colon, and by
# their shape («<number unit …») they are indistinguishable from a wrapped result.
# Without this check the wrap recovery takes the first legend row: for antibody markers the
# legend threshold landed in the profile instead of the result printed on the form.
_LEGEND = re.compile(r"иммунитет|вакцинац|ревакцинац|обнаружен|не выявлен|отрицательн|"
                     r"положительн|сомнени|контроль через|рекомендуется|указывает на|"
                     r"интерпретац|норма для|сероконверс", re.IGNORECASE)
# The biomaterial of the form. Without it «Гормоны мочи»/«Гормоны слюна» pour their values
# into the serum keys (urine aldosterone → blood aldosterone) and corrupt the series.
_BIOMAT = re.compile(r"(?:Биоматериал|Specimen|Sample\s+type|Specimen\s+type)\s*:\s*([^\n;,]+)",
                     re.IGNORECASE)
# Derived documents (summary analytical reports rather than lab forms): they carry tables
# spanning many dates, and the parser would attribute all of the values to a single date.
_DERIVED = re.compile(r"Сводный\s+аналитический\s+отч|АНАЛИЗ\s+ЛАБОРАТОРНЫХ\s+ИССЛЕДОВАНИЙ", re.IGNORECASE)
# The words each biomaterial is written with, in both languages. English is added
# to the SAME table rather than to a second one: the specimen gate has one job —
# keeping «Гормоны мочи» from pouring its numbers into the blood markers — and two
# tables would be two chances for the languages to disagree about what urine is.
_MAT_WORDS = ((("моча", "мочи", "urine"), "urine"),
              (("слюна", "слюн", "saliva"), "saliva"),
              (("кал", "фекал", "stool", "faec", "fec"), "stool"))
# The form «Анализ фекалий на дисбактериоз кишечника» prints the result as a POWER of ten
# rather than as an ordinary number: «10^6», or collapsed to «106» when the superscript is
# lost during text extraction («1010» = 10^10). The general numeric collector would read «10»
# or «106» out of that, so this form has its own parsing branch.
# The value is stored as the EXPONENT, i.e. log10 CFU/g: 10^6 → 6.0. That way the series can
# be compared and trended, and «grew by an order of magnitude» = +1.
# A censored result («менее 10^4») is stored AT THE BOUND — exactly the same convention as
# for «<0,4 Ед/мл» in the other forms. «0» / «отсутствуют» → 0.
_DYSB_FORM = re.compile(r"Анализ\s+фекалий\s+на\s+дисбактериоз", re.IGNORECASE)
_DYSB_UNIT = re.compile(r"(КОЕ/г|%)")
# `\d{1,2}` is greedy: on «1010» it gives exponent 10, on «109» it gives 9. Requiring at least
# one digit after «10» keeps the exponent from being confused with the percent limit «менее 10».
_DYSB_POW = re.compile(r"(менее|не\s+более|более)?\s*10\s*\^?\s*(\d{1,2})\b", re.IGNORECASE)
_DYSB_ABSENT = re.compile(r"отсутству|отсуству|не\s+обнаружен", re.IGNORECASE)
_DYSB_PCT_REF = re.compile(r"(менее|не\s+более)\s+(\d+(?:[.,]\d+)?)", re.IGNORECASE)

# A coprogram and «Исследование кала» print a WORD result («умеренно», «скудно», «не обнаружено»)
# rather than a number: the general numeric collector sees nothing there at all, and both forms
# counted as «non-laboratory» for years. The words are mapped onto an ordinal score 0–4 — only
# that way does the marker join a series and become comparable between draws. The scale is
# described in each marker's note, so a «3» in labs.json cannot be read as a measured quantity.
# The same biomaterial arrives in DIFFERENT layouts: the classic manual «Копрограмма», the
# automated «Копрологическое исследование … с фотофайлами микроскопии» (whose sections are
# called «Физические свойства»/«Элементы микроскопии»), an express occult blood test and a form
# with the H. pylori antigen. Only two layouts out of five reached the template — the automated
# coprological form and the H. pylori antigen form were not parsed at all.
_STOOL_FORM = re.compile(r"Макроскопическое\s+исследование|Копрограмма|"
                         r"Копрологическое\s+исследование|Элементы\s+микроскопии|"
                         r"Антиген\s+Helicobacter", re.IGNORECASE)
_OCCULT_FORM = re.compile(r"кала\s+на\s+скрыт|скрыт\w*\s+кров", re.IGNORECASE)
# The section of the form. «Слизь» is printed TWICE — in macroscopy (by eye) and in microscopy
# (under the microscope). Without the split the first row won, and microscopic mucus — the
# clinically meaningful one — was silently lost under the macroscopic «не обнаружена».
_SEC_MACRO = re.compile(r"макроскопическое\s+исследование|физические\s+свойства", re.IGNORECASE)
_SEC_MICRO = re.compile(r"микроскопическое\s+исследование|элементы\s+микроскопии", re.IGNORECASE)
_STOOL_SCALE = (
    (("не обнаружено", "не обнаружены", "не обнаружен", "отсутствуют", "отсутствует",
      "отрицательный", "нет"), 0.0),
    (("скудно", "единично", "единичные"), 1.0),
    (("немного", "небольшое"), 2.0),
    (("умеренно", "умеренное"), 3.0),
    (("много", "обильно", "значительно", "большое"), 4.0),
    (("положительный", "обнаружен", "обнаружены", "обнаружено"), 1.0),
)



def _is_legend(t: str) -> bool:
    """A threshold row from the legend, not a result.

    What sets it apart from a result is a leading «<»/«>» PLUS a verbal interpretation:
    «<0.01 МЕ/мл Иммунитет отсутствует, требуется вакцинация». A genuine result can carry a
    verbal reference too («6,52 <20 - не обнаружены ; >20 - обнаружены Ед/мл», «0,48 мМЕ/мл
    <10 (не обнаружены)»), but the value itself stands without a leading sign — so a check on
    the words alone is not enough, it cut off anti-CCP and anti-HBsAg.
    """
    ts = t.lstrip()
    return bool(ts[:1] in "<>" and _LEGEND.search(t))


def _specimen(text: str) -> str:
    """The biomaterial of the form: blood (by default) / urine / saliva / stool.

    What it returns is a VALUE the code compares — `parse_report` matches it against the
    `specimen` field of knowledge/lab_markers.json, which is how «Гормоны мочи» is kept from
    pouring its numbers into the blood markers. Both sides of that comparison moved to the
    controlled vocabulary at once, in one commit: a gate whose two sides speak different
    alphabets does not fail, it silently stops matching, and every urine marker would go
    missing while the run still reported success.

    The WORDS it recognises stay Russian — they are read off a Russian form. That is the
    project's standing split: recognition is input and belongs to the language of the source,
    the value produced is ours and belongs to the vocabulary.
    """
    m = _BIOMAT.search(text)
    if m:
        v = m.group(1).strip().lower()
        for words, name in _MAT_WORDS:
            if any(w in v for w in words):
                return name
        return "blood"
    head = "\n".join(text.splitlines()[:40]).lower()
    for words, name in _MAT_WORDS[:2]:
        if any(("в " + w) in head or ("суточной " + w) in head for w in words):
            return name
    return "blood"


# The row a value has been wrapped onto. A leading «<» is a censored result
# («<0.4 Ед/мл» for Helicobacter pylori IgG), a leading «%» is the unit moved to
# the start of the row («Ширина распределения RBC по» ⏎ «% 12,5 11,5 - 14,5»).
_VALUE_LINE = re.compile(r"^\s*(?:[<>]\s*)?(?:%\s*)?(" + _NUM + r")(?![0-9A-Za-zА-Яа-яЁё])\s")


def _to_float(s: str) -> float:
    for sp in (" ", "\u00a0", "\u202f", "\u2009"):   # a space inside a number = thousands mark
        s = s.replace(sp, "")
    return float(s.replace(",", "."))


def _range_span(t: str, pos: int = 0):
    """The first reference range in a row: (start, end, lo, hi), or None.

    Understands a space as a thousands separator («1 500,0»), but accepts the glue only when
    it does not break the order of the bounds: in «228 200 - 360» the lower bound is 200,
    while 228 is the marker's result.
    """
    m = _RANGE_TH.search(t, pos)
    if not m:
        return None
    lo, hi = _to_float(m.group(1)), _to_float(m.group(2))
    start = m.start()
    if lo > hi and any(c in m.group(1) for c in " \u00a0\u202f\u2009"):
        tl = _TAIL3.search(m.group(1))
        if tl:
            lo = _to_float(tl.group(0))
            start = m.start(1) + tl.start()
    return (start, m.end(), lo, hi)


def _row_fits(t: str, sex: str, age: float) -> bool:
    """Whether a reference row fits the profile owner (sex + age).

    A row without a group label counts as fitting — that is an ordinary single-line reference.
    """
    if _ROW_ALIEN.search(t):
        return False
    if sex == "male" and _ROW_FEM.search(t):
        return False
    if sex == "female" and re.search(r"мужчин|юнош", t, re.IGNORECASE):
        return False
    b = _ROW_BAND.search(t)
    if b and not (float(b.group(1)) <= age <= float(b.group(2))):
        return False
    o = _ROW_OVER.search(t)
    if o and age <= float(o.group(1) or o.group(2)):
        return False
    u = _ROW_UNDER.search(t)
    if u and age >= float(u.group(1)):
        return False
    return True


def _row_limits(t: str):
    """(lo, hi) from a block row: the range «A - B», or a one-sided bound «< X» / «> X»."""
    sp = _range_span(t)
    if sp:
        return sp[2], sp[3]
    mu = _ROW_UPPER.search(t)
    if mu:
        return None, _to_float(mu.group(1))
    ml = _ROW_LOWER.search(t)
    if ml:
        return _to_float(ml.group(1), ), None
    return None, None


_OWNER_CACHE: Dict[str, Any] = {}


def _owner():
    """(sex, age) of the owner from profile/metrics.json — used to pick the right row of a
    multi-line reference. No profile / no birth date → (None, None), the logic is off."""
    if _OWNER_CACHE:
        return _OWNER_CACHE.get("sex"), _OWNER_CACHE.get("age")
    sex = age = None
    try:
        d = json.loads((core.profile_dir() / "metrics.json").read_text(encoding="utf-8"))
        pr = d.get("profile") or {}
        sex = pr.get("sex")
        bd = pr.get("birth_date") or (str(pr["birth_year"]) + "-01-01" if pr.get("birth_year") else None)
        if bd:
            y, m, dd = (int(x) for x in bd.split("-")[:3])
            today = _dt.date.today()
            age = today.year - y - ((today.month, today.day) < (m, dd))
    except Exception:
        pass
    _OWNER_CACHE.update({"sex": sex, "age": age})
    return sex, age


def _manifest_file() -> Path:
    p = core.mkdir_private(core.cache_dir())
    return p / "ingest_labs_manifest.json"


def _load_manifest() -> Dict[str, float]:
    f = _manifest_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:
        return {}


def _save_manifest(d: Dict[str, float]) -> None:
    try:
        core.write_json(_manifest_file(), d, indent=1)
    except Exception:
        pass


def _have_extractor() -> Optional[str]:
    try:
        import pdfplumber  # noqa: F401
        return "pdfplumber"
    except Exception:
        pass
    if shutil.which("pdftotext"):
        return "pdftotext"
    try:
        from pdfminer.high_level import extract_text  # noqa: F401
        return "pdfminer"
    except Exception:
        return None


def _ensure_extractor() -> Optional[str]:
    """Which PDF text extractor is available — without installing anything.

    This function used to install `pdfplumber` itself when a PDF turned up,
    trying three strategies in a row, the last one with
    `--break-system-packages`. Putting a form in a folder would reach out to the
    network and change the user's Python environment, with nothing asked and
    nothing said. For a tool whose whole claim is that it acts only on command,
    that was a contradiction — and it was invisible, which is worse.

    `pdfplumber` is a declared dependency now, so after `pip install scholion` it
    is simply there. When it is not — a source tree, a stripped environment — the
    honest move is to say so and name the command, not to run it.
    """
    return _have_extractor()


def _read_pdf(path: Path) -> Optional[str]:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except ImportError:
        pass
    except Exception:
        return ""
    if shutil.which("pdftotext"):
        try:
            r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                               capture_output=True, text=True, timeout=90)
            return r.stdout
        except Exception:
            return ""
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(path))
    except Exception:
        return None


def _stool_score(tail: str) -> Optional[float]:
    """The first meaningful token of a word result → a score of 0–4.

    The result stands first after the name, the reference follows it (its words are in the
    scale too, which is why the FIRST match is taken and nothing beyond it is looked at). A
    word outside the scale is a qualitative finding («йодофильная флора: кокки»): it is coded
    as 1 («found») rather than dropped, otherwise the finding vanishes from the profile.
    """
    t = " ".join(tail.split()).lower()
    # The Russian translation of a Latin name is printed in brackets AFTER the marker name
    # and before the result: «Entamoeba coli (кишечная амёба) обнаружено». Without stripping
    # the brackets the first token turns out to be «(кишечная», it fails the letter check,
    # and a positive finding silently dropped out of the parse.
    if t.startswith("("):
        close = t.find(")")
        if close != -1:
            t = t[close + 1:].strip()
    if not t:
        return None
    for words, score in _STOOL_SCALE:
        for w in words:
            if t.startswith(w):
                return score
    first = t.split(" ")[0].strip(",.;:")
    if re.fullmatch(_NUM, first):
        # «Лейкоциты 2 отсутствуют» — some rows of the automated form arrive as a count in the
        # field of view, not as a word. The count goes onto the same 0–4 axis: the reference
        # here is still «отсутствуют», what matters is «more than zero», not the exact value.
        # The ceiling of 4 keeps an outlier from stretching the scale and zeroing word points.
        return min(_to_float(first) or 0.0, 4.0)
    if len(first) >= 3 and first[0].isalpha():
        return 1.0
    return None


def _parse_stool(text: str, markers: Dict[str, Any]) -> Dict[str, Any]:
    """Parsing of a coprogram and «Исследование кала» → {key: {value, ref_low, ref_high}}.

    A form row: «<name> <result> <reference>» in words alone. The name is looked for as a
    PREFIX of the row (otherwise «эритроциты» would be caught from foreign rows), and of the
    matches the longest one is taken («растительная клетчатка неперевариваемая» ⊃ «растительная клетчатка»).

    The occult blood test is parsed separately: there the name is broken by a wrap across three
    rows and the result is cut in half («положитель» / «ный»), so row-by-row parsing does not
    work. In that form the reference column is always «отрицательный», so any «положитель…» in
    the text is the result. The sign is looked for only inside the occult blood form itself: in
    a coprogram «положительный» is normal stercobilin.
    """
    found: Dict[str, Any] = {}
    section = ""
    for raw in text.splitlines():
        low = unicodedata.normalize("NFC", raw).strip().lower()
        if not low:
            continue
        if _SEC_MACRO.search(low):
            section = "macro"
        elif _SEC_MICRO.search(low):
            section = "micro"
        best = None
        for key, spec in markers.items():
            if key in found or spec.get("occult"):
                continue
            if spec.get("section") and section and spec["section"] != section:
                continue          # a same-named row from a foreign section (macro/micro mucus)
            for syn in core.marker_rules(spec, "names"):
                if low.startswith(syn) and (best is None or len(syn) > best[0]):
                    best = (len(syn), key, syn)
        if best is None:
            continue
        _, key, syn = best
        spec = markers[key]
        tail = low[len(syn):]
        if spec.get("numeric"):
            mm = re.match(r"\s*(" + _NUM + r")\b", tail)
            val = _to_float(mm.group(1)) if mm else None
        else:
            val = _stool_score(tail)
        if val is None:
            continue
        found[key] = {"value": val, "ref_low": spec.get("ref_low"), "ref_high": spec.get("ref_high")}
    for key, spec in markers.items():
        # An aggregate key: over time the lab split some rows into subtypes («Эпителий»
        # → squamous + columnar), and the series would break off at that point.
        # If only a subtype is printed, the aggregate = the MAXIMUM over the subtypes:
        # a finding in any one of them is a finding for the marker as a whole. The form's
        # own aggregate row, when present, always wins — hence `key in found`.
        agg = spec.get("agg_of")
        if not agg or key in found:
            continue
        vals = [found[k]["value"] for k in agg if k in found]
        if vals:
            found[key] = {"value": max(vals), "ref_low": spec.get("ref_low"),
                          "ref_high": spec.get("ref_high")}
    if _OCCULT_FORM.search(text):
        for key, spec in markers.items():
            if spec.get("occult"):
                found[key] = {"value": 1.0 if re.search(r"положитель", text, re.IGNORECASE) else 0.0,
                              "ref_low": spec.get("ref_low"), "ref_high": spec.get("ref_high")}
    return found


def _parse_dysb(text: str, markers: Dict[str, Any]) -> Dict[str, Any]:
    """Parsing of the form «Анализ фекалий на дисбактериоз кишечника» → {key: {value, ref_low, ref_high}}.

    A form row: «<name> <unit> <result> <reference>», where both the result and the reference
    are written as powers of ten. When a long name is wrapped, the lab prints the unit
    FIRST on its own row and breaks the name around it
    («Другие условно-патогенные» ⏎ «КОЕ/г менее 104 менее 104» ⏎ «энтеробактерии») —
    so when the head is empty the name is assembled from the neighbouring rows on both sides.
    """
    lines = text.splitlines()
    dysb = {k: v for k, v in markers.items() if k.startswith("dysb_")}
    found: Dict[str, Any] = {}
    for i, ln in enumerate(lines):
        m = _DYSB_UNIT.search(ln)
        if not m:
            continue
        unit, head, tail = m.group(1), ln[:m.start()].strip(), ln[m.end():]
        if not head:                      # the name is broken by a wrap around the unit
            head = " ".join(x.strip() for x in lines[max(0, i - 1):i] + lines[i + 1:i + 2])
        low = unicodedata.normalize("NFC", head).lower()
        best = None
        for key, spec in dysb.items():
            if key in found:
                continue
            if any(x in low for x in core.marker_rules(spec, "exclude")):
                continue                  # «патогенные энтеробактерии» ⊂ «другие условно-патогенные…»
            for syn in core.marker_rules(spec, "names"):
                if syn in low and (best is None or len(syn) > best[0]):
                    best = (len(syn), key)
        if best is None:
            continue
        key = best[1]
        val = rl = rh = cens = None
        if unit == "%":
            mm = re.match(r"\s*(" + _NUM + r")\b", tail)
            if mm:
                val = _to_float(mm.group(1))
                rest = tail[mm.end():]
                r = _DYSB_PCT_REF.search(rest)
                rh = _to_float(r.group(2)) if r else (0.0 if _DYSB_ABSENT.search(rest) else None)
        else:
            toks = list(_DYSB_POW.finditer(tail))
            if toks:
                val = float(toks[0].group(2))      # censored («менее 10^4») — kept at the bound
                pref0 = (toks[0].group(1) or "").lower()
                # the censoring sign is kept apart: «менее 10^5» at a lower bound of 10^5 is
                # BELOW range, while the bare value on the bound would be read as «normal»
                cens = "<" if pref0.startswith(("менее", "не")) else (
                    ">" if pref0.startswith("более") else None)
                norm = toks[1:]
                if len(norm) == 2 and not norm[0].group(1) and not norm[1].group(1):
                    rl, rh = float(norm[0].group(2)), float(norm[1].group(2))
                elif len(norm) == 1:
                    pref = (norm[0].group(1) or "").lower()
                    if pref.startswith("более"):
                        rl = float(norm[0].group(2))
                    else:                          # «менее» / «не более» / no word at all
                        rh = float(norm[0].group(2))
            elif re.match(r"\s*0\b", tail) or _DYSB_ABSENT.match(tail.strip()):
                val = 0.0                          # 0 = not detected (log10 scale)
                if _DYSB_ABSENT.search(tail):
                    rh = 0.0
        if val is None:
            continue
        rec: Dict[str, Any] = {"value": val, "ref_low": rl, "ref_high": rh}
        if cens:
            rec["censored"] = cens
        found[key] = rec
    return found


def parse_report(text: str, markers: Dict[str, Any], source: str = "") -> Tuple[Optional[str], Dict[str, Any]]:
    """From the report text: the date (YYYY-MM-DD) and {key: {value, ref_low, ref_high}}.

    Accounts for line wrapping in tables: when a marker name is broken
    («Антитела к циклическому / <value> / цитруллиновому пептиду (АЦЦП)»),
    the value is taken from the neighbouring row that starts with a number.
    """
    date = None
    m = _DATE.search(text) or _DATE_FALLBACK.search(text)
    if m:
        date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    else:
        m = _DATE_EN.search(text)
        if m:
            date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"   # already ISO
    if _DERIVED.search(text[:4000]):
        return None, {}      # a derived report, not a form — it is not a source of data
    if text.count("Генотип") >= 3 and "Единицы" not in text:
        return None, {}      # genotyping, not measurement: there are no numeric results
    mat = _specimen(text)
    tl = text.lower()
    # For this lab the method/panel is printed NOT in the body of the form but only in the file
    # name («(Ответ МС)» — LC-MS/MS, «(Ответ ИХЛА)», «(Ответ Иммунохимия)», «(Ответ ИСП)»).
    # Without the file name, form_require/form_exclude cannot tell the second method of the
    # same draw from the first, and keys such as *_immuno have nothing to bind them to a form.
    # macOS hands out file names in NFD («й» = и + U+0306), and then a form_require holding a
    # word with «й»/«ё» («Общий анализ», «Гормоны мочи ... ») never matches at all.
    hay = unicodedata.normalize("NFC", tl + " \n " + (source or "")).lower()

    def _form_ok(v):
        req = [x.lower() for x in core.marker_rules(v, "form_require")]
        exc = [x.lower() for x in core.marker_rules(v, "form_exclude")]
        if req and not any(x in hay for x in req):
            return False
        if exc and any(x in hay for x in exc):
            return False
        return True

    markers = {k: v for k, v in markers.items()
               if mat in ([v.get("specimen")] if isinstance(v.get("specimen"), str)
                          else (v.get("specimen") or ["blood"])) and _form_ok(v)}
    if _STOOL_FORM.search(text) or _OCCULT_FORM.search(text):
        # Word-based stool forms: the general numeric collector finds nothing here
        # (except pH), so this branch parses them whole and returns straight away.
        return date, _parse_stool(text, markers)
    if _DYSB_FORM.search(text):
        # This form writes its result its own way (powers of ten) — the general collector
        # does not apply and would give garbage («10» out of «10^6»), so the branch returns.
        return date, _parse_dysb(text, markers)
    lines = text.splitlines()
    found: Dict[str, Any] = {}

    def _wrapped_tail(i: int) -> str:
        for j in (i + 1, i - 1):
            if 0 <= j < len(lines):
                if _VALUE_LINE.match(lines[j]):
                    return lines[j]
        return ""

    def _mask(t: str) -> str:
        """Mask everything in the row tail that is NOT the result, preserving positions:
        numbers inside units («10^9/л», «109/л», «10*12/л») and reference ranges («1,78 - 6,04»).
        Without this the parser takes «10» from a unit, or the lower bound, instead of the result."""
        out = t
        for rx in (_UNITNUM, _NAMENUM, _AGERANGE):
            out = rx.sub(lambda mm: " " * (mm.end() - mm.start()), out)
        pos = 0
        while True:
            sp = _range_span(out, pos)
            if not sp:
                break
            out = out[:sp[0]] + " " * (sp[1] - sp[0]) + out[sp[1]:]
            pos = sp[1]
        return out

    def _pick(masked: str, pl) -> Optional[re.Match]:
        """The result number from the row tail. With plausible, the first one falling into the
        physiological range is taken (that is how the «абс.» and «%» columns of same-named rows
        are separated). Without plausible — the first «clean» number (the previous behaviour)."""
        for mt in _CLEAN.finditer(masked):
            if pl is None or pl[0] <= _to_float(mt.group(1)) <= pl[1]:
                return mt
        return None

    def _occ(hay: str, needle: str):
        """Every occurrence of the name in the row (two-column forms repeat it twice).

        For LATIN names the match must stand on a word boundary. Without that a short
        acronym is caught inside a foreign word, and a number from an entirely different
        assay lands in the profile. A real case: «homa» was found inside «Chlamydia
        trac-HOMA-tis», and an antibody titre row produced a phantom HOMA-IR point.
        Cyrillic names are long and not exposed to this — the rule leaves them alone.
        """
        ascii_name = needle.isascii()
        out, j = [], hay.find(needle)
        while j >= 0:
            if not ascii_name:
                out.append(j)
            else:
                before = hay[j - 1] if j > 0 else " "
                end = j + len(needle)
                after = hay[end] if end < len(hay) else " "
                # …with one exception, and it is the English plural. A form prints
                # «Triglycerides», «Platelets», «Monocytes»; the dictionary holds
                # the singular, because that is the form the analyte has a name
                # in. The boundary rule then rejects the match on the trailing
                # «s» and the marker is silently never found — which is how the
                # English base panel could be complete and still not parse an
                # English row. A trailing «s» followed by a non-letter is still a
                # word boundary; «eos» inside «eosinophil» is not, because what
                # follows the s there is a letter.
                if after == "s" and not (hay[end + 1] if end + 1 < len(hay) else " ").isalnum():
                    after = " "
                if not (before.isalnum() or after.isalnum()):
                    out.append(j)
            j = hay.find(needle, j + 1)
        return out

    for i, ln in enumerate(lines):
        if not any(c.isalpha() for c in ln):
            continue
        low = ln.lower()
        # 1) for every key — the LONGEST matching name and ALL of its occurrences
        hits = {}
        for key, spec in markers.items():
            if key in found:
                continue
            if any(x in low for x in core.marker_rules(spec, "exclude")):
                continue
            best = None
            for syn in core.marker_rules(spec, "names"):
                pos = _occ(low, syn)
                if pos and (best is None or len(syn) > best[0]):
                    best = (len(syn), syn, pos)
            if best:
                hits[key] = best
        if not hits:
            continue
        # 2) a longer name beats a shorter one ONLY when they compete for the same text,
        #    i.e. the short one is a substring of the long one («тестостерон свободный»
        #    beats «тестостерон»). Lengths used to be compared across the whole row, and in
        #    two-column element forms («Бериллий (Be) … Кадмий (Cd) …») a long name from the
        #    first column silenced the marker of the second: cadmium, lead, titanium, zinc,
        #    chromium, mercury and cobalt were not extracted at all and silently dropped out.
        #    A tie on one name between a pair of keys (e.g. «нейтрофилы» — % and abs.):
        #    BOTH are taken, the columns are separated by require + plausible.
        for key, (_l, syn, pos) in hits.items():
            if any(_l < o[0] and syn in o[1] for k2, o in hits.items() if k2 != key):
                continue
            spec = markers[key]
            # The qualifier window: when the value is already printed on this row, the
            # qualifier stands on the VERY next row («…антиген <value> нг/мл 0,000 - 2,000» ⏎
            # «(ПСА общий)»); when the row holds only a broken name, the next one is taken by
            # the value and the qualifier comes one row further. A wider window is not
            # allowed: in the «Онкомаркеры» form the rows of total and free PSA stand side by
            # side, and total PSA cut itself off by the word «свободный» from the next row.
            nxt = " ".join(lines[i + 1:i + 2 if any(c.isdigit() for c in ln) else i + 3]).lower()
            if any(x in nxt for x in core.marker_rules(spec, "next_exclude")):
                continue
            nreq = [r.lower() for r in core.marker_rules(spec, "next_require")]
            if nreq and not any(x in nxt for x in nreq):
                continue
            req = [r.lower() for r in core.marker_rules(spec, "require")]
            pl = spec.get("plausible")
            # units: {unit substring: multiplier to the key's canonical unit}. It works both as
            # a gate (none of the units present in the segment — the row is not ours) and as a
            # conversion: labs changed units between years (apolipoprotein B мг/дл vs г/л,
            # folic acid нг/мл vs нмоль/л) — without this one and the same series breaks apart.
            units = spec.get("units") or {}
            # A segment = the text from an occurrence of the name to the next one (or to the
            # end). That way, in a row «Нейтрофилы % 45 45-70 Нейтрофилы 109/л 3,4 1,8-6,6»,
            # the «%» column and the «10^9/л» column are parsed independently, each by its key.
            segs = [ln[p + len(syn):(pos[j + 1] if j + 1 < len(pos) else len(ln))]
                    for j, p in enumerate(pos)]
            got = None
            pedi_hit = False
            for seg in segs:
                sl = seg.lower()
                fac = 1.0
                if units:
                    best_u = None
                    for u, f in units.items():
                        if u.lower() in sl and (best_u is None or len(u) > len(best_u)):
                            best_u, fac = u, f
                    if best_u is None:
                        continue    # the unit of this marker is not in the segment
                elif req and not any(x in sl for x in req):
                    continue        # wrong column / wrong unit
                if _PEDI.search(seg):
                    pedi_hit = True
                    continue        # the segment holds only paediatric/female references
                nm = _pick(_mask(seg), pl)
                if nm:
                    got = (nm, seg, fac)
                    break
            if spec.get("value_below"):
                # The name is broken by a wrap, and the tail of the FIRST row holds numbers
                # from the neighbouring columns («:: 4% - 8% указывает на средний риск»), so
                # the usual wrap recovery does not fire: the result is printed separately on
                # the next row. The only such case is «Индекс омега-3 (ЭПК+ДГК : ЖК)».
                tail = _wrapped_tail(i)
                nm = None if _is_legend(tail) else _pick(_mask(tail), pl)
                got = (nm, tail, 1.0) if nm else None
            if got is None and (pedi_hit or not any(c.isdigit() for c in segs[0])):
                # The name is broken by a wrap — the value is printed on the neighbouring row.
                # This path used to be closed by the condition `not req and not units`, so any
                # marker with a gate stayed unreachable: «Простатспецифический антиген» ⏎
                # «<value> 0,00 - 2,00» ⏎ «(ПСА общий)» (require) and «Витамин 25-ОН D» ⏎
                # «<value> нг/мл» (units) were extracted from no form at all. Now the gates are
                # applied to THE TAIL ITSELF: units works both as a check and as a multiplier,
                # require as a check. Plus the run on pedi_hit: when ALL segments of the row
                # turned out to be paediatric references («ФСГ … Девочки …»), the result is
                # looked for in the wrapped tail as well.
                tail = _wrapped_tail(i)
                sl = tail.lower()
                fac = 1.0
                ok = bool(tail)
                if ok and units:
                    best_u = None
                    for u, f in units.items():
                        if u.lower() in sl and (best_u is None or len(u) > len(best_u)):
                            best_u, fac = u, f
                    ok = best_u is not None
                elif ok and req and not any(x in sl for x in req):
                    ok = False
                if ok and (_PEDI.search(tail) or _is_legend(tail)):
                    ok = False
                if ok:
                    nm = _pick(_mask(tail), pl)
                    if nm:
                        got = (nm, tail, fac)
            if got is None:
                continue
            nm, tail, fac = got
            rl = rh = None
            rest = _AGERANGE.sub(lambda mm: " " * (mm.end() - mm.start()), tail)[nm.end():]
            sp = _range_span(rest)                      # the range is SOUGHT after the value
            if sp:
                rl, rh = sp[2] * fac, sp[3] * fac
            # A multi-line reference: when the range on the result row is labelled with the
            # WRONG group (female, paediatric, a foreign age span), the first fitting row of
            # the block below is taken. Example: «17-ОН-прогестерон <value> Новорожденные
            # (до 7 дней): 1,20 - 7,80» → descend to «Мужчины (старше 18): < 4,20».
            o_sex, o_age = _owner()
            if rl is not None and o_age is not None and not _row_fits(tail[nm.end():], o_sex, o_age):
                rl = rh = None
                for j in range(i + 1, min(i + 8, len(lines))):
                    row = lines[j]
                    if not _ROW_LABEL.match(row):
                        break
                    if not _row_fits(row, o_sex, o_age):
                        continue
                    a, b = _row_limits(_AGERANGE.sub(lambda mm: " " * (mm.end() - mm.start()), row))
                    if a is not None or b is not None:
                        rl = a * fac if a is not None else None
                        rh = b * fac if b is not None else None
                    break
            val = _to_float(nm.group(1)) * fac
            if fac != 1.0:
                val = round(val, 2 if abs(val) >= 1 else 4)
                rl = round(rl, 2 if abs(rl) >= 1 else 4) if rl is not None else None
                rh = round(rh, 2 if abs(rh) >= 1 else 4) if rh is not None else None
            cens = None
            if spec.get("titer"):
                # A serological titre is printed as «< 1:10», not as a number. An ordinary parse
                # takes «1» out of «1:10» — a meaningless number (the numerator of the dilution,
                # not the result). The dilution's DENOMINATOR (10) is stored with the censoring
                # sign «<»: «titre below 1:10» = not detected, so the series is comparable between draws.
                tm = re.search(r"(<|>|менее|более)?\s*1\s*:\s*(\d+)", tail[nm.end():] or tail)
                if tm:
                    val = float(tm.group(2))
                    pre = (tm.group(1) or "").lower()
                    cens = "<" if pre.startswith(("<", "менее")) else (
                        ">" if pre.startswith((">", "более")) else None)
            found[key] = {"value": val,
                          "ref_low": rl, "ref_high": rh}
            if cens:
                found[key]["censored"] = cens
    return date, found


def ingest(folder: str, force: bool = False) -> Dict[str, Any]:
    """Walk the folder of PDFs and update labs.json with new markers. Incremental."""
    ex = _ensure_extractor()
    if not ex:
        return {"ok": False, "error": _t("ingest_labs.no_pdf_reader")}
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": _t("ingest_labs.folder_not_found", path=root)}
    markers = core.lab_markers().get("markers", {})
    existing = {k: m.get("name") for k, m in core.labs().get("markers", {}).items()}
    manifest = _load_manifest()
    files = sorted(root.rglob("*.pdf"))
    out = {"ok": True, "engine": ex, "files_seen": len(files), "files_processed": 0,
           "points_added": 0, "skipped": 0, "per_file": [], "conflicts": []}
    # (key, month) -> (value, file). One and the same marker for one date occurs in several
    # forms (different orders from one draw, duplicates in subfolders). The last processed
    # file used to win — silently and non-deterministically. Now the FIRST one in sort order
    # wins, and the discrepancy goes into out["conflicts"] and into the report.
    seen_pt: Dict[tuple, tuple] = {}
    for f in files:
        try:
            mt = f.stat().st_mtime
        except Exception:
            continue
        rk = str(f)
        if not force and manifest.get(rk) == mt:
            out["skipped"] += 1
            continue
        text = _read_pdf(f) or ""
        if not (_DATE.search(text) or _DATE_FALLBACK.search(text)
                or _DATE_EN.search(text)):   # not a lab report (or a scan without text)
            manifest[rk] = mt
            continue
        date, found = parse_report(text, markers, source=str(f))
        ftl = text.lower()
        if not date or not found:
            manifest[rk] = mt
            continue
        added = []
        ym = date[:7]   # the profile stores points at month granularity (as reconcile does)
        for key, v in found.items():
            spec = markers[key]
            if spec.get("ref_locked"):
                # Qualitative panels print in the «Норма» column not a range but a scale of
                # interpretation: «<15 - не обнаружено; 15-25 сомнительно; >25 - обнаружено».
                # The parser sees the range 15-25 there and takes the «grey zone» for the
                # reference — a negative result then reads as «below normal».
                # ref_locked=true: the reference comes only from the dictionary, form ignored.
                rl, rh = spec.get("ref_low"), spec.get("ref_high")
            else:
                rl = v["ref_low"] if v["ref_low"] is not None else spec.get("ref_low")
                rh = v["ref_high"] if v["ref_high"] is not None else spec.get("ref_high")
            # display_name — the printed name of the marker, used when names[] holds only
            # lower-case search substrings (e.g. the dysbacteriosis panel).
            name = (existing.get(key) or core.marker_display(spec, i18n.lang())
                    or (core.marker_rules(spec, "names") or [key])[0].capitalize())
            prio = 2 if any(x.lower() in ftl for x in core.marker_rules(spec, "prefer_form")) else 1
            prev = seen_pt.get((key, ym))
            if prev is not None:
                if prev[0] == v["value"]:
                    continue
                if prio <= prev[2]:           # an equal or higher-priority method is recorded
                    out["conflicts"].append({"marker": key, "date": ym,
                                             "kept": prev[0], "kept_from": prev[1],
                                             "other": v["value"], "other_from": f.name})
                    continue
                out["conflicts"].append({"marker": key, "date": ym,      # new method prevails
                                         "kept": v["value"], "kept_from": f.name,
                                         "other": prev[0], "other_from": prev[1]})
            seen_pt[(key, ym)] = (v["value"], f.name, prio)
            r = store.add_lab_point(key, ym, v["value"], name=name, unit=spec.get("unit"),
                                    ref_low=rl, ref_high=rh, direction=spec.get("direction"),
                                    censored=v.get("censored"))
            if r.get("ok"):
                added.append(key)
        manifest[rk] = mt
        if added:
            out["files_processed"] += 1
            out["points_added"] += len(added)
            out["per_file"].append({"file": f.name, "date": ym, "draw_date": date, "markers": added})
    _save_manifest(manifest)
    core.reset_cache()
    return out
