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
import csv
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
                        r"при\s+ходьбе|в\s+покое|по\s+умолчанию|остальные|прочие|"
                        r"таннер|стадия|\d+\s*-?\s*й?\s*триместр|"
                        # A bare Roman numeral opening the row, when a number follows
                        # it: «I    0,10 - 0,98» is a pubertal stage on a form that
                        # dropped the word «Таннер». Requiring the number keeps a
                        # stray capital I from swallowing an ordinary row.
                        r"[IVX]{1,4}(?=[\s:.\-–—(]*\d))",
                        re.IGNORECASE)
# A row that belongs to SOMEBODY ELSE. Three additions, each from a real form:
#
# «таннер» without the word «шкала» before it — Gemotest prints «Таннер I», and the
# old pattern required «шкала таннер», so a man of 41 was measured against stage I
# and 18.5 nmol/L of testosterone read as nineteen times the upper bound (task 65).
#
# A bare Roman numeral opening the row — the same block on other forms drops the
# word «Таннер» entirely and prints «II 0,10 - 1,20».
#
# «триместр» — a trimester row sits UNDER a «Женщины» heading and does not repeat
# the word «беременн», so it passed the filter as an ordinary adult row. The
# profile has no pregnancy status at all, so no trimester row is ever applicable
# (task 66c).
_ROW_ALIEN = re.compile(r"новорожд|девочк|мальчик|детск|дети|подростк|беремен|пуповин|"
                        r"терапевтическ|таннер|триместр|"
                        r"^\s*(?:стадия\s*)?[IVX]{1,4}(?=[\s:.\-–—(]*\d)",
                        re.IGNORECASE | re.MULTILINE)
_BLOCK_HEAD = re.compile(r"^\s*(?:референс|норм[аы]|reference|значени)", re.IGNORECASE)
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
# The CLOCK TIME of the draw, when the form prints one right after the date.
#
# Until now a point was stored at month granularity, so two draws on one day
# collapsed into a single value and the second one was reported as a discrepancy
# with the first. That is a real and ordinary situation — blood taken before a
# procedure or a dose and again after it — and calling it a conflict tells the
# person their data disagrees with itself when in fact it is doing exactly what
# it should. The time is what tells the two apart, so it is read when the form
# prints it and the point keeps it.
_TIME_AFTER = re.compile(r"^[^\d\n]{0,12}(\d{1,2})[:.](\d{2})")

# A delimited export has no «Дата взятия» line: it has a date COLUMN, and the
# date sits at the start of every data row. Only ISO order is accepted here for
# the same reason as below — «03/04/2024» is two different days depending on who
# printed it — and only at the start of a row followed by a separator, so that a
# birth date inside a sentence cannot be mistaken for a draw date.
_DATE_ROW = re.compile(r'^\s*"?(\d{4})-(\d{2})-(\d{2})"?\s*[,;\t]', re.MULTILINE)


def table_dates(text: str) -> list:
    """Distinct ISO dates that begin a row. Sorted, deduplicated, never guessed at."""
    return sorted({f"{a}-{b}-{c}" for a, b, c in _DATE_ROW.findall(text)})


_DATE_FALLBACK = re.compile(r"Регистрация\s+биоматериала[^\d]*(\d{2})\.(\d{2})\.(\d{4})", re.IGNORECASE)
# The same date on an English form — and ONLY in ISO order, deliberately.
# «03/04/2024» is the fourth of March in the United States and the third of April
# almost everywhere else, and nothing in the row says which lab wrote it. A parser
# that guesses is right about half the time and silent about the other half, and a
# lab point filed under the wrong month is worse than a lab point not filed: it
# joins a series and moves a trend. So an unambiguous date is read and an
# ambiguous one is left for the person to enter, with the file skipped as «not a
# report» exactly as before.
_EN_LABEL = (r"(?:collected|collection\s+date|date\s+of\s+collection|specimen\s+collected|"
             r"date\s+collected|specimen\s+date|date\s+of\s+service|"
             r"drawn|draw\s+date|sample\s+date|date\s+drawn|report\s+date|date\s+reported)")

#: Labels that are NEAR the draw and are not it. An American laboratory prints
#: «Ordered Date» on a lipid panel and never prints the draw at all; four forms
#: in the reference corpus are dated this way and nothing else on the page dates
#: them. Refusing all four buys nothing — the order and the draw are a day or two
#: apart — but taking the number silently would file a point under a date the
#: form does not claim. So it is read, and the report says which date it is.
_EN_LABEL_NEAR = r"(?:ordered\s+date|date\s+ordered|received\s+date|date\s+received)"

_DATE_EN = re.compile(_EN_LABEL + r"[^\d]{0,20}(\d{4})-(\d{2})-(\d{2})", re.IGNORECASE)

#: `July 27, 2015` and `27 July 2015` — the form American laboratories print most
#: often after the slashed one. Unambiguous by construction: the month is spelt,
#: so there is nothing to guess.
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_DATE_EN_MONTH = re.compile(
    _EN_LABEL + r"[^A-Za-z\d]{0,20}([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})", re.IGNORECASE)
_DATE_EN_MONTH_FIRST_DAY = re.compile(
    _EN_LABEL + r"[^A-Za-z\d]{0,20}(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", re.IGNORECASE)

