"""When a genome file may ship — the one exception, defined once.

Four independent gates keep genomic formats out of this project: `.gitignore`,
the pre-commit check (`check_staged.py`), the build audit (`make_shareable.py`)
and the `.gitignore` the build writes into the public package. Each of them is
right, and each of them is wrong about exactly one file: the few-line VCF that
the test suite needs in order to prove that an unread position is not read as the
reference.

That test guards the strongest failure the audit of v2.10.0 found — a connected
genome producing a LESS cautious answer than no genome at all — so shipping the
test without its fixture would leave the regression uncovered for everyone but
the owner. Shipping the fixture means opening a hole in four bans.

The hole is therefore cut once, here, and by CONTENT rather than by name. A path
in an exception list is a promise about a name; a real genome renamed to
`tiny.vcf.gz` would walk straight through it. What follows cannot be walked
through by renaming:

* the file lives in `tests/fixtures/genome/` — the sandbox, not a data slot;
* it declares itself invented in its own `##` header, in words a human wrote;
* it is at most 64 KiB and at most 50 called positions.

The size and row caps are what make the declaration safe to trust. A person's
variant call set is megabytes at the very least, and the smallest useful slice of
one still carries hundreds of rows: there is no way to smuggle a medical record
through a limit this low, whatever the header says. The declaration answers "is
this meant to be real"; the caps answer "could this be real at all".

An index (`.tbi`) carries no data of its own and is judged by its VCF: allowed
when the file it indexes is allowed, refused when it stands alone — an index
without its VCF is either a leftover or the visible half of something else.
"""
from __future__ import annotations

import gzip
from pathlib import Path
from typing import Optional, Tuple

#: The only directory a genome fixture may live in. Kept as a tuple of path parts
#: so that the same check works on a repository-relative path and on a path
#: inside a built package.
FIXTURE_DIR: Tuple[str, ...] = ("tests", "fixtures", "genome")

#: Hard ceilings. See the module docstring: these, not the declaration, are what
#: make the exception unusable for carrying real data.
MAX_BYTES = 64 * 1024
MAX_ROWS = 50

#: The same stems as the rest of the project's self-declaration checks, in both
#: alphabets and for the same reason: this reads a sentence written by a human,
#: so it is input, not printed text.
_SYNTHETIC_WORDS = ("SYNTHETIC", "FIXTURE", "СИНТЕТ", "ФИКСТУР", "ВЫМЫШЛ")


def _in_fixture_dir(p: Path) -> bool:
    parts = p.parts
    n = len(FIXTURE_DIR)
    return any(parts[i:i + n] == FIXTURE_DIR for i in range(len(parts) - n + 1))


def vcf_text(path) -> Optional[str]:
    """The VCF as text, decompressed if need be. None if it is not a VCF at all.

    Exported because a caller that lets the file through owes it a content check:
    the exception costs the fixture its exemption from being read, not the other
    way round.
    """
    p = Path(path)
    low = p.name.lower()
    try:
        if low.endswith(".vcf.gz"):
            with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
                return fh.read(MAX_BYTES * 8)
        if low.endswith(".vcf"):
            return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return None


def check(path) -> Tuple[bool, str]:
    """May this genome file ship? Returns (verdict, the reason it was refused).

    The reason is returned rather than printed because three different tools
    report it three different ways, and a check that can only print is a check
    that cannot be tested.
    """
    p = Path(path)
    low = p.name.lower()

    if low.endswith(".tbi"):
        sibling = p.with_name(p.name[:-4])
        if not sibling.exists():
            return False, "an index whose VCF is not here — a leftover, or half of something else"
        ok, why = check(sibling)
        return ok, (f"the VCF it indexes is not allowed: {why}" if not ok else "")

    if not _in_fixture_dir(p):
        return False, ("a genome file outside " + "/".join(FIXTURE_DIR)
                       + " — the exception covers the test sandbox and nothing else")
    if not (low.endswith(".vcf") or low.endswith(".vcf.gz")):
        return False, "not a VCF: only a variant call set can declare itself in a header"
    try:
        size = p.stat().st_size
    except OSError:
        return False, "the file does not open — it could not be checked"
    if size > MAX_BYTES:
        return False, (f"{size} bytes, the ceiling is {MAX_BYTES} — a fixture that big "
                       f"is no longer obviously invented")

    text = vcf_text(p)
    if text is None:
        return False, "the file does not open as a VCF — it could not be checked"

    header = [ln for ln in text.splitlines() if ln.startswith("##")]
    declared = " ".join(header).upper()
    if not any(w in declared for w in _SYNTHETIC_WORDS):
        return False, ("the header does not declare the file invented — add a `##` line "
                       "saying so outright (e.g. `##source=SYNTHETIC test fixture`)")

    rows = sum(1 for ln in text.splitlines() if ln and not ln.startswith("#"))
    if rows > MAX_ROWS:
        return False, f"{rows} called positions, the ceiling is {MAX_ROWS}"

    return True, ""


def allowed(path) -> bool:
    return check(path)[0]
