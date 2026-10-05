"""The Ouroboros plugin: registers the Scholion tools in the Ouroboros registry.

The Ouroboros mechanism: a module in ouroboros/tools/ exports get_tools() -> list[ToolEntry].
ToolEntry(name, schema, handler), handler(ctx, **args) -> str, the schema in OpenAI format.
Auto-discovery picks the module up on its own.

Installation: do not copy this file — it imports its neighbours inside the package, and
a copy in Ouroboros's tools package cannot find them. Place one line there instead,
`from scholion.ouroboros_tools import get_tools` (README, «A plugin for Ouroboros»), and
point SCHOLION_PROFILE_DIR / SCHOLION_REPO_DIR at the user's profile folder. Below is a soft
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
def _reported(data, render):
    """A handler that builds a structure and renders it — and can hand back both.

    `both(**args)` is what the MCP server calls when a client reads structured
    tool output: the structure the report was rendered from, not a second one
    computed beside it, so the text and the JSON cannot describe different runs.
    """
    def handler(ctx: "ToolContext", **kwargs) -> str:
        return render(data(**kwargs))

    def both(**kwargs):
        r = data(**kwargs)
        return render(r), r
    handler.both = both
    return handler


def _yes(value) -> bool:
    """A flag as a host may send it: a boolean, or the word for one."""
    return value is True or str(value).strip().lower() in ("true", "yes", "1")


def _with_second_reading(flag: str, first, second):
    """One tool, two readings of one subject — the second behind a flag.

    `first` and `second` are (data, render) pairs. The tool door is kept short on
    purpose: a model choosing among forty names chooses worse than among thirty,
    so a reading that belongs to a subject a tool already covers is reached
    through that tool rather than given a name of its own. Which command each
    reading answers to is written in `contract.PLUGIN` and `contract.PLUGIN_ARGS`,
    and the manifest prints the call in full.
    """
    def pick(kwargs):
        kwargs = dict(kwargs)
        chosen = second if _yes(kwargs.pop(flag, False)) else first
        return chosen, kwargs

    def handler(ctx: "ToolContext", **kwargs) -> str:
        (data, render), rest = pick(kwargs)
        return render(data(**rest))

    def both(**kwargs):
        (data, render), rest = pick(kwargs)
        r = data(**rest)
        return render(r), r
    setattr(handler, "both", both)
    return handler


_h_check_drug = _reported(lambda drug="": engine.check_drug_gene(drug),
                          lambda r: fmt.drug_check(r))
def _marker_catalogue(markers: str = ""):
    from scholion import core as _core  # noqa: E402
    return {"markers": _core.marker_catalog()}


# `markers` takes KEYS, and nothing a model could call printed them: the labs
# report names a marker the way a form does. The catalogue is the second reading.
_h_analyze_labs = _with_second_reading(
    "catalogue",
    (lambda markers="": engine.analyze_labs([m.strip() for m in markers.split(",") if m.strip()] or None),
     lambda r: fmt.labs_report(r)),
    (_marker_catalogue, lambda r: fmt.markers_report(r)))
_h_suggest_tests = _reported(lambda: engine.suggest_tests(), lambda r: fmt.tests_report(r))


def _h_genome(ctx: "ToolContext", rsid: str = "", gene: str = "") -> str:
    return fmt.genome_report(engine.genome_lookup(rsid=rsid or None, gene=gene or None))


_h_prescription = _reported(lambda drug="": engine.check_new_prescription(drug),
                            lambda r: fmt.prescription_check(r))
_h_metrics = _reported(lambda: engine.metrics_summary(), lambda r: fmt.metrics_report(r))
_h_clinvar = _reported(lambda: engine.clinvar_findings(), lambda r: fmt.clinvar_report(r))


def _h_lifestyle(ctx: "ToolContext") -> str:
    return fmt.lifestyle_report(engine.lifestyle())


_h_prs = _reported(lambda: engine.prs_findings(), lambda r: fmt.prs_report(r))
_h_longevity = _reported(lambda: engine.longevity_findings(), lambda r: fmt.longevity_report(r))
_h_goal = _reported(lambda: engine.goal_dashboard(), lambda r: fmt.goal_report(r))


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


def _args(ctx: "ToolContext", given: dict) -> dict:
    """Arguments by keyword, or off `ctx.args` for a host that still passes them there.

    Three handlers read `ctx.args` while the other twenty-nine took keywords, and
    the MCP server and the Hub both call `handler(ctx, **args)` — so the one
    write a model was given, `sch_focus_log`, answered every MCP call with a
    TypeError from 16.08.2026 until the audit of 12.09.2026 found it. The test
    that covered it set `ctx.args` by hand, which is why it stayed green.
    """
    # Keywords win whenever one of them carries a value; `ctx.args` is read
    # only when every keyword is at its default, so a host that fills BOTH and
    # passes empty keywords is answered from `ctx.args` — the one shape no
    # known host produces.
    if any(v not in (None, "", False) for v in given.values()):
        return given
    old = getattr(ctx, "args", None)
    return dict(old) if isinstance(old, dict) and old else given


def _h_ingest_labs(ctx: "ToolContext", folder: str = "") -> str:
    import json
    import os
    import shlex
    import subprocess
    import sys
    import tempfile
    from scholion import core, container, ingest_labs
    # An empty folder name is refused HERE as well as in the engine: `Path("")`
    # is the current directory, and a tool called with no folder once
    # transcribed every PDF under the process's working directory into the
    # profile (12.09.2026, in an audit harness — the owner's own reports).
    if not (folder or "").strip():
        return "⚠️ " + _t("ingest_labs.folder_not_named")
    inputs = ingest_labs._inputs(folder)
    if not inputs["ok"]:
        return "⚠️ " + inputs["error"]
    # The parent must witness the first naming itself: a child's lazy naming
    # is indistinguishable from somebody replacing the pinned container.
    container.gate()
    if container.capture()["id"] is None:
        container.ensure()
    # A worker can be stopped before Hub's hard 120-second limit. The importer
    # checkpoints completed files; a killed worker never marks its current file.
    env = dict(os.environ)
    env["SCHOLION_PROFILE_DIR"] = str(core.profile_dir())
    env["SCHOLION_REPO_DIR"] = str(core.repo_dir())
    command = [sys.executable, "-m", "scholion", "ingest-labs", folder, "--json"]
    try:
        with tempfile.TemporaryDirectory(prefix="scholion-ingest-worker-") as isolated:
            env["SCHOLION_WORKSTATION"] = os.path.join(isolated, "no-workstation.json")
            worker = subprocess.run(command, capture_output=True, text=True, env=env, timeout=105)
    except subprocess.TimeoutExpired:
        return "⚠️ " + _t("tool.host_ingest_timeout", command="scholion ingest-labs " + shlex.quote(folder))
    try:
        r = json.loads(worker.stdout)
    except (ValueError, TypeError):
        return "⚠️ " + (worker.stderr.strip() or _t("web.common.error"))
    core.reset_cache()
    if not isinstance(r, dict):
        return "⚠️ " + _t("web.common.error")
    if not r.get("ok"):
        return fmt.ingest_labs_report(r) if r.get("errors") else f"⚠️ {r.get('error')}"
    # The same report the command line prints — the per-file table used to be
    # a private summary here, and it read a key (`date`) the engine never wrote.
    return fmt.ingest_labs_report(r)


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
def _snapshot_text(r) -> str:
    import json as _json
    return _json.dumps(r, ensure_ascii=False, indent=2)


# The snapshot is the overview with nothing phrased: whose profile this is, which
# marker keys and which pharmacogenes it holds, which target genes have no data.
_h_overview = _with_second_reading(
    "snapshot",
    (lambda: engine.overview(), lambda r: fmt.overview_report(r)),
    (lambda: engine.load_profile(), _snapshot_text))
_h_second_opinion = _reported(lambda: engine.second_opinion(), lambda r: fmt.second_opinion_report(r))


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


def _h_marker_propose(ctx: "ToolContext", key: str = "", names: str = "",
                      unit: str = "", names_en: str = "") -> str:
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
    a = _args(ctx, {"key": key, "names": names, "unit": unit, "names_en": names_en})
    names_ru = [x for x in (a.get("names") or "").split(";") if x.strip()]
    return fmt.markers_local_report(_ml.propose(
        (a.get("key") or "").strip(),
        unit=(a.get("unit") or "").strip(),
        names_ru=names_ru, names_en=[x for x in (a.get("names_en") or "").split(";") if x.strip()],
        by="model"))


def _h_lab_draw(ctx: "ToolContext", day: str = "", reason: str = "", between: str = "") -> str:
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
    a = _args(ctx, {"day": day, "reason": reason, "between": between})
    return fmt.draw_context_report(_st.set_draw_context(
        (a.get("day") or "").strip(), (a.get("reason") or "").strip(),
        (a.get("between") or "").strip()))


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
        text = path.read_text(encoding="utf-8")
    except OSError:
        # An incomplete build. Saying nothing here would read as «this product has
        # no rules», which is the worst of the available untruths.
        return _t("skill.file_missing", path=str(path))
    return text.rstrip("\n") + "\n" + _canon_through_this_door(text)


def _canon_through_this_door(text: str) -> str:
    """The commands the canon names, as the calls this door answers them by.

    The canon is written once, for every door, and it names COMMANDS: «run
    `selfcheck` before any negative conclusion», «`genome-status` prints which
    paths this input opens». A model that reads it here holds tools, not a
    shell, and a rule naming something it cannot call is a rule it cannot
    follow. The table is generated from the contract, so it cannot name a tool
    that is not there; a command the canon names and no tool answers fails the
    build (`contract.check_door_claims`).
    """
    from scholion import contract as _c  # noqa: E402
    rows = []
    for cmd in _c.commands_named_in(text):
        call = _c.tool_call(cmd)
        if call:
            rows.append(f"- `{cmd}` — {call}")
        elif cmd in _c.CANON_FORBIDS:
            # Named by the canon only to say when a model may not start it.
            rows.append(f"- `{cmd}` — {_t('rules.no_tool_persons_act')}")
    if not rows:
        return ""
    return "\n---\n\n" + _t("rules.through_this_door") + "\n\n" + "\n".join(rows) + "\n"


def _evidence_legend():
    from scholion.engine import panel_gate as _pg  # noqa: E402
    return _pg.legend()



def _h_rules_or_levels(ctx: "ToolContext", levels=False) -> str:
    """The canon — or, with `levels`, what each evidence level A–E means.

    An answer prints a level as a letter, and the letter decides whether a
    conclusion may follow at all. The legend was written down as travelling
    inside every such answer; in the laboratory report it did not.
    """
    if _yes(levels):
        return fmt.evidence_levels_report(_evidence_legend())
    return _h_rules(ctx)



def _h_limits(ctx: "ToolContext", bed: bool = False, panel: str = "") -> str:
    from scholion import limits as _lim  # noqa: E402
    a = _args(ctx, {"bed": bed, "panel": panel})
    if a.get("bed"):
        panels = [x.strip() for x in str(a.get("panel") or "").split(",") if x.strip()]
        return fmt.weak_bed_report(_lim.weak_regions_bed(panels))
    return fmt.limits_report(_lim.report())


_h_radar = _reported(lambda: engine.health_radar(), lambda r: fmt.radar_report(r))


def _h_focus(ctx: "ToolContext") -> str:
    return fmt.render_focus(engine.focus_dashboard())


def _h_focus_log(ctx: "ToolContext", date: str = "", alcohol: str = "", atenolol: bool = False,
                 late_meal: bool = False, note: str = "", factors: str = "") -> str:
    """The one tool that writes. See `contract.DICTATED` for why it may.

    It records what the person said happened — a glass of wine, a late meal, a
    dose taken — and nothing else. What it must NOT be handed is an inference:
    the journal is the evidence a later analysis reads, and an entry that already
    contains the conclusion makes that analysis circular.
    """
    from . import store
    a = _args(ctx, {"date": date, "alcohol": alcohol, "atenolol": atenolol,
                    "late_meal": late_meal, "note": note, "factors": factors})
    date = (a.get("date") or "").strip()
    res = store.add_focus_entry(
        date,
        alcohol=(a.get("alcohol") or "").strip(),
        atenolol=bool(a.get("atenolol")),
        late_meal=bool(a.get("late_meal")),
        note=(a.get("note") or "").strip(),
        factors=[x.strip() for x in str(a.get("factors") or "").split(",") if x.strip()])
    if not res.get("ok"):
        return f"⚠️ {res.get('error', '')}"
    return _t("tool.sch_focus_log.done", date=date, action=res.get("action", ""))


def _h_brief(ctx: "ToolContext") -> str:
    return fmt.render_brief(engine.lifestyle_brief())


_h_acmg = _reported(lambda: engine.acmg_findings(), lambda r: fmt.acmg_report(r))


def _h_goal_suggest(ctx: "ToolContext") -> str:
    """Proposes targets; it does NOT write them.

    The write path stays behind `--write` on the command line and behind a button
    in the interface. A model that could set somebody's health goals by calling a
    tool is a model changing the profile, and the canon it is handed says it does
    not do that.
    """
    return fmt.goal_suggest_report(engine.suggest_goal_targets())


def _h_screen(ctx: "ToolContext", disease_class: str = "") -> str:
    return fmt.screen_report(engine.screen(disease_class or None))


def _h_lipid_genetics(ctx: "ToolContext") -> str:
    return fmt.lipid_genetics_report(engine.lipid_genetics())


def _h_version(ctx: "ToolContext") -> str:
    """READ: this build, the version the data was last used with, what the releases in
    between ask to recompute — and whether a newer build is out (the package registry,
    at most once a day, never offline). Writes nothing."""
    from scholion import updates as _upd, upgrade as _upg  # noqa: E402
    return fmt.version_report(_upd.status()) + "\n\n" + fmt.update_report(_upg.notice())


def _h_update(ctx: "ToolContext", confirm=False) -> str:
    """INSTALLS the newer build into this environment — only with confirm=true, which the
    description reserves for the person's own yes in this conversation."""
    from scholion import upgrade as _upg  # noqa: E402
    yes = confirm is True or str(confirm).strip().lower() in ("true", "yes", "1")
    return fmt.update_install_report(_upg.install(confirm=yes))