#: `07/27/2015`. READ ONLY WHEN THE ORDER IS DECIDABLE — that is, when one of the
#: two numbers is greater than twelve and can therefore only be the day. On
#: `07/12/2015` both readings are possible: the twelfth of July in the United
#: States, the seventh of December almost everywhere else. Nothing on the page
#: says which laboratory printed it, so a parser that picks one is right about
#: half the time and silent about the other half — and a point filed under the
#: wrong month is worse than a point not filed, because it joins a series and
#: moves a trend. The ambiguous case is NAMED, not guessed: same rule as the
#: sex-specific interval that is left empty rather than borrowed.
_DATE_EN_SLASH = re.compile(_EN_LABEL + r"[^\d]{0,20}(\d{1,2})/(\d{1,2})/(\d{2,4})", re.IGNORECASE)
_DATE_EN_SLASH_NEAR = re.compile(
    _EN_LABEL_NEAR + r"[^\d]{0,20}(\d{1,2})/(\d{1,2})/(\d{2,4})", re.IGNORECASE)

#: A bare slashed date anywhere, used only under a column header (below).
_SLASH_ANY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{2,4})(?![\d/])")


def _year(raw: str) -> Optional[int]:
    """Four digits, or two expanded the way every C library expands them."""
    n = int(raw)
    if len(raw) == 4:
        return n if 1900 <= n <= 2100 else None
    return 2000 + n if n <= 68 else 1900 + n


def page_convention(text: str) -> Optional[str]:
    """Which order this page prints its slashed dates in, read off the page.

    A laboratory report rarely carries only one date: the draw, the entry and
    the report are all on it, and one of them is usually decidable — `12/15/2008`
    can only be the fifteenth of December, because there is no fifteenth month.
    That single decidable date establishes what the OTHER dates on the same page
    mean, and «12/10/2008» beside it is then the tenth of December rather than a
    coin toss.

    This is not the guess the refusal rule exists to prevent. The evidence is on
    the page, in the same table, printed by the same instrument. What is still
    refused is a page whose dates CONTRADICT each other, and a page where nothing
    is decidable at all.
    """
    mdy = dmy = False
    for m in _SLASH_ANY.finditer(text or ""):
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b <= 12:
            dmy = True
        elif b > 12 and a <= 12:
            mdy = True
    if mdy and dmy:
        return None
    return "mdy" if mdy else ("dmy" if dmy else None)


def _slash_date(a: int, b: int, raw_year: str, raw: str, convention: Optional[str] = None):
    """(iso, ambiguity) for `a/b/year`, refusing where the order is undecidable.

    One rule, in one place, so the same discipline holds whether the date was
    found beside its label or underneath a column heading.
    """
    year = _year(raw_year)
    if year is None or a > 31 or b > 31 or a < 1 or b < 1:
        return None, None
    if a > 12 and b <= 12:                     # only D/M/Y reads
        return f"{year}-{b:02d}-{a:02d}", None
    if b > 12 and a <= 12:                     # only M/D/Y reads
        return f"{year}-{a:02d}-{b:02d}", None
    if a == b and a <= 12:
        # «04/04/2017» reads the same in both orders. Refusing it printed
        # «which is either 2017-04-04 or 2017-04-04» and threw away a form about
        # which there was nothing to be unsure of. A refusal costs a real
        # measurement; spend it only where there is a real choice to be wrong.
        return f"{year}-{a:02d}-{b:02d}", None
    if a <= 12 and b <= 12:
        if convention == "mdy":
            return f"{year}-{a:02d}-{b:02d}", None
        if convention == "dmy":
            return f"{year}-{b:02d}-{a:02d}", None
        return None, {"raw": raw.strip(), "both": [f"{year}-{a:02d}-{b:02d}",
                                                   f"{year}-{b:02d}-{a:02d}"]}
    return None, None


#: A form that prints its dates as a TABLE — a heading line naming the columns,
#: the values on the line below it. Every LabCorp-derived report in the reference
#: corpus is built this way, and the label-then-date reader finds nothing on such
#: a page: the words and the numbers are never on the same line.
_COL_COLLECTED = re.compile(r"(?:date|time)\s+collected", re.IGNORECASE)
#: Other date columns of the same heading. Reading the first date under the
#: heading is only sound while «collected» is the leftmost of them — otherwise
#: the first number belongs to another column and we would be filing the wrong
#: day. Where that cannot be established, nothing is read.
_COL_OTHER = re.compile(r"(?:date|time)\s+(?:entered|reported|received|ordered)|date\s+of\s+birth",
                        re.IGNORECASE)


def columnar_date(text: str, convention: Optional[str] = None):
    """(date, ambiguity) from a heading line with the values on the next line."""
    lines = [ln for ln in (text or "").splitlines()]
    for i, line in enumerate(lines):
        m = _COL_COLLECTED.search(line)
        if not m or _SLASH_ANY.search(line):
            continue
        other = _COL_OTHER.search(line)
        if other and other.start() < m.start():
            # «Date Reported … Date Collected»: the first date below the heading
            # is not the draw. Say nothing rather than file the wrong day.
            continue
        for nxt in lines[i + 1:i + 3]:
            if not nxt.strip():
                continue
            hit = _SLASH_ANY.search(nxt)
            if hit:
                return _slash_date(int(hit.group(1)), int(hit.group(2)),
                                   hit.group(3), hit.group(0), convention)
            break
    return None, None


