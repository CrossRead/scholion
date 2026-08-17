"""Strip a person's identifiers out of text they are about to publish.

The moment this exists for: somebody hits a bug, copies the output of a command
into an issue, and the output is a medical record. Not by accident — by design.
Every report this project prints is about one person, so anything pasted from it
carries their lab values, their genotypes, sometimes the sample identifier the
laboratory printed on the form.

Zero incidents is a metric that cannot be recovered after the fact. A log posted
to a public tracker is public from that second, and deleting the issue does not
delete the copy the search index took.

**What this tool refuses to pretend.** It cannot know what is personal in
general. A number is a lab value or a version, a word is a surname or a gene
name, and no rule tells them apart from the outside. So it does two separate
things and reports them separately:

* it REPLACES what it can recognise — the identifiers the person listed in
  `.personal_patterns`, e-mail addresses, phone numbers, dates of birth, home
  paths that carry an account name, and long identifier-looking tokens;
* it POINTS AT what it cannot decide — numbers standing next to marker names,
  genotypes, dates — and says how many there are, so the decision is taken by
  the person and not silently on their behalf.

A tool that returned only the first half would be worse than none: it would read
as a guarantee, and the reader would stop looking.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from . import core
from .i18n import t as _t

MASK = "[redacted]"

#: Structural classes — recognisable by shape rather than by content, which is
#: why they can be replaced without knowing the person.
RULES: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+\d{1,3}[\s(-]?)?(?:\d[\s()-]?){9,14}\d(?!\d)")),
    # A date of birth is written the same way as any other date; the tool cannot
    # tell them apart, so it masks the DAY.MONTH.YEAR form wholesale and says so.
    ("date", re.compile(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b")),
    # A path with a home directory in it names the account, and the account is
    # usually the person: /Users/ivanov/…, C:\Users\ivanov\…, /home/ivanov/…
    ("home_path", re.compile(r"(?i)(?:/Users/|/home/|C:\\Users\\)[^\s/\\:'\"]+")),
    # A laboratory sample number: a long run of digits and letters with no spaces.
    # Public identifiers are excluded by name — an rsID, a PGS model, a ClinVar or
    # Ensembl accession are exactly what a bug report is ABOUT, and masking them
    # would leave a person with a redacted text they cannot file. The tool would
    # also then be contradicting itself: it lists genotype tokens below as
    # something it deliberately does not touch.
    ("sample_id", re.compile(r"\b(?!(?:rs|pgs|rcv|vcv|ens|nm_|np_|chr)\d?)"
                             r"(?=[A-Za-z0-9-]{9,})(?=[^\s]*\d)[A-Za-z0-9][A-Za-z0-9-]{8,}\b",
                             re.IGNORECASE)),
)

#: What the tool can see but must not decide. Counted and named, never touched.
NOTICES: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("genotype", re.compile(r"\b(?:rs\d{2,})\b|\b[ACGT]/[ACGT]\b|\b\*\d+/\*\d+\b")),
    ("measurement", re.compile(r"\b\d+[.,]\d+\s*(?:mmol/L|ммоль/л|µmol/L|мкмоль/л|g/L|г/л|"
                               r"ng/mL|нг/мл|U/L|Ед/л|%)")),
)


def _personal_patterns() -> List[str]:
    """The identifiers the person listed for themselves, if they have.

    `.personal_patterns` is deliberately outside git — it is a list of somebody's
    name, sample number and e-mail. The redactor reads it and never prints it: the
    report says how many patterns matched, not which.
    """
    path = core.repo_dir() / ".personal_patterns"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("warn:"):
            line = line[5:].strip()
        out.append(line)
    return out


def redact(text: str) -> Dict[str, Any]:
    """Return the cleaned text, what was replaced, and what needs a human."""
    replaced: Dict[str, int] = {}

    own = _personal_patterns()
    for pat in own:
        body = pat[3:] if pat.startswith("re:") else re.escape(pat)
        try:
            rx = re.compile(body, re.IGNORECASE)
        except re.error:
            continue
        text, n = rx.subn(MASK, text)
        if n:
            replaced["your own patterns"] = replaced.get("your own patterns", 0) + n

    for name, rx in RULES:
        text, n = rx.subn(MASK, text)
        if n:
            replaced[name] = n

    notices: Dict[str, int] = {}
    for name, rx in NOTICES:
        n = len(rx.findall(text))
        if n:
            notices[name] = n

    return {"text": text, "replaced": replaced, "notices": notices,
            "patterns_loaded": len(own),
            "warning": _t("redact.no_patterns") if not own else ""}


def run(path: str = "-", write: str = "") -> Dict[str, Any]:
    """Redact a file (or stdin when the path is `-`)."""
    if path == "-":
        import sys
        raw = sys.stdin.read()
        source = "stdin"
    else:
        p = Path(path).expanduser()
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": _t("redact.no_file", path=str(p))}
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:                                      # noqa: BLE001
            return {"ok": False, "error": str(e)}
        source = str(p)

    res = redact(raw)
    res.update({"ok": True, "source": source})
    if write:
        out = Path(write).expanduser()
        out.write_text(res["text"], encoding="utf-8")
        res["written_to"] = str(out)
    return res
