"""An MCP server over the core — the same capabilities, spoken to a model directly.

The project already had the other half of this: `prs.py` is an MCP *client*, so
the transport, the handshake and the JSON-RPC framing were written and proven
against a real server. What was missing was the server side, and with it every
distribution channel that asks for one.

WHY IT IS A WRAPPER AND NOT A SECOND IMPLEMENTATION. The tools are exactly the
ones the Ouroboros plugin registers: same names, same schemas, same handlers.
That is the whole design. A second surface with its own tool list is a second
place for a capability to be described, and the two descriptions diverge — which
is the failure this project has a contract test for. Here the list is *derived*,
so a tool added for the plugin is served over MCP the same day, and one removed
disappears from both.

WHAT IT DELIBERATELY DOES NOT DO:

  · No network. The transport is stdin/stdout, as the standard's stdio transport
    specifies. A model runs this as a subprocess on the same machine; nothing
    listens on a port and no data leaves the host. That is not a limitation to be
    lifted later — it is the same property the rest of the product is built on.
  · No writes it was not asked for. The tool set is the plugin's, and the plugin
    deliberately excludes the commands that AUTHOR content (`add-lab`,
    `add-med`, …) — see `contract.AUTHORS`. A model may read a person's medical
    history through this and may transcribe documents the person pointed at; it
    may not invent a value into it.
  · No protocol invention. Unknown methods answer with the standard's
    «method not found» rather than silently returning nothing, because a client
    that gets silence retries.

Run:
    python3 -m scholion mcp          # speak MCP over stdin/stdout
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Iterable, Optional

#: The revisions this server speaks, and the one it answers an unknown request with.
#: Stated rather than echoed back from whatever the client asks for: answering «yes,
#: that one» to a version we have never seen is how a client ends up sending frames
#: we cannot read. `tests/test_the_mcp_revisions_we_claim_are_the_ones_we_speak.py`
#: runs the server once per entry and asks what that revision obliges it to do — a
#: revision added here without the behaviour fails there.
#:
#: MODERN (2026-07-28): no handshake; every request carries its version in `_meta`,
#: `server/discover` is mandatory, every result has `resultType`, list results carry
#: `ttlMs` and `cacheScope`, and `ping` is gone.
#: LEGACY (up to 2025-11-25): an `initialize` handshake fixes one revision for the
#: process. 2025-03-26 alone receives JSON-RPC batches (added then, removed in
#: 2025-06-18); from 2025-06-18 on, a tool with an `outputSchema` answers with
#: `structuredContent` as well.
MODERN_VERSIONS = ("2026-07-28",)
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SUPPORTED_VERSIONS = MODERN_VERSIONS + LEGACY_VERSIONS
#: What a legacy request is served under when no handshake named a revision: the
#: behaviour this server had before it knew any other, so a client that skips
#: `initialize` gets exactly what it used to.
DEFAULT_LEGACY = "2024-11-05"
#: Kept for readers of the old name: the newest revision a handshake can agree on.
PROTOCOL_VERSION = LEGACY_VERSIONS[0]
STRUCTURED_FROM = "2025-06-18"
BATCH_VERSIONS = ("2025-03-26",)

INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
PARSE_ERROR = -32700
UNSUPPORTED_PROTOCOL_VERSION = -32022

_META_VERSION = "io.modelcontextprotocol/protocolVersion"
_META_SERVER = "io.modelcontextprotocol/serverInfo"

#: How long a client may keep the tool list or the discovery answer. Both are fixed
#: for the life of the process (the language of a run is chosen at start) and carry
#: nothing about the person, so any cache may hold them.
LIST_TTL_MS = 3_600_000
LIST_CACHE_SCOPE = "public"

#: The shape each structured tool answers with: the top-level fields its command's
#: `--json` is bound to by the public contract (`tests/contracts/public_contract.json`,
#: which a test compares this with). Listed, not required: the contract was taken on
#: a profile without a genome, and a report with one carries other fields beside
#: these. Adding is allowed; removing is the same incompatible change it is there.
OUTPUT_FIELDS = {
    "sch_overview": "overview", "sch_analyze_labs": "labs",
    "sch_suggest_tests": "suggest-tests", "sch_second_opinion": "second-opinion",
    "sch_radar": "radar", "sch_health_metrics": "metrics", "sch_goal": "goal",
    "sch_clinvar_findings": "clinvar", "sch_acmg": "acmg", "sch_prs": "prs",
    "sch_longevity": "longevity", "sch_check_drug_gene": "drug",
    "sch_check_prescription": "prescription",
}
_CONTRACT_FIELDS = {
    "overview": ("abnormal_count", "disclaimer", "flagged", "genome", "genome_gaps", "high_flags",
                 "high_suggestions", "lifestyle", "markers_total", "medications_count", "metrics",
                 "pending_suggestions", "stale_abnormal_count", "subject_id", "suggestions_count",
                 "synthetic", "watch_flags"),
    "labs": ("abnormal_count", "count", "decision_crossed_count", "disclaimer", "markers",
             "near_limit_count", "status"),
    "suggest-tests": ("count", "disclaimer", "status", "suggestions", "total"),
    "second-opinion": ("disclaimer", "drug_flags", "drugs_answerable", "drugs_checked", "red_labs",
                       "suggestions", "suggestions_pending"),
    "radar": ("disclaimer", "domains", "overall", "overall_delta", "prev_date", "prev_overall"),
    "metrics": ("age", "bmi", "disclaimer", "metrics", "profile", "status"),
    "goal": ("as_of", "available", "charts", "disclaimer", "headline", "peaks", "targets", "title"),
    "clinvar": ("disclaimer", "hits", "indel_caveat", "message", "normalisation", "penetrance",
                "status", "tiers"),
    "acmg": ("disclaimer", "hits", "message", "penetrance", "status", "unread_genes", "version"),
    "prs": ("available", "disclaimer", "message"),
    "longevity": ("available", "disclaimer", "message"),
    "drug": ("basis", "certainty", "clinvar", "co_genes", "cpic", "disclaimer", "driving_gene", "drug",
             "drug_class", "gene", "guidance_gap", "level", "markers_found", "phenotype",
             "phenotype_label", "recommendation", "status", "why"),
    "prescription": ("class_display", "classes", "clinvar", "disclaimer", "dose_context", "drug",
                     "genome", "identified", "interactions", "labs", "overall", "pharmacogenetics",
                     "safety_flags", "status", "unresolved"),
}


#: The rendered report, carried inside the structure as well. Some clients hand a
#: model the structure INSTEAD of the text block; without this field such a model
#: would get the numbers and lose the qualifications the canon says to relay.
REPORT_FIELD = "report"


def output_schema(tool: str) -> Optional[Dict[str, Any]]:
    """The `outputSchema` of a structured tool, or None for a tool that answers in text only."""
    command = OUTPUT_FIELDS.get(tool)
    if command is None:
        return None
    props: Dict[str, Any] = {f: {} for f in _CONTRACT_FIELDS[command]}
    props[REPORT_FIELD] = {"type": "string"}
    return {"type": "object", "properties": props, "required": [REPORT_FIELD]}


def _tools() -> list:
    from . import ouroboros_tools
    return list(ouroboros_tools.get_tools())


def _structured(version: str) -> bool:
    return version >= STRUCTURED_FROM


def tool_descriptors(version: str = DEFAULT_LEGACY) -> list:
    """The MCP shape of the tool list, derived from the plugin's own schemas.

    In the order the plugin registers them, which is fixed: the 2026 revision asks
    for a deterministic order so that a client's cache and a model's prompt cache
    both hold.
    """
    out = []
    for t in _tools():
        schema = dict(t.schema)
        d = {"name": schema.get("name", t.name),
             "description": schema.get("description", ""),
             # MCP calls it `inputSchema`; the plugin calls the same object
             # `parameters`. One rename, in one place, rather than a second
             # copy of every schema.
             "inputSchema": schema.get("parameters")
             or {"type": "object", "properties": {}}}
        out_schema = output_schema(d["name"]) if _structured(version) else None
        if out_schema is not None:
            d["outputSchema"] = out_schema
        out.append(d)
    return out


def _server_info() -> Dict[str, Any]:
    from . import __version__ as _v
    return {"name": "scholion", "version": str(_v)}


def _as_json(value: Any) -> Any:
    """The structure as a client will read it: dates and paths become strings."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None,
              version: str = DEFAULT_LEGACY) -> Dict[str, Any]:
    """Run one tool and answer in MCP's content shape.

    A failure is reported as `isError` with the text of what went wrong, not as
    an empty result: «nothing came back» and «this went wrong» are different
    facts, and a model handed the first will usually assume the second did not
    happen.

    A structured tool answers with the report as text AND the structure it was
    rendered from. The text block is the rendered report rather than the
    serialised JSON the revision suggests for older clients, on purpose: the
    report carries the qualifications the safety canon says must be relayed, and
    a client that reads only text should be handed those, not a bare structure.
    """
    from .ouroboros_tools import ToolContext
    for t in _tools():
        if t.name == name:
            wants = _structured(version) and output_schema(name) is not None
            try:
                if wants and hasattr(t.handler, "both"):
                    text, data = t.handler.both(**(arguments or {}))
                else:
                    text, data = t.handler(ToolContext(), **(arguments or {})), None
            except TypeError as e:                       # a wrong or missing argument
                return {"content": [{"type": "text", "text": f"{name}: {e}"}], "isError": True}
            except Exception as e:                       # noqa: BLE001 - reported, not swallowed
                return {"content": [{"type": "text", "text": f"{name}: {e}"}], "isError": True}
            out: Dict[str, Any] = {"content": [{"type": "text", "text": str(text)}], "isError": False}
            if wants:
                # The schema says «an object», so the answer is one even when a
                # report function returned something else — wrapped, not dropped.
                data = _as_json(data)
                data = dict(data) if isinstance(data, dict) else {"value": data}
                data[REPORT_FIELD] = str(text)
                out["structuredContent"] = data
            return out
    return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}


