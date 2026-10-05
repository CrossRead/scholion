"""C11 of the 0.6.0 brief: one container looks the same alone and among many.

P1 of task 192: the version is one for the patient and for the clinician; the
patient simply has one container and the clinician many. So a person's data
must answer the same whether its folder is the only data directory on the
machine (no workstation, as in 0.5) or the active container among several —
every read command, in both output forms. Only the header may differ, and in
0.6.0 the header is drawn by the page (stage 7), not by these commands.

Comparing against 0.5.9 would not do: task 217 changes the output on purpose.
The comparison is the same build, the same folder, two ways of reaching it.
"""
from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import support
from scholion import cli, contract, core, demo

#: Read commands with the arguments they are called with. Every read command of
#: the parser is here unless it is in SKIP; a new one fails the coverage check.
CALLS = [
    ["overview"], ["second-opinion"], ["radar"], ["medications"], ["labs"], ["metrics"],
    ["limits"], ["evidence-levels"], ["markers"], ["suggest-tests"], ["genome-status"],
    ["genome-updates"], ["genome", "rs4149056"], ["drug", "omeprazole"],
    ["prescription", "Levothyroxine"], ["prescription", "Combined oral contraceptive"],
    ["system"], ["system", "cardio"], ["system", "thyroid", "--register", "clinician"],
    ["panel", "lipids"], ["screen"], ["brief"], ["brief-review"], ["focus"], ["lifestyle"],
    ["goal"], ["goal-suggest"], ["clinvar"], ["acmg"], ["prs"], ["longevity"],
    ["lipid-genetics"], ["phenoage"], ["profile"], ["capabilities"], ["flag-rate"],
    ["array"], ["selfcheck"], ["sources"], ["version"], ["target", "list"], ["marker"],
    ["assistant"], ["doc"], ["skill", "--path"],
]

#: Not compared, each for its reason.
SKIP = {
    "patients": "its whole job is to differ: one container, or the list of several",
    "tools": "a statement about the machine's programs, not about the person",
}


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(list(argv))
    core.reset_cache()
    return code, out.getvalue()


class TestOneContainerAloneAndAmongMany(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="alone_many_")).resolve()
        files = demo.build_all()
        restore = support.workstation(cls.base, {})
        try:
            profile = cls.base / "legacy" / "profile"
            profile.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                (profile / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            (cls.base / "legacy" / "container.json").write_text(
                json.dumps({"id": "p-aaaaaa", "engine": "test"}), encoding="utf-8")
            cls.alone = {tuple(c): _run(c + ["--json"]) for c in CALLS}
            cls.alone_text = {tuple(c): _run(c) for c in CALLS}
            others = {}
            for cid in ("p-bbbbbb", "p-cccccc"):
                other = copy.deepcopy(files)
                other["medications.json"]["medications"] = []
                folder = cls.base / "patients" / cid
                (folder / "profile").mkdir(parents=True)
                for name, data in other.items():
                    (folder / "profile" / name).write_text(json.dumps(data), encoding="utf-8")
                (folder / "container.json").write_text(json.dumps({"id": cid}), encoding="utf-8")
                others[cid] = str(folder)
            (cls.base / "workstation.json").write_text(json.dumps({
                "root": str(cls.base / "patients"), "active": "p-aaaaaa",
                "containers": {"p-aaaaaa": str(cls.base / "legacy"), **others}}),
                encoding="utf-8")
            core.reset_cache()
            cls.many = {tuple(c): _run(c + ["--json"]) for c in CALLS}
            cls.many_text = {tuple(c): _run(c) for c in CALLS}
        finally:
            restore()
            shutil.rmtree(cls.base, True)

    def test_every_read_command_is_compared(self):
        import argparse
        cmds = set()
        for a in cli.build_parser()._actions:
            if isinstance(a, argparse._SubParsersAction):
                cmds |= set(a.choices)
        reads = {c for c in cmds if c not in contract.WRITES and support.ARGS_FOR.get(c, []) is not None}
        called = {c[0] for c in CALLS}
        self.assertEqual(set(), reads - called - set(SKIP),
                         "a read command that is not compared alone and among many")
        self.assertGreaterEqual(len(CALLS), 45)

    def test_the_same_answer_in_both_forms(self):
        for call in CALLS:
            key = tuple(call)
            with self.subTest(call=" ".join(call)):
                self.assertEqual(self.alone[key], self.many[key])
                self.assertEqual(self.alone_text[key], self.many_text[key])

    def test_the_comparison_compared_something(self):
        code, out = self.many[("medications",)]
        self.assertEqual(0, code)
        self.assertIn("Levothyroxine", out, "among many, the active container was not the one read")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
