"""The demo genome is a published reference material, and the tool proves it.

The showcase needs a real genome or the strongest layer of the product goes
undemonstrated. It must not need somebody's private one. The Genome in a Bottle
samples are made and consented to be published — and the trio this offers is
consented for commercial redistribution — so the demo can be real without the
question of whose data it is ever arising.

Three things are checked, and the second is the reason this file exists.

**Every offered sample carries the sentence that justifies offering it.** A
source without a consent note is a source somebody re-researches later, after
the file is already on disk.

**No file name is written down.** The benchmark is versioned and the release
directory moves; a typed name turns into a 404 whose message is about the wrong
thing. The tool reads the listing and refuses when the pick is not unambiguous —
and that refusal is exercised here, because the author of this tool could not
reach the listing to see its shape and a guess that nobody tested is not better
than no guess.

**The offline switch stops it before the network.** It is the only thing in the
tree that downloads on purpose, so it is the one place where that promise can be
broken quietly.
"""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

import support

ROOT = support.ROOT
TOOL = ROOT / "src" / "tools" / "fetch_demo_genome.py"


def _mod():
    spec = importlib.util.spec_from_file_location("_t_demo_genome", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestWhatIsOffered(unittest.TestCase):

    def setUp(self):
        if not TOOL.exists():
            self.skipTest("the tool is not part of this build")
        self.m = _mod()

    def test_every_sample_says_who_it_is_and_why_it_may_be_shown(self):
        for name, spec in self.m.SAMPLES.items():
            with self.subTest(sample=name):
                for field in ("path", "build", "who", "consent"):
                    self.assertTrue(spec.get(field), f"«{field}» is empty")
                self.assertGreater(len(spec["consent"]), 40,
                                   "a consent note this short is a label, not a reason")

    def test_the_default_is_one_of_them(self):
        self.assertIn(self.m.DEFAULT, self.m.SAMPLES)

    def test_nothing_is_fetched_from_anywhere_but_the_publisher(self):
        source = TOOL.read_text(encoding="utf-8")
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", source))
        self.assertEqual(hosts, {"ftp-trace.ncbi.nlm.nih.gov"},
                         "the tool reaches a host that is not the one publishing the data")

    def test_no_benchmark_file_name_is_written_down(self):
        """A typed name is a 404 about the wrong thing the day the release moves."""
        source = TOOL.read_text(encoding="utf-8")
        typed = [s for s in re.findall(r'"([^"]*\.vcf\.gz)"', source) if "\\" not in s]
        self.assertEqual(typed, [], f"a call set file name is hardcoded: {typed}")

    def test_it_carries_nothing_the_corpus_rule_forbids(self):
        """The internal reference test and this tool are opposite cases, and the
        rule that separates them has to hold in the file that comes closest to
        crossing it."""
        from test_the_reference_corpus_does_not_ship import offences
        self.assertEqual(offences(TOOL.read_text(encoding="utf-8")), [])


class TestThePickIsUnambiguousOrItStops(unittest.TestCase):

    def setUp(self):
        if not TOOL.exists():
            self.skipTest("the tool is not part of this build")
        self.m = _mod()

    def _listing(self, *names):
        return "".join(f'<a href="{n}">{n}</a>\n' for n in names)

    def test_one_call_set_and_its_index_are_found(self):
        vcf, tbi = self.m.pick(self._listing(
            "HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz",
            "HG005_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi",
            "HG005_GRCh38_1_22_v4.2.1_benchmark.bed"))
        self.assertTrue(vcf.endswith(".vcf.gz"))
        self.assertTrue(tbi.endswith(".tbi"))

    def test_the_index_is_not_mistaken_for_the_call_set(self):
        vcf, _ = self.m.pick(self._listing(
            "x_benchmark.vcf.gz", "x_benchmark.vcf.gz.tbi"))
        self.assertFalse(vcf.endswith(".tbi"))

    def test_two_candidates_stop_it_and_name_what_it_saw(self):
        with self.assertRaises(SystemExit) as cm:
            self.m.pick(self._listing("a_benchmark.vcf.gz", "b_benchmark.vcf.gz"))
        self.assertIn("a_benchmark.vcf.gz", str(cm.exception))

    def test_none_stops_it_too(self):
        with self.assertRaises(SystemExit):
            self.m.pick(self._listing("readme.txt"))


class TestTheOfflineSwitchIsObeyed(unittest.TestCase):

    def setUp(self):
        if not TOOL.exists():
            self.skipTest("the tool is not part of this build")
        self.m = _mod()

    def test_it_refuses_before_touching_the_network(self):
        import os
        def explode(*a, **k):                     # noqa: ANN001
            raise AssertionError("the network was touched with the switch on")
        real_get, real_env = self.m._get, os.environ.get("SCHOLION_OFFLINE")
        self.m._get = explode
        os.environ["SCHOLION_OFFLINE"] = "1"
        try:
            self.assertEqual(self.m.main(["--list"]), 1)
        finally:
            self.m._get = real_get
            if real_env is None:
                os.environ.pop("SCHOLION_OFFLINE", None)
            else:
                os.environ["SCHOLION_OFFLINE"] = real_env


class TestARemoteListingIsRemoteInput(unittest.TestCase):
    """A name that came off somebody else's server decides where a file is written.

    Found by reading the network hardening the other line of work was doing at
    the same time: the pattern that picks a call set out of the listing accepts
    any characters but a quote, so a listing could offer «../../x_benchmark.vcf.gz»
    and the download would land outside the folder the person named — or offer a
    whole address and send the request to a host nobody checked. Both are refused
    rather than cleaned up: a name this cannot use is a listing it does not
    understand, and guessing what was meant is how the wrong file arrives.
    """

    def setUp(self):
        if not TOOL.exists():
            self.skipTest("the tool is not part of this build")
        self.m = _mod()

    def _listing(self, *names):
        return "".join(f'<a href="{n}">{n}</a>\n' for n in names)

    def test_a_name_that_climbs_out_of_the_folder_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            self.m.pick(self._listing("../../away_benchmark.vcf.gz"))
        self.assertIn("plain file name", str(cm.exception))

    def test_a_name_that_is_an_address_is_refused(self):
        with self.assertRaises(SystemExit):
            self.m.pick(self._listing("https://elsewhere.example/x_benchmark.vcf.gz"))

    def test_an_address_outside_the_publisher_is_refused_before_the_request(self):
        with self.assertRaises(SystemExit) as cm:
            self.m._checked("https://elsewhere.example/file.vcf.gz")
        self.assertIn("not under", str(cm.exception))

    def test_a_redirect_is_never_followed(self):
        """The host is checked when the address is built; a 3xx would undo that."""
        h = self.m._NoRedirect()
        self.assertIsNone(h.redirect_request(None, None, 302, "Found", {},
                                             "https://elsewhere.example/x"))


if __name__ == "__main__":
    unittest.main()