def english_date(text: str):
    """(date, ambiguity) for an English form. Either may be None.

    `ambiguity` is a dict describing a date that WAS found and cannot be read —
    it exists so the caller can say «this form has a date I refuse to guess at»
    instead of the untrue «no date on this form».
    """
    m = _DATE_EN.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", None
    for pattern, order in ((_DATE_EN_MONTH, "mdy"), (_DATE_EN_MONTH_FIRST_DAY, "dmy")):
        m = pattern.search(text)
        if not m:
            continue
        name, day = (m.group(1), m.group(2)) if order == "mdy" else (m.group(2), m.group(1))
        month = _MONTHS.get(name.lower()) or _MONTHS.get(
            next((full for full in _MONTHS if full.startswith(name.lower()[:3])), ""), None)
        if month and 1 <= int(day) <= 31:
            return f"{m.group(3)}-{month:02d}-{int(day):02d}", None
    conv = page_convention(text)
    m = _DATE_EN_SLASH.search(text)
    if m:
        iso, amb = _slash_date(int(m.group(1)), int(m.group(2)), m.group(3),
                               m.group(0), conv)
        if iso or amb:
            return iso, amb
    return columnar_date(text, conv)


def english_date_near(text: str):
    """A date the form gives for something NEAR the draw — the order, the receipt.

    Returned separately from `english_date` on purpose: the caller has to be able
    to say which date it filed. Same refusal rule, because an order date read in
    the wrong month is exactly as wrong as a draw date read in the wrong month.
    """
    for pattern in (re.compile(_EN_LABEL_NEAR + r"[^\d]{0,20}(\d{4})-(\d{2})-(\d{2})",
                               re.IGNORECASE),):
        m = pattern.search(text or "")
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", None, "ordered"
    m = _DATE_EN_SLASH_NEAR.search(text or "")
    if m:
        iso, amb = _slash_date(int(m.group(1)), int(m.group(2)), m.group(3),
                               m.group(0), page_convention(text))
        return iso, amb, "ordered"
    return None, None, None


#: A date in the FILE NAME. Usable, and marked as what it is: the name of a file
#: is not the form, it is what somebody called the form — and people rename files
#: to the day they downloaded them. So it is read only when the page itself
#: carries no date, and the report says the date did not come off the page.
_DATE_IN_NAME = re.compile(r"(?<!\d)(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?!\d)")


#: `Blood_Chemistry_Labs_1-15-2015.pdf`, `LEF_Blood_Tests_April_12__2017.pdf`.
#: American files are named the American way, and the same refusal rule applies:
#: a spelled month cannot be misread, `1-15-2015` cannot be misread because
#: there is no fifteenth month, and `4-11-2017` can — so it is not read.
_NAME_SLASHED = re.compile(r"(?<!\d)(\d{1,2})[-_.](\d{1,2})[-_.](20\d{2})(?!\d)")
_NAME_MONTH = re.compile(r"([A-Za-z]{3,9})[-_. ]+(\d{1,2})[-_,. ]+(20\d{2})(?!\d)")


def date_from_filename(name: str):
    m = _DATE_IN_NAME.search(name or "")
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = _NAME_MONTH.search(name or "")
    if m:
        month = _MONTHS.get(m.group(1).lower()) or _MONTHS.get(
            next((full for full in _MONTHS if full.startswith(m.group(1).lower()[:3])), ""), None)
        if month and 1 <= int(m.group(2)) <= 31:
            return f"{m.group(3)}-{month:02d}-{int(m.group(2)):02d}"
    m = _NAME_SLASHED.search(name or "")
    if m:
        iso, _amb = _slash_date(int(m.group(1)), int(m.group(2)), m.group(3), m.group(0))
        return iso
    return None
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