def _h_recompute(ctx: "ToolContext", confirm=False) -> str:
    """READ by default: what this build asks the person's own data to recompute and why each
    step can or cannot run. With confirm=true it STARTS those steps in the background —
    reserved for the person's own yes in this conversation."""
    from scholion import recompute as _rc  # noqa: E402
    yes = confirm is True or str(confirm).strip().lower() in ("true", "yes", "1")
    if not yes:
        return fmt.recompute_plan_report(_rc.plan())
    return fmt.recompute_run_report(_rc.start_in_background())



# --- reads the canon sends a model to, and the door did not carry ----------
# An outside report against 0.4.11 found the shape: the canon names a command
# («`genome-status` prints which paths this input opens», «run `selfcheck`
# before any negative conclusion about labs»), the tool door had no such tool,
# and the reason written down for the absence — «already inside overview» — was
# not true: the overview carries a COUNT of prescriptions and the word
# «connected». A model could run a prescription check against a regimen it
# could not read, and the only route left to it was to ask the person to recite
# the list — the recalled answer the canon forbids. All four are reads.
def _medications():
    return engine.medications_view()


def _genome_status():
    from scholion import core as _core  # noqa: E402
    return {**engine.genome_status(), "gaps": _core.genome_gaps()}


# Neither reading takes a folder. The audit rebuilds the record of which form
# each point came from, and a model that could point it at a folder of its own
# choosing could rewrite that record from forms that are not the person's. The
# folder is the one the profile declares; naming another is the person's command.
def _selfcheck():
    from scholion import reconcile as _rec, updates as _upd  # noqa: E402
    res = _rec.reconcile(None)
    if isinstance(res, dict):
        res["skill_copies"] = _upd.skill_copies()
    return res


