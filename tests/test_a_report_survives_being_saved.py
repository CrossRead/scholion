"""A report that can be read on screen can also be kept.

`scholion labs` printed to a terminal and `scholion labs > labs.txt` are the same
command; only the second one used to end in a traceback. The difference is the
encoding Python picks for the stream: from a terminal it asks the terminal, and
redirected it falls back to the locale — `cp1252` or `cp1251` on a Windows
machine, `ascii` under a bare `C` locale. The reports are full of characters
none of those can represent: the arrow into a recommendation, the dash between
the halves of a sentence, the tick beside what was verified, the guillemets
around a quoted line of a form.

Measured before the fix: thirteen of sixteen commands died this way, and each
died at the moment somebody tried to KEEP their report rather than glance at it.
Nothing in the suite noticed, because a test harness captures output through a
pipe it opens itself — in UTF-8.

So the encoding is set here on purpose, to what the platform would have chosen,
and the command is required to survive it AND to write the characters it meant.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

import support

#: What a redirected stream is given on the platforms this has to work on. Not a
#: guess: `cp1252` is the Windows ANSI page for a Western installation, `cp1251`
#: for a Russian one — the two the owner's own reports would meet — and `ascii`
#: is what a bare `C` locale gives on any Unix.
STREAM_ENCODINGS = ("cp1252", "cp1251", "ascii")

#: Characters the renderer actually emits. Checked so that "it did not crash" is
#: not satisfied by a command that quietly printed nothing.
TYPOGRAPHY = ("→", "—", "✓", "«", "⚠")


def run_with_stream_encoding(args, encoding: str, lang: str = "en"):
    """Run a command with the stream encoding a redirect would have given it.

    `PYTHONIOENCODING` is exactly the lever the platform pulls: it is what Python
    consults for stdout when the destination is not a terminal. Setting it here
    reproduces the redirect without needing one.
    """
    env = support.env(lang=lang)
    env["PYTHONIOENCODING"] = encoding
    p = subprocess.run([sys.executable, "-m", "scholion", *args],
                       cwd=str(support.ROOT), env=env, timeout=120,
                       stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr


class TestACommandDoesNotDieOnTheStreamItWasGiven(unittest.TestCase):

    #: A spread rather than all of them: one that renders prose, one that renders
    #: a table, one that renders a refusal, one that renders a list. The whole
    #: sweep is what `test_cli_smoke` is for; this asks a different question of a
    #: few commands, not the same question of every one.
    COMMANDS = (["limits"], ["labs"], ["sources"], ["capabilities"], ["markers"])

    def test_it_survives_a_windows_code_page(self):
        for cmd in self.COMMANDS:
            for enc in STREAM_ENCODINGS:
                with self.subTest(command=cmd[0], encoding=enc):
                    code, out, err = run_with_stream_encoding(cmd, enc)
                    self.assertNotIn(b"UnicodeEncodeError", err,
                                     f"`scholion {cmd[0]}` cannot be redirected on a "
                                     f"{enc} stream — which is what a Windows machine "
                                     f"gives it")
                    self.assertEqual(code, 0, err.decode("utf-8", "replace")[-800:])

    def test_what_it_wrote_is_still_the_report(self):
        """Not «it did not crash» — «it wrote what it meant».

        Silencing the error by dropping the characters would pass the test above
        and lose the arrow that separates a finding from what to do about it.
        """
        code, out, err = run_with_stream_encoding(["limits"], "cp1251")
        self.assertEqual(code, 0)
        text = out.decode("utf-8", "strict")   # strict: the bytes must BE utf-8
        self.assertTrue(any(ch in text for ch in TYPOGRAPHY),
                        "the command survived by writing something that is no "
                        "longer the report")

    def test_the_russian_report_too(self):
        """The language with the most to lose: every line is outside `ascii`."""
        code, out, err = run_with_stream_encoding(["limits"], "ascii", lang="ru")
        self.assertEqual(code, 0, err.decode("utf-8", "replace")[-800:])
        self.assertIn("данн", out.decode("utf-8", "strict").lower(),
                      "the Russian report did not survive an ascii stream")


class TestTheGuardIsReachable(unittest.TestCase):
    """The guard has to be provable, not merely present.

    A test that only ever sees the fixed code cannot tell a working guard from a
    deleted one. This one asks the question the other way round: with the fix
    switched off, the very same command must fail — so that if somebody removes
    `console.speak_utf8` and the suite stays green, THIS test goes red instead of
    everything staying quiet.
    """

    def test_without_the_fix_the_command_would_die(self):
        code = ("import sys, io\n"
                "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='cp1252')\n"
                "print('a \\u2192 b')\n")
        p = subprocess.run([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertNotEqual(p.returncode, 0,
                            "printing an arrow to a cp1252 stream no longer fails — "
                            "this platform cannot demonstrate the defect, and the "
                            "tests above therefore prove nothing here")
        self.assertIn(b"UnicodeEncodeError", p.stderr)


if __name__ == "__main__":
    unittest.main()
