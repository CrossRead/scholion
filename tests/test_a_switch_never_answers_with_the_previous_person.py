"""C1 of the 0.6.0 brief: a switch never answers with the previous person.

One process, two people, A → B → A. Every path in the product is resolved on
each call, and every cache that holds a person's data is keyed by the file it
read (C3), so after `use B` nothing of A may come back — and after `use A`
everything of A must. The failure this guards against looks like a normal
answer: a radar, a list of medicines, only somebody else's.

Held through the core, the command line and the local page, on the demo
profile and a second person who differs from it where it is easy to see:
another prescription list and another TSH.
"""
from __future__ import annotations

import copy
import io
import json
import os
import shutil
import socket
import tempfile
import threading
import unittest
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import support
from scholion import container, core, demo, engine

A, B = "p-aaaaaa", "p-bbbbbb"


def _other(files):
    """The demo person's files changed where a leak would show."""
    files = copy.deepcopy(files)
    files["medications.json"]["medications"] = [
        {"name": "Metformin", "dose": "500 mg", "status": "active"}]
    for p in files["labs.json"]["markers"]["tsh"]["series"]:
        p["value"] = 9.9
    return files


class _Two(unittest.TestCase):

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="switch_")).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        files = demo.build_all()
        self.addCleanup(support.workstation(self.base, {A: files, B: _other(files)}))

    @staticmethod
    def meds():
        return sorted(m.get("name") for m in core.active_medications())

    @staticmethod
    def tsh():
        m = next(m for m in engine.analyze_labs()["markers"] if m.get("key") == "tsh")
        return m.get("value", m.get("latest"))


class TestTheCore(_Two):

    def test_a_then_b_then_a(self):
        first = (self.meds(), self.tsh(), engine.regimen_cautions())
        self.assertIn("Levothyroxine", " ".join(first[0]))
        container.use(B)
        second = (self.meds(), self.tsh(), engine.regimen_cautions())
        self.assertEqual(["Metformin"], second[0], "B answered with A's prescriptions")
        self.assertNotEqual(first[1], second[1], "B answered with A's TSH")
        self.assertEqual([], second[2], "A's factor V caution reached B")
        container.use(A)
        self.assertEqual(first, (self.meds(), self.tsh(), engine.regimen_cautions()),
                         "coming back to A did not give A back")

    def test_every_slot_moves_with_the_container(self):
        # A slot the environment names stays where it was named: the suite keeps
        # the genome off that way, and an explicit variable beats the container.
        slots = [n for n in core.DATA_SLOTS if not os.environ.get(f"SCHOLION_{n.upper()}_DIR")]
        self.assertIn("profile", slots)
        for name in slots:
            with self.subTest(slot=name):
                self.assertEqual(self.base / "patients" / A / name, core.slot_dir(name))
        self.assertTrue(str(core.cache_dir()).startswith(str(self.base / "patients" / A)))
        container.use(B)
        for name in slots:
            with self.subTest(slot=name):
                self.assertEqual(self.base / "patients" / B / name, core.slot_dir(name))

    def test_an_active_container_whose_folder_is_gone_is_refused(self):
        shutil.rmtree(self.base / "patients" / A)
        with self.assertRaises(container.ContainerError) as e:
            core.profile_dir()
        self.assertEqual("container.missing", e.exception.code)


class TestTheCommandLine(_Two):

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        from scholion import cli
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_patient_reads_another_for_one_command(self):
        code, out, _ = self.run_cli("medications", "--json", "--patient", B)
        self.assertEqual(0, code)
        self.assertEqual(["Metformin"], [m["name"] for m in json.loads(out)["medications"]])
        self.assertEqual(A, container.workstation()["active"], "--patient moved the active one")
        code, out, _ = self.run_cli("medications", "--json")
        self.assertIn("Levothyroxine", out, "the next command did not come back to A")

    def test_use_prints_whom_it_is_working_with(self):
        code, out, _ = self.run_cli("use", B)
        self.assertEqual(0, code)
        self.assertIn(B, out)
        self.assertEqual(B, container.workstation()["active"])

    def test_an_unknown_id_is_refused_with_its_own_code(self):
        for argv in (("use", "p-nobody"), ("labs", "--patient", "p-nobody")):
            with self.subTest(argv=argv):
                code, _, err = self.run_cli(*argv)
                self.assertEqual(6, code)
                self.assertIn("p-nobody", err)

    def test_patient_without_an_id_is_refused(self):
        code, _, err = self.run_cli("labs", "--patient")
        self.assertEqual(2, code)
        self.assertIn("--patient", err)

    def test_patients_prints_the_list_with_the_active_one_marked(self):
        from scholion.i18n import t
        code, out, _ = self.run_cli("patients")
        self.assertEqual(0, code)
        line = next(ln for ln in out.splitlines() if A in ln)
        self.assertIn(t("patients.active_mark").strip(), line)
        self.assertNotIn(t("patients.active_mark").strip(),
                         next(ln for ln in out.splitlines() if B in ln))

    def test_patients_names_the_active_one(self):
        code, out, _ = self.run_cli("patients", "--json")
        rows = {r["id"]: r for r in json.loads(out)["containers"]}
        self.assertEqual({A, B}, set(rows))
        self.assertEqual([A], [k for k, r in rows.items() if r["active"]])