def _selfcheck_text(r) -> str:
    from scholion import reconcile as _rec  # noqa: E402
    return _rec.selfcheck_summary(r) + fmt.skill_copies_lines(r.get("skill_copies"))


def _capabilities():
    from scholion import contract as _c  # noqa: E402
    return _c.capabilities()


def _reconcile():
    from scholion import reconcile as _rec  # noqa: E402
    return _rec.reconcile(None)


_h_medications = _reported(_medications, lambda r: fmt.medications_report(r))
# What a fresh ClinVar changed for this person is a fact about the same file the
# status describes, and it had no door at all.
_h_genome_status = _with_second_reading(
    "updates",
    (_genome_status, lambda r: fmt.genome_status_report(r)),
    (lambda: engine.genome_updates(), lambda r: fmt.genome_updates_report(r)))
# The banner is the short reading; the audit behind it — which value is on which
# form and absent from the profile — is the long one, over the same run.
_h_selfcheck = _with_second_reading(
    "full",
    (_selfcheck, _selfcheck_text),
    (_reconcile, lambda r: fmt.reconcile_report(r)))
_h_capabilities = _reported(_capabilities, lambda r: fmt.capabilities_report(r))


def _h_system(ctx: "ToolContext", key: str = "", register: str = "") -> str:
    """The third entry. Read-only: the card assembles what the engine already
    holds around one system and writes nothing."""
    if not (key or "").strip():
        return fmt.systems_report(engine.systems())
    reg = (register or "patient").strip()
    card = engine.system(key.strip(), reg)
    text = fmt.system_report(card)
    # An assistant receives every hypothesis with its passport and the rule for
    # retelling it, in either register (0.6.0, U2): the person's screen shows
    # their number, the model is told what they rest on and how to say them.
    from .format_system import hypotheses_lines
    gen = card.get("genetics") if isinstance(card.get("genetics"), dict) else {}
    extra = hypotheses_lines(gen, True) if reg != "clinician" else []
    if extra or hypotheses_lines(gen, False):
        text = text.rstrip() + "\n" + "\n".join(extra) + "\n\n" + _t("system.hyp.rule") + "\n"
    return text


