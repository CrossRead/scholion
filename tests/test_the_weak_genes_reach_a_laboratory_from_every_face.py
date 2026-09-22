"""The genes a «nothing found» cannot rest on reach a laboratory from every face.

Task 5. Since 0.4.8 the coverage table could hand its weak genes over as a BED —
worst gene first, each interval carrying its percentage, the track line saying
these are gene loci with a margin and not coding sequence. No door reached it:
the command printed nothing, the page showed nothing, the assistant's tool could
not ask, and the release notes sent a person to do it «by hand».

The same release also found where the refusals pointed. Three sentences told a
person to run `bash src/ingest/qc_callability.sh` — a script the package does
not carry — while `scholion coverage` has measured the same table since the
measurement moved into the package. A refusal that names a file the reader does
not have is the defect the ClinVar button was fixed for on 13.09; this is the
same one in three more places.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import support
from scholion import core, ouroboros_tools
from scholion.i18n import en, ru

HEAD = ("gene\tpanel\tchrom\tlength_bp\tmean_depth\trel_to_panel\tpct_1x\tpct_10x"
        "\tpct_20x\tpct_30x\tstart\tend")
ROWS = [
    "BRCA1\tACMG\tchr17\t300000\t31.0\t1.00\t99.0\t99.5\t95.0\t80.0\t43044000\t43126000",
    "PMS2\tACMG\tchr7\t300000\t12.0\t0.40\t90.0\t61.2\t40.0\t20.0\t5970000\t6010000",
    "CYP2D6\tPGX\tchr22\t300000\t9.0\t0.30\t80.0\t44.0\t30.0\t10.0\t42120000\t42135000",
]
PATHLIKE = re.compile(r"src/ingest|\.sh\b|site-packages")


class _Profile(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="weakbed-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.profile = self.tmp / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, self.profile)
        (self.profile / "callability.tsv").write_text("\n".join([HEAD] + ROWS) + "\n",
                                                     encoding="utf-8")


class TestTheCommand(_Profile):

    def test_the_output_is_the_bed_itself(self):
        code, out, err = support.run(["limits", "--bed"], self.profile)
        self.assertEqual(0, code, err)
        lines = out.strip().split("\n")
        self.assertTrue(lines[0].startswith("track name=scholion_weak"), lines[0])
        genes = [ln.split("\t")[3] for ln in lines[1:]]
        self.assertEqual(["CYP2D6", "PMS2"], genes, "worst gene first, the well-read one absent")

    def test_a_panel_narrows_it(self):
        code, out, _ = support.run(["limits", "--bed", "--panel", "ACMG"], self.profile)
        self.assertEqual(0, code)
        self.assertEqual(["PMS2"], [ln.split("\t")[3] for ln in out.strip().split("\n")[1:]])

    def test_out_writes_the_file_and_says_so(self):
        target = self.tmp / "for_the_lab.bed"
        code, out, _ = support.run(["limits", "--bed", "--out", str(target)], self.profile)
        self.assertEqual(0, code)
        self.assertTrue(target.read_text(encoding="utf-8").startswith("track name="))
        self.assertIn(str(target), out)

    def test_a_refusal_is_not_a_file_and_the_code_says_so(self):
        (self.profile / "callability.tsv").unlink()
        code, out, _ = support.run(["limits", "--bed"], self.profile)
        self.assertEqual(1, code, "a script redirecting this into a file must be able to tell")
        self.assertNotIn("track name=", out)
        self.assertIn("scholion coverage", out)

    def test_json_carries_the_structure(self):
        r = support.run_json(["limits", "--bed"], self.profile)
        self.assertEqual(2, r["regions"])


class TestTheAssistantsTool(_Profile):

    def test_the_tool_can_ask_for_it(self):
        old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        self.addCleanup(lambda: os.environ.update({"SCHOLION_PROFILE_DIR": old})
                        if old is not None else os.environ.pop("SCHOLION_PROFILE_DIR", None))
        core.reset_cache()
        tool = next(t for t in ouroboros_tools.get_tools() if t.name == "sch_limits")
        self.assertIn("bed", tool.schema["parameters"]["properties"])
        text = ouroboros_tools._h_limits(None, bed=True, panel="PGX")
        self.assertTrue(text.startswith("track name="), text[:80])
        self.assertIn("CYP2D6", text)
        self.assertNotIn("PMS2", text)


class TestNoRefusalNamesAScriptThePackageLacks(unittest.TestCase):

    KEYS = ("limits.bed_never_computed", "limits.bed_no_coordinates", "limits.coverage_closes")

    def test_the_sentences_name_the_command(self):
        for cat, lang in ((en.MESSAGES, "en"), (ru.MESSAGES, "ru")):
            for k in self.KEYS:
                with self.subTest(lang=lang, key=k):
                    self.assertNotRegex(cat[k], PATHLIKE)
                    self.assertIn("scholion coverage", cat[k])

    def test_the_source_list_names_the_command(self):
        from scholion import sources
        for key, src in sources.SOURCES.items() if hasattr(sources, "SOURCES") else ():
            cmd = src.get("command") or ""
            with self.subTest(source=key):
                self.assertNotIn("qc_callability", cmd)


if __name__ == "__main__":
    unittest.main()


class TestTheServerDoorHandsOverAFile(unittest.TestCase):
    """The page's door: JSON by default, and with `?download=1` the file itself,
    named for the person who will receive it — or a sentence, never a file,
    when there is nothing a laboratory could read."""

    @classmethod
    def setUpClass(cls):
        import os, shutil, socket, tempfile, threading, time
        from pathlib import Path
        from scholion import server
        cls._tmp = tempfile.mkdtemp(prefix="scholion-bed-")
        cls._profile = Path(cls._tmp) / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, cls._profile)
        cls._was = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(cls._profile)
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0)); cls.port = s.getsockname()[1]
        cls.srv = server._Server(("127.0.0.1", cls.port), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        for _ in range(50):
            try:
                urllib.request.urlopen(cls.base + "/api/ping", timeout=2).read(); break
            except Exception:
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        import os
        cls.srv.shutdown(); cls.srv.server_close()
        if cls._was is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = cls._was

    def test_json_by_default_and_a_file_on_request(self):
        import json
        from scholion import limits as _lim
        bed = "chr1\t100\t200\tGENEA\t12.5\n"
        with mock.patch.object(_lim, "weak_regions_bed", lambda panels=None: {"ok": True, "bed": bed, "regions": 1, "genes": ["GENEA"]}):
            r = urllib.request.urlopen(self.base + "/api/limits/bed", timeout=5)
            self.assertEqual(1, json.loads(r.read())["regions"])
            r = urllib.request.urlopen(self.base + "/api/limits/bed?download=1&panel=ACMG", timeout=5)
            self.assertIn("attachment", r.headers.get("Content-Disposition", ""))
            self.assertIn("scholion_weak_genes.bed", r.headers.get("Content-Disposition", ""))
            self.assertEqual(bed, r.read().decode("utf-8"))

    def test_a_refusal_is_json_even_when_a_file_was_asked_for(self):
        import json
        from scholion import limits as _lim
        with mock.patch.object(_lim, "weak_regions_bed", lambda panels=None: {"ok": False, "note": "never computed"}):
            r = urllib.request.urlopen(self.base + "/api/limits/bed?download=1", timeout=5)
            self.assertNotIn("attachment", r.headers.get("Content-Disposition", "") or "")
            self.assertFalse(json.loads(r.read())["ok"])
