"""The engine package must STAY a package — this is the gate that makes it so.

On 18.08.2026 the 2800-line flat engine.py became eight domain modules behind
a re-export facade (v0.3.2). A structure like that decays in a known way: the
next capability lands in the facade "for a moment", a module quietly doubles,
a convenience import closes a cycle nobody drew. None of those steps look like
decisions while they happen, which is why a convention held in memory does not
survive them. So the convention is held here instead, the same way the four
faces are: an invariant, a red test, and a visible ritual for changing the
rule when the rule should change.

Four claims, each with its own failure message:

  1. The facade defines nothing.  engine/__init__.py is imports and a
     docstring — a `def` added there is the first line of the next monolith.
  2. Domain imports stay acyclic at the top level.  The one sanctioned back
     edge (pgx -> lifestyle._brief_life) is lazy, inside a function body, and
     therefore invisible to this check — that is what makes it sanctioned.
  3. Every module has a SIZE BUDGET, written down here.  Exceeding it is not
     forbidden — it is a decision: either split the module or raise its budget
     in the same commit, with a reason about the capability, not the calendar.
     A new engine/*.py with no budget line fails for the same reason: a new
     domain is a decision, and this table is where it is recorded.
  4. The facade may not shrink, and every public submodule name must reach it.
     A capability that exists in a submodule but not at engine.<name> is
     invisible to six consumers that have called that address for a year.
"""
from __future__ import annotations

import ast
import io
import unittest
from pathlib import Path

import support  # noqa: F401  -- path setup, same as every test here
from scholion import engine as engine_pkg

ENGINE_DIR = Path(engine_pkg.__file__).resolve().parent

# The budgets. Roughly current size + a third: enough room for ordinary growth,
# small enough that a module heading back toward monolith trips the wire while
# the diff is still one review long. Raising a number is allowed and visible.
LINE_BUDGETS = {
    "__init__": 220,     # imports only -- claim 1 keeps it honest anyway
    "_helpers": 250,
    # 450 → 480 on 19.08.2026. Three capabilities took the room, all of them in
    # the same place because they are all about what a single measurement means:
    # a draw's clock time and the same-day pair it forms (a repeat is not a
    # discrepancy), a reference interval borrowed from the catalogue when the form
    # printed none, and the guard that refuses to borrow a sex-specific interval
    # for a person whose sex was never recorded. Splitting them out would put the
    # question «may this number be compared with that corridor» in two files.
    # 480 → 530 on 19.08.2026. One capability, and it belongs beside the others
    # above because it is the same question: a decision threshold stated as «3×
    # the upper limit of normal» is a RULE, and the upper limit of normal is a
    # sex pair. Storing the product instead of the rule is what gave a woman on a
    # statin no signal at ALT 110 and none at CK 520. The computation has to sit
    # next to the corridor logic — moving it out would split «which bound applies
    # to this person» across two files, which is exactly the split that produced
    # the defect.
    # 530 → 560 on 19.08.2026: AUTHOR_SETTINGS — the three numbers in this module
    # that nobody published, each with what would replace it and what it does not
    # license. It lives beside them rather than in a registry elsewhere, because a
    # declaration a reader has to go and find is one they will not find.
    # 560 → 580 on 21.08.2026: task 100. A point now carries where its DATE came
    # from, and a claim about a shift has to say when one of the two days was not
    # printed on any form. Both are readers of a field that would otherwise be
    # written and never looked at.
    "labs": 580,
    "goals": 550,
    # 460 → 490 on 19.08.2026: the sex guard on polygenic traits is applied where
    # the report is BUILT, not only where the score is computed, because
    # `prs_results.json` is a stored result that may predate the moment the
    # person recorded their sex.
    # 490 → 530 on 19.08.2026: what the polygenic computation does NOT do —
    # strand-ambiguous variants, missing variants summed as a zero dose, hard
    # genotypes, an unpinned reference panel — is printed on every report instead
    # of being remembered by whoever reads it. The sum happens in another
    # process, so these are not repairable here; that is precisely why they have
    # to be said rather than left implicit.
    # 530 → 580 on 21.08.2026: task 99. The three closed paths used to key on the
    # CARRIER — «is this an array» — and a chip does not stop being a chip by
    # arriving as a VCF. The room went to NARROW_INPUTS, the enumeration of the
    # measured classes that may not answer, and to one branch per class so that
    # each refusal names its own number instead of a shared sentence.
    # 580 → 650 on 24.08.2026. The provenance of the reference panel, and it
    # belongs here because it is a fact ABOUT the percentiles this module
    # already reports. Three things were being reported as one: the panel the
    # stored numbers were computed against, where that came from, and which
    # panel applies now. A flag said «ancestry stated» by asking the profile
    # rather than the file, so once the panel began to be determined from the
    # genome it went true for everybody with one while the numbers went on
    # being scored against a default. Splitting it out would put «what panel
    # is this percentile in» in a different file from the percentile.
    "genomics": 650,
    "sources": 180,
    "pgx": 900,
    "lifestyle": 980,
    "profile_view": 220,
}