def _row_fits(t: str, sex: str, age: Optional[float]) -> bool:
    """Whether a reference row fits the profile owner (sex + age).

    A row without a group label counts as fitting — that is an ordinary single-line reference.
    `age` follows `_owner()`'s own contract: no birth year on file means `age is None`, and
    then the age logic is off — an age-banded row is neither confirmed nor excluded by it,
    the same way a row with no group label at all counts as fitting. Sex is a separate
    question and is still enforced with age unknown.
    """
    if _ROW_ALIEN.search(t) or _local_row_rule(t, "alien"):
        return False
    if sex == "male" and _ROW_FEM.search(t):
        return False
    if sex == "female" and re.search(r"мужчин|юнош", t, re.IGNORECASE):
        return False
    b = _ROW_BAND.search(t)
    if age is not None and b and not (float(b.group(1)) <= age <= float(b.group(2))):
        return False
    o = _ROW_OVER.search(t)
    if age is not None and o and age <= float(o.group(1) or o.group(2)):
        return False
    u = _ROW_UNDER.search(t)
    if age is not None and u and age >= float(u.group(1)):
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
    multi-line reference. No profile / no birth date → (None, None), the logic is off.

    Keyed by the profile file and its mtime, like every other reader in the
    project. It used to be a plain `if _OWNER_CACHE: return …`, and the first
    read won for the life of the process — including the read that happened
    BEFORE the person filled in their sex. Two ways that bites: the server holds
    one process across a whole session, so a profile edited in the web interface
    kept being ingested against `(None, None)`; and the value cached first is the
    one that turns the row filter OFF, so the failure is towards silence in a
    place where silence looks like a working filter.
    """
    mfile = core.profile_dir() / "metrics.json"
    try:
        st = mfile.stat()
        # mtime AND size: a profile edited twice inside one filesystem tick has
        # the same mtime, and «the timestamp did not move» would then mean «the
        # file did not change» — which is how a stale cache survives the test
        # written to catch it.
        key = (str(mfile), st.st_mtime_ns, st.st_size)
    except OSError:
        key = (str(mfile), None, None)
    if _OWNER_CACHE.get("_key") == key:
        return _OWNER_CACHE.get("sex"), _OWNER_CACHE.get("age")
    _OWNER_CACHE.clear()
    sex = age = None
    try:
        d = json.loads(mfile.read_text(encoding="utf-8"))
        pr = d.get("profile") or {}
        sex = pr.get("sex")
        bd = pr.get("birth_date") or (str(pr["birth_year"]) + "-01-01" if pr.get("birth_year") else None)
        if bd:
            y, m, dd = (int(x) for x in bd.split("-")[:3])
            today = _dt.date.today()
            age = today.year - y - ((today.month, today.day) < (m, dd))
    except Exception:
        pass
    _OWNER_CACHE.update({"sex": sex, "age": age, "_key": key})
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


def _local_row_rule(row: str, kind: str) -> bool:
    """Does a CONFIRMED local row rule match this line?

    Proposed rules are not consulted: a row rule decides WHICH corridor is taken
    from a multi-line block, so an unconfirmed one would pick a corridor — and
    the whole discipline here is that ambiguity is answered with silence rather
    than with a plausible pick.
    """
    try:
        from . import markers_local as _ml
        pats = _ml.confirmed_row_rules(kind)
    except Exception:
        return False
    for p in pats:
        try:
            if re.search(p, row, re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def _fitting_rows(lines, i, o_sex, o_age):
    """Every row of the reference block below line `i` that applies to this person.

    Returns a list of (low, high). The caller uses it only when the list holds
    exactly one entry: ambiguity is answered with silence, not with the first
    candidate.
    """
    out = []
    for j in range(i + 1, min(i + 10, len(lines))):
        row = lines[j]
        if not row.strip():
            continue
        if not _ROW_LABEL.match(row) and not _local_row_rule(row, "label"):
            # A heading such as «Референсные значения:» does not end the block —
            # it introduces it. Only a row that is neither a heading nor a
            # labelled row means the block is over.
            if _BLOCK_HEAD.match(row):
                continue
            break
        if not _row_fits(row, o_sex, o_age):
            continue
        a, b = _row_limits(_AGERANGE.sub(lambda mm: " " * (mm.end() - mm.start()), row))
        if a is not None or b is not None:
            out.append((a, b))
    return out


def parse_report(text: str, markers: Dict[str, Any], source: str = "",
                 date_hint: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Any]]:
    """From the report text: the date (YYYY-MM-DD) and {key: {value, ref_low, ref_high}}.

    Accounts for line wrapping in tables: when a marker name is broken
    («Антитела к циклическому / <value> / цитруллиновому пептиду (АЦЦП)»),
    the value is taken from the neighbouring row that starts with a number.
    """
    date = None
    m = _DATE.search(text) or _DATE_FALLBACK.search(text)
    if not m and date_hint:
        # The caller established the date another way — a table whose rows all
        # carry one and the same date. It is passed in rather than guessed here,
        # and it is used ONLY when the form itself printed no draw date: a date
        # the form states always wins over one a caller inferred.
        date = date_hint
    if m:
        date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    else:
        found, _ambiguous = english_date(text)
        if found:
            date = found
            m = None            # no anchor to read a clock time from
    if date and m:
        # Only a time printed IMMEDIATELY after the date is taken. A clock time
        # found anywhere else on the form may belong to the report, the printing
        # or the laboratory's opening hours, and a wrong time is worse than none:
        # it would order two draws the wrong way round.
        tm = _TIME_AFTER.match(text[m.end():m.end() + 24])
        if tm:
            hh, mm = int(tm.group(1)), int(tm.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                date = f"{date}T{hh:02d}:{mm:02d}"
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
            row_fits = _row_fits(tail[nm.end():], o_sex, o_age)
            # Descend into the block below when the row's own range belongs to
            # somebody else, AND ALSO when the row printed no range at all — many
            # forms put the value on one line and the whole reference block under
            # it, and that case used to end with no corridor at any cost.
            if o_age is not None and (rl is None or not row_fits):
                rl = rh = None
                fits = _fitting_rows(lines, i, o_sex, o_age)
                # «The only applicable row», not «the first row that passed».
                # Taking the first is how a woman who is not pregnant was measured
                # against the second-trimester interval: several rows passed a flat
                # filter and the earliest won. When more than one row fits, the
                # form is ambiguous to us and the point keeps no range — the
                # project's own rule, and the one the report quoted back at us.
                if len(fits) == 1:
                    rl, rh = fits[0]
                    rl = rl * fac if rl is not None else None
                    rh = rh * fac if rh is not None else None
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


_LABEL_ROW = re.compile(r"^\s*([А-ЯЁA-Z][^\d]{3,60}?)\s{2,}"
                        r"(?:[<>]?\s*)?\d[\d.,]*\s*([А-Яа-яA-Za-z%/^*]+[^\s]*)?")


def _unrecognised_labels(text: str, limit: int = 12):
    """The printed LABELS of rows that look like results and matched no marker.

    Labels and units only. Not the values — a proposal for the dictionary is
    about what a row is called, and the patient's numbers have no business
    leaving the machine or entering a draft. This is the raw material task 80
    turns into a proposed dictionary entry, and on its own it already replaces
    «19 files went past in silence» with a list a person can read.
    """
    markers = core.lab_markers().get("markers", {})
    known = []
    for spec in markers.values():
        known.extend(x.lower() for x in core.marker_rules(spec, "names"))
    out = []
    for ln in text.splitlines():
        m = _LABEL_ROW.match(ln)
        if not m:
            continue
        label = " ".join(m.group(1).split())
        low = label.lower()
        if any(k in low for k in known):
            continue
        if any(low.startswith(x) for x in ("дата", "пациент", "врач", "заказ", "адрес")):
            continue
        item = {"label": label, "unit": (m.group(2) or "").strip()}
        if item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def _sex_specific_and_sex_unknown(spec) -> bool:
    """True when this marker's default range is sex-specific and the sex is unknown."""
    if not spec.get("ref_by_sex"):
        return False
    return core.profile_sex() not in ("male", "female")


