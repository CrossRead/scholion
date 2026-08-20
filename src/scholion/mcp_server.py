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

#: The revision of the protocol this server speaks. Stated rather than echoed
#: back from whatever the client asks for: answering «yes, that one» to a version
#: we have never seen is how a client ends up sending frames we cannot read.
PROTOCOL_VERSION = "2024-11-05"

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
PARSE_ERROR = -32700


def _tools() -> list:
    from . import ouroboros_tools
    return list(ouroboros_tools.get_tools())


def tool_descriptors() -> list:
    """The MCP shape of the tool list, derived from the plugin's own schemas."""
    out = []
    for t in _tools():
        schema = dict(t.schema)
        out.append({"name": schema.get("name", t.name),
                    "description": schema.get("description", ""),
                    # MCP calls it `inputSchema`; the plugin calls the same object
                    # `parameters`. One rename, in one place, rather than a second
                    # copy of every schema.
                    "inputSchema": schema.get("parameters")
                    or {"type": "object", "properties": {}}})
    return out


def _server_info() -> Dict[str, Any]:
    from . import __version__ as _v
    return {"name": "scholion", "version": str(_v)}


def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run one tool and answer in MCP's content shape.

    A failure is reported as `isError` with the text of what went wrong, not as
    an empty result: «nothing came back» and «this went wrong» are different
    facts, and a model handed the first will usually assume the second did not
    happen.
    """
    from .ouroboros_tools import ToolContext
    for t in _tools():
        if t.name == name:
            try:
                text = t.handler(ToolContext(), **(arguments or {}))
            except TypeError as e:                       # a wrong or missing argument
                return {"content": [{"type": "text", "text": f"{name}: {e}"}], "isError": True}
            except Exception as e:                       # noqa: BLE001 - reported, not swallowed
                return {"content": [{"type": "text", "text": f"{name}: {e}"}], "isError": True}
            return {"content": [{"type": "text", "text": str(text)}], "isError": False}
    return {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True}


def handle(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, one answer out (or None for a notification)."""
    method = message.get("method")
    mid = message.get("id")
    params = message.get("params") or {}

    def ok(result):
        return None if mid is None else {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, text):
        return None if mid is None else {"jsonrpc": "2.0", "id": mid,
                                         "error": {"code": code, "message": text}}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL_VERSION,
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": _server_info()})
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": tool_descriptors()})
    if method == "tools/call":
        name = params.get("name")
        if not name:
            return err(INVALID_PARAMS, "tools/call needs a tool name")
        return ok(call_tool(name, params.get("arguments") or {}))
    return err(METHOD_NOT_FOUND, f"method not found: {method}")


def serve(stdin: Optional[Iterable[str]] = None, stdout=None) -> int:
    """Read newline-delimited JSON-RPC from stdin, answer on stdout.

    Both streams are parameters so the loop can be exercised by a test without a
    subprocess: the thing worth testing is the dialogue, not the pipe.
    """
    src = stdin if stdin is not None else sys.stdin
    out = stdout if stdout is not None else sys.stdout
    for line in src:
        line = (line or "").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError as e:
            out.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                  "error": {"code": PARSE_ERROR,
                                            "message": f"not JSON: {e}"}}) + "\n")
            out.flush()
            continue
        try:
            answer = handle(message)
        except Exception as e:                            # noqa: BLE001
            answer = {"jsonrpc": "2.0", "id": message.get("id"),
                      "error": {"code": INTERNAL_ERROR, "message": str(e)}}
        if answer is not None:
            out.write(json.dumps(answer, ensure_ascii=False) + "\n")
            out.flush()
    return 0
