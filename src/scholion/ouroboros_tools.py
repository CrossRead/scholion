"""The Ouroboros plugin: registers the Scholion tools in the Ouroboros registry.

The Ouroboros mechanism: a module in ouroboros/tools/ exports get_tools() -> list[ToolEntry].
ToolEntry(name, schema, handler), handler(ctx, **args) -> str, the schema in OpenAI format.
Auto-discovery picks the module up on its own.

Installation: put this file (and the scholion package from src/) where Ouroboros sees them,
and point SCHOLION_PROFILE_DIR / SCHOLION_REPO_DIR at the user's profile folder. Below is a soft
import, so that the module can be tested outside Ouroboros as well.
"""
from __future__ import annotations

from . import engine
from . import format as fmt
from .i18n import t as _t

# --- soft import of the Ouroboros types -----------------------------------
try:
    from ouroboros.tools.registry import ToolEntry, ToolContext  # type: ignore
    _HAVE_OURO = True
except Exception:  # standalone mode (tests / development outside Ouroboros)
    _HAVE_OURO = False

    class ToolContext:  # a minimal stub
        pass

    class ToolEntry:  # repeats the Ouroboros signature
        def __init__(self, name, schema, handler, is_code_tool=False,
                     timeout_sec=360, mutates_worktree=False):
            self.name, self.schema, self.handler = name, schema, handler
            self.is_code_tool = is_code_tool
            self.timeout_sec = timeout_sec
            self.mutates_worktree = mutates_worktree


# --- handlers (ctx is ignored; the profile is read from SCHOLION_PROFILE_DIR) ---
def _h_check_drug(ctx: "ToolContext", drug: str = "") -> str:
    return fmt.drug_check(engine.check_drug_gene(drug))


def _h_analyze_labs(ctx: "ToolContext", markers: str = "") -> str:
    keys = [m.strip() for m in markers.split(",") if m.strip()] or None
    return fmt.labs_report(engine.analyze_labs(keys))


def _h_suggest_tests(ctx: "ToolContext") -> str:
    return fmt.tests_report(engine.suggest_tests())


def _h_genome(ctx: "ToolContext", rsid: str = "", gene: str = "") -> str:
    return fmt.genome_report(engine.genome_lookup(rsid=rsid or None, gene=gene or None))


def _h_prescription(ctx: "ToolContext", drug: str = "") -> str:
    return fmt.prescription_check(engine.check_new_prescription(drug))


def _h_metrics(ctx: "ToolContext") -> str:
    return fmt.metrics_report(engine.metrics_summary())


def _h_clinvar(ctx: "ToolContext") -> str:
    return fmt.clinvar_report(engine.clinvar_findings())


def _h_lifestyle(ctx: "ToolContext") -> str:
    return fmt.lifestyle_report(engine.lifestyle())


def _h_prs(ctx: "ToolContext") -> str:
    return fmt.prs_report(engine.prs_findings())


def _h_longevity(ctx: "ToolContext") -> str:
    return fmt.longevity_report(engine.longevity_findings())


def _h_goal(ctx: "ToolContext") -> str:
    return fmt.goal_report(engine.goal_dashboard())


def _h_phenoage(ctx: "ToolContext", panel: str = "latest") -> str:
    """Biological age. Refuses to compute on an incomplete panel — that is the rule, not a bug."""
    from scholion import phenoage as _pa  # noqa: E402
    # The words are ARGUMENTS a model may pass, compared against, never printed.
    if (panel or "").strip().lower() in ("panels", "--panels", "обзор"):
        return _pa.format_panels(_pa.panels_overview())
    return _pa.format_result(_pa.compute_panel(panel or "latest"))


def _h_provenance(ctx: "ToolContext", refresh: bool = False) -> str:
    """Reverse check: every profile point has a printed source report or a correct derivation.

    Complements reconcile, which goes the other way (report → profile). Verdicts:
    form / alt_form / derived_ok / derived_bad / derived_orphan / conflict / manual.
    «manual» does not mean «checked by hand», it means «confirmed by nothing»: such a point
    must not be presented as a fact.
    """
    from scholion import provenance as _pv  # noqa: E402
    return _pv.format_report(_pv.audit(refresh=bool(refresh)))


def _h_ingest_labs(ctx: "ToolContext", folder: str = "") -> str:
    from scholion import ingest_labs  # noqa: E402
    r = ingest_labs.ingest(folder)
    if not r.get("ok"):
        return f"⚠️ {r.get('error')}"
    files = "; ".join(f"{p['file']} ({p['date']}): {len(p['markers'])}" for p in r.get("per_file", []))
    return (_t("tool.ingest_labs.done", files=r['files_processed'],
               points=r['points_added'], skipped=r['skipped'])
            + (f"\n{files}" if files else ""))


