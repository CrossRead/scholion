"""The external-tools list matches the scripts, and nothing installs by itself.

Two different things are pinned here, and they fail in opposite directions.

**Drift.** The list of tools lives in `knowledge/external_tools.json`, and the
tools are actually needed by `src/ingest/*.sh`. Two lists maintained by hand
diverge — quietly, and in the worse direction: a script starts checking for a
binary nobody wrote down, so `scholion init` reports everything is in place and
the person discovers the gap an hour into an alignment. So the scripts are read
and the two sets are compared.

**Installing without being asked.** Until v2.6.1 the PDF path ran
`pip install pdfplumber` by itself the moment a form appeared in a folder. This
module runs a package manager, which is a bigger version of the same power, so
the refusals are tested — and, crucially, so is the positive case. A test that
only checks "nothing ran" passes just as well when nothing can ever run, and
that is exactly how the v2.6.0 TLS tests passed while the code was broken. The
positive control is what makes the two refusals mean something.
"""
from __future__ import annotations

import json
import os
import re
import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, i18n, tools

INGEST = support.ROOT / "src" / "ingest"

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]*$")
_DIRECT = re.compile(r"command -v\s+[\"']?([A-Za-z][A-Za-z0-9_.+-]*)")
_FORLOOP = re.compile(r"for\s+(\w+)\s+in\s+([^;\n]+?)\s*;\s*do(.{0,200})", re.S)


def tools_the_scripts_check() -> dict:
    """Every binary the preparation scripts test for, and where.

    Both shapes are read, because both are in the tree: `command -v samtools`
    directly, and `for t in bcftools bgzip tabix; do command -v "$t"`. Reading
    only the first form is how `tabix` — which appears exclusively inside a loop —
    would go missing from a list whose whole job is to be complete.
    """
    found: dict = {}
    for path in sorted(INGEST.glob("*.sh")):
        text = path.read_text(encoding="utf-8", errors="replace")
        loop_vars, names = set(), set()
        for m in _FORLOOP.finditer(text):
            var, items, body = m.group(1), m.group(2), m.group(3)
            if f'command -v "${var}"' in body or f"command -v ${var}" in body:
                loop_vars.add(var)
                names.update(w for w in items.split() if _NAME.match(w))
        names.update(n for n in _DIRECT.findall(text) if n not in loop_vars)
        for n in names:
            found.setdefault(n, []).append(path.name)
    return found


class TestTheListMatchesTheScripts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        i18n.set_lang("en")
        core.reset_cache()
        cls.kb = core.external_tools()
        cls.checked = tools_the_scripts_check()

    @classmethod
    def tearDownClass(cls):
        i18n.set_lang(None)
        core.reset_cache()

    def test_every_tool_the_scripts_need_is_described(self):
        missing = sorted(set(self.checked) - set(self.kb["tools"]))
        detail = "; ".join(f"{n} ({', '.join(self.checked[n])})" for n in missing)
        self.assertEqual(missing, [],
                         "a script checks for a tool the list does not know — init will report "
                         "everything as ready and the gap will surface mid-run: " + detail)

    def test_the_list_does_not_invent_tools(self):
        """The reverse direction, and the one that rots silently.

        A tool left behind after a script stopped using it is offered for
        installation forever: nobody notices, because an extra installation
        breaks nothing. It just quietly makes the first run longer and the list
        less trustworthy.
        """
        extra = sorted(set(self.kb["tools"]) - set(self.checked))
        self.assertEqual(extra, [],
                         "the list names tools no script checks for any more: " + ", ".join(extra))

    def test_every_set_names_tools_that_exist(self):
        for key, s in self.kb["sets"].items():
            for name in list(s.get("tools", [])) + list(s.get("optional", [])):
                with self.subTest(set=key, tool=name):
                    self.assertIn(name, self.kb["tools"],
                                  f"set «{key}» names «{name}», which has no entry")

    def test_every_tool_belongs_to_a_set(self):
        in_sets = {n for s in self.kb["sets"].values()
                   for n in list(s.get("tools", [])) + list(s.get("optional", []))}
        orphans = sorted(set(self.kb["tools"]) - in_sets)
        self.assertEqual(orphans, [],
                         "a tool in no set is never offered and never explained: " + ", ".join(orphans))

    def test_exactly_the_base_set_is_offered_at_first_run(self):
        """A first run that opens with eleven installations reads as a demand.

        The rule taken with the owner: the set without which the genome layer
        does not work at all is offered at `init`; everything else is offered by
        the step that needs it, when it needs it.
        """
        offered = sorted(k for k, s in self.kb["sets"].items() if s.get("offer_at_init"))
        self.assertEqual(offered, ["base"],
                         "the first run offers more than the base set — that is a demand, not a question")

    def test_package_names_are_strings_under_managers_we_drive(self):
        allowed = {m["key"] for m in tools.MANAGERS.values()}
        for name, entry in self.kb["tools"].items():
            for manager, package in (entry.get("packages") or {}).items():
                with self.subTest(tool=name, manager=manager):
                    self.assertIn(manager, allowed, "a manager nothing knows how to run")
                    self.assertTrue(isinstance(package, str) and package.strip(),
                                    "an empty package name is worse than none: it produces a "
                                    "command that fails without saying why")

    def test_a_tool_without_a_package_says_why(self):
        """No silent gaps. If we cannot install it, the report has to explain."""
        for name, entry in self.kb["tools"].items():
            if entry.get("packages") or entry.get("system"):
                continue
            with self.subTest(tool=name):
                self.assertTrue(entry.get("note"),
                                f"«{name}» has neither a package nor an explanation — the report "
                                f"would say 'installed by hand' and stop there")