# --- schemas (OpenAI function-calling) -------------------------------------
# A description is the only thing the model reads before deciding to call a tool, so it
# is text like any other and lives in the catalogue. It is built at CALL time rather than
# at import: the language of a run is not known when the module is loaded.
_TOOLS = (
    ("sch_check_drug_gene", ("drug",), ["drug"], _h_check_drug),
    ("sch_analyze_labs", ("markers", "catalogue"), [], _h_analyze_labs),
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
    ("sch_overview", ("snapshot",), [], _h_overview),
    ("sch_second_opinion", (), [], _h_second_opinion),
    ("sch_limits", ("bed", "panel"), [], _h_limits),
    ("sch_rules", ("levels",), [], _h_rules_or_levels),
    ("sch_sources", (), [], _h_sources),
    ("sch_lab_draw", ("day", "reason", "between"), ["day"], _h_lab_draw),
    ("sch_marker_propose", ("key", "names", "unit", "names_en"), ["key", "names"],
     _h_marker_propose),
    ("sch_array", (), [], _h_array),
    ("sch_flag_rate", (), [], _h_flag_rate),
    ("sch_radar", (), [], _h_radar),
    ("sch_focus", (), [], _h_focus),
    ("sch_focus_log", ("date", "alcohol", "factors", "atenolol", "late_meal", "note"), ["date"],
     _h_focus_log),
    ("sch_brief", (), [], _h_brief),
    ("sch_acmg", (), [], _h_acmg),
    ("sch_goal_suggest", (), [], _h_goal_suggest),
    ("sch_lipid_genetics", (), [], _h_lipid_genetics),
    ("sch_screen", ("disease_class",), [], _h_screen),
    ("sch_system", ("key", "register"), [], _h_system),
    ("sch_version", (), [], _h_version),
    ("sch_update", ("confirm",), [], _h_update),
    ("sch_recompute", ("confirm",), [], _h_recompute),
    ("sch_medications", (), [], _h_medications),
    ("sch_genome_status", ("updates",), [], _h_genome_status),
    ("sch_selfcheck", ("full",), [], _h_selfcheck),
    ("sch_capabilities", (), [], _h_capabilities),
)