#: What a folder of results actually holds. The walk used to be `rglob("*.pdf")`,
#: and that is a claim about the world rather than about this folder: a lab hands
#: out PDFs, but an export hands out CSV, a portal hands out TSV, and the PGP
#: corpus keeps a participant's measured values in
#: `hu…_phenotypes_2018.csv` — read as nothing at all, so the person's lab layer
#: stayed empty while their genome was read fine. Text files go to the same
#: parser: what makes a row a lab result is the row, not the container.
_TEXT_SUFFIXES = (".csv", ".tsv", ".txt", ".tab", ".md")

#: A text file bigger than this is not a lab form. The cap keeps a stray genome
#: export in the same folder from being read into memory as prose.
_TEXT_MAX_BYTES = 8 * 1024 * 1024


def _read_any(path: Path) -> Optional[str]:
    """The text of a result file, whatever kind it is. None = we cannot read it."""
    if path.suffix.lower() == ".pdf":
        return _read_pdf(path)
    try:
        if path.stat().st_size > _TEXT_MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


#: A DELIMITED EXPORT IS A DIFFERENT KIND OF INPUT, and this is the whole reason
#: it gets its own reader instead of a wider date regex.
#:
#: A paper form is one draw: one date at the top, a column of analytes under it.
#: That shape is baked into `parse_report`, correctly, because that is how a form
#: is printed. A table is the other shape — every ROW is a measurement, with its
#: own date — and a person's export usually holds years of them. Reading it as a
#: form means either taking one date for all of it (a history flattened into a
#: day) or refusing the file (a history thrown away). Neither is acceptable, and
#: neither is a parser bug: they are the answers a form-shaped reader has.
#:
#: So: same dictionary, same unit gate, same rule that a corridor comes from the
#: document — a different arrangement of the page.
_TABLE_COLUMNS = {
    "date": ("date", "timestamp", "collected", "collection date", "draw date", "datetime",
             "date collected", "observation date", "дата", "дата забора"),
    "label": ("test", "analyte", "marker", "name", "test name", "component", "observation",
              "phenotype", "measurement", "item", "показатель", "тест", "анализ"),
    "value": ("result", "value", "result value", "numeric result", "результат", "значение"),
    "unit": ("unit", "units", "uom", "единица", "единицы", "ед. изм."),
    "range": ("reference range", "reference", "ref range", "normal range", "range",
              "референс", "референсные значения", "норма"),
}

_RANGE_TEXT = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*(?:-|–|—|to|\.\.)\s*(-?\d+(?:[.,]\d+)?)")

#: `Rheumatoid factor - IU / mL` — a real export writes the unit INTO the label,
#: because a table with one value column has nowhere else to put it. Split off,
#: but only when the tail is a unit this project already knows: a dash is a
#: perfectly ordinary character in an analyte's name («HbA1c - IFCC», «anti-CCP»),
#: and guessing that the last words after a dash are a unit would rename markers.
#: The unit table is the authority; nothing here decides what looks like one.
_LABEL_UNIT = re.compile(r"^(?P<name>.+?)\s+[-–—]\s+(?P<unit>[^-–—]{1,24})$")


def split_label_unit(label: str):
    """(key, label, unit) for a row label that may carry its unit inside it.

    THE DICTIONARY DECIDES, not the shape of the string. A dash is an ordinary
    character in an analyte's name — «anti-CCP», «HbA1c - IFCC», «Complete Blood
    Count - Hematocrit» — so a rule like «everything after the last dash is a
    unit» would rename markers. Instead: the whole label is offered to the
    dictionary first; only if that fails is the tail cut off and the head offered
    again. The tail is called a unit exactly when doing so is what made the
    marker resolvable, which is the only evidence available and the only one
    needed.
    """
    raw = (label or "").strip()
    hit = core.resolve_marker(raw)
    if hit.get("key"):
        return hit["key"], raw, None
    m = _LABEL_UNIT.match(raw)
    if m:
        head = m.group("name").strip()
        hit = core.resolve_marker(head)
        if hit.get("key"):
            return hit["key"], head, m.group("unit").strip()
    return None, raw, None