class TestThePage(_Two):

    def setUp(self):
        super().setUp()
        from scholion import server
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.srv = server._Server(("127.0.0.1", self.port), server.Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.server_close)
        self.addCleanup(self.srv.shutdown)

    def call(self, path, body=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json", "Host": f"127.0.0.1:{self.port}",
            "Origin": f"http://127.0.0.1:{self.port}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())

    def names(self):
        return sorted(m["name"] for m in self.call("/api/medications")["medications"])

    def test_a_then_b_then_a_without_a_restart(self):
        first = self.names()
        self.assertTrue(self.call("/api/use", {"id": B})["ok"])
        self.assertEqual(["Metformin"], self.names(), "the page answered B with A's list")
        self.assertTrue(self.call("/api/use", {"id": A})["ok"])
        self.assertEqual(first, self.names())

    def test_the_page_lists_the_people_only_where_there_are_several(self):
        rows = self.call("/api/patients")["containers"]
        self.assertEqual({A, B}, {r["id"] for r in rows})


class TestTheUpdateNoteIsTheProgramsNotThePersons(_Two):
    """Whether a newer build exists is asked once per machine, not once per
    patient: with a workstation the note lives beside it (task 192)."""

    def test_the_note_does_not_follow_the_container(self):
        from scholion import upgrade
        first = upgrade._notice_path()
        self.assertEqual(self.base, first.parent)
        container.use(B)
        self.assertEqual(first, upgrade._notice_path())


class TestOneContainerLooksAsIn05(unittest.TestCase):
    """P1: with no workstation there is no choice, and the data directory is the one."""

    def test_no_workstation_no_choice(self):
        base = Path(tempfile.mkdtemp(prefix="alone_")).resolve()
        self.addCleanup(shutil.rmtree, base, True)
        self.addCleanup(support.workstation(base, {}))
        self.assertIsNone(container.active_dir())
        listing = container.listing()
        self.assertIsNone(listing["workstation"])
        from scholion import cli
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(0, cli.main(["patients"]))
        self.assertIn("init --patient", out.getvalue(), "one person: the way to add a second")
        self.assertEqual(1, len(listing["containers"]))
        with self.assertRaises(container.ContainerError) as e:
            container.use(A)
        self.assertEqual("container.no_workstation", e.exception.code)


class TestInitPatient(unittest.TestCase):

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="initp_")).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.addCleanup(support.workstation(self.base, {}))

    def test_the_first_one_adopts_the_data_directory_in_place_and_keeps_it_active(self):
        legacy = self.base / "legacy"
        (legacy / "profile").mkdir(parents=True)
        (legacy / "profile" / "labs.json").write_text("{}", encoding="utf-8")
        r = container.create(label="second person", root=str(self.base / "patients"))
        self.assertTrue(r["first"])
        self.assertTrue((legacy / "container.json").is_file(), "container №1 got no ID")
        self.assertEqual(r["adopted"], container.workstation()["active"],
                         "creating a container switched the person")
        self.assertEqual(legacy.resolve(), core.repo_dir())
        self.assertEqual({r["adopted"], r["id"]}, set(container.registry()))

    def test_an_empty_install_starts_with_the_new_one_active(self):
        r = container.create(root=str(self.base / "patients"))
        self.assertIsNone(r["adopted"])
        self.assertEqual(r["id"], container.workstation()["active"])
        self.assertRegex(r["id"], r"^p-[a-z0-9]{6}$")

    def test_an_own_id_is_checked_and_never_taken_twice(self):
        container.create("clinic-0042", root=str(self.base / "patients"))
        for cid, code in (("clinic-0042", "container.id_taken"), ("a b", "container.bad_id"),
                          ("x", "container.bad_id")):
            with self.subTest(cid=cid):
                with self.assertRaises(container.ContainerError) as e:
                    container.create(cid)
                self.assertEqual(code, e.exception.code)

    def test_the_root_is_set_once(self):
        container.create(root=str(self.base / "patients"))
        with self.assertRaises(container.ContainerError) as e:
            container.create(root=str(self.base / "elsewhere"))
        self.assertEqual("container.root_is_set", e.exception.code)

    def test_the_command_lays_the_whole_layout_into_the_new_container(self):
        from scholion import cli
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["init", "--patient", "--root", str(self.base / "patients"),
                             "--sex", "female", "--no-tools", "--json"])
        self.assertEqual(0, code, err.getvalue())
        folder = Path(json.loads(out.getvalue())["path"])
        for slot in ("profile", "genome", "raw", "work", "archive"):
            with self.subTest(slot=slot):
                self.assertTrue((folder / slot).is_dir())
        metrics = json.loads((folder / "profile" / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual("female", metrics["profile"]["sex"])
        self.assertFalse(any((self.base / "legacy").iterdir()), "the 0.5 directory was touched")

    def test_init_patient_with_an_id_after_it_is_refused(self):
        from scholion import cli
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = cli.main(["init", "--patient", "p-abc123", "--no-tools"])
        self.assertEqual(2, code)
        self.assertIn("--id", err.getvalue())

    def test_the_label_is_kept_in_the_container_and_nowhere_else(self):
        r = container.create(label="Room 4, Tuesday", root=str(self.base / "patients"))
        self.assertEqual("Room 4, Tuesday", container.read(Path(r["path"]))["label"])
        self.assertNotIn("Room 4", (self.base / "workstation.json").read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
