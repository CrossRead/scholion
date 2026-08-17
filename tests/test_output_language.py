"""The English report is English all the way down.

The project accepts Russian on the input side for ever — lab forms, marker
names, the wording a laboratory prints on paper. That is a feature, and the
resolver in `core._localized` deliberately falls back to the language of the
source rather than dropping a value it cannot translate. The cost of that
design is a failure mode nobody notices by reading the code: a phrase that was
never routed through the message catalogue keeps printing Russian, and it
prints it in the middle of an English report, where it looks like the author
was careless rather than like a defect.

That failure is invisible in unit tests, because each unit is correct. It is
only visible from outside, in the finished text. So this is checked the way a
reader would check it: run every report and look for Cyrillic.

The profile used here is the synthetic demo — a fictional person whose forms
are English. Against the owner's own Russian forms the same reports legitimately
print Russian marker names, because the name comes from the paper in his hand;
running the gate on Russian source data would measure the data, not the code.
"""
from __future__ import annotations

import re
import unittest

import support

CYRILLIC = re.compile(r"[Ѐ-ӿ]+")

DEMO_PROFILE = support.ROOT / "demo" / "profile"

# `skill` prints a document, not a report: the instruction for a language model.
# Its language is governed by `src/tools/check_language.py` and by
# `tests/test_owner_split.py`, and it legitimately quotes Russian lab-form
# vocabulary as samples the model will encounter. Checking it here would test
# the same thing twice and in the weaker way.
NOT_A_REPORT = {"skill", "serve", "init", "demo"}


def _reports():
    from scholion import contract
    return sorted(c for c in contract.cli_commands()
                  if c not in NOT_A_REPORT and support.ARGS_FOR.get(c, []) is not None)


@unittest.skipUnless(DEMO_PROFILE.is_dir(), "the demo profile is not part of this build")
class TestEnglishOutputHasNoRussian(unittest.TestCase):

    def test_no_cyrillic_in_any_english_report(self):
        for command in _reports():
            with self.subTest(command=command):
                args = [command, *support.ARGS_FOR.get(command, [])]
                code, out, err = support.run(args, profile_dir=DEMO_PROFILE,
                                             lang="en")
                self.assertEqual(code, 0, f"{command}: return code {code}\n{err}")
                found = sorted(set(CYRILLIC.findall(out)))
                self.assertEqual(
                    found, [],
                    f"«{command}» printed Russian into the English report: "
                    + ", ".join(found[:10])
                    + " — a phrase that never went through src/scholion/i18n, "
                      "or a knowledge field whose 'en' side holds Russian text")

    def test_the_gate_would_notice(self):
        """Protection against "green because nothing was checked".

        A report list that silently became empty, or a runner that stopped
        passing the language through, would make the test above pass on any
        codebase at all.
        """
        self.assertGreater(len(_reports()), 15,
                           "the report list collapsed — the gate above checks nothing")
        code, out, _ = support.run(["overview"], profile_dir=DEMO_PROFILE, lang="ru")
        self.assertEqual(code, 0)
        self.assertTrue(CYRILLIC.search(out),
                        "the Russian report came out without a single Cyrillic letter — "
                        "the language is not reaching the process, so the English "
                        "check above proves nothing")


if __name__ == "__main__":
    unittest.main()
