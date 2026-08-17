"""The inventory of outgoing requests is complete and honestly named.

The claim "nothing leaves" is verified not by the text of the README but by a
scan of the code — and the scan, like any negative result, must have coverage.
The test watches two things: that all the files were read rather than some of
them, and that the hosts that were found do not disappear from the report at the
next edit.
"""
import unittest
from pathlib import Path

from scholion import assistant, i18n

PKG = Path(assistant.__file__).resolve().parent
INGEST = PKG.parent / "ingest"


def _count(root: Path, suffixes) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for p in root.rglob("*")
               if p.suffix in suffixes and "__pycache__" not in p.parts and p.is_file())


class TestScanCoverage(unittest.TestCase):

    def setUp(self):
        self.a = assistant._audit_core()

    def test_every_core_file_was_read(self):
        self.assertEqual(self.a["files"], _count(PKG, {".py"}),
                         "the scan did not read every file of the core — the verdict does not "
                         "cover all the code")

    def test_data_preparation_is_read_if_present(self):
        """The genome build scripts download reference data. Not reading them and
        printing "where the application goes" at the same time means showing an
        incomplete list."""
        if not INGEST.is_dir():
            self.skipTest("the data-preparation directory is not part of this build")
        # The coverage line is compared through the catalogue, not through its wording:
        # the phrase is printed in the reader's language and a literal here would tie
        # the test to one of them.
        expected = i18n.t("assistant.scan_ingest", files=self.a["files"], lines=self.a["lines"])
        head = expected.split("{")[0].split(":")[0]
        self.assertTrue(any(s.startswith(head) for s in self.a["scanned"]),
                        f"the coverage does not name data preparation: {self.a['scanned']}")

    def test_the_coverage_is_named_in_words(self):
        self.assertTrue(self.a.get("scanned"), "the report does not say what exactly was read")


class TestHostInventory(unittest.TestCase):
    """The hosts that ARE in the code are obliged to be in the report.

    This is protection not against malice but against quiet divergence: a request
    was added — and the shop window promising "nothing leaves" became untrue,
    with nobody there to notice it.
    """

    def setUp(self):
        self.a = assistant._audit_core()

    def test_the_known_core_hosts_are_in_place(self):
        for host in ("rxnav.nlm.nih.gov", "rest.ensembl.org"):
            with self.subTest(host=host):
                self.assertIn(host, self.a["network_hosts"])

    def test_translators_are_not_hidden(self):
        """A translator is not a "public reference book": the name of the drug the
        person is asking about goes there. If it is in the code, it is obliged to
        be visible in the report under its own name."""
        translators = [h for h in self.a["network_hosts"] if "translate" in h]
        self.assertTrue(translators,
                        "the code contacts a translator and the report does not say so")

    def test_the_verdict_about_models_is_separate_from_the_hosts(self):
        """Two different statements: "there are no calls to language models" and
        "there are no network requests". The first is true, the second is not, and
        they must not be conflated."""
        self.assertEqual(self.a["verdict"], i18n.t("assistant.verdict_clean"))
        self.assertTrue(self.a["network_hosts"],
                        "the inventory is empty — either the scan is broken or the code has changed")


if __name__ == "__main__":
    unittest.main()