def _modules():
    return {p.stem: p for p in ENGINE_DIR.glob("*.py")}


def _top_level_engine_imports(path):
    """Names of sibling engine modules imported at the TOP LEVEL of `path`."""
    with io.open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    siblings = set(_modules())
    out = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module and node.module in siblings:
                out.add(node.module)
    return out


class TestTheFacadeDefinesNothing(unittest.TestCase):
    def test_init_is_imports_and_a_docstring_only(self):
        with io.open(ENGINE_DIR / "__init__.py", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        offenders = [
            f"line {n.lineno}: {type(n).__name__}"
            for n in tree.body
            if not isinstance(n, (ast.Import, ast.ImportFrom))
            and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
        ]
        self.assertEqual(offenders, [],
                         "engine/__init__.py defines something. The facade re-exports; "
                         "logic lives in a domain module — put it there and import it: "
                         + "; ".join(offenders))


class TestDomainImportsStayAcyclic(unittest.TestCase):
    def test_no_top_level_cycle_between_engine_modules(self):
        graph = {name: _top_level_engine_imports(path)
                 for name, path in _modules().items() if name != "__init__"}
        # Kahn: if topological elimination stalls, whatever remains is cyclic.
        remaining = {k: set(v) for k, v in graph.items()}
        changed = True
        while changed:
            changed = False
            for name in [n for n, deps in remaining.items() if not deps]:
                remaining.pop(name)
                for deps in remaining.values():
                    deps.discard(name)
                changed = True
        self.assertEqual(remaining, {},
                         "top-level imports between engine modules form a cycle: "
                         f"{ {k: sorted(v) for k, v in remaining.items()} }. "
                         "If one back reference is genuinely needed, make it lazy "
                         "inside the function that needs it and say why — that is "
                         "how pgx reaches lifestyle._brief_life.")


class TestEveryModuleHasABudgetAndKeepsIt(unittest.TestCase):
    def test_no_module_without_a_budget_line(self):
        unbudgeted = sorted(set(_modules()) - set(LINE_BUDGETS))
        self.assertEqual(unbudgeted, [],
                         f"engine/{unbudgeted} has no size budget. A new domain module "
                         "is a decision — record it by adding a budget line to "
                         "LINE_BUDGETS in this test, in the same commit.")

    def test_no_budget_line_without_a_module(self):
        stale = sorted(set(LINE_BUDGETS) - set(_modules()))
        self.assertEqual(stale, [],
                         f"LINE_BUDGETS names modules that do not exist: {stale} — "
                         "a stale entry is a hole in the gate.")

    def test_every_module_fits_its_budget(self):
        for name, path in sorted(_modules().items()):
            with self.subTest(module=name):
                with io.open(path, encoding="utf-8") as fh:
                    lines = fh.read().count("\n")
                self.assertLessEqual(
                    lines, LINE_BUDGETS[name],
                    f"engine/{name}.py is {lines} lines against a budget of "
                    f"{LINE_BUDGETS[name]}. Two honest ways forward, both in this "
                    "commit: split the module along a domain line, or raise the "
                    "budget here with a reason about the capability that needed "
                    "the room. Growing past the wire silently is the one option "
                    "this test exists to remove.")


class TestTheFacadeCoversTheDomains(unittest.TestCase):
    def test_every_public_submodule_name_is_reachable_at_the_old_address(self):
        """engine.<name> has been the address for a year; a capability parked
        only at engine.<module>.<name> is invisible to all six consumers."""
        for name, path in sorted(_modules().items()):
            if name == "__init__":
                continue
            with io.open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in tree.body:
                public = None
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    public = node.name
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and not t.id.startswith("_"):
                            public = t.id
                if public:
                    with self.subTest(module=name, name=public):
                        self.assertTrue(
                            hasattr(engine_pkg, public),
                            f"engine/{name}.py defines public «{public}» but the "
                            "facade does not re-export it — add it to the module's "
                            "import block in engine/__init__.py.")

    def test_the_facade_does_not_shrink_below_the_v032_surface(self):
        """The 100 names the flat file exposed on the day of the split. Names
        may be ADDED; removing one is a compat break and says so."""
        frozen = """_recent DISCLAIMER _match_count _basis _basis_note _OPS
            _active_names_by_class _brief_num compute_phenotype check_drug_gene
            _latest _flag_value MOVE_MIN_PCT MOVE_MIN_SD _personal_move
            _decision_limits NEAR_LIMIT_FRACTION _near_limit _trend analyze_labs
            _latest_value _eval_condition _PRIORITY_ORDER _marker_last_date
            suggest_tests load_profile overview _metrics_overview _WATCHLIST
            metrics_summary genome_lookup genome_status clinvar_findings
            _penetrance_block acmg_findings apoe PRS_DISCLAIMER
            _annotate_prs_evidence prs_findings genome_updates longevity_findings
            _goal_series _goal_lv _goal_merge _goal_num _goal_now goal_dashboard
            _guidance_for _check_drug_online _classes_for _SEV_ORDER
            check_interactions _assess_gene _genome_for_drug _labs_for_drug
            _rsids_for_genes clinvar_for_drug _dose_context _own_safety_flags
            check_new_prescription provenance _RADAR_DOMAINS _wear_status
            lifestyle _prev_point _marker_health_at _marker_health health_radar
            _lifestyle_overview second_opinion _BRIEF_TOKEN _brief_lab
            _brief_life _brief_goal _brief_resolve _brief_newest
            _brief_snapshot_item lifestyle_brief _focus_nights _focus_mean
            _focus_metric _focus_lever_check _focus_clock _focus_journal_split
            _focus_evidence focus_dashboard _months_between _marker_direction
            _meets _best_of _guideline_candidate suggest_goal_targets
            _GOAL_MIN_POINTS _GOAL_MIN_SPAN_MONTHS _GOAL_MIN_GAIN _PCSK9_LOF
            _PCSK9_WAITING _LPA_PGS _copies_of lipid_genetics""".split()
        missing = sorted(n for n in frozen if not hasattr(engine_pkg, n))
        self.assertEqual(missing, [],
                         f"the facade lost {missing} — an address consumers and "
                         "tests have used since before the split. Removing a name "
                         "is a compatibility decision, not a refactoring side "
                         "effect; if it is deliberate, remove it from this frozen "
                         "list in the same commit and record it in the changelog.")

    def test_the_function_wins_the_lifestyle_name(self):
        """`lifestyle` is both a submodule and a function; the facade binds the
        function last, and this holds even after a direct submodule import."""
        import types
        import scholion.engine.lifestyle  # noqa: F401  -- the provocation
        self.assertIsInstance(engine_pkg.lifestyle, types.FunctionType,
                              "engine.lifestyle resolves to the submodule, not the "
                              "function — a year of callers just broke. Keep the "
                              "function's import after everything that can import "
                              "the submodule.")


if __name__ == "__main__":
    unittest.main()
