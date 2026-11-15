"""Staged reference updates preserve data and separate source from claim review."""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, reference_updates as updates, variant_annotations as annotations
from tests.test_variant_annotation_reference import source_entry, source_feature


class RefreshReferenceKnowledge(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.repo = self.root / "person-a"
        (self.repo / "profile").mkdir(parents=True)
        environment = patch.dict(os.environ, {"SCHOLION_REPO_DIR": str(self.repo),
            "SCHOLION_PROFILE_DIR": str(self.repo / "profile"), "SCHOLION_OFFLINE": "1"})
        environment.start()
        self.addCleanup(environment.stop)
        location = patch.object(core, "_KNOWLEDGE_DIR", self.bundle)
        location.start()
        self.addCleanup(location.stop)
        core.reset_cache()
        annotations._load.cache_clear()
        annotations._indices.cache_clear()
        record = annotations.uniprot_record(source_entry(), source_feature(), "2026_04", "2026-11-14", {"HGNC:1"})
        self.base = {"_meta": {"schema": 1, "updated": "2026-11-14", "release": "2026_04"},
                     "genes": {"HGNC:1": {"symbol": "SYNTH", "aliases": []}},
                     "proteins": {"P00001": {"entry_version": 1, "sequence_version": 1}},
                     "record_fields": list(annotations.RECORD_FIELDS),
                     "records": [[record.get(key) for key in annotations.RECORD_FIELDS]],
                     "models": [{"model_id": "model-a", "gene": "SYNTH", "variant_ids": ["rs100"],
                         "checked_on": "2026-11-13", "sources": [{"pmid": "100"}], "genotypes": []}],
                     "supported_contexts": [{"context_id": "context-a", "variant_identifier": "rs100"}]}
        self.bundled = self.bundle / annotations.ANNOTATIONS
        self.bundled.write_text(json.dumps(self.base), encoding="utf-8")
        self.original = self.bundled.read_bytes()

    def response(self, description=None, *, total=1, release="2026_04", next_url=None, features=True):
        entry = {**source_entry(), "entryAudit": {"entryVersion": 2, "sequenceVersion": 1,
                                                  "lastAnnotationUpdateDate": "2026-11-04"}}
        feature = source_feature()
        if description is not None:
            feature["description"] = description
        if features:
            entry["features"] = [feature]
        headers = {"x-uniprot-release": release, "x-total-results": str(total)}
        if next_url:
            headers["link"] = '<' + next_url + '>; rel="next"'
        return {"data": {"results": [entry]}, "headers": headers}

    def test_changed_source_is_staged_and_requires_explicit_acceptance(self):
        preview = updates.preview(lambda url: self.response("Activity retained in the new experiment."))
        self.assertEqual(preview["status"], "review_ready")
        self.assertFalse(preview["accepted"])
        self.assertFalse((self.repo / "knowledge" / annotations.ANNOTATIONS).exists())
        self.assertEqual(self.bundled.read_bytes(), self.original)
        self.assertIn("model-a", preview["models_requiring_review"])
        result = updates.accept(preview["token"])
        self.assertTrue(result["accepted"])
        active = annotations.catalogue()
        self.assertEqual(next(annotations.records(active))["description"], "Activity retained in the new experiment.")
        self.assertTrue(active["models"][0]["review_required"])
        self.assertEqual(active["models"][0]["checked_on"], "2026-11-13")
        history = self.repo / "knowledge/.reference-updates/history" / (preview["token"] + ".json")
        self.assertEqual(json.loads(history.read_text(encoding="utf-8")), self.base)

    def test_unchanged_source_does_not_renew_primary_claim_review(self):
        preview = updates.preview(lambda url: self.response())
        self.assertEqual(preview["change_count"], 0)
        updates.accept(preview["token"])
        self.assertEqual(annotations.catalogue()["models"][0]["checked_on"], "2026-11-13")
        self.assertFalse(annotations.catalogue()["_meta"]["primary_studies_independently_reviewed"])

    def test_function_only_response_does_not_overwrite_variant_knowledge(self):
        with self.assertRaisesRegex(ValueError, "FUNCTION-only"):
            updates.preview(lambda url: self.response(features=False))
        self.assertEqual(updates.status()["job"]["status"], "failed")
        self.assertEqual(self.bundled.read_bytes(), self.original)

    def test_incomplete_pagination_and_offsite_next_link_are_refused(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            updates.preview(lambda url: self.response(total=2))
        with self.assertRaisesRegex(ValueError, "pagination"):
            updates.preview(lambda url: self.response(next_url="https://example.org/private"))
        self.assertEqual(self.bundled.read_bytes(), self.original)

    def test_offline_failure_keeps_the_previous_snapshot(self):
        with self.assertRaises(RuntimeError):
            updates.preview()
        self.assertEqual(self.bundled.read_bytes(), self.original)
        self.assertFalse((self.repo / "knowledge" / annotations.ANNOTATIONS).exists())

    def test_cancellation_between_source_pages_never_applies_partial_data(self):
        def fetch(url):
            updates.cancel()
            return self.response()
        result = updates.preview(fetch)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse((self.repo / "knowledge" / annotations.ANNOTATIONS).exists())

    def test_changed_base_rejects_a_stale_preview(self):
        preview = updates.preview(lambda url: self.response("A new source assertion."))
        changed = {**self.base, "_meta": {**self.base["_meta"], "updated": "2026-12-01"}}
        core.write_knowledge_local(annotations.ANNOTATIONS, changed)
        before = core.knowledge_path(annotations.ANNOTATIONS).read_bytes()
        with self.assertRaisesRegex(RuntimeError, "changed after"):
            updates.accept(preview["token"])
        self.assertEqual(core.knowledge_path(annotations.ANNOTATIONS).read_bytes(), before)

    def test_an_acceptance_write_failure_preserves_the_old_reference(self):
        preview = updates.preview(lambda url: self.response("Changed activity."))
        with patch.object(core, "write_knowledge_local", side_effect=OSError("synthetic write failure")):
            with self.assertRaises(OSError):
                updates.accept(preview["token"])
        self.assertEqual(self.bundled.read_bytes(), self.original)
        self.assertEqual(updates.status()["job"]["status"], "review_ready")

    def test_another_container_cannot_accept_this_preview(self):
        preview = updates.preview(lambda url: self.response())
        other = self.root / "person-b"
        (other / "profile").mkdir(parents=True)
        with patch.dict(os.environ, {"SCHOLION_REPO_DIR": str(other), "SCHOLION_PROFILE_DIR": str(other / "profile")}):
            core.reset_cache()
            with self.assertRaisesRegex(ValueError, "not ready"):
                updates.accept(preview["token"])
            self.assertFalse((other / "knowledge" / annotations.ANNOTATIONS).exists())

    def test_calendar_schedule_is_opt_in_and_clamps_month_end(self):
        with patch.object(updates, "preview") as run:
            self.assertEqual(updates.check_due(date(2027, 3, 1))["status"], "disabled")
            run.assert_not_called()
            updates.configure(True, 3)
            self.base["_meta"]["updated"] = "2026-11-30"
            self.bundled.write_text(json.dumps(self.base), encoding="utf-8")
            self.assertEqual(updates.check_due(date(2027, 2, 28))["status"], "current")
            run.assert_not_called()
            updates.check_due(date(2027, 3, 1))
            run.assert_called_once()

    def test_preview_tokens_are_not_paths(self):
        with self.assertRaises(ValueError):
            updates.diff("../../elsewhere")


class ReferenceErrorPrivacy(RefreshReferenceKnowledge):
    def test_a_local_snapshot_write_failure_never_enters_the_agent_visible_job_status(self):
        original_write = updates._write
        def fail_pending(name, value):
            if name.startswith("pending-"):
                raise OSError("synthetic failure at /private/person-data/knowledge/snapshot.json")
            original_write(name, value)
        with patch.object(updates, "_write", side_effect=fail_pending):
            with self.assertRaises(OSError):
                updates.preview(lambda url: self.response())
        status = updates.status()
        self.assertEqual(status["job"]["status"], "failed")
        self.assertNotIn("/private/", json.dumps(status))
        self.assertIn("previous active knowledge", status["job"]["error"])
        self.assertEqual(self.bundled.read_bytes(), self.original)
