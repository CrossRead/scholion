"""contract.py — the project's public contract and the entry-point parity rule.

Why. One core has three faces: the web interface, the CLI and the Ouroboros
plugin. As long as a capability is added to the web «quickly», it sticks to that
interface: the assistant does not see it, a script cannot call it, and a user
without a browser does not get it. This is not a hypothesis — that is what
happened: «Second opinion», the summary and the health index by body system
lived only in the tabs for half a year.

The rule: **a capability appears in the core and gets an entry point in the CLI
and in the web at the same time**. So that the rule does not rest on memory, the
«API route → CLI command» map lives here, and `tests/test_parity.py` fails if a
route appeared in the server that is neither in the map nor in the exception list.

Exceptions are listed by name and with a reason. There are no silent exceptions:
if a route cannot be reproduced in the CLI, the reason has to be written down.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

PKG = Path(__file__).resolve().parent

# --- «METHOD /route» → the CLI command that gives THE SAME result -----------
# The method in the key is not a formality: on /api/labs GET reads the analysis and
# POST adds a data point — two different capabilities, and covering one does not
# close the other.
PARITY: Dict[str, str] = {
    # reading
    "GET /api/overview": "overview",
    "GET /api/goal": "goal",
    "GET /api/goal-suggest": "goal-suggest",
    "GET /api/labs": "labs",
    "GET /api/drug": "drug",
    "GET /api/suggest-tests": "suggest-tests",
    "GET /api/genome": "genome",
    "GET /api/genome-status": "genome-status",
    "GET /api/genome-updates": "genome-updates",
    "GET /api/second-opinion": "second-opinion",
    "GET /api/radar": "radar",
    "GET /api/prescription-check": "prescription",
    "GET /api/medications": "medications",
    "GET /api/limits": "limits",
    "GET /api/markers": "markers",
    "GET /api/metrics": "metrics",
    "GET /api/focus": "focus",
    "GET /api/lifestyle-brief": "brief",
    "GET /api/lifestyle": "lifestyle",
    "GET /api/clinvar": "clinvar",
    "GET /api/prs": "prs",
    "GET /api/longevity": "longevity",
    "GET /api/lipid-genetics": "lipid-genetics",
    "GET /api/sources": "provenance",
    "GET /api/assistant": "assistant",
    # writing
    "POST /api/labs": "add-lab",
    # The same command; `--write` is its flag. The map names commands, not
    # invocations — a route whose CLI twin needs an argument is still covered.
    "POST /api/goal": "goal-suggest",
    "POST /api/medications": "add-med",
    "POST /api/medications/remove": "remove-med",
    "POST /api/metrics": "add-metric",
    "POST /api/focus/log": "focus-log",
    "POST /api/pick-folder": "set-folder",
    "POST /api/ingest-garmin": "ingest-garmin",
    "POST /api/ingest-studies": "ingest-studies",
    "POST /api/ingest-labs": "ingest-labs",
    "POST /api/assistant/context": "assistant",      # the --context flag
}

# --- routes that have no command and should not have one ------------------
# The reasons below are written for whoever edits this file, and they reach nobody else:
# they surface only in the failure message of tests/test_parity.py. Like the comments and
# the docstrings around them, they are kept in English rather than in the catalogue —
# a phrase no reader of the product can ever see is not a message, it is documentation.
NO_CLI: Dict[str, str] = {
    "GET /api/ping": "a liveness check of the server; there is no server in the CLI",
    "GET /api/i18n": "the catalogue of phrases for the web page's labels; in the CLI the "
                     "process prints its own labels, so there is nobody to hand them to",
    "GET /api/diag": "diagnostics of the browser's network access to the server",
    "GET /api/update-status": "the state of a BACKGROUND server task; in the CLI the task is "
                              "synchronous",
    "POST /api/run-update": "starts the same update_check.sh that the CLI calls directly",
    "GET /api/source-config": "reads the interface settings; in the CLI the path is an argument",
    "POST /api/clear-folder": "resets an interface setting; the inverse of set-folder",
    "POST /api/metrics/profile": "the fields of a web form (sex, height, date of birth)",
}

# CLI commands that have no route and should not have one: this is not a gap in the web.
CLI_ONLY: Dict[str, str] = {
    "capabilities": "the manifest of this build. In the web the tab bar IS the manifest — a "
                    "person sees what exists by looking at it — so a page listing commands "
                    "nobody types would answer a question the interface has already answered",
    "serve": "the command that starts the server itself",
    "doc": "a document the output refers to, printed from inside the package: after "
           "`pip install` README, PREPARING-THE-GENOME and DATA-LAYOUT are not on disk, "
           "and advice to open a file somebody cannot open reads as a broken install",
    "skill": "the instruction for an external model: after `pip install` the file lies inside "
             "site-packages and its path cannot be named to a person. Not needed in the web — "
             "no model works there",
    "profile": "a snapshot of the profile for the skill; in the web that state is on the screens",
    "acmg": "ACMG SF secondary findings — in the web they are part of the «Genome» tab",
    "phenoage": "biological age: computed from a panel; in the web it is a block of the overview",
    "reconcile": "the PDF → profile audit, a long maintenance operation",
    "selfcheck": "a short integrity banner for the start of an assistant's session",
    "add-lab": "manual entry of a point; in the web it is a form on the «Labs» tab",
    "redact": "strips a person's identifiers out of text they are about to publish. There is "
              "deliberately no route: a web form that accepts a pasted medical log would "
              "create one more place for that log to exist, and the whole point of the "
              "command is that the text stops existing in fewer places, not more",
    "import-labs": "a CSV/TSV panel imported from a path on disk. The web has no route because "
                   "a page reachable from a browser must not be able to read an arbitrary file "
                   "by name — that is a file picker's job, and the picker is the next step, not "
                   "this command",
    "add-med": "manual entry of a drug; in the web it is a form on the «Prescriptions» tab",
    "remove-med": "withdrawing a drug; in the web it is a button on the «Prescriptions» tab",
    "init": "the first run on an empty machine: it creates the profile's files. The web does "
            "not even start without a profile — this command can have no route",
    "demo": "unfolds a synthetic profile for demonstrations and tests; a maintenance "
            "operation, not a capability of the product",
    "tools": "external command-line tools (bcftools, htslib, mosdepth…): what is missing and "
             "installing it. A statement about the machine, not about the person — and it runs "
             "a package manager, which is the one thing a web page reachable from a browser "
             "must never be able to start",
}

_ROUTE_RE = re.compile(r"""(?:p|u\.path)\s*(?:==|in)\s*\(?["']([^"']+)["']""")


def server_routes() -> List[str]:
    """Routes of the form «GET /api/…» declared in the server.

    The source is read instead of starting the server: the parity test has to work
    where the port is taken or the network is unavailable too. The method is
    determined by which handler body (do_GET / do_POST) the route string occurs in.
    """
    txt = (PKG / "server.py").read_text(encoding="utf-8")
    blocks = []
    for method in ("GET", "POST"):
        start = txt.find(f"def do_{method}(")
        if start < 0:
            continue
        rest = txt[start + 1:]
        nxt = min([i for i in (rest.find("\n    def do_"), rest.find("\nclass ")) if i > 0]
                  or [len(rest)])
        blocks.append((method, rest[:nxt]))
    found = set()
    for method, block in blocks:
        for m in _ROUTE_RE.findall(block):
            if m.startswith("/api/"):
                found.add(f"{method} {m}")
        for tup in re.findall(r"(?:p|u\.path)\s+in\s+\(([^)]*)\)", block):
            for s in re.findall(r"['\"]([^'\"]+)['\"]", tup):
                if s.startswith("/api/"):
                    found.add(f"{method} {s}")
    return sorted(found)


def cli_commands() -> List[str]:
    """The list of CLI commands — from the parser itself, not by a regex over the source."""
    from . import cli
    parser = cli.build_parser()
    for action in parser._subparsers._group_actions:      # noqa: SLF001 — argparse gives no public path
        if action.choices:
            return sorted(action.choices)
    return []


# --- the third face: the Ouroboros plugin ---------------------------------
# The docstring at the top of this file names three faces of one core, and until
# v0.3.1 the map covered two. The plugin drifted exactly the way the web had
# before the map existed: nine capabilities — including `limits`, the answer to
# «what can this data NOT tell you» — had a CLI command and a route and no tool,
# so a model connected through Ouroboros could not ask for them. The model is the
# reader who needs `limits` most, and it was the one that could not call it.
#
# The map below is CLI command → tool name. Everything a CLI read command
# produces is expected to have a tool unless a reason is written down.
PLUGIN: Dict[str, str] = {
    "drug": "sch_check_drug_gene",
    "labs": "sch_analyze_labs",
    "suggest-tests": "sch_suggest_tests",
    "genome": "sch_genome_lookup",
    "prescription": "sch_check_prescription",
    "metrics": "sch_health_metrics",
    "lifestyle": "sch_lifestyle",
    "clinvar": "sch_clinvar_findings",
    "prs": "sch_prs",
    "longevity": "sch_longevity",
    "goal": "sch_goal",
    "phenoage": "sch_phenoage",
    "provenance": "sch_provenance",
    "ingest-labs": "sch_ingest_labs",
    "overview": "sch_overview",
    "second-opinion": "sch_second_opinion",
    "limits": "sch_limits",
    "radar": "sch_radar",
    "focus": "sch_focus",
    "brief": "sch_brief",
    "acmg": "sch_acmg",
    "goal-suggest": "sch_goal_suggest",
    "lipid-genetics": "sch_lipid_genetics",
}

# Commands with no tool, and why. The bar is deliberately higher than for the web:
# a model that cannot see a capability does not know it is missing, and will
# answer from what it has instead of saying it cannot.
NO_PLUGIN: Dict[str, str] = {
    "serve": "starts a server; a model has no browser to point at it",
    "init": "creates the profile directory — the person's decision, not a model's",
    "demo": "lays out a fictional profile; a model asking for one is a model about to "
            "confuse it with the person's own",
    "doc": "prints a document that ships with the package; the model is handed the "
           "instruction directly and does not read the product's manuals",
    "skill": "prints the model's own instruction to a person; calling it from inside the "
             "model is a loop",
    "assistant": "describes how to connect a model — addressed to the person doing the "
                 "connecting",
    "profile": "a snapshot for the skill's own context, assembled before the tools run",
    "markers": "the catalogue for an entry form; a model writes no forms",
    "medications": "the list is already inside overview and second-opinion",
    "genome-status": "already inside overview",
    "genome-updates": "the result of a background refresh the model does not start",
    "selfcheck": "an integrity banner printed at the start of a session, before any tool",
    "reconcile": "a long maintenance audit over every PDF; minutes, not a tool call",
    "redact": "strips identifiers out of text a person is about to publish — the one "
              "command whose entire purpose is that the text reaches FEWER places",
    "tools": "checks for external programs and offers to install them — a package "
             "manager is not a thing a model should be reaching for",
    "capabilities": "the manifest of the command line, and a model reaching Scholion through "
                    "the plugin is handed its tool list directly — that list is already the "
                    "manifest of ITS surface. A tool enumerating tools is a mirror",
    # writes: a model does not change the profile. The canon it is handed says so, and
    # the absence of a tool is what makes that more than a promise.
    "add-lab": "a write", "add-med": "a write", "remove-med": "a write",
    "add-metric": "a write", "focus-log": "a write", "set-folder": "a write",
    "import-labs": "a write", "ingest-studies": "a write", "ingest-garmin": "a write",
}


def plugin_tools() -> List[str]:
    """The tool names the plugin actually registers — asked of the module, not a regex."""
    from . import ouroboros_tools
    return sorted(t.name for t in ouroboros_tools.get_tools())


def check_plugin_parity() -> List[str]:
    """Discrepancies between the CLI and the plugin. Empty list = parity is upheld."""
    problems: List[str] = []
    cmds, tools = set(cli_commands()), set(plugin_tools())
    for cmd in sorted(cmds):
        if cmd in PLUGIN:
            if PLUGIN[cmd] not in tools:
                problems.append(f"«{cmd}» → the map names the tool «{PLUGIN[cmd]}», "
                                f"and the plugin does not register it")
        elif cmd not in NO_PLUGIN:
            problems.append(
                f"«{cmd}»: the command exists and no tool answers to it. Add one and a line "
                f"to PLUGIN, or write the reason into NO_PLUGIN — there are no silent "
                f"exceptions, and a model cannot notice a capability it was never shown")
    for cmd, tool in PLUGIN.items():
        if cmd not in cmds:
            problems.append(f"the map binds «{cmd}» to «{tool}», and the CLI has no such command")
    for tool in sorted(tools):
        if tool not in set(PLUGIN.values()):
            problems.append(f"tool «{tool}» answers to no command: either it is a capability "
                            f"the other two faces lack, or the map is stale")
    return problems


# --- the fourth face: what the model is TOLD exists -------------------------
# A capability the instruction does not name is, from a model's side, a
# capability that does not exist. It will answer from what it knows about
# instead — which is the failure this whole layer is built to prevent, arriving
# through the one door nobody was watching.
#
# Measured before this list was written: the shared instruction named 40 of 47
# commands. Three of the seven missing were real capabilities — `acmg`,
# `goal-suggest`, `lipid-genetics` — and two of those three had been added the
# same week. The other four are meta and are recorded below.
#
# Deliberately a CHECK and not a generator. The block in the instruction carries
# curated invocations — `genome rs0000000`, `phenoage --panels`, `tools --set
# NAME` — which are worth more to a reader than a line per bare command, and a
# generator would flatten them. What must not happen is silent absence.
INSTRUCTION_DOC = "share/skill/INSTRUCTION.md"

NO_INSTRUCTION: Dict[str, str] = {
    "demo": "lays out a fictional profile — offering it to a model invites the one confusion "
            "this project cannot afford, between the demo and the person",
    "doc": "prints a document that ships with the package; the model is handed the "
           "instruction directly and has no use for the product's manuals",
    "skill": "prints this very instruction to a person. A model calling it reads itself",
    "redact": "strips identifiers out of text a person is about to publish. Addressed to the "
              "person, and its whole purpose is that the text reaches fewer places",
}


def instruction_text() -> str:
    """The shared instruction, wherever this build keeps it.

    The source repository keeps it at INSTRUCTION_DOC; the built package does
    not carry share/ and keeps the identical copy (sync_rules holds them equal)
    beside this module. The first version of this function knew only the first
    address — and passed every test in the repository it was written in, then
    failed inside the package on the owner's publish run: a check agreeing with
    the single environment its author sat in, the same class again.
    """
    from pathlib import Path as _P
    here = _P(__file__).resolve()
    for candidate in (here.parents[2] / INSTRUCTION_DOC,
                      here.parent / "skill" / "INSTRUCTION.md"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "the shared instruction is in neither of its two homes: "
        f"{INSTRUCTION_DOC} (source repository) or skill/INSTRUCTION.md "
        "(inside the package)")


def check_instruction_parity() -> List[str]:
    """Every command is either named in the instruction or excused by name."""
    import re as _re
    problems: List[str] = []
    try:
        text = instruction_text()
    except OSError:
        return []            # the shared source does not travel inside the package
    for cmd in sorted(cli_commands()):
        named = bool(_re.search(r"\bscholion %s\b" % _re.escape(cmd), text))
        if named and cmd in NO_INSTRUCTION:
            problems.append(f"«{cmd}» is excused in NO_INSTRUCTION and named anyway — "
                            f"decide which is true")
        elif not named and cmd not in NO_INSTRUCTION:
            problems.append(f"«{cmd}»: the instruction does not name it, so no model knows "
                            f"it exists. Add a line, or a reason to NO_INSTRUCTION")
    return problems


# --- the interface can render every phrase it reaches for -------------------
def check_i18n_keys() -> List[str]:
    """Literal keys used by the page exist in BOTH catalogues.

    A missing key does not crash: the page prints ⟦web.some.key⟧ where a sentence
    should be. Which means it fails in front of the reader and nowhere else — no
    exception, no log, no test — and only in the language that lacks it, so it is
    invisible to whoever wrote the other one.

    Only literal keys are checked. `t('goalgen.skip.' + reason)` is composed at
    run time and no static check can resolve it; those families are covered by
    the tests that own the value sets instead, which is the honest division.
    """
    import re as _re
    from pathlib import Path as _P
    from .i18n import en as _en, ru as _ru
    html = (_P(__file__).resolve().parent / "web" / "index.html").read_text(encoding="utf-8")
    used = set(_re.findall(r"""\bt\(\s*['"]([a-zA-Z0-9_.]+)['"]""", html))
    plural = set(_re.findall(r"""\bplural\([^,]+,\s*['"]([a-zA-Z0-9_.]+)['"]""", html))
    problems: List[str] = []
    for lang, cat in (("en", _en.MESSAGES), ("ru", _ru.MESSAGES)):
        for k in sorted(used):
            if k.endswith(".") or k in cat:
                continue        # a composed prefix, or present
            problems.append(f"{lang}: the page asks for «{k}» and the catalogue has no such "
                            f"key — it will print ⟦{k}⟧ to the reader")
        for k in sorted(plural):
            missing = [f for f in ("one", "few", "many") if f"{k}.{f}" not in cat]
            if missing:
                problems.append(f"{lang}: «{k}» is used as a plural and lacks the "
                                f"{', '.join(missing)} form(s)")
    return problems


# --- commands that change something, and the line inside that set -----------
# Every one of these writes. They do not all write the same KIND of thing, and
# the difference decides which of them a model may be handed.
#
# The distinction was forced by a test rather than chosen: an assertion that «no
# tool writes to the profile» went red on `sch_ingest_labs`, which has been in
# the plugin from the beginning. The claim was false and had been for months —
# the earlier version of that test checked a hand-written list that happened not
# to contain it, which is the shape of a check that agrees with its author.
#
# So the honest split. AUTHORS creates a value that exists nowhere else: somebody
# decides a number and it becomes part of the person's record. TRANSCRIBES moves
# what is already in the person's own documents — a folder of laboratory PDFs
# they pointed at, a device export they downloaded — into the profile, and
# invents nothing. A model transcribing a form the person put in a folder is a
# different act from a model typing a value it settled on itself, and only the
# second is the one the canon forbids.
WRITES = {
    "init", "demo", "add-lab", "add-med", "remove-med", "add-metric", "focus-log",
    "set-folder", "import-labs", "ingest-labs", "ingest-studies", "ingest-garmin",
    "redact",
}

# Creates a value that came from nobody's document. None of these is a tool, and
# a test keeps it that way.
AUTHORS = {
    "add-lab", "add-med", "remove-med", "add-metric", "focus-log",
    "init", "demo", "set-folder",
}

# Moves the person's own documents into the profile. `ingest-labs` IS a tool, on
# purpose and recorded here rather than by omission: a model that has just been
# handed a folder of new results should be able to load them, and the values it
# writes are the laboratory's, read off the form.
TRANSCRIBES = {"ingest-labs", "ingest-studies", "ingest-garmin", "import-labs", "redact"}


def capabilities() -> Dict[str, Any]:
    """What this build can do, for a reader that is not a person.

    THE COMMAND LINE IS A MODEL-FACING SURFACE FIRST. That is not how this file
    read until now — it spoke of «a person typing, and every script» — and the
    correction matters more than the wording. A model reaching Scholion through
    a shell learns what to run from its INSTRUCTION, not by exploring: it will
    not try `--help` on a hunch, it will answer from what it already believes.
    So the instruction being complete is not a nicety of documentation, it is the
    discovery mechanism of the main surface, and the day it falls behind, the
    surface silently shrinks to whatever the instruction remembers.
    
    This function is the second route to the same truth, and it exists because
    the first one is a hand-written document. Generated from the parser and from
    the maps above, it cannot fall behind them; a model with a stale instruction
    and a current binary can ask the binary. `scholion capabilities --json`.
    """
    out = []
    from . import cli as _cli
    parser = _cli.build_parser()
    helps: Dict[str, str] = {}
    for action in parser._subparsers._group_actions:      # noqa: SLF001
        if action.choices:
            for sub in action._get_subactions():          # noqa: SLF001
                helps[sub.dest] = (sub.help or "").strip()
    routes = {cmd: r for r, cmd in PARITY.items()}
    try:
        named = instruction_text()
    except OSError:
        named = ""
    import re as _re
    for cmd in sorted(cli_commands()):
        out.append({
            "command": cmd,
            "does": helps.get(cmd, ""),
            "writes": cmd in WRITES,
            "kind": ("authors" if cmd in AUTHORS
                     else "transcribes" if cmd in TRANSCRIBES else "reads"),
            "faces": {
                "cli": True,
                "web": routes.get(cmd),
                "plugin": PLUGIN.get(cmd),
                "instruction": bool(named and _re.search(
                    r"\bscholion %s\b" % _re.escape(cmd), named)),
            },
        })
    from . import __version__
    return {"version": __version__, "count": len(out), "commands": out,
            "reads_only": sorted(c["command"] for c in out if not c["writes"]),
            "writes": sorted(c["command"] for c in out if c["writes"])}


def check_all_faces() -> Dict[str, List[str]]:
    """Every face of the core, in one answer.

    One call rather than four, because the question an author actually has is
    «what did I forget», and four separate red tests answer it one quarter at a
    time — a run per face, a fix per run. A capability is added to the core and
    then reaches a person through the web, the command line, a model's tool list
    and a model's instruction; the tick is not finished until all four move.
    """
    return {
        "web ↔ CLI": check_parity(),
        "CLI ↔ plugin": check_plugin_parity(),
        "CLI ↔ the model's instruction": check_instruction_parity(),
        "interface ↔ the phrase catalogues": check_i18n_keys(),
    }


def check_parity() -> List[str]:
    """The list of discrepancies. An empty list = parity is upheld."""
    problems: List[str] = []
    routes, cmds = server_routes(), set(cli_commands())
    for r in routes:
        if r in PARITY:
            if PARITY[r] not in cmds:
                problems.append(f"{r} → the map names the command «{PARITY[r]}», "
                                f"and the CLI does not have it")
        elif r not in NO_CLI:
            problems.append(
                f"{r}: the route exists in the web but is not described. Add a CLI command "
                f"and a line to PARITY, or write the reason into NO_CLI — there are no "
                f"silent exceptions")
    for route, cmd in PARITY.items():
        if route not in routes:
            problems.append(f"{route}: the map has it, the server has no such route "
                            f"(renamed or deleted?) → command «{cmd}»")
    for cmd in cmds:
        if cmd not in set(PARITY.values()) and cmd not in CLI_ONLY:
            problems.append(f"command «{cmd}»: bound to no route and not described in CLI_ONLY")
    return problems