def _column_map(header: list) -> dict:
    """Header cell → what it is. Unrecognised columns are simply not used."""
    out = {}
    for i, cell in enumerate(header):
        name = (cell or "").strip().strip('"').casefold()
        for role, spellings in _TABLE_COLUMNS.items():
            if role in out:
                continue
            if name in spellings or any(name.startswith(sp) for sp in spellings):
                out[role] = i
                break
    return out


def _number(raw: str):
    try:
        return float(str(raw).strip().replace(",", ".").replace("<", "").replace(">", ""))
    except (TypeError, ValueError):
        return None


def parse_table(text: str, markers: dict, source: str = "") -> dict:
    """Rows of a delimited export → points, each with the date of its own row.

    Returns {ok, rows, points, unrecognised, reason}. `unrecognised` holds the
    labels no dictionary entry matched — the same material a dictionary proposal
    is built from, and never a guess: a row whose analyte cannot be named is not
    stored under an approximate name.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(lines) < 2:
        return {"ok": False, "reason": "not_a_table"}
    delimiter = "," if lines[0].count(",") > lines[0].count("\t") else "\t"
    reader = list(csv.reader(lines, delimiter=delimiter))
    if not reader:
        return {"ok": False, "reason": "not_a_table"}
    cols = _column_map(reader[0])
    if not all(k in cols for k in ("date", "label", "value")):
        return {"ok": False, "reason": "not_a_table", "columns": cols}
    points, unrecognised = [], []
    for row in reader[1:]:
        if len(row) <= max(cols.values()):
            continue
        raw_date = (row[cols["date"]] or "").strip().strip('"')
        label = (row[cols["label"]] or "").strip().strip('"')
        value = _number(row[cols["value"]])
        if not raw_date or not label or value is None:
            continue
        stamp = raw_date[:10] if _DATE_ROW.match(raw_date + ",") else None
        if not stamp:
            iso, _amb = english_date("collected " + raw_date)
            stamp = iso
        if not stamp:
            continue
        if len(raw_date) >= 16 and raw_date[10] in "T ":
            stamp = f"{stamp}T{raw_date[11:16]}"
        key, label, label_unit = split_label_unit(label)
        if not key or key not in markers:
            # The SAME shape the PDF path produces — `{label, unit}`. It used to
            # be a bare string here, and `format.ingest_report` reads `row["label"]`,
            # so a table with one unknown row crashed the whole report with
            # `'str' object has no attribute 'get'` — after the recognised rows
            # had already been stored. Seven points went in and the person saw a
            # traceback instead of them. One name, two shapes, and the renderer
            # could only be right about one of them; the shape is settled at the
            # source rather than defended against downstream.
            unrecognised.append({"label": label, "unit": label_unit or None})
            continue
        low = high = None
        if "range" in cols and len(row) > cols["range"]:
            m = _RANGE_TEXT.search(row[cols["range"]] or "")
            if m:
                low, high = _number(m.group(1)), _number(m.group(2))
        unit = (row[cols["unit"]].strip().strip('"') if "unit" in cols and len(row) > cols["unit"]
                else None) or label_unit
        points.append({"key": key, "label": label, "date": stamp, "value": value,
                       "unit": unit or None, "ref_low": low, "ref_high": high})
    seen, unique = set(), []
    for row in unrecognised:
        mark = (row["label"], row["unit"])
        if mark not in seen:
            seen.add(mark)
            unique.append(row)
    return {"ok": True, "rows": len(reader) - 1, "points": points,
            "unrecognised": sorted(unique, key=lambda r: r["label"]), "source": source}


def ingest(folder: str, force: bool = False) -> Dict[str, Any]:
    """Walk the folder of results and update labs.json with new markers. Incremental."""
    ex = _ensure_extractor()
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": _t("ingest_labs.folder_not_found", path=root)}
    markers = core.lab_markers().get("markers", {})
    existing = {k: m.get("name") for k, m in core.labs().get("markers", {}).items()}
    manifest = _load_manifest()
    files = sorted(f for f in root.rglob("*")
                   if f.is_file()
                   and (f.suffix.lower() == ".pdf" or f.suffix.lower() in _TEXT_SUFFIXES))
    if not files:
        return {"ok": False, "error": _t("ingest_labs.folder_empty", path=root)}
    if not ex and all(f.suffix.lower() == ".pdf" for f in files):
        # Only PDFs here and nothing to read them with: that is a refusal, and it
        # names the command. But it is no longer a refusal for the whole folder —
        # a CSV next to those PDFs is readable with no extractor at all.
        return {"ok": False, "error": _t("ingest_labs.no_pdf_reader")}
    out = {"ok": True, "engine": ex, "files_seen": len(files), "files_processed": 0,
           "points_added": 0, "skipped": 0, "per_file": [], "conflicts": [],
           "repeats": [], "draw_times": {}, "resolution_mixed": [],
           # Every file that produced nothing says WHY, by name. «19 of 47 went
           # past both counters in silence» was the first real user's report, and
           # the cause was that `skipped` counted only «unchanged since last run»
           # while three other paths returned without touching any counter at all.
           # A file dropped silently is indistinguishable from a file that was
           # never there — the project's own rule 9, which the code broke.
           "not_ingested": []}
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
        if f.suffix.lower() == ".pdf" and not ex:
            out["not_ingested"].append({"file": f.name, "reason": "no_pdf_reader",
                                        "detail": _t("ingest_labs.no_pdf_reader")})
            continue
        text = _read_any(f) or ""
        hint = None
        # Task 100. Which of the three date sources actually answered for THIS
        # file. It travels to the stored point, because the caveat printed here
        # is gone the moment the ingest output scrolls away, and the point lives
        # on in a series for years.
        date_src = "form"
        # THE ROW-WISE READER GOES FIRST for anything that is not a PDF. If the
        # file is a table with a date column, every row is a measurement with its
        # own date and the form-shaped reader below must not see it — that reader
        # can only file a whole file under one day, which for a history is either
        # destruction or refusal.
        if f.suffix.lower() != ".pdf" and text.strip():
            table = parse_table(text, markers, source=str(f))
            if table.get("ok") and table["points"]:
                added_here = []
                for pt in table["points"]:
                    spec = markers[pt["key"]]
                    r = store.add_lab_point(pt["key"], pt["date"], pt["value"],
                                            name=existing.get(pt["key"])
                                            or core.marker_display(spec, i18n.lang()) or pt["label"],
                                            unit=pt["unit"] or spec.get("unit"),
                                            ref_low=pt["ref_low"], ref_high=pt["ref_high"],
                                            direction=spec.get("direction"),
                                            # A delimited export dates every ROW,
                                            # and that column is the draw.
                                            date_source="form", subject="owner")
                    if r.get("ok"):
                        added_here.append(pt["key"])
                        if r.get("resolution_mixed"):
                            # The same report the PDF path makes below. A
                            # delimited export reaches the profile through THIS
                            # call, so a doubling found here was detected by the
                            # store and then dropped on the floor — the flag
                            # existed and the person was never shown it.
                            out.setdefault("resolution_mixed", []).append(
                                {"marker": pt["key"], "date": pt["date"],
                                 "others": r["resolution_mixed"]})
                manifest[rk] = mt
                if added_here:
                    out["files_processed"] += 1
                    out["points_added"] += len(added_here)
                    out["per_file"].append({"file": f.name, "kind": "table",
                                            "rows": table["rows"],
                                            "dates": sorted({p["date"][:10] for p in table["points"]})[:1]
                                            + (["…"] if len({p["date"][:10] for p in table["points"]}) > 1 else []),
                                            "markers": sorted(set(added_here))})
                if table["unrecognised"]:
                    out["not_ingested"].append(
                        {"file": f.name, "reason": "table_labels_unknown",
                         "detail": _t("ingest_labs.reason_table_labels", n=len(table["unrecognised"])),
                         "unrecognised": table["unrecognised"][:40]})
                continue
        if f.suffix.lower() != ".pdf" and text.strip():
            # Not a table this reader can use — no date column, or none of its
            # rows resolved. A delimited file still dates its rows rather than
            # its header, so one date across the whole of it is a draw date and
            # several are a history this reader could not place. The second case
            # is named rather than resolved by taking the first: picking one of
            # several dates for somebody's results is a guess, and a silent one.
            dates = table_dates(text)
            if len(dates) == 1:
                hint = dates[0]
            elif len(dates) > 1:
                out["not_ingested"].append(
                    {"file": f.name, "reason": "several_draw_dates",
                     "detail": _t("ingest_labs.reason_several_dates", n=len(dates),
                                  first=dates[0], last=dates[-1])})
                manifest[rk] = mt
                continue
        en_date, ambiguous = english_date(text)
        if ambiguous:
            # A date IS on the page and cannot be read. Saying «no date on this
            # form» here would be untrue, and «no date» is the sentence that
            # makes a person go looking for one.
            out["not_ingested"].append(
                {"file": f.name, "reason": "ambiguous_date",
                 "detail": _t("ingest_labs.reason_ambiguous_date", raw=ambiguous["raw"],
                              first=ambiguous["both"][0], second=ambiguous["both"][1])})
            manifest[rk] = mt
            continue
        if not (hint or en_date or _DATE.search(text) or _DATE_FALLBACK.search(text)):
            # Before the file name: a date the form gives for something NEAR the
            # draw. Four lipid panels in the reference corpus print «Ordered
            # Date» and nothing else — refusing them buys nothing, since the
            # order and the draw are a day or two apart, but filing the number
            # without saying which date it is would be a claim the form does not
            # make. So it is used, and named.
            near_date, near_amb, near_kind = english_date_near(text)
            if near_amb:
                out["not_ingested"].append(
                    {"file": f.name, "reason": "ambiguous_date",
                     "detail": _t("ingest_labs.reason_ambiguous_date", raw=near_amb["raw"],
                                  first=near_amb["both"][0], second=near_amb["both"][1])})
                manifest[rk] = mt
                continue
            if near_date:
                hint = near_date
                date_src = "ordered"
                out.setdefault("date_not_the_draw", []).append(
                    {"file": f.name, "date": near_date, "kind": near_kind,
                     "note": _t("ingest_labs.date_not_the_draw", date=near_date)})
        if not (hint or en_date or _DATE.search(text) or _DATE_FALLBACK.search(text)):
            # Before giving up: the FILE NAME. It is a weaker witness than the
            # page — people rename files to the day they downloaded them — so it
            # is used only here, at the end, and the report says the date did not
            # come off the form.
            hint = date_from_filename(f.name)
            if hint:
                date_src = "filename"
                out.setdefault("date_from_filename", []).append(
                    {"file": f.name, "date": hint,
                     "note": _t("ingest_labs.date_from_filename", date=hint)})
        if not (hint or en_date or _DATE.search(text) or _DATE_FALLBACK.search(text)):
            out["not_ingested"].append(
                {"file": f.name,
                 "reason": "no_draw_date" if text.strip() else "no_text",
                 "detail": _t("ingest_labs.reason_no_date") if text.strip()
                           else _t("ingest_labs.reason_no_text")})
            manifest[rk] = mt
            continue
        date, found = parse_report(text, markers, source=str(f), date_hint=hint)
        ftl = text.lower()
        if not date or not found:
            # Name the lines that were not recognised, not just the file. This is
            # what a dictionary proposal (task 80) will be built from: the labels
            # and units of the rows nobody could place, and nothing else — never
            # the patient's numbers.
            out["not_ingested"].append(
                {"file": f.name,
                 "reason": "no_date" if not date else "no_known_marker",
                 "detail": _t("ingest_labs.reason_no_date") if not date
                           else _t("ingest_labs.reason_no_marker"),
                 "unrecognised": [] if not date else _unrecognised_labels(text)})
            manifest[rk] = mt
            continue
        added = []
        # The point keeps the FULL stamp the form printed — day, and the clock time
        # when there was one. Truncating to the month was what made two draws in a
        # single day indistinguishable, so the second one could only be recorded as
        # a discrepancy with the first.
        stamp = date
        day = date[:10]
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
                rl, rh = v["ref_low"], v["ref_high"]
                if rl is None and rh is None and _sex_specific_and_sex_unknown(spec):
                    # The dictionary default for these six markers IS the male
                    # range — uric acid, testosterone, creatinine, ferritin,
                    # haematocrit, haemoglobin. Substituting it for a person whose
                    # sex nobody asked for is how a woman's normal testosterone
                    # was flagged against 12.1–34.4. The project's own rule says a
                    # marker with no range from the form gets no range at all; it
                    # applies here, and the point is stored without one rather
                    # than with a plausible wrong one.
                    pass
                else:
                    rl = rl if rl is not None else spec.get("ref_low")
                    rh = rh if rh is not None else spec.get("ref_high")
            # display_name — the printed name of the marker, used when names[] holds only
            # lower-case search substrings (e.g. the dysbacteriosis panel).
            name = (existing.get(key) or core.marker_display(spec, i18n.lang())
                    or (core.marker_rules(spec, "names") or [key])[0].capitalize())
            prio = 2 if any(x.lower() in ftl for x in core.marker_rules(spec, "prefer_form")) else 1
            # A REPEAT is not a conflict. Two stamps on one day are two measurements —
            # blood drawn before a procedure or a dose and again after it — and both
            # belong in the series. A conflict is two readings claiming to be THE SAME
            # measurement: the same stamp, a different number.
            same_day = seen_pt.get((key, day))
            if same_day is not None and same_day[3] != stamp:
                out.setdefault("repeats", []).append(
                    {"marker": key, "day": day,
                     "first": {"at": same_day[3], "value": same_day[0], "from": same_day[1]},
                     "second": {"at": stamp, "value": v["value"], "from": f.name}})
            prev = seen_pt.get((key, stamp))
            if prev is not None:
                if prev[0] == v["value"]:
                    continue
                if prio <= prev[2]:           # an equal or higher-priority method is recorded
                    out["conflicts"].append({"marker": key, "date": stamp,
                                             "kept": prev[0], "kept_from": prev[1],
                                             "other": v["value"], "other_from": f.name})
                    continue
                out["conflicts"].append({"marker": key, "date": stamp,   # new method prevails
                                         "kept": v["value"], "kept_from": f.name,
                                         "other": prev[0], "other_from": prev[1]})
            seen_pt[(key, stamp)] = (v["value"], f.name, prio, stamp)
            seen_pt.setdefault((key, day), (v["value"], f.name, prio, stamp))
            r = store.add_lab_point(key, stamp, v["value"], name=name, unit=spec.get("unit"),
                                    ref_low=rl, ref_high=rh, direction=spec.get("direction"),
                                    censored=v.get("censored"),
                                    date_source=date_src, subject="owner")
            if r.get("ok"):
                added.append(key)
                if r.get("resolution_mixed"):
                    # One measurement now standing in the series twice, at two
                    # resolutions. Not refused — both points may be honest — but a
                    # doubling nobody is told about is one nobody will ever undo.
                    out.setdefault("resolution_mixed", []).append(
                        {"marker": key, "date": stamp, "others": r["resolution_mixed"]})
        manifest[rk] = mt
        if added:
            out["files_processed"] += 1
            out["points_added"] += len(added)
            # `date` stays the month for the readers that already parse it; the
            # full stamp is `draw_date`. `ym` was the month variable, and when the
            # point started keeping its full stamp the assignment went and this
            # reference stayed: every ingest that actually added a point raised
            # NameError, and no test noticed because none of them ran a successful
            # ingest end to end. `test_ingest_reads_a_table.py` now does.
            out["per_file"].append({"file": f.name, "date": day[:7],
                                    "draw_date": date, "markers": added})
    _save_manifest(manifest)
    core.reset_cache()
    return out
