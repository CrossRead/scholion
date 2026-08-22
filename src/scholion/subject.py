"""Whose datum is this — the mark on the datum itself, and the rule that follows.

Task 102.

The profile could already say that it was a demonstration: `scholion init --demo`
writes `synthetic: true` into the metadata of every file it lays down. The mark
was on the FILE, and a file is not what a conclusion is drawn from. Adding one's
own measurement to a demonstration profile therefore worked — the point joined a
series of invented numbers, the file went on saying `synthetic: true`, which was
now false, and the overview counted the abnormalities of a person who is partly
fictional and partly real without saying which half was which.

Two facts were held and neither was compared with the other: «this file is
fabricated» and «this number was measured on the person reading it».

So the mark moves to the datum, with a closed vocabulary, and one rule holds the
rest together:

    **one profile, one person.**

A datum that would put a second person into a profile is refused, with one
deliberate exception: the person themselves. Their own measurement does not join
a fictional history — it replaces it. The demonstration is erased, loudly and
completely, because it is generated from a seed and can be built again in one
command, whereas a measurement cannot.

The same rule answers the genome. The reference genome the project can fetch
(`src/tools/fetch_demo_genome.py`) is a real, published sample of a real, other
person. Read beside the demonstration's laboratory history it produces
conclusions about nobody at all — a chimera of two strangers, presented as one
case. `genome.vcf_path()` asks this module before it answers, so the two cannot
meet in the first place; the alternative was a caveat printed next to the
conclusion, and a caveat is not a mechanism.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .i18n import t as _t

#: Who a datum can belong to. A closed vocabulary, for the reason task 100 gave
#: for the date of a point: an open one is not a vocabulary, and a word nobody
#: declared reads as «we know».
SUBJECTS = {
    "owner": "the person whose profile this is",
    "demo": "the fictional person of the demonstration — every figure generated, belonging to nobody",
    "reference": "a published reference sample: a real measurement of somebody else, meant to be looked at",
    "unattributed": "written before a datum said whose it was; the file is asked instead",
}

#: The subjects that are not the person reading. Data of theirs never enters a
#: conclusion beside the person's own.
NOT_THE_OWNER = ("demo", "reference")

#: What an undeclared datum is called. Never «owner»: a caller that did not say
#: cannot be assumed to have known, and this is the assumption the field exists
#: to remove.
UNATTRIBUTED = "unattributed"

#: The metadata field a whole file carries when every datum in it has the same
#: subject. `synthetic: true` is the older spelling of `subject: demo` and is
#: still read — a profile written by an earlier version must keep working.
FIELD = "subject"


def valid(name: Optional[str]) -> bool:
    return name in SUBJECTS


def unknown_error(value: Any) -> Dict[str, Any]:
    """The refusal for a subject nobody declared, in the shape the writers return."""
    return {"ok": False,
            "error": _t("subject.unknown", value=str(value),
                        accepted=", ".join(sorted(SUBJECTS)))}


def label(name: Optional[str]) -> str:
    """What to call a subject on screen."""
    if name in ("owner", "demo", "reference", UNATTRIBUTED):
        return _t("subject." + name)
    return name or ""


# ── reading ──────────────────────────────────────────────────────────────────
def of_file(data: Dict[str, Any]) -> str:
    """The subject a whole profile file declares.

    `synthetic: true` is honoured because every demonstration profile ever
    written carries it and no file carries the new field yet. Silence is
    `unattributed`, not `owner`: an unmarked file is what every real profile
    looks like today, and the erase below is allowed to touch nothing that is
    merely silent.
    """
    if not isinstance(data, dict):
        return UNATTRIBUTED
    meta = data.get("_meta") or data.get("meta") or {}
    if not isinstance(meta, dict):
        return UNATTRIBUTED
    declared = meta.get(FIELD)
    if valid(declared):
        return str(declared)
    if meta.get("synthetic"):
        return "demo"
    return UNATTRIBUTED


def of_point(point: Dict[str, Any], file_subject: str = UNATTRIBUTED) -> str:
    """The subject of one datum: its own word, or the file's if it has none.

    This is the whole of the migration. A point written before this field
    existed takes the answer from the file it lies in — which is exactly what
    the reader would conclude by hand, and which turns the file mark into the
    default rather than into a second, competing truth.
    """
    if isinstance(point, dict) and valid(point.get(FIELD)):
        return str(point[FIELD])
    return file_subject if valid(file_subject) else UNATTRIBUTED


def _points_of(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every datum in a profile file, whatever the file's shape.

    Three shapes exist and all three are walked rather than named one by one:
    markers with series (labs, metrics), a flat list (medications), and a file
    that holds no data at all (a template).
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return out
    markers = data.get("markers")
    if isinstance(markers, dict):
        for m in markers.values():
            if isinstance(m, dict):
                out += [p for p in (m.get("series") or []) if isinstance(p, dict)]
    for key in ("medications", "items", "entries"):
        v = data.get(key)
        if isinstance(v, list):
            out += [p for p in v if isinstance(p, dict)]
    return out


def subjects_in(data: Dict[str, Any]) -> List[str]:
    """Which subjects one file holds, file mark and data together."""
    fs = of_file(data)
    found = {of_point(p, fs) for p in _points_of(data)}
    if not found:
        found = {fs}
    return sorted(found)


def _profile_files(pdir: Path) -> List[Path]:
    return sorted(p for p in pdir.glob("*.json") if p.is_file())


def profile_subjects(pdir: Optional[Path] = None) -> Dict[str, List[str]]:
    """{subject: [file names]} — who the data in this profile belong to."""
    from . import core
    pdir = Path(pdir) if pdir is not None else core.profile_dir()
    out: Dict[str, List[str]] = {}
    if not pdir.is_dir():
        return out
    for p in _profile_files(pdir):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            continue
        for s in subjects_in(data):
            out.setdefault(s, []).append(p.name)
    return out


def profile_subject(pdir: Optional[Path] = None) -> Optional[str]:
    """The single subject of a profile, or None when it holds nobody's data.

    `unattributed` is not an answer on its own — it is what every profile
    written before this field looked like — so it is dropped when anything else
    is present, and reported as `owner` when it is all there is: an unmarked
    file in a person's own profile directory is that person's, and saying
    otherwise would refuse every existing installation its own data.
    """
    have = profile_subjects(pdir)
    named = [s for s in have if s != UNATTRIBUTED]
    if not named:
        return "owner" if have else None
    if len(named) == 1:
        return named[0]
    return "mixed"


# ── the erase ────────────────────────────────────────────────────────────────
def erasable(pdir: Path) -> List[Path]:
    """The files that hold demonstration data and nothing else.

    The gate of the erase, and the reason it is safe: a file is only listed when
    every subject in it is one of `NOT_THE_OWNER`. A file that is merely silent
    is never listed, so the failure mode this could have had — «an unmarked
    profile looked like a demonstration» — cannot occur.
    """
    out: List[Path] = []
    for p in _profile_files(pdir):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            continue
        seen = subjects_in(data)
        if seen and all(s in NOT_THE_OWNER for s in seen):
            out.append(p)
    return out


def _demo_index(pdir: Path) -> Optional[Path]:
    """`index.md` if it is the demonstration's own, unedited.

    The demonstration generates deterministically, so identity with the shipped
    text is a fact rather than a guess. A file somebody has edited is theirs and
    stays — this is the difference between erasing generated data and erasing
    somebody's writing.
    """
    p = pdir / "index.md"
    if not p.is_file():
        return None
    try:
        from . import demo as _demo
        return p if p.read_text(encoding="utf-8") == _demo.INDEX_MD else None
    except Exception:                                            # noqa: BLE001
        return None


def claim_for_owner(pdir: Optional[Path] = None) -> Dict[str, Any]:
    """The person's own datum is about to be written: the demonstration goes.

    Returns `{"claimed": False}` when there is nothing to erase, which is the
    ordinary case and costs one directory listing.

    The demonstration is erased rather than moved aside. Moving it aside leaves
    a second profile nobody asked for, in a folder nobody will look in, holding
    a fictional person's abnormalities — and `scholion init --demo` puts it back
    byte for byte, from a seed, in one command.
    """
    from . import core
    pdir = Path(pdir) if pdir is not None else core.profile_dir()
    if not pdir.is_dir():
        return {"claimed": False}
    doomed = erasable(pdir)
    if not doomed:
        return {"claimed": False}
    idx = _demo_index(pdir)
    if idx is not None:
        doomed.append(idx)
    erased = []
    for p in doomed:
        try:
            p.unlink()
            erased.append(p.name)
        except OSError:                                          # pragma: no cover
            pass
    core.reset_cache()
    return {"claimed": True, "erased": sorted(erased),
            "message": _t("subject.demo_erased", files=", ".join(sorted(erased)))}


# ── the genome ───────────────────────────────────────────────────────────────
#: What a genome folder puts beside the file to say whose it is. Written by
#: `src/tools/fetch_demo_genome.py`; absent beside a person's own genome, which
#: is the common case and means «the profile's own subject».
SIDECAR = "SUBJECT.json"


def genome_note(folder: Path) -> Dict[str, Any]:
    """What the folder says about the person the genome came from."""
    p = Path(folder) / SIDECAR
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def of_genome(vcf: Path) -> str:
    """The subject of a genome file: what the folder declares, and nothing more.

    A folder that says nothing is `unattributed`, NOT «the owner». The difference
    decides a real case: every genome anybody has ever put in the folder is
    unmarked, and reading silence as a claim would turn each of them into a
    second person the moment the profile beside it was a demonstration. Silence
    is not a claim — the same rule the erase above obeys.
    """
    note = genome_note(Path(vcf).parent)
    s = note.get(FIELD)
    return str(s) if valid(s) else UNATTRIBUTED


def genome_conflict(vcf: Optional[Path], pdir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Whether this genome and this profile describe two different people.

    None means they may be read together. A dict is the refusal, and it names
    both sides: a message that says only «refused» sends the reader to look for
    a fault in the file, which is the one place there is no fault.
    """
    if vcf is None:
        return None
    theirs = of_genome(Path(vcf))
    if theirs == UNATTRIBUTED:
        # The file does not say whose it is, so it is this profile's — which is
        # what every installation before this field looked like, and what a
        # person's own genome will always look like.
        return None
    mine = profile_subject(pdir)
    if mine is None or mine == UNATTRIBUTED:
        # A profile with no data of anybody's takes the genome it is given.
        return None
    if theirs == mine:
        return None
    note = genome_note(Path(vcf).parent)
    return {"reason": "another_person",
            "genome_subject": theirs,
            "profile_subject": mine,
            "who": note.get("who") or label(theirs),
            "path": str(vcf),
            "message": _t("subject.genome_not_ours",
                          path=str(vcf),
                          who=note.get("who") or label(theirs),
                          whose=label(mine)),
            "fix": _t("subject.genome_fix")}
