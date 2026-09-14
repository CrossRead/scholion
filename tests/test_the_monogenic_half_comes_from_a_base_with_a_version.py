"""The monogenic half of a system panel comes from a base with a version.

Task 173: a panel of «risk alleles» written by one clinician put a gene with a
Definitive gene↔disease assertion and a gene with no assertion anywhere in the
world in one table, with the same wording, and said «heterozygous» about five
recessive genes without saying they were recessive. The fix is not a better
list — it is a list that arrives from GenCC with its classification, its mode
of inheritance, its submitter, its date and the export's own date beside every
row, so that a reader can see where each line came from and how old it is.

What is held here, on a synthetic export that never touches the network:

* the filter keeps the genes whose disease names belong to the system and
  drops the rest;
* two submitters disagreeing about one gene are BOTH kept — a disagreement is
  shown, never averaged — and a `Limited` row is kept too, because which
  classifications may be printed as a finding is the engine's decision;
* the mode of inheritance is normalised into the alphabet the engine reads
  while GenCC's own spelling stays beside it;
* every row is marked `monogenic`, so it can never be printed in the shape of a
  polygenic score;
* the file records when it was pulled and when the export it came from was
  refreshed, and the freshness check reads those dates;
* `SCHOLION_OFFLINE=1` stops the tool before a socket is opened, and `--list`
  downloads nothing;
* the filter file is keyed by the radar's own laboratory domains (eleven until
  13.09.2026, twelve since «Heart and vessels» was added), and every entry is
  composed from a named source — until 13.09.2026 only the thyroid was, and
  every other entry said why it was empty rather than looking like a system
  nobody asked about.
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from scholion import core

sys.path.insert(0, str(support.ROOT / "src" / "tools"))
import fetch_gencc  # noqa: E402

KNOWLEDGE = Path(core.__file__).resolve().parent / "knowledge"
FILTER = KNOWLEDGE / "system_disease_terms.json"
SHIPPED = KNOWLEDGE / "gencc_gene_disease.json"
MOI_ALPHABET = {"AD", "AR", "XL", "XLR", "XLD", "MT", "SD", "unknown"}
VALID_TIERS = {"guideline_verbatim", "guideline_compiled", "guideline_mixed",
               "primary_literature", "curated_reference", "derived"}

#: The header of the real export (new format, verified 12.09.2026). Rows are
#: built by column name so a test row cannot drift from the layout.
HEADER = ("sgc_id version_number gene_curie gene_symbol disease_curie disease_title "
          "disease_original_curie disease_original_title classification_curie "
          "classification_title moi_curie moi_title submitter_curie submitter_title "
          "submitted_as_hgnc_id submitted_as_hgnc_symbol submitted_as_disease_id "
          "submitted_as_disease_name submitted_as_moi_id submitted_as_moi_name "
          "submitted_as_submitter_id submitted_as_submitter_name "
          "submitted_as_classification_id submitted_as_classification_name "
          "submitted_as_date submitted_as_public_report_url submitted_as_notes "
          "submitted_as_pmids submitted_as_assertion_criteria_url "
          "submitted_as_submission_id submitted_run_date").split()


def _row(**kw) -> str:
    cells = {h: "" for h in HEADER}
    cells.update(kw)
    return "\t".join(cells[h] for h in HEADER)


#: Three genes. GENEA: two submitters disagree (Definitive against Limited) about
#: one dominant thyroid disease, the second row spelling its inheritance with no
#: curie. GENEB: recessive, dyshormonogenesis. GENEC: a heart disease, outside
#: the thyroid filter.
SYNTHETIC = "\n".join([
    "\t".join(HEADER),
    _row(sgc_id="SGC-000001", version_number="1", gene_curie="HGNC:90001", gene_symbol="GENEA",
         disease_curie="MONDO:0900001", disease_title="congenital hypothyroidism",
         disease_original_title="HYPOTHYROIDISM, CONGENITAL, NONGOITROUS, 99",
         classification_title="Definitive", moi_curie="HP:0000006", moi_title="Autosomal dominant",
         submitter_title="Submitter One", submitted_as_date="2024-05-01 10:00:00"),
    _row(sgc_id="SGC-000002", version_number="2", gene_curie="HGNC:90001", gene_symbol="GENEA",
         disease_curie="MONDO:0900001", disease_title="congenital hypothyroidism",
         classification_title="Limited", moi_curie="", moi_title="Autosomal dominant inheritance",
         submitter_title="Submitter Two", submitted_as_date="2023-01-15 09:30:00"),
    _row(sgc_id="SGC-000003", version_number="1", gene_curie="HGNC:90002", gene_symbol="GENEB",
         disease_curie="MONDO:0900002", disease_title="thyroid dyshormonogenesis 9",
         classification_title="Strong", moi_curie="HP:0000007", moi_title="Autosomal recessive",
         submitter_title="Submitter One", submitted_as_date="2022-11-30 12:00:00"),
    _row(sgc_id="SGC-000004", version_number="1", gene_curie="HGNC:90003", gene_symbol="GENEC",
         disease_curie="MONDO:0900003", disease_title="dilated cardiomyopathy 99",
         classification_title="Definitive", moi_curie="HP:0000006", moi_title="Autosomal dominant",
         submitter_title="Submitter One", submitted_as_date="2021-02-02 08:00:00"),
    "",
])


def _radar_keys() -> list:
    """The radar domains that carry a genetic half — the laboratory systems
    (eleven until 13.09.2026, twelve since). `knowledge/radar_domains.json`
    names one more, fitness, built from wearables and flagged
    `genetic_half: false`; a gene↔disease filter for it would be a filter for
    nothing, so it is not a key here. The engine's constant is the fallback
    for a tree where the file has not landed yet."""
    p = KNOWLEDGE / "radar_domains.json"
    if p.exists():
        doms = (json.loads(p.read_text(encoding="utf-8")).get("domains") or [])
        keys = [x["key"] for x in doms
                if isinstance(x, dict) and x.get("genetic_half", x.get("source") == "labs")]
        if keys:
            return keys
    import importlib
    mod = importlib.import_module("scholion.engine.lifestyle")
    return [k for k, _ in mod._RADAR_DOMAINS]


def _quiet(fn, *args, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(*args, **kw)
    return rc, buf.getvalue()


class _Tmp(unittest.TestCase):
    def setUp(self):
        # Resolved: on macOS TMPDIR is a symlink and paths compared later differ.
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.tsv = self.tmp / "gencc-synthetic.tsv"
        self.tsv.write_text(SYNTHETIC, encoding="utf-8")
        self.out = self.tmp / "gencc_gene_disease.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _compose(self, *extra):
        rc, text = _quiet(fetch_gencc.main, ["--from", str(self.tsv), "--out", str(self.out),
                                             "--export-date", "2026-09-06", *extra])
        self.assertEqual(rc, 0, text)
        return json.loads(self.out.read_text(encoding="utf-8"))


class TestTheFilterComposesFromTheBase(_Tmp):

    def test_the_thyroid_filter_keeps_its_genes_and_the_heart_gene_lands_on_the_heart(self):
        doc = self._compose()
        # Every laboratory system has a filter since 13.09.2026, so the systems
        # that appear are the ones the synthetic rows matched — and none of them
        # may appear with zero genes: an empty match is not a system.
        self.assertIn("thyroid", doc["systems"])
        for key, block in doc["systems"].items():
            self.assertGreater(block["gene_count"], 0, f"{key}: a system with zero genes was written")
        # The synthetic «heart gene» (dilated cardiomyopathy) matched no filter
        # while the radar had no heart; since «Heart and vessels» was added
        # later on 13.09.2026 it lands there — and only there.
        self.assertIn("cardio", doc["systems"])
        self.assertEqual(["GENEC"], sorted(doc["systems"]["cardio"]["genes"]))
        for key, block in doc["systems"].items():
            if key != "cardio":
                self.assertNotIn("GENEC", block["genes"], f"{key}: the heart gene matched a filter")
        genes = doc["systems"]["thyroid"]["genes"]
        self.assertEqual(sorted(genes), ["GENEA", "GENEB"])
        self.assertNotIn("GENEC", genes)
        self.assertEqual(doc["systems"]["thyroid"]["gene_count"], 2)
        self.assertEqual(genes["GENEA"]["hgnc_id"], "HGNC:90001")

    def test_two_submitters_disagreeing_are_both_kept_and_limited_survives(self):
        doc = self._compose()
        rows = doc["systems"]["thyroid"]["genes"]["GENEA"]["submissions"]
        self.assertEqual(len(rows), 2, "a disagreement is shown, never averaged")
        self.assertEqual(sorted(r["classification"] for r in rows), ["Definitive", "Limited"])
        self.assertEqual(sorted(r["submitter"] for r in rows), ["Submitter One", "Submitter Two"])
        limited = next(r for r in rows if r["classification"] == "Limited")
        # The loader keeps it; the engine decides that it is not a finding.
        self.assertEqual(limited["mode"], "monogenic")
        self.assertEqual(limited["curated_on"], "2023-01-15 09:30:00")
        self.assertEqual(limited["submission_id"], "SGC-000002")
        self.assertEqual(limited["submission_version"], "2")

    def test_inheritance_is_normalised_and_the_original_spelling_stays(self):
        doc = self._compose()
        genes = doc["systems"]["thyroid"]["genes"]
        b = genes["GENEB"]["submissions"][0]
        self.assertEqual(b["moi_code"], "AR")
        self.assertEqual(b["moi"], "Autosomal recessive")
        a = genes["GENEA"]["submissions"]
        # One row carries the HPO curie, the other only a title — both land on AD.
        self.assertEqual({r["moi_code"] for r in a}, {"AD"})
        self.assertIn("Autosomal dominant inheritance", [r["moi"] for r in a])
        self.assertEqual(fetch_gencc.normalise_moi("", "X-linked recessive"), "XLR")
        self.assertEqual(fetch_gencc.normalise_moi("", "X-linked dominant"), "XLD")
        self.assertEqual(fetch_gencc.normalise_moi("HP:0001417", ""), "XL")
        self.assertEqual(fetch_gencc.normalise_moi("", "Mitochondrial"), "MT")
        self.assertEqual(fetch_gencc.normalise_moi("", "Semidominant"), "SD")
        self.assertEqual(fetch_gencc.normalise_moi("", "Y-linked"), "unknown",
                         "a mode outside the alphabet is unknown, not guessed")

    def test_every_row_is_monogenic_and_says_what_it_matched(self):
        doc = self._compose()
        for g in doc["systems"]["thyroid"]["genes"].values():
            for r in g["submissions"]:
                self.assertEqual(r["mode"], "monogenic")
                self.assertIn(r["matched"], ("hypothyroidism", "dyshormonogenesis",
                                             "thyroid dyshormonogenesis"))
                self.assertEqual(r["gencc_version_or_date"], "2026-09-06")

    def test_meta_carries_the_dates_the_licence_and_the_filter_version(self):
        doc = self._compose("--etag", '"abc"')
        m = doc["_meta"]
        self.assertEqual(m["downloaded"], _dt.date.today().isoformat())
        self.assertEqual(m["export_last_modified"], "2026-09-06")
        self.assertEqual(m["export_etag"], '"abc"')
        self.assertEqual(m["export_rows_read"], 4)
        filt = json.loads(FILTER.read_text(encoding="utf-8"))
        self.assertEqual(m["filter_version"], filt["_meta"]["version"])
        self.assertEqual(m["filter_file"], FILTER.name)
        self.assertIn("CC0 1.0", m["license"])
        self.assertEqual(m["mode"], "monogenic")
        self.assertIn(m["source_tier"], VALID_TIERS)
        self.assertTrue(m.get("source_tier_note"))
        self.assertEqual(m["source_url"], fetch_gencc.URL)
        self.assertTrue(fetch_gencc.URL.startswith("https://thegencc.org/"))

    def test_an_export_missing_a_column_is_refused_by_name(self):
        bad = self.tmp / "bad.tsv"
        header = [h for h in HEADER if h != "moi_title"]
        bad.write_text("\t".join(header) + "\n" + "\t".join(["x"] * len(header)) + "\n",
                       encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            _quiet(fetch_gencc.main, ["--from", str(bad), "--out", str(self.out)])
        self.assertIn("moi_title", str(cm.exception))
        self.assertFalse(self.out.exists())

    def test_a_filter_with_terms_but_no_source_is_refused(self):
        filt = {"_meta": {"version": "t"}, "systems": {"thyroid": {"terms": ["hypothyroidism"],
                                                                    "source": None}}}
        p = self.tmp / "filter.json"
        p.write_text(json.dumps(filt), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            _quiet(fetch_gencc.main, ["--from", str(self.tsv), "--out", str(self.out),
                                      "--filter", str(p)])
        self.assertIn("source", str(cm.exception))
        self.assertFalse(self.out.exists())

    def test_a_mondo_id_in_the_filter_catches_a_disease_no_substring_would(self):
        filt = {"_meta": {"version": "t"},
                "systems": {"thyroid": {"terms": [], "mondo_ids": ["MONDO:0900003"],
                                        "source": "the test"}}}
        p = self.tmp / "filter.json"
        p.write_text(json.dumps(filt), encoding="utf-8")
        doc = self._compose("--filter", str(p))
        self.assertEqual(list(doc["systems"]["thyroid"]["genes"]), ["GENEC"])
        self.assertEqual(doc["systems"]["thyroid"]["genes"]["GENEC"]["submissions"][0]["matched"],
                         "MONDO:0900003")


class TestNothingIsFetchedUnlessAsked(_Tmp):

    def _no_network(self):
        boom = mock.Mock(side_effect=AssertionError("a socket was opened"))
        return (mock.patch.object(fetch_gencc.urllib.request, "urlopen", boom),
                mock.patch.object(fetch_gencc.urllib.request.OpenerDirector, "open", boom))

    def test_offline_refuses_before_any_request(self):
        # SCHOLION_OFFLINE=1 is how the suite runs; make it explicit here anyway.
        p1, p2 = self._no_network()
        with mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": "1"}), p1, p2:
            rc, text = _quiet(fetch_gencc.main, ["--out", str(self.out)])
        self.assertEqual(rc, 1)
        self.assertIn("SCHOLION_OFFLINE", text)
        self.assertFalse(self.out.exists())

    def test_offline_refuses_list_too_because_a_head_is_a_request(self):
        p1, p2 = self._no_network()
        with mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": "1"}), p1, p2:
            rc, _ = _quiet(fetch_gencc.main, ["--list", "--out", str(self.out)])
        self.assertEqual(rc, 1)

    def test_from_and_age_need_no_network(self):
        p1, p2 = self._no_network()
        with mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": "1"}), p1, p2:
            self._compose()
            rc, _ = _quiet(fetch_gencc.main, ["--age", "--out", str(self.out)])
        self.assertEqual(rc, 0)

    def test_list_asks_with_head_and_downloads_nothing(self):
        head = mock.Mock(return_value={"status": 200, "size": 25_000_000,
                                       "last_modified": "Sun, 06 Sep 2026 06:01:23 GMT",
                                       "etag": '"x"', "content_type": "text/tab-separated-values"})
        get = mock.Mock(side_effect=AssertionError("--list must not download"))
        with mock.patch.dict("os.environ", {"SCHOLION_OFFLINE": ""}), \
                mock.patch.object(fetch_gencc, "_head", head), \
                mock.patch.object(fetch_gencc, "_get", get):
            rc, text = _quiet(fetch_gencc.main, ["--list", "--out", str(self.out)])
        self.assertEqual(rc, 0, text)
        self.assertEqual(head.call_count, 1)
        self.assertEqual(get.call_count, 0)
        self.assertIn("23.8 MB", text)
        self.assertFalse(self.out.exists())

    def test_the_address_is_checked_and_a_redirect_is_refused(self):
        with self.assertRaises(SystemExit):
            fetch_gencc._checked("https://search.thegencc.org/download/x")
        h = fetch_gencc._NoRedirect()
        self.assertIsNone(h.redirect_request(None, None, 301, "", {}, "https://elsewhere/"))


class TestFreshnessIsReadFromTheFile(_Tmp):

    def test_age_reads_both_dates_and_judges_by_the_export(self):
        self._compose()
        rep = fetch_gencc.age(self.out, today=_dt.date(2026, 12, 15))
        self.assertTrue(rep["present"])
        self.assertEqual(rep["export_last_modified"], "2026-09-06")
        self.assertEqual(rep["export_last_modified_days"], 100)
        self.assertEqual(rep["downloaded"], _dt.date.today().isoformat())
        rc_ok, _ = _quiet(fetch_gencc._print_age, rep, 120)
        rc_old, text = _quiet(fetch_gencc._print_age, rep, 30)
        self.assertEqual((rc_ok, rc_old), (0, 1))
        self.assertIn("older than 30 days", text)

    def test_no_file_means_the_half_is_authored_by_hand_and_exits_one(self):
        rc, text = _quiet(fetch_gencc.main, ["--age", "--out", str(self.tmp / "absent.json")])
        self.assertEqual(rc, 1)
        self.assertIn("by hand", text)

    def test_the_named_check_is_the_same_door(self):
        import check_gencc_freshness
        self._compose()
        rc, _ = _quiet(check_gencc_freshness.main, ["--out", str(self.out)])
        self.assertEqual(rc, 0)


class TestTheFilterFileIsKeyedByTheRadar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.filt = json.loads(FILTER.read_text(encoding="utf-8"))
        cls.keys = _radar_keys()

    def test_every_system_is_a_radar_domain_and_every_domain_is_present(self):
        # Eleven until 13.09.2026; twelve since «Heart and vessels» (cardio) was
        # added to the radar by the owner's decision of that day (task 179).
        self.assertEqual(len(self.keys), 12)
        self.assertIn("cardio", self.keys)
        self.assertEqual(sorted(self.filt["systems"]), sorted(self.keys))

    def test_every_laboratory_system_is_composed_from_a_named_source(self):
        """Since 13.09.2026 (owner's decision, task 178) every system carries a
        filter: terms, an `exclude` list, and a source that names the report the
        terms were tuned in. The thyroid keeps its report-173 terms; ten point
        at report 178; «Heart and vessels», added later the same day, points at
        report 179. No system says `why_empty` any more — an empty half with a
        reason was the state of the day before."""
        report = {"thyroid": "173", "cardio": "179"}
        for key, spec in self.filt["systems"].items():
            with self.subTest(system=key):
                self.assertTrue(spec["terms"], "a system with no terms is a system nobody composed")
                self.assertTrue(spec["source"])
                self.assertIn("PanelApp", spec["source"])
                self.assertIn(report.get(key, "178"), spec["source"])
                self.assertIsInstance(spec.get("exclude", []), list)
                self.assertFalse(spec.get("why_empty"), "a composed system carries no why_empty")
        thy = self.filt["systems"]["thyroid"]
        for t in ("hypothyroidism", "hyperthyroidism", "athyreosis", "thyroid hypoplasia",
                  "thyroid hormone metabolism", "thyroid cancer"):
            self.assertIn(t, thy["terms"])
        self.assertTrue(any("dyshormonogenesis" in t for t in thy["terms"]))
        # The vetoes the report justifies by name.
        self.assertIn("homocystinuria", self.filt["systems"]["renal"]["exclude"])
        self.assertIn("goutieres", self.filt["systems"]["renal"]["exclude"])
        self.assertIn("diabetes insipidus", self.filt["systems"]["glucose"]["exclude"])

    def test_the_filter_declares_its_version_and_tier(self):
        m = self.filt["_meta"]
        self.assertTrue(m.get("version"))
        self.assertEqual(m.get("source_tier"), "curated_reference")
        self.assertEqual(fetch_gencc.load_filter(FILTER)["_meta"]["version"], m["version"])
        self.assertEqual(sorted(fetch_gencc.active_systems(self.filt)), sorted(self.keys),
                         "every laboratory system is active since 13.09.2026")

    def test_an_exclude_substring_vetoes_a_row_whichever_term_it_matched(self):
        """`cystinuria` is inside `homocystinuria` and `gout` inside
        `Aicardi-Goutieres`; no positive term separates them, so the filter
        carries vetoes and the tool honours them before any term is tried."""
        spec = {"terms": ["gout", "cystinuria"], "ids": set(), "source": "x",
                "exclude": ["goutieres", "homocystinuria"]}
        self.assertEqual("gout", fetch_gencc.match(spec, {"disease": "Gout, early-onset", "disease_original": ""}))
        self.assertIsNone(fetch_gencc.match(spec, {"disease": "Aicardi-Goutieres syndrome 1", "disease_original": ""}))
        self.assertEqual("cystinuria", fetch_gencc.match(spec, {"disease": "cystinuria type A", "disease_original": ""}))
        self.assertIsNone(fetch_gencc.match(spec, {"disease": "classic homocystinuria", "disease_original": ""}))
        self.assertIsNone(fetch_gencc.match(spec, {"disease": "gout", "disease_original": "AICARDI-GOUTIERES"}),
                          "the veto reads the original title too")
        loaded = fetch_gencc.active_systems({"systems": {"renal": {
            "terms": ["Gout"], "exclude": [" Goutieres "], "source": "x"}}})
        self.assertEqual(["goutieres"], loaded["renal"]["exclude"])


@unittest.skipUnless(SHIPPED.exists(), "no shipped GenCC file in this build")
class TestTheShippedFileValidates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(SHIPPED.read_text(encoding="utf-8"))
        cls.keys = set(_radar_keys())

    def test_meta(self):
        m = self.doc["_meta"]
        for k in ("downloaded", "export_last_modified", "filter_version", "license",
                  "source_url", "source_tier", "export_rows_read"):
            self.assertTrue(m.get(k), f"_meta.{k} missing")
        _dt.date.fromisoformat(m["downloaded"])
        _dt.date.fromisoformat(m["export_last_modified"])
        self.assertIn("CC0 1.0", m["license"])
        self.assertIn(m["source_tier"], VALID_TIERS)
        self.assertEqual(m["mode"], "monogenic")
        filt = json.loads(FILTER.read_text(encoding="utf-8"))
        self.assertEqual(m["filter_version"], filt["_meta"]["version"],
                         "the shipped file was composed with a filter that has since changed")

    def test_rows(self):
        n = 0
        for key, block in self.doc["systems"].items():
            self.assertIn(key, self.keys)
            self.assertEqual(block["gene_count"], len(block["genes"]))
            self.assertGreater(block["gene_count"], 0)
            for gene, entry in block["genes"].items():
                self.assertTrue(entry["submissions"], f"{gene}: no submissions")
                for r in entry["submissions"]:
                    n += 1
                    for k in ("disease", "classification", "moi", "moi_code", "submitter",
                              "curated_on", "gencc_version_or_date", "mode", "matched"):
                        self.assertIn(k, r, f"{gene}: row without {k}")
                    self.assertIn(r["moi_code"], MOI_ALPHABET)
                    self.assertEqual(r["mode"], "monogenic")
                    self.assertTrue(r["classification"])
        self.assertGreater(n, 0)

    def test_the_seven_genes_of_the_report_read_as_the_report_said(self):
        """Report 173 checked these on the GenCC site on 12.09.2026. DIO2 had no
        submission at all; TG carried a Limited row for thyroid cancer; TPO and
        SECISBP2 were recessive. If the base has moved on, this fails and the
        report is the thing to re-read, not the test to loosen."""
        genes = self.doc["systems"].get("thyroid", {}).get("genes", {})
        if not genes:
            self.skipTest("the shipped file carries no thyroid system")
        for g in ("TSHR", "DUOX2", "TPO", "SECISBP2", "TG", "DIO1"):
            self.assertIn(g, genes)
        self.assertNotIn("DIO2", genes)
        self.assertEqual({r["moi_code"] for r in genes["TPO"]["submissions"]}, {"AR"})
        self.assertEqual({r["moi_code"] for r in genes["SECISBP2"]["submissions"]}, {"AR"})
        tg = genes["TG"]["submissions"]
        self.assertTrue(any(r["classification"] == "Limited" and "cancer" in r["disease"] for r in tg))
        self.assertTrue(any(r["classification"] == "Strong" and r["moi_code"] == "AR" for r in tg))
        self.assertEqual({r["moi_code"] for r in genes["TSHR"]["submissions"]}, {"AD", "AR"})


if __name__ == "__main__":
    unittest.main()