class TestNothingRunsUnasked(unittest.TestCase):
    """The refusals, and the positive control that gives them meaning."""

    def setUp(self):
        self.was_offline = os.environ.get("SCHOLION_OFFLINE")
        os.environ.pop("SCHOLION_OFFLINE", None)   # the suite sets it; here it is the subject
        i18n.set_lang("en")

    def tearDown(self):
        if self.was_offline is None:
            os.environ.pop("SCHOLION_OFFLINE", None)
        else:
            os.environ["SCHOLION_OFFLINE"] = self.was_offline
        i18n.set_lang(None)

    def test_a_manager_is_really_run_when_everything_is_in_order(self):
        """The positive control.

        Without it the two tests below would pass on a machine where no manager
        exists — that is, for a reason that has nothing to do with the rule they
        claim to check. That failure mode is not hypothetical: the v2.6.0 TLS
        tests passed exactly that way.
        """
        with mock.patch.object(tools, "which", side_effect=lambda n: "/fake/brew" if n == "brew" else None), \
             mock.patch.object(tools.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            r = tools.install(["samtools", "bcftools"], "brew", confirm=True)
        self.assertTrue(run.called, "the manager was not run even with a confirmation — "
                                    "the refusal tests below would then prove nothing")
        argvs = [c.args[0] for c in run.call_args_list]
        self.assertIn(["brew", "install", "samtools"], argvs)
        self.assertEqual(r["still_missing"], ["samtools", "bcftools"],
                         "success is asked of the machine, not deduced from the exit code")

    def test_without_confirmation_nothing_is_run(self):
        with mock.patch.object(tools, "which", side_effect=lambda n: "/fake/brew" if n == "brew" else None), \
             mock.patch.object(tools.subprocess, "run") as run:
            r = tools.install(["samtools"], "brew")
        self.assertFalse(run.called, "a package manager was started without a confirmation")
        self.assertTrue(r["refused"])
        self.assertEqual(r["reason"], "not_confirmed")

    def test_offline_refuses_even_with_a_confirmation(self):
        """SCHOLION_OFFLINE is a statement about the machine, not about one request."""
        os.environ["SCHOLION_OFFLINE"] = "1"
        with mock.patch.object(tools, "which", side_effect=lambda n: "/fake/brew" if n == "brew" else None), \
             mock.patch.object(tools.subprocess, "run") as run:
            r = tools.install(["samtools"], "brew", confirm=True)
        self.assertFalse(run.called, "installing reached the network in offline mode")
        self.assertEqual(r["reason"], "offline")

    def test_the_first_run_question_does_not_install_into_a_pipeline(self):
        """No terminal means nobody to answer, and silence is not consent."""
        import io
        with mock.patch.object(tools, "which", side_effect=lambda n: "/fake/brew" if n == "brew" else None), \
             mock.patch.object(tools.sys.stdin, "isatty", return_value=False), \
             mock.patch.object(tools.subprocess, "run") as run:
            out = io.StringIO()
            r = tools.offer_after_init(stream=out)
        self.assertFalse(run.called, "something was installed with nobody at the terminal")
        self.assertEqual(r["reason"], "not_a_tty")
        self.assertIn("scholion tools --install", out.getvalue(),
                      "the way to do it later was not named")

    def test_the_question_can_be_switched_off_entirely(self):
        with mock.patch.object(tools.subprocess, "run") as run:
            r = tools.offer_after_init(skip=True)
        self.assertFalse(run.called)
        self.assertFalse(r["asked"])


class TestNoAdministratorRights(unittest.TestCase):
    """`sudo` never appears — not in a command, not in the knowledge file.

    The rule is not «we are careful». Homebrew and conda are the managers this
    module drives precisely because they install into the user's own prefix; a
    manager that needs root is quoted as text, for the person to run. A test is
    the only thing that keeps that distinction from being eroded by one
    convenient exception.
    """

    def test_no_generated_command_asks_for_root(self):
        kb = core.external_tools()
        for name in kb["tools"]:
            for manager in tools.MANAGERS:
                package = tools.package_for(name, manager)
                if not package:
                    continue
                with self.subTest(tool=name, manager=manager):
                    argv = tools._argv(manager, package)
                    self.assertNotIn("sudo", argv)
                    self.assertNotIn("sudo", " ".join(argv))

    def test_no_entry_in_the_knowledge_file_suggests_root_either(self):
        """The entries, not the file's own explanation of why there is none.

        `_meta` is where the rule is written down and therefore the one place the
        word belongs; checking the whole file made the test fail on its own
        documentation, which teaches the next person to delete the rule rather
        than keep it.
        """
        data = json.loads((core._KNOWLEDGE_DIR / "external_tools.json").read_text(encoding="utf-8"))
        acted_on = json.dumps({k: v for k, v in data.items() if k != "_meta"}, ensure_ascii=False)
        self.assertNotIn("sudo", acted_on,
                         "a note telling the person to use sudo makes the promise above false")

    def test_the_plan_never_uses_a_shell(self):
        """Package names come out of a JSON file. Through a shell, a bad line in
        that file becomes arbitrary code; through argv it becomes a package that
        is not found."""
        source = (support.ROOT / "src" / "scholion" / "tools.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)


class TestThePlan(unittest.TestCase):

    def setUp(self):
        i18n.set_lang("en")
        core.reset_cache()

    def tearDown(self):
        i18n.set_lang(None)
        core.reset_cache()

    def test_one_package_covering_two_tools_is_installed_once(self):
        p = tools.plan(["bgzip", "tabix"], "brew")
        self.assertEqual([s["package"] for s in p["steps"]], ["htslib"])
        self.assertEqual(p["steps"][0]["tools"], ["bgzip", "tabix"])

    def test_a_tool_with_no_package_for_this_manager_is_named_not_dropped(self):
        p = tools.plan(["pypgx"], "brew")
        self.assertEqual(p["steps"], [])
        self.assertEqual([u["tool"] for u in p["unhandled"]], ["pypgx"])
        self.assertTrue(tools.other_routes("pypgx", "brew"),
                        "there is a conda route and the report has to show it")

    def test_the_conda_command_names_the_channels(self):
        argv = tools._argv("conda", "samtools")
        self.assertIn("bioconda", argv)
        self.assertIn("-y", argv, "an installation that stops on a prompt looks like a hang")

    def test_sets_can_be_asked_for_by_name(self):
        st = tools.status()
        self.assertIn("base", tools.set_names(st))
        with mock.patch.object(tools, "which", return_value=None):
            st = tools.status()
            self.assertEqual(tools.tools_of(["base"], st),
                             ["samtools", "bcftools", "bgzip", "tabix"])

    def test_a_tool_needed_by_two_sets_is_listed_once(self):
        with mock.patch.object(tools, "which", return_value=None):
            st = tools.status()
            names = tools.tools_of(["base", "hla"], st)
        self.assertEqual(len(names), len(set(names)), "samtools was listed twice")


class TestTheReportSpeaksBothLanguages(unittest.TestCase):

    def tearDown(self):
        i18n.set_lang(None)
        core.reset_cache()

    def test_no_missing_phrases_and_no_raw_language_maps(self):
        for code in ("en", "ru"):
            with self.subTest(language=code):
                i18n.set_lang(code)
                core.reset_cache()
                text = tools.report()
                self.assertNotIn("⟦", text, "a key with no phrase in the catalogue")
                self.assertNotIn("{'en'", text)
                self.assertNotIn('{"en"', text)
                self.assertTrue(text.strip())

    def test_the_json_output_is_an_object_with_the_sets(self):
        data = support.run_json(["tools"])
        self.assertIn("sets", data)
        self.assertIn("missing", data)
        self.assertTrue(any(s["key"] == "base" for s in data["sets"]))

    def test_the_command_refuses_an_unknown_set(self):
        code, out, err = support.run(["tools", "--install", "--set", "no-such-set"])
        self.assertEqual(code, 2)
        self.assertIn("base", err, "the refusal does not say what the available sets are")


if __name__ == "__main__":
    unittest.main()
