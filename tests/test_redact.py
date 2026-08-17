"""Text a person is about to publish, with their identifiers taken out of it.

The scenario is not hypothetical and it is not rare: somebody hits a bug, copies
the output of a command into an issue, and the output is a medical record. That
is not an accident of the output — it is what the output IS. Every report this
project prints is about one person.

Two properties are tested here, and the second is the one that makes the tool
honest rather than dangerous:

* what can be recognised by shape is removed — e-mail, phone, a date written as a
  date of birth, a home path that names the account, a laboratory sample number,
  and whatever the person listed for themselves;
* what CANNOT be decided from the outside is left alone and REPORTED. A number is
  a lab value or a version; a token is a genotype or a version string. A tool
  that silently guessed would be trusted, and being trusted is exactly the
  property it must not have here.

The third case is the one that would quietly ruin the tool's usefulness: masking
the public identifiers a bug report is about — an rsID, a PGS model, a ClinVar
accession. A redactor that eats those hands the person a text they cannot file,
and it contradicts its own report, which lists genotype tokens as untouched.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support

from scholion import core, redact


class TestWhatIsRemoved(unittest.TestCase):

    def test_an_email_goes(self):
        r = redact.redact("write to someone@example.org please")
        self.assertNotIn("someone@example.org", r["text"])
        self.assertIn("email", r["replaced"])

    def test_a_date_of_birth_shaped_date_goes(self):
        r = redact.redact("born 03.03.1970")
        self.assertNotIn("03.03.1970", r["text"])

    def test_a_home_path_loses_the_account_name(self):
        r = redact.redact("/Users/ivanov/genome/x.vcf and /home/ivanov/labs")
        self.assertNotIn("ivanov", r["text"])
        self.assertIn("home_path", r["replaced"])

    def test_a_sample_number_goes(self):
        # An invented number, and it has to stay invented: the sanitiser replaces the
        # owner's real one on the way into the package, and a test written around
        # that string would pass here and fail for every recipient.
        r = redact.redact("sample LX7742001QF was sequenced")
        self.assertNotIn("LX7742001QF", r["text"])


class TestWhatMustSurvive(unittest.TestCase):
    """Masking these would leave a person unable to file the report at all."""

    def test_an_rsid_survives(self):
        r = redact.redact("genotype at rs4149056 looks wrong")
        self.assertIn("rs4149056", r["text"])

    def test_a_pgs_model_identifier_survives(self):
        r = redact.redact("model PGS000803 gives a percentile of 94")
        self.assertIn("PGS000803", r["text"])

    def test_a_clinvar_accession_survives(self):
        r = redact.redact("see VCV000012345 for the classification")
        self.assertIn("VCV000012345", r["text"])

    def test_the_tool_does_not_contradict_its_own_report(self):
        """It lists genotype tokens as untouched — so it must not touch them."""
        text = "rs4149056 T/C and CYP2C19 *2/*17"
        r = redact.redact(text)
        self.assertIn("genotype", r["notices"])
        for token in ("rs4149056", "T/C", "*2/*17"):
            self.assertIn(token, r["text"])


class TestWhatIsReportedRatherThanDecided(unittest.TestCase):
    """Runs against an EMPTY data root on purpose.

    The first version of this class read whatever `.personal_patterns` the machine
    happened to have. It passed in the cloud, where there is none, and failed on
    the owner's laptop, where there is one — a test whose verdict depends on whose
    computer it runs on teaches people to re-run the suite until it is green.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._old = os.environ.get("SCHOLION_REPO_DIR")
        os.environ["SCHOLION_REPO_DIR"] = str(self.dir)
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_REPO_DIR", None)
        else:
            os.environ["SCHOLION_REPO_DIR"] = self._old
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_lab_values_are_counted_and_left(self):
        r = redact.redact("Glucose 5.4 mmol/L, ferritin 41.2 ng/mL")
        self.assertEqual(r["notices"].get("measurement"), 2)
        self.assertIn("5.4", r["text"])

    def test_without_a_pattern_file_the_report_says_so(self):
        """Silence here would read as «your name is gone». It is not."""
        r = redact.redact("Ivanov had a test")
        self.assertTrue(r["warning"], "a redactor that does not know the person's name must "
                                      "say so — otherwise its silence is a promise it cannot keep")
        self.assertIn("Ivanov", r["text"])


class TestThePersonsOwnPatterns(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._old = os.environ.get("SCHOLION_REPO_DIR")
        os.environ["SCHOLION_REPO_DIR"] = str(self.dir)
        (self.dir / ".personal_patterns").write_text(
            "# mine\nIvanov\nre:LX\\d{4}[A-Z0-9]+\n", encoding="utf-8")
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_REPO_DIR", None)
        else:
            os.environ["SCHOLION_REPO_DIR"] = self._old
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_listed_name_is_removed(self):
        r = redact.redact("patient Ivanov, IVANOV again")
        self.assertNotIn("vanov", r["text"], "the match must be case-insensitive: a surname "
                                             "printed in capitals on a form is the same surname")
        self.assertIn("your own patterns", r["replaced"])

    def test_the_report_never_prints_the_patterns_themselves(self):
        """The report is shown; the patterns are somebody's name and sample number."""
        r = redact.redact("patient Ivanov")
        self.assertNotIn("Ivanov", str(r["replaced"]))
        self.assertNotIn("Ivanov", r.get("warning", ""))

    def test_a_regular_expression_pattern_works(self):
        r = redact.redact("sample LX7742001QF")
        self.assertNotIn("LX7742001QF", r["text"])

    def test_a_broken_pattern_does_not_take_the_run_with_it(self):
        (self.dir / ".personal_patterns").write_text("re:[unclosed\nIvanov\n", encoding="utf-8")
        r = redact.redact("patient Ivanov")
        self.assertNotIn("Ivanov", r["text"],
                         "one unparseable line must not stop the others from being applied")


class TestTheIssueTemplatesSayIt(unittest.TestCase):
    """The templates are the only place most people will read this rule.

    A tool nobody is told about protects nobody, and the moment a person is about
    to paste a medical record is the moment they are looking at the issue form.
    """

    DIR = support.ROOT / ".github" / "ISSUE_TEMPLATE"

    @unittest.skipIf(not (support.ROOT / ".github").is_dir(),
                     ".github is not part of this build")
    def test_every_template_warns_before_the_first_paste_box(self):
        templates = sorted(self.DIR.glob("*.md"))
        self.assertTrue(templates, "there are no issue templates at all")
        for p in templates:
            with self.subTest(template=p.name):
                text = p.read_text(encoding="utf-8")
                head = text.split("```")[0]
                self.assertTrue(any(w in head.lower() for w in ("redact", "do not attach")),
                                "the warning must stand ABOVE the first code block — a caution "
                                "printed after the box people paste into is a caution nobody "
                                "reads")

    @unittest.skipIf(not (support.ROOT / ".github").is_dir(),
                     ".github is not part of this build")
    def test_blank_issues_are_off(self):
        cfg = (self.DIR / "config.yml").read_text(encoding="utf-8")
        self.assertIn("blank_issues_enabled: false", cfg,
                      "a blank issue is a template with no warning on it")


if __name__ == "__main__":
    unittest.main()