# --- the reports a model asks for ABOUT THE PERSON --------------------------
# These nine were missing until v0.3.1, and the reason is worth naming because it
# is the project's own recurring one. `contract.py` was written after «Second
# opinion» lived only in the web tabs for half a year, and it enforces parity
# between the web and the CLI — while its own opening paragraph calls the plugin
# the THIRD face of one core. The map never covered it, so the plugin drifted
# exactly the way the web had, and a model connected through Ouroboros could not
# ask for the summary, the second opinion, or — worst of the three — the limits.
#
# `limits` is the one that mattered most. It is the answer to «what can this data
# NOT tell you», the capability the whole project is built around, and the model
# that most needed it was the one that could not call it.
def _h_overview(ctx: "ToolContext") -> str:
    return fmt.overview_report(engine.overview())


def _h_second_opinion(ctx: "ToolContext") -> str:
    return fmt.second_opinion_report(engine.second_opinion())


def _h_flag_rate(ctx: "ToolContext") -> str:
    """READ-ONLY: on what share of objects each flag fired.

    The cheap check this project asks for before any interpretation, and the one
    a model should run before repeating a flag back to a person: a threshold that
    marks nearly every object carries no information, however plausible it looks.
    """
    from scholion import prevalence as _pv  # noqa: E402
    return fmt.prevalence_report(_pv.report())


def _h_array(ctx: "ToolContext") -> str:
    """READ-ONLY: what a genotyping array carries, and what it cannot answer.

    The number a model most needs before it says anything about this person's
    genome: whether the input is a chip at all, which catalogue loci it carries,
    and which it never interrogated — so that «no variant found» is never
    repeated back as reassurance about a locus nobody looked at.
    """
    from scholion import array_genome as _arr  # noqa: E402
    return fmt.array_report(_arr.catalogue_coverage())


def _h_marker_propose(ctx: "ToolContext") -> str:
    """WRITES a dictionary RULE — never a value, and never a confirmation.

    The model may say «a row printed as X in unit Y is probably this marker».
    It may not say what the row's number was, and it may not confirm its own
    proposal: an entry stays `proposed` until a person vouches for it, and while
    it is proposed the marker is shown without any statement about the norm.

    That division is the whole design. A value read by a model would be a
    probabilistic number among reproducible ones; a RULE proposed by a model is a
    line of JSON that a person can check by eye, that reads the number with the
    same deterministic code as everything else, and that keeps working for
    everyone after the conversation is over.

    A reference range is deliberately not accepted here — it is a clinical claim,
    and the project's own contribution rules say a language model is not a source
    for one.
    """
    from scholion import markers_local as _ml  # noqa: E402
    names = [x for x in (ctx.args.get("names") or "").split(";") if x.strip()]
    return fmt.markers_local_report(_ml.propose(
        (ctx.args.get("key") or "").strip(),
        unit=(ctx.args.get("unit") or "").strip(),
        names_ru=names, names_en=[x for x in (ctx.args.get("names_en") or "").split(";") if x.strip()],
        by="model"))


def _h_lab_draw(ctx: "ToolContext") -> str:
    """WRITES: record why a day holds two draws and what stood between them.

    The one write the model is given here, and it is given deliberately: the
    engine can see that two measurements share a day but only a person knows that
    an infusion, a dose or a stress test stood between them, and the answer
    usually arrives in conversation rather than at a prompt. The model records
    what the person SAID; it does not infer the event, and it never touches a
    value — the same boundary as everywhere else, where numbers come from the
    form and the model may only add what it was told.
    """
    from scholion import store as _st  # noqa: E402
    day = (ctx.args.get("day") or "").strip()
    reason = (ctx.args.get("reason") or "").strip()
    between = (ctx.args.get("between") or "").strip()
    return fmt.draw_context_report(_st.set_draw_context(day, reason, between))


def _h_sources(ctx: "ToolContext") -> str:
    """READ-ONLY: the register of external sources and when each was imported.

    The listing only. Refreshing reaches the network and rewrites reference data
    on the person's machine; that is the owner's command to type, not a tool a
    model may fire. A model that can SEE the dates can say «your pharmacogenetic
    table was imported eight months ago» — which is the useful half.
    """
    from scholion import sources as _src  # noqa: E402
    return fmt.sources_report({"sources": _src.state(), "results": []})


def _h_rules(ctx: "ToolContext") -> str:
    """The safety canon, handed to whoever is about to speak for this product.

    A model that arrives through the skill is given 73 KB of instruction and this
    canon with it. A model that arrives through the tool interface is given a list
    of tools and nothing else — it knows what it may call and not what it must not
    say. Every answer already carries the one-line disclaimer, and a disclaimer is
    a boundary, not an instruction.

    So the canon is a tool. It is the only way that works on every host: a field
    in the handshake is ignored by clients that do not read it, and a document on
    disk is not reachable from a sandbox, but a tool the model can see it can
    call.
    """
    from pathlib import Path as _P
    path = _P(__file__).resolve().parent / "skill" / "ASSISTANT-RULES.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        # An incomplete build. Saying nothing here would read as «this product has
        # no rules», which is the worst of the available untruths.
        return _t("skill.file_missing", path=str(path))


