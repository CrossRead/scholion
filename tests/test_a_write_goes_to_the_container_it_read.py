"""C7 of the 0.6.0 brief: a write lands in the container that was read, or nowhere.

A command, a request, a session reads the container that is active when it
starts. `use` in another terminal while it runs moves every path in the
product at once — and without a gate, the next write would put person A's
prescription into person B's profile, silently and in the right format. The
gate (`container.pinned`, `container.gate`) is taken at the start of every
command line and every page request that writes; `core.write_json` asks it
before every write into the profile.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import support
from scholion import container, core, demo, store

A, B = "p-aaaaaa", "p-bbbbbb"


class _Two(unittest.TestCase):

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="gate_")).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        files = demo.build_all()
        self.addCleanup(support.workstation(self.base, {A: files, B: files}))

    def meds_of(self, cid):
        path = self.base / "patients" / cid / "profile" / "medications.json"
        return [m["name"] for m in json.loads(path.read_text(encoding="utf-8"))["medications"]]


class TestTheGate(_Two):

    def test_paths_remain_bound_after_the_live_selection_changes(self):
        with container.pinned():
            original = core.profile_dir()
            container.use(B)
            self.assertEqual(original, core.profile_dir())
            with self.assertRaises(container.ContainerError):
                container.named()

    def test_an_external_write_is_checked_after_the_lock_was_taken(self):
        external = self.base / "external"
        external.mkdir()
        target = external / "medications.json"
        target.write_text(json.dumps({"medications": [{"name": "audit-entry"}]}), encoding="utf-8")
        for cid in (A, B):
            (self.base / "patients" / cid / "profile" / "sources.json").write_text(
                json.dumps({"folders": {"medications": str(external)}}), encoding="utf-8")
        before = target.read_bytes()
        original = store._path

        def switch(name):
            container.use(B)
            return original(name)

        with container.pinned(), mock.patch.object(store, "_path", switch):
            with self.assertRaises(container.ContainerError):
                store.remove_medication("audit-entry")
        self.assertEqual(before, target.read_bytes())

    def test_switch_during_an_agent_read_returns_no_mixed_answer(self):
        from scholion import ouroboros_tools
        from scholion.engine import profile_view
        original = profile_view.analyze_labs

        def switch():
            result = original()
            container.use(B)
            return result

        handler = next(t.handler for t in ouroboros_tools.get_tools() if t.name == "sch_overview")
        with mock.patch.object(profile_view, "analyze_labs", switch):
            with self.assertRaises(container.ContainerError):
                handler.both()

    def test_corrupt_identity_is_preserved_and_not_replaced(self):
        path = self.base / "patients" / A / "container.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(container.ContainerError):
            container.ensure(path.parent)
        self.assertEqual("{broken", path.read_text(encoding="utf-8"))

    def test_workstation_with_wrong_shape_does_not_select_the_legacy_profile(self):
        path = self.base / "workstation.json"
        for value in ([], None, {}, {"containers": [], "active": A}):
            with self.subTest(value=value):
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(container.ContainerError):
                    container.active_dir()

    def test_worker_keeps_its_container_and_refuses_a_late_start(self):
        from scholion import recompute
        context = container.capture()
        container.use(B)
        with mock.patch.object(recompute, "run") as run:
            recompute._run_claimed(None, None, context)
        run.assert_not_called()
        job = self.base / "patients" / A / "profile" / recompute.JOB
        self.assertEqual("failed", json.loads(job.read_text(encoding="utf-8"))["status"])
        self.assertFalse((self.base / "patients" / B / "profile" / recompute.JOB).exists())

    def test_a_switch_in_the_middle_refuses_the_write(self):
        before_a, before_b = self.meds_of(A), self.meds_of(B)
        with container.pinned():
            container.use(B)            # somebody else, in another terminal
            with self.assertRaises(container.ContainerError) as e:
                store.add_medication("Atorvastatin", "10 mg", subject="owner")
        self.assertEqual("container.changed", e.exception.code)
        self.assertIn(A, str(e.exception))
        self.assertIn(B, str(e.exception))
        self.assertEqual(before_b, self.meds_of(B), "A's write landed in B's profile")
        self.assertEqual(before_a, self.meds_of(A))

    def test_without_a_switch_the_write_goes_through(self):
        with container.pinned():
            store.add_medication("Atorvastatin", "10 mg", subject="owner")
        self.assertIn("Atorvastatin", self.meds_of(A))

    def test_another_person_copied_into_the_same_folder_is_refused(self):
        """The folder is the same; the ID in it is not. Copying one container
        over another is the manual version of the same accident."""
        with container.pinned():
            (self.base / "patients" / A / "container.json").write_text(
                json.dumps({"id": "p-cccccc"}), encoding="utf-8")
            with self.assertRaises(container.ContainerError):
                store.add_medication("Atorvastatin", "10 mg", subject="owner")

    def test_the_command_line_is_pinned(self):
        real = store.add_medication

        def switched_midway(*a, **k):
            container.use(B)
            return real(*a, **k)

        from scholion import cli
        out, err = io.StringIO(), io.StringIO()
        before_b = self.meds_of(B)
        with mock.patch.object(store, "add_medication", switched_midway), \
                redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["add-med", "Atorvastatin", "--dose", "10 mg"])
        self.assertEqual(6, code, err.getvalue())
        self.assertEqual(before_b, self.meds_of(B))


class TestTheIdIsWrittenLazily(unittest.TestCase):
    """P1: an install that never asks for a second person gets its ID at the
    first write into the profile, and nothing else changes."""

    def test_sibling_explicit_profiles_are_different_even_without_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.addCleanup(support.pin_profile(root / "first"))
            with container.pinned():
                with mock.patch.dict(os.environ, {"SCHOLION_PROFILE_DIR": str(root / "second")}):
                    with self.assertRaises(container.ContainerError):
                        container.gate()

    def test_an_unwitnessed_id_appearing_is_not_lazy_naming(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.addCleanup(support.pin_profile(root / "profile"))
            with container.pinned():
                (root / "container.json").write_text(json.dumps({"id": A}), encoding="utf-8")
                with self.assertRaises(container.ContainerError):
                    container.gate()

    def test_the_first_write_names_the_container(self):
        root = Path(tempfile.mkdtemp(prefix="lazy_")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        (root / "profile").mkdir()
        self.addCleanup(support.pin_profile(root / "profile"))
        self.assertIsNone(container.read(root))
        store.add_medication("Atorvastatin", "10 mg", subject="owner")
        rec = container.read(root)
        self.assertRegex(rec["id"], r"^p-[a-z0-9]{6}$")
        first = rec["id"]
        store.add_medication("Metformin", "500 mg", subject="owner")
        self.assertEqual(first, container.read(root)["id"], "the ID changed between writes")

    def test_a_cache_write_names_nothing(self):
        root = Path(tempfile.mkdtemp(prefix="lazy_")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        (root / "profile").mkdir()
        self.addCleanup(support.pin_profile(root / "profile"))
        core.write_json(root / "work" / "cache" / "x.json", {"a": 1})
        self.assertIsNone(container.read(root))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
