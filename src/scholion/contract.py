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
from typing import Dict, List

PKG = Path(__file__).resolve().parent

# --- «METHOD /route» → the CLI command that gives THE SAME result -----------
# The method in the key is not a formality: on /api/labs GET reads the analysis and
# POST adds a data point — two different capabilities, and covering one does not
# close the other.
PARITY: Dict[str, str] = {
    # reading
    "GET /api/overview": "overview",
    "GET /api/goal": "goal",
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
    "GET /api/sources": "provenance",
    "GET /api/assistant": "assistant",
    # writing
    "POST /api/labs": "add-lab",
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