# The JSON type of every parameter. Kept next to the tools rather than inside the
# catalogue: a type is a contract with the model's function-calling, not a phrase.
_PARAM_TYPE = {"refresh": "boolean", "atenolol": "boolean", "late_meal": "boolean", "confirm": "boolean",
               "bed": "boolean", "catalogue": "boolean", "updates": "boolean", "full": "boolean",
               "levels": "boolean", "snapshot": "boolean"}


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
    return [ToolEntry(name, _schema(name, params, required), _noted(handler, name))
            for name, params, required, handler in _TOOLS]


#: The container this process's conversation is fixed to (task 192, R2). One
#: process is one conversation for the MCP server; for Ouroboros, the first call
#: fixes it. `pin_session()` takes it at the handshake.
_PIN = None


def _pin():
    global _PIN
    if _PIN is None:
        from scholion import container as _container  # noqa: E402
        _PIN = _container.AgentPin()
    return _PIN


def pin_session() -> None:
    """The MCP handshake: this conversation reads the container active now."""
    _pin().take()


def unpin_session() -> None:
    """Tests only: a new conversation."""
    _pin().reset()


def _noted(handler, name):
    """Every answer names its container, and the first carries the update note.

    The container (task 192): before anything is read, a call is refused if the
    active container is no longer the one this conversation started with; what
    the call writes is held to that container; the answer ends with its ID —
    never its label, since a tool's answer reaches the model's provider.

    The note: a person using the product through an assistant never sees the
    page's update note (owner, 14.09.2026). Whatever the model calls first, the
    answer ends with one line saying a newer build is out and that installing it
    is the person's call. The registry is asked at most once a day and never
    offline."""
    from scholion import container as _container  # noqa: E402

    def noted(out):
        from scholion import upgrade as _upg  # noqa: E402
        note = _upg.session_note()
        cid = _container.named()["id"]
        tail = [x for x in (note, _t("tool.container_line", id=cid) if cid else "") if x]
        return "\n\n".join([str(out)] + tail)

    def guarded(call, structured=False):
        with _container.pinned(_pin().check()):
            from scholion import lifecycle, contract
            action = 'read' if contract.tool_annotations(name)['readOnlyHint'] else 'write'
            lifecycle.record_current(action, lifecycle.AGENT_SURFACE.get())
            from scholion import linear, recompute
            with linear.host_read(enabled=bool(recompute.per_call_host())) as read:
                try:
                    result = call()
                except linear.Unreadable:
                    if not read["refused"]:
                        raise
                    result = None
                if read["refused"]:
                    message = "⚠️ " + _t("genome.refused.host_linear")
                    result = ((noted(message), {"status": "refused", "reason": "host_linear",
                               "message": message, "container": _container.named()})
                              if structured else noted(message))
            _container.gate()
            return result

    def run(ctx, **kwargs):
        return guarded(lambda: noted(handler(ctx, **kwargs)))
    run.__name__, run.__doc__ = handler.__name__, handler.__doc__
    if hasattr(handler, "both"):
        def both(**kwargs):
            def call():
                text, data = handler.both(**kwargs)
                if isinstance(data, dict):
                    data = {**data, "container": _container.named()}
                return noted(text), data
            return guarded(call, structured=True)
        run.both = both
    return run


if __name__ == "__main__":  # a quick self-test of the wrapper
    for t in get_tools():
        print(f"[tool] {t.name}: {t.schema['description'][:60]}…")
    # The Russian drug name is the point of the self-test: it proves the tool answers a
    # query typed the way the owner types it, whatever language the report comes out in.
    print("\n--- sch_check_drug_gene('клопидогрел') ---")
    print(_h_check_drug(ToolContext(), drug="клопидогрел")[:300])
