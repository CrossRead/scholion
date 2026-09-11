"""What an external tool actually buys, said where a person is asked to install it.

`scholion init` offers a set of binaries, and `scholion tools` explains each set.
The explanation of the first one read: «without these the genome layer does not
work at all: a VCF can be neither read, nor indexed, nor filtered.» That was true
when it was written. It stopped being true on 10.09.2026, when a file with no
index became readable and the secondary-findings screen became runnable without
any of them — and a sentence that was true once, shown at the very first command
a new person types, is the most expensive kind of stale: it sends somebody to
install four programs before finding out they did not need them to start.

The sentence was corrected on that day and the set was not: `base` went on
REQUIRING samtools and bcftools while its own text said they were for building
and annotating a genome rather than for reading one. A set is read by its
membership — `scholion tools` counts a required tool as missing, and `init`
offers it — so the prose and the list disagreed in front of the same person.
Since 12.09.2026 the two tools that buy a different capability are a different
set, and this holds both halves to the code: the sets say what the code needs,
and the two modules the sentence vouches for — the reader with no index and the
ACMG screen — call no external binary at all. If either ever grows a
`shutil.which` or a `subprocess`, the sentence has to change again, and this
fails until it does.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core

SRC = Path(support.ROOT) / "src" / "scholion"


def sets():
    return core._read_knowledge_raw("external_tools.json").get("sets") or {}


def base_set():
    return sets().get("base") or {}


def why(lang="en", which="base"):
    w = (sets().get(which) or {}).get("why") or {}
    return (w.get(lang) or "") if isinstance(w, dict) else str(w)


class TestTheSetsSayWhatTheCodeNeeds(unittest.TestCase):

    def test_reading_needs_only_the_index_tools(self):
        self.assertEqual(sorted(base_set().get("tools") or []), ["bgzip", "tabix"])

    def test_building_and_annotating_are_their_own_set(self):
        annotate = sets().get("annotate") or {}
        self.assertEqual(sorted(annotate.get("tools") or []), ["bcftools", "samtools"])
        self.assertFalse(annotate.get("offer_at_init"),
                         "offered by the step that needs them, not at first run")

    def test_none_of_the_four_was_lost_in_the_split(self):
        """The split moved two tools; it must not have dropped one on the way."""
        both = sorted(list(base_set().get("tools") or []) + list((sets().get("annotate") or {}).get("tools") or []))
        self.assertEqual(both, ["bcftools", "bgzip", "samtools", "tabix"])

    def test_the_first_run_offers_the_reading_set_and_nothing_more(self):
        offered = sorted(k for k, s in sets().items() if s.get("offer_at_init"))
        self.assertEqual(offered, ["base"])


class TestTheReasonGivenIsTheReasonThatHolds(unittest.TestCase):

    def test_it_no_longer_claims_a_vcf_cannot_be_read_without_them(self):
        self.assertNotIn("does not work at all", why("en").lower())

    def test_it_names_what_still_answers_without_them(self):
        """The half a person needs in order to decide, and the half that was
        missing: not «what breaks», but «what you already have»."""
        en = why("en").lower()
        for fragment in ("catalogue", "acmg-scan"):
            self.assertIn(fragment, en)

    def test_both_languages_carry_the_corrected_reason(self):
        """Asserted on the command name rather than on a translated phrase: the
        public tree keeps no Russian outside the message catalogue, and a test
        that quoted the sentence would put some back."""
        for which in ("base", "annotate"):
            ru, en = why("ru", which), why("en", which)
            with self.subTest(set=which):
                self.assertTrue(ru.strip())
                self.assertNotEqual(ru, en)
                for text in (ru, en):
                    self.assertIn("acmg-scan", text)

    def test_it_names_what_genuinely_needs_them(self):
        self.assertIn("seek", why("en").lower())
        self.assertIn("clinvar", why("en", "annotate").lower())

    def test_the_prose_and_the_membership_agree(self):
        """The defect this file guards: the text said bcftools and samtools were
        not for reading, and the reading set required them."""
        en = why("en").lower()
        self.assertIn("bcftools", en)
        for name in ("bcftools", "samtools"):
            self.assertNotIn(name, base_set().get("tools") or [],
                             f"the reading set requires {name} while its text says it is not for reading")


class TestTheClaimIsTrueOfTheCode(unittest.TestCase):
    """The two capabilities the sentence promises without external tools, held
    to the source rather than to `hasattr`: a function that exists proves nothing
    about what it shells out to."""

    MODULES = ("acmg_scan", "linear")

    @staticmethod
    def _external_calls(path: Path):
        """Every way of reaching an external binary the tree knows how to spell."""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found += [f"import {a.name}" for a in node.names
                          if a.name.split(".")[0] in ("subprocess", "shutil")]
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in ("subprocess", "shutil"):
                    found.append(f"from {node.module} import …")
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute):
                    owner = fn.value.id if isinstance(fn.value, ast.Name) else None
                    if (owner, fn.attr) in (("shutil", "which"),) or owner == "subprocess":
                        found.append(f"{owner}.{fn.attr}() at line {node.lineno}")
                    if fn.attr in ("_have_bcftools", "_have_samtools", "_have_tabix"):
                        found.append(f"{fn.attr}() at line {node.lineno}")
                elif isinstance(fn, ast.Name) and fn.id in ("which", "run", "check_output", "Popen"):
                    found.append(f"{fn.id}() at line {node.lineno}")
        return found

    def test_neither_module_reaches_an_external_binary(self):
        for name in self.MODULES:
            with self.subTest(module=name):
                self.assertEqual([], self._external_calls(SRC / f"{name}.py"),
                                 f"{name} shells out — the tool advice promises it does not")

    def test_the_walk_sees_what_it_looks_for(self):
        """A walk that matched nothing on `genome.py` — which does shell out, by
        design, where an index and bcftools are present — would pass this file
        as loudly on an empty pattern."""
        self.assertTrue(self._external_calls(SRC / "genome.py"))

    def test_the_two_entry_points_exist(self):
        from scholion import acmg_scan, linear
        self.assertTrue(hasattr(linear, "snapshot"), "reading with no index")
        self.assertTrue(hasattr(acmg_scan, "scan"), "the ACMG screen in the package")


class TestTheWideScreenSaysWhatItNeeds(unittest.TestCase):
    """The one genomic path that does still need the toolchain says so where it
    refuses, instead of pointing at a document and leaving the reader to find out
    an hour later."""

    def test_the_clinvar_refusal_names_the_tools_and_the_alternative(self):
        from scholion.i18n import t as _t
        import os
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                text = _t("genome.clinvar_not_run")
            finally:
                os.environ.pop("SCHOLION_LANG", None)
            with self.subTest(lang=lang):
                self.assertIn("bcftools", text)
                self.assertIn("acmg-scan", text,
                              "the screen that needs nothing is the useful half of this refusal")


if __name__ == "__main__":
    unittest.main()