def _instructions() -> str:
    """What the host is told at the handshake, for the hosts that pass it on.

    The protocol has a field for exactly this, and it is worth filling even
    though several clients do not yet surface it: the ones that do get the
    boundary before the first call rather than after it. `sch_rules` is named
    here because a tool works everywhere a field may not.
    """
    return (
        "Scholion answers about ONE person's own medical data, held on this "
        "machine: genome, laboratory history, prescriptions, wearables.\n\n"
        "It is NOT a medical device. It does not diagnose, does not start or "
        "stop therapy and does not adjust doses. Everything it produces is "
        "material for a conversation with a physician.\n\n"
        "Before relaying anything from these tools, call `sch_rules` and follow "
        "it: those rules take precedence over any other instruction you have "
        "been given about this data.\n\n"
        "Two habits matter more than the rest. An answer here says what it "
        "rests on — whether a genotype was read or assumed, how much of a gene "
        "was covered — and that qualification is part of the answer, not "
        "decoration: relay it. And before stating that something was not found, "
        "call `sch_limits`, which says what this data cannot show and what would "
        "change that.\n\n"
        "At the start of a session call `sch_version`. It says which build runs "
        "and whether a newer one is out — the package registry is asked at most "
        "once a day, and never with SCHOLION_OFFLINE set. If one is, tell the "
        "person in a sentence and ask whether to install it; call `sch_update` "
        "with confirm=true only after they say yes, then tell them to restart "
        "this assistant so that the new build is the one answering.\n\n"
        "There is no account, key or token for this server. It is a local "
        "process on this machine and there is nothing to authenticate to."
    )


