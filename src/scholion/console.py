"""The stream the reports are printed to, made able to carry them.

Every report this program renders is written in the characters of ordinary
typography — an arrow into the recommendation, a dash between the two halves of
a sentence, a tick beside what was verified, guillemets around a quoted line of
a form. They are not decoration that could be dropped: they are what the
renderer emits, in both languages it speaks.

Whether those characters survive being printed is decided by the ENCODING OF THE
STREAM, and that is not a property of this program. Attached to a terminal,
Python asks the terminal. Redirected to a file or into a pipe, it falls back to
the encoding of the locale — `cp1252` or `cp1251` on a Windows machine, `ascii`
under a bare `C` locale. Neither can represent an arrow, so

    scholion labs > labs.txt

ends in `UnicodeEncodeError` and a traceback, having written a truncated file.
Measured before this existed: thirteen of sixteen commands died that way, and
they died at the moment somebody tried to KEEP their report rather than glance
at it.

The fix is to say what the stream should be rather than inherit it. UTF-8 is the
right answer for a file — it is what every later reader will assume, and what
Python itself defaults to from 3.15. `backslashreplace` is deliberate over the
usual `replace`: a character that still cannot be written appears as its own
escape rather than as a question mark, so a person can see WHAT was lost. A
stream that is already UTF-8 is left untouched, and so is one that cannot be
reconfigured — a test's `StringIO`, a stream somebody replaced on purpose.
"""
from __future__ import annotations

import sys
from typing import List

#: Spellings of the same encoding. `sys.stdout.encoding` is whatever the
#: platform called it, and comparing to the single string "utf-8" would
#: reconfigure a stream that was already right.
_UTF8 = {"utf-8", "utf8", "utf_8", "u8", "cp65001"}


def speak_utf8(*streams) -> List[str]:
    """Give the output streams an encoding that can carry a report.

    Returns the names of the streams that had to be changed — empty when the
    environment was already able to print. The return value is what a test can
    assert on: a guard whose effect cannot be observed cannot be proved to work.
    """
    changed: List[str] = []
    for s in (streams or (sys.stdout, sys.stderr)):
        if s is None:
            continue
        enc = (getattr(s, "encoding", "") or "").lower().replace("-", "-")
        if enc.lower() in _UTF8:
            continue
        recfg = getattr(s, "reconfigure", None)
        if recfg is None:
            # Not a text stream this program owns — a StringIO under test, or a
            # stream the caller substituted. Rewriting it would be a surprise.
            continue
        try:
            recfg(encoding="utf-8", errors="backslashreplace")
        except (ValueError, OSError):
            # Already detached, or in a state that refuses reconfiguration. The
            # print that follows may still fail — but failing to print is not a
            # reason to fail to run.
            continue
        changed.append(getattr(s, "name", "") or repr(s))
    return changed