def _h_limits(ctx: "ToolContext") -> str:
    from scholion import limits as _lim  # noqa: E402
    return fmt.limits_report(_lim.report())


def _h_radar(ctx: "ToolContext") -> str:
    return fmt.radar_report(engine.health_radar())


def _h_focus(ctx: "ToolContext") -> str:
    return fmt.render_focus(engine.focus_dashboard())


def _h_brief(ctx: "ToolContext") -> str:
    return fmt.render_brief(engine.lifestyle_brief())


def _h_acmg(ctx: "ToolContext") -> str:
    return fmt.acmg_report(engine.acmg_findings())


def _h_goal_suggest(ctx: "ToolContext") -> str:
    """Proposes targets; it does NOT write them.

    The write path stays behind `--write` on the command line and behind a button
    in the interface. A model that could set somebody's health goals by calling a
    tool is a model changing the profile, and the canon it is handed says it does
    not do that.
    """
    return fmt.goal_suggest_report(engine.suggest_goal_targets())


def _h_lipid_genetics(ctx: "ToolContext") -> str:
    return fmt.lipid_genetics_report(engine.lipid_genetics())


# --- schemas (OpenAI function-calling) -------------------------------------
# A description is the only thing the model reads before deciding to call a tool, so it
# is text like any other and lives in the catalogue. It is built at CALL time rather than
# at import: the language of a run is not known when the module is loaded.
_TOOLS = (
    ("sch_check_drug_gene", ("drug",), ["drug"], _h_check_drug),
    ("sch_analyze_labs", ("markers",), [], _h_analyze_labs),
    ("sch_suggest_tests", (), [], _h_suggest_tests),
    ("sch_genome_lookup", ("rsid", "gene"), [], _h_genome),
    ("sch_check_prescription", ("drug",), ["drug"], _h_prescription),
    ("sch_health_metrics", (), [], _h_metrics),
    ("sch_lifestyle", (), [], _h_lifestyle),
    ("sch_clinvar_findings", (), [], _h_clinvar),
    ("sch_prs", (), [], _h_prs),
    ("sch_longevity", (), [], _h_longevity),
    ("sch_goal", (), [], _h_goal),
    ("sch_phenoage", ("panel",), [], _h_phenoage),
    ("sch_provenance", ("refresh",), [], _h_provenance),
    ("sch_ingest_labs", ("folder",), ["folder"], _h_ingest_labs),
    ("sch_overview", (), [], _h_overview),
    ("sch_second_opinion", (), [], _h_second_opinion),
    ("sch_limits", (), [], _h_limits),
    ("sch_rules", (), [], _h_rules),
    ("sch_sources", (), [], _h_sources),
    ("sch_lab_draw", ("day", "reason", "between"), ["day"], _h_lab_draw),
    ("sch_marker_propose", ("key", "names", "unit", "names_en"), ["key", "names"],
     _h_marker_propose),
    ("sch_array", (), [], _h_array),
    ("sch_flag_rate", (), [], _h_flag_rate),
    ("sch_radar", (), [], _h_radar),
    ("sch_focus", (), [], _h_focus),
    ("sch_brief", (), [], _h_brief),
    ("sch_acmg", (), [], _h_acmg),
    ("sch_goal_suggest", (), [], _h_goal_suggest),
    ("sch_lipid_genetics", (), [], _h_lipid_genetics),
)

# The JSON type of every parameter. Kept next to the tools rather than inside the
# catalogue: a type is a contract with the model's function-calling, not a phrase.
_PARAM_TYPE = {"refresh": "boolean"}


def _schema(name: str, params, required) -> dict:
    props = {p: {"type": _PARAM_TYPE.get(p, "string"),
                 "description": _t(f"tool.{name}.param.{p}")} for p in params}
    schema = {"name": name,
              "description": _t(f"tool.{name}.description"),
              "parameters": {"type": "object", "properties": props}}
    if required:
        schema["parameters"]["required"] = list(required)
    return schema


def get_tools():
    """The entry point for the Ouroboros auto-discovery."""
    return [ToolEntry(name, _schema(name, params, required), handler)
            for name, params, required, handler in _TOOLS]


if __name__ == "__main__":  # a quick self-test of the wrapper
    for t in get_tools():
        print(f"[tool] {t.name}: {t.schema['description'][:60]}…")
    # The Russian drug name is the point of the self-test: it proves the tool answers a
    # query typed the way the owner types it, whatever language the report comes out in.
    print("\n--- sch_check_drug_gene('клопидогрел') ---")
    print(_h_check_drug(ToolContext(), drug="клопидогрел")[:300])
