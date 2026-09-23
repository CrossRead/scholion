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
    # task 200 put a domain of its own (routes) and the gate's LINKS on the facade
    "__init__": 250,     # imports only -- claim 1 keeps it honest anyway
    "_helpers": 250,
    # Added 08.09.2026 with task 132: the two quantities printed beside a
    # polygenic percentile — its stability under another reference population
    # or another model, and the model's informativeness. It is about the QUALITY
    # of a stored score and computes none; `genomics.py` was at its wire, and
    # the line between «what the score is» and «what the score is worth» is a
    # domain line, not a page break.
    "prs_quality": 140,
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
    # 580 → 680 on 28.08.2026. One capability, and it belongs beside the two
    # above for the same reason they belong beside each other: it answers «did
    # this person's number really move», and that question already lives here.
    # `_personal_move` asks it of the last point against the personal baseline;
    # `change_floor` asks it of two consecutive points, which is the comparison
    # `_trend` prints as «↑ 44 %» and which had no notion of scatter at all.
    # Splitting them would put one question in two files — the split that
    # produced the corridor defects named above.
    # 680 → 710 on 08.09.2026. The age axis of the corridor rule, beside the
    # sex axis added the same day and for the same reason both sit here: «may
    # this number be compared with that corridor» is one question, and IGF-1's
    # band is as much a part of it as HDL's sex. A marker's corridor is refused
    # for one nearer reason, and the two axes have to be read in one place for
    # «one reason» to be true.
    # 710 → 730 the same day: two more words of the same rule — a corridor that
    # could not be checked (`unreviewed`, lent to nobody) and a test that
    # exists for one sex only (PSA), which is not a corridor question at all
    # and had to be told apart from one in the same place.
    # 730 → 760 the same evening, task 142: the corridor printed on the form
    # travels with the point and the verdict stands on it, with whose corridor
    # it is and whether the flags of a series still share one ruler. Third
    # raise in a day on the same question — the corridor rule has become a
    # domain of its own, and task 143 is to move it out; the budget is raised
    # here so that the release carries the fix, and the split follows.
    # 760 → 680 on 12.09.2026, task 143: the split followed. «Which corridor
    # applies to this point and why» and «do the flags of this series share
    # one ruler» now live in `corridor.py`; `analyze_labs` places their answers
    # and computes none of them. The budget goes back to where it stood before
    # the three raises, because the capability they paid for is no longer here.
    # 680 → 690 on 12.09.2026, task 168 step 6: a marker's row names the system
    # whose panel holds it, so the card of a system is reachable from the marker
    # on every face — one field and the lazy helper that reads the domain file.
    # +10 for the list of every system a marker counts in (task 200).
    # task 200: the two conditions that ask for a test nobody has ever taken
    "labs": 760,
    # Added 12.09.2026, task 170: the clinician's target beside the corridor —
    # what a treatment aims at, told apart from what a laboratory calls normal.
    # It landed inside labs.py first and pushed it 90 lines over its wire; the
    # same domain line as corridor.py, drawn the same day.
    "targets": 160,
    # Added 12.09.2026 with task 143, out of `labs`: one question, «may this
    # number be compared with that corridor», that had raised the budget of
    # its host three times in one day. Sex, age band, `unreviewed`, a test of
    # one sex, the form's own printed range, and whether a series' flags still
    # share one ruler — every refusal is decided here and named once. Sized at
    # current length plus a third; the next axis of the same question (a
    # corridor bound to a laboratory or a method, say) belongs here too.
    "corridor": 250,
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
    # 650 → 720 on 09.09.2026. The catalogue names things and the stored file
    # counts them — one join, used by both the polygenic layer and the longevity
    # one, plus the verdict recomputed from the catalogue rather than trusted
    # from a file written months ago. It belongs beside the two readers it
    # serves: a shared helper one module away would be a third place to ask
    # «whose string is this», which is the question that produced the defect.
    # 720 → 780 on 09.09.2026. An exome stopped being refused as «too narrow»:
    # the class it now gets opens ClinVar and the ACMG list and keeps polygenic
    # scores shut, and an answer given on it carries the boundary of the input it
    # was read from. That is a second gate beside the first and the sentence that
    # travels with an OPEN path — both belong where the paths are, because the
    # rule they encode is «which question may this file answer», which is the
    # only subject this module has.
    # 780 → 900 on 11.09.2026. A gene is now asked of every shelf that holds
    # anything about one — the curated catalogue, the ClinVar scan matched by
    # coordinate, the shipped ACMG panel, coverage — and each reports what it
    # holds, that it holds nothing, or that it could not be asked and why. The
    # room went to `clinvar_for_gene` and `gene_layers`. Before them the only
    # path a person takes for a gene read one shelf and answered «not in the
    # coordinate reference», which is a statement about that shelf and reads as
    # a statement about the genome; a clinician was told there was nothing to
    # say about the bile-acid transporters while the ClinVar table held 386
    # findings.
    # 900 → 990 on 11.09.2026. How well THIS gene was read now travels with the
    # answer about it, judged against the file's own middle rather than a
    # clinical bar — measured first: at 20× on a 30× genome the median callable
    # fraction is 79.8 % and no gene of ninety-three reaches 95 %, so an absolute
    # threshold fires on 89 of them and measures the depth curve instead of the
    # gene. Against the median, eight fire, and they are the ones hard to
    # sequence for known reasons.
    # 990 → 1020 on 12.09.2026. The gene frame stops swallowing: a scan that
    # was not run carries the scan's own sentence instead of a phrase about
    # coordinates, the truncation warning travels into the frame, and each
    # `except` that used to collapse into «not measured» or `pass` names its
    # failure as a state of its own. Reporting costs lines; silence cost a
    # false «clean» on a hereditary-cancer gene.
    # 1020 → 1060 on 12.09.2026. A gene answers with the verdict somebody
    # wrote about it. One such sentence was found written, verified, translated
    # and read by nothing at all; the shelf that now carries it exists so that
    # the next one cannot be written for nobody.
    # 1060 → 1100 on 12.09.2026. What licenses saying anything about a locus is
    # decided here, in five named states, so that the one which licenses nothing
    # can be printed instead of leaving a genotype to stand on its own.
    # New on 12.09.2026. The link between a prescription and a gene has a
    # class, and the class decides what may be said about it; three of the five
    # classes are read from a curated file and never derived, so the module is
    # as much a gate as a classifier.
    # 200 → 280 on 12.09.2026. A clinician read the fifth class and answered
    # that «the gene is absent» is a claim about a person we never made. It is
    # now measured against the person's own file, in four states, and the
    # measurement lives here.
    # New on 12.09.2026. The second entry: a class of disease instead of a
    # prescription. It shares the vocabulary with `decision` and not the
    # question — there the gene list is derived from a drug, here it is fixed in
    # advance and comes from a published panel, which is a different contract
    # with the reader and deserves its own file.
    # New on 12.09.2026, task 171. What the three list-generating entries share
    # — the five kinds, the gate that counts what it drops, the pending row, a
    # gene row with its reading, and the four-state verdict with the unread
    # count inside it — lives here once, because the refusal sentence is the
    # product and three copies of it drift into three sentences. `decision` and
    # `screening` shrank by what moved out.
    # 175 added the one rule for whether a gene's bases were read.
    # task 200 / owner 17.09.2026: a gene the file read with its depth
    # unmeasured is a third state, and a list that is not read whole says
    # WHICH reason and what closes it — both live here
    "panel_form": 400,
    # New on 12.09.2026, task 168 (step 3). The third entry: a body system of
    # the radar, with its genetic half read from a curated file by POSITION,
    # the evidence mode of every row, the questions for a clinician and the
    # three baskets of the next step. Screen-less in this step; sized for the
    # seven layers it assembles and the reasons each of them can be absent.
    # 700 → 900 the same day: the monogenic half is MERGED from a base with
    # a version (GenCC, every submitter side by side) and the clinician's
    # signed exclusions on top of it — composition from the base, exceptions
    # from her — and the merge, the carrier rule per gene and the exclusion
    # block are what the room went to.
    # 900 → 1060 on 12.09.2026, task 168 steps 4–7: the two layers that were
    # placeholders became real — the current prescriptions acting on a system
    # through the class→system map, and the clinician's target beside the
    # corridor with its question — plus the composition a prescription
    # inherits and the two counts the second ring is drawn from.
    # 1060 → 1300 on 13.09.2026, task 178: the common variation of a system
    # became a block of its own — the pinned polygenic models a map places on
    # the system, each with the person's percentile, one question per reliable
    # score above the line, a patient's projection of the rows — and the genome
    # basket learned to say what a full genome would close for a person who
    # has an array, an exome, a panel or no file.
    # 13.09.2026: the ACMG scan counted as the ClinVar source for its 84 genes,
    # a reason as a sentence with the step that closes it, the genome basket
    # grouped by reason — found on a reference genome (1300 → 1340).
    # 13.09.2026: the segment panels read their unreadable genes (a gene beside its
    # pseudogene, a repeat) and fold the questions waiting on one untaken marker
    # into one (1340 → 1380; 1351 lines when raised).
    # 13.09.2026: a row says WHO signed its sentence — the signer the file names
    # becomes a state the reader is told about, an unknown signer is not taken
    # for a signature, and the count and date of the signing reach the summary
    # (1380 → 1400; 1392 lines when raised).
    # 13.09.2026: an expectation is asked only of the genotype it names, the
    # corridor open at one end is written by the end it has, and each half of
    # the list carries its own read count (1400 → 1430; 1419 when raised).
    # 1430 → 1450 on 14.09.2026: every panel position is carried as a state in
    # both registers, so the radar can say the panel was checked whole.
    # +20: a system's long panel beside its score, and markers in two systems (task 200).
    # task 200: the chain link, the intake route, the load a fasting corridor
    # cannot stand in for, and the block that answers a decision to correct
    "system_panels": 1600,
    "screening": 270,
    # 300 → 340 on 12.09.2026, task 168 step 7: a prescription's genes are no
    # longer a hand-written list but are inherited through the system its
    # class acts on, and the drug entry became the clinician's exceptions —
    # a sentence, a class, or a signed exclusion, the unsigned one counted.
    "decision": 340,
    # 13.09.2026: a locus carried in ONE copy is judged against one copy — the
    # copies are measured from the coverage table itself rather than asked of
    # a profile, and the reference point is the median of the same kind of
    # locus (1100 → 1160; 1148 lines when raised).
    "genomics": 1160,
    # 180 → 200 on 12.09.2026: the build's age says WHY it is unknown — no
    # journal, a heading that drifted, or a read that raised — instead of
    # one word for all three.
    "sources": 200,
    # 900 → 940 on 10.09.2026. «Which prescriptions is this compared against» is
    # now asked rather than assumed: a stopped or paused entry takes no part, and
    # what was left out travels with the answer instead of vanishing from it. Both
    # halves belong here — the check and the statement of its own baseline are one
    # capability, and separating them is how a comparison came to be silent about
    # what it did not include.
    # 940 → 960 on 12.09.2026: the snapshot date of the guideline copy says
    # «unreadable (…)» when the provenance could not be read, instead of the
    # empty string that a provenance WITHOUT a date also returns.
    # 960 → 1010 on 12.09.2026. Two answers that were empty now say what they
    # are: how well the gene was read travels with every gene on the
    # prescription path, and a missing guideline row carries the written reason
    # there is none instead of the generic sentence that there is none.
    # 1010 → 1160 on 22.09.2026 (0.5.7 review). Five answers that read as
    # reassuring from missing input now say what is missing: an unread second
    # gene of a two-gene drug, a called phenotype the table has no word for,
    # every CPIC gene of the drug reaching the prescription verdict, a genotype
    # counted only when its letters are the locus's own, and drug names matched
    # as whole words so a guideline is never printed for a different medicine.
    # All five are the drug-gene answer itself; none is a domain to split along.
    "pgx": 1160,
    # 980 → 1010 on 08.09.2026. `_placement` — which of a system's markers a
    # mark on the figure is about, and the score of the markers made in that
    # one place. It belongs beside `health_radar` because the domain's own
    # score is computed from the same list two lines above: splitting them
    # would put a panel in one file and that panel's places in another, and
    # the two would drift the way every pair of copies in this project has.
    "lifestyle": 1010,
    # A domain of its own on 14.09.2026: the review of a brief block — what
    # arrived after its wording was read, and a request built from it. It
    # reads the brief and the labs and writes nothing.
    "brief_review": 160,
    # 14.09.2026: the panel of a system as the catalogue describes it, for the
    # clinician — references and sentences, no genome, no labs.
    "panel_catalogue": 120,
    "pgx_labels": 60,
    # The gate a curated panel row passes (task 199): the locus rule, the
    # impersonal review, the evidence legend — split out of system_panels.
    "panel_gate": 330,
    # A system's long laboratory panel, shown and never scored (task 200).
    # 120 → 190 on 21.09.2026 (task 205 D, E): the panel author's pathway groups,
    # value-only markers and companion markers. A split was tried and undone: a
    # new module has no accepted reach number until the suite is measured on the
    # machine the baseline belongs to, and this is one reading of one panel.
    "panel_labs": 190,
    # task 200: the correction-route block — a curated object, its gate and its
    # grouping; the rules themselves live in knowledge/, not here
    "routes": 230,
    # tasks 175/201/203: what «read» means and why a row was not read — out of panel_form
    "panel_reading": 200,
    # tasks 199/201: a person's state at one position — out of system_panels
    "panel_genotype": 170,
    # task 199: what the book holds beyond its rows — groups, panels on demand,
    # the local note, the marker index; lifted out of system_panels on 18.09.2026
    "panel_book": 260,
    # 220 → 240 on 12.09.2026: the overview's age line names why it could not
    # be computed rather than answering «unknown» with nothing beside it.
    "profile_view": 240,
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
