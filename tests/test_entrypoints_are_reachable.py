"""A command the application prints has to be one the reader can run.

The «Assistant» tab lists the ways into the product and prints, under each, the
line that connects it. For the Claude skill — the flagship route, the one three
release tasks were spent on — that line was built as
`REPO / "src" / "skill" / "INSTRUCTION.owner.md"`, and both halves were wrong.

`REPO` is `PKG.parents[1]`: the repository root when the code runs from the
source tree, and the parent of site-packages after `pip install`, where it names
nothing. And `INSTRUCTION.owner.md` is the owner's clinical key, which never
ships. So on every machine except one the tab showed the badge «not found» and
then printed, underneath it, a symlink command into an empty path. The defect
was invisible from inside the repository, which is where it was written.

The guard is not «the path equals X». It is that whatever the application tells
somebody to do, the thing it points at is there. That holds in a checkout and in
an installed package, which is the whole point.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import support


class TestEveryPrintedCommandPointsAtSomethingThatExists(unittest.TestCase):

    def setUp(self):
        from scholion import assistant
        self.eps = {e["id"]: e for e in assistant.status()["entrypoints"]}

    def test_the_skill_entry_names_a_directory_that_holds_a_skill(self):
        e = self.eps["skill"]
        if e["state"] == "missing":
            self.assertIsNone(e.get("how"),
                              "the entry says the skill was not found and then prints a "
                              "command that claims to install it")
            return
        how = e.get("how") or ""
        self.assertIn("ln -s", how)
        quoted = how.split("'")
        self.assertGreaterEqual(len(quoted), 2, f"no path is quoted in: {how}")
        target = Path(quoted[1])
        self.assertTrue(target.is_dir(), f"the command points at a directory that does "
                                         f"not exist: {target}")
        self.assertTrue((target / "SKILL.md").is_file(),
                        f"{target} exists but holds no SKILL.md, so a model that follows "
                        f"this command loads nothing")

    def test_the_skill_entry_never_points_at_the_owners_edition(self):
        """The directory handed to a model must hold no `*.owner.*` file.

        This is the assertion that catches the original defect ON THE MACHINE WHERE
        IT WAS WRITTEN, which is what the first three attempts at this test did not
        do. `src/skill/` exists in a checkout and does hold a SKILL.md, so «the path
        exists» is green for the owner and red for everybody else — the project's
        recurring failure shape, a check that agrees with the one environment it was
        authored in.

        `src/skill/` also holds `INSTRUCTION.owner.md`: 117 KB of diplotypes,
        phenotypes and drug caveats belonging to one person. Symlinking it into
        `~/.claude/skills` would hand a model the owner's clinical key. So the old
        line was not merely broken, it was pointed at the wrong directory — and
        naming a directory free of `*.owner.*` is both the safety rule and the
        discriminator the environment cannot mask.
        """
        e = self.eps["skill"]
        how = e.get("how") or ""
        if not how:
            return
        target = Path(how.split("'")[1])
        owners = sorted(p.name for p in target.glob("*.owner.*"))
        self.assertEqual(owners, [],
                         f"the install route points at {target}, which carries {owners} — "
                         f"the owner-only edition, handed to whichever model follows it")

    def test_the_plugin_entry_names_a_file_that_exists(self):
        e = self.eps["ouroboros"]
        if e["state"] == "missing":
            return
        # The detail line carries the path. Whatever it names has to be there —
        # the same failure, one entry down.
        self.assertTrue(any(Path(tok).exists() for tok in e["detail"].replace(":", " ").split()
                            if "/" in tok or tok.endswith(".py")),
                        f"the plugin entry names nothing that exists: {e['detail']}")

    def test_the_command_a_model_is_told_to_run_resolves(self):
        e = self.eps["any"]
        self.assertIn("scholion", e.get("how") or "")


class TestTheInterfaceShowsTheVersionItIs(unittest.TestCase):
    """A build string kept by hand said «2026-07-30 · radar dynamics + tab freshness»
    while the package was 0.2.2 — a changelog line frozen in the header of a medical
    application, and wrong. There is one version, and it lives in the VERSION file."""

    def test_the_server_reports_the_package_version(self):
        from scholion import server, __version__
        self.assertEqual(server.VERSION, __version__)
        self.assertEqual(__version__.strip(),
                         (support.ROOT / "VERSION").read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    unittest.main()