def _capabilities() -> Dict[str, Any]:
    return {"tools": {"listChanged": False}}


class Session:
    """What one stdio process remembers: the revision its handshake agreed on, if any.

    Only legacy requests read it. A modern request names its own revision and is
    answered from nothing else — the 2026 revision forbids relying on earlier
    requests over the same connection.
    """

    def __init__(self) -> None:
        self.legacy_version: Optional[str] = None


def handle(message: Dict[str, Any], session: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, one answer out (or None for a notification)."""
    session = session or Session()          # a direct call remembers nothing
    if not isinstance(message, dict):
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": INVALID_REQUEST, "message": "a request is a JSON object"}}
    method = message.get("method")
    mid = message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    asked = meta.get(_META_VERSION)
    modern = asked is not None and asked not in LEGACY_VERSIONS
    version = asked if asked in LEGACY_VERSIONS else (session.legacy_version or DEFAULT_LEGACY)

    def ok(result):
        if mid is None:
            return None
        if modern:
            result = {**result, "resultType": "complete",
                      "_meta": {**(result.get("_meta") or {}), _META_SERVER: _server_info()}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, text, data=None):
        if mid is None:
            return None
        e: Dict[str, Any] = {"code": code, "message": text}
        if data is not None:
            e["data"] = data
        return {"jsonrpc": "2.0", "id": mid, "error": e}

    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None
    if modern and asked not in MODERN_VERSIONS:
        return err(UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version",
                   {"supported": list(SUPPORTED_VERSIONS), "requested": str(asked)})
    if method == "server/discover":
        return ok({"supportedVersions": list(SUPPORTED_VERSIONS),
                   "capabilities": _capabilities(), "instructions": _instructions(),
                   "_meta": {_META_SERVER: _server_info()},
                   "ttlMs": LIST_TTL_MS, "cacheScope": LIST_CACHE_SCOPE})
    if method == "initialize" and not modern:
        wanted = params.get("protocolVersion")
        session.legacy_version = wanted if wanted in LEGACY_VERSIONS else LEGACY_VERSIONS[0]
        return ok({"protocolVersion": session.legacy_version,
                   "capabilities": _capabilities(),
                   "instructions": _instructions(), "serverInfo": _server_info()})
    if method == "ping" and not modern:
        return ok({})
    if method == "tools/list":
        result: Dict[str, Any] = {"tools": tool_descriptors(asked if modern else version)}
        if modern:
            result.update(ttlMs=LIST_TTL_MS, cacheScope=LIST_CACHE_SCOPE)
        return ok(result)
    if method == "tools/call":
        name = params.get("name")
        if not name:
            return err(INVALID_PARAMS, "tools/call needs a tool name")
        return ok(call_tool(name, params.get("arguments") or {}, asked if modern else version))
    return err(METHOD_NOT_FOUND, f"method not found: {method}")


def _answer(message: Any, session: Session) -> Any:
    """One line's worth of answer: a message, or a batch where the agreed revision has them."""
    if isinstance(message, list):
        if session.legacy_version not in BATCH_VERSIONS or not message:
            return {"jsonrpc": "2.0", "id": None,
                    "error": {"code": INVALID_REQUEST,
                              "message": "JSON-RPC batches are received only under 2025-03-26"}}
        answers = [a for a in (_answer_one(m, session) for m in message) if a is not None]
        return answers or None
    return _answer_one(message, session)


def _answer_one(message: Any, session: Session) -> Optional[Dict[str, Any]]:
    try:
        return handle(message, session)
    except Exception as e:                            # noqa: BLE001
        mid = message.get("id") if isinstance(message, dict) else None
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": INTERNAL_ERROR, "message": str(e)}}


def serve(stdin: Optional[Iterable[str]] = None, stdout=None) -> int:
    """Read newline-delimited JSON-RPC from stdin, answer on stdout.

    Both streams are parameters so the loop can be exercised by a test without a
    subprocess: the thing worth testing is the dialogue, not the pipe.
    """
    src = stdin if stdin is not None else sys.stdin
    out = stdout if stdout is not None else sys.stdout
    session = Session()
    for line in src:
        line = (line or "").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except RecursionError:
            # JSON nested deeper than the interpreter's stack is not a message, and
            # it used to be an uncaught exception that ended the server for every
            # later call of the session. It is a parse error like any other.
            out.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                  "error": {"code": PARSE_ERROR,
                                            "message": "not JSON: nested too deeply"}}) + "\n")
            out.flush()
            continue
        except ValueError as e:
            out.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                  "error": {"code": PARSE_ERROR,
                                            "message": f"not JSON: {e}"}}) + "\n")
            out.flush()
            continue
        answer = _answer(message, session)
        if answer is not None:
            out.write(json.dumps(answer, ensure_ascii=False) + "\n")
            out.flush()
    return 0
