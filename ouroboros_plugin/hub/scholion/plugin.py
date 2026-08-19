"""Scholion — a local second-opinion layer over the owner's own medical data.

The analysis lives in the `scholion` pip package (declared in install_specs and
installed into this skill's isolated prefix); this file adapts its tools to the
frozen PluginAPI contract. One implementation, several doors — the package's
CLI, its local web app, the classic ouroboros/tools module and this Hub skill
all call the same engine facade, so the Hub skill cannot drift from the
product: there is nothing here to drift.

Honesty about permissions, in one place:

- ``fs`` — the tools READ the owner's profile that the scholion CLI keeps in
  the platform data directory (or wherever SCHOLION_PROFILE_DIR points). One
  tool writes: ``ingest_labs`` transcribes the owner's own laboratory PDFs
  into the profile — it moves the person's documents and invents nothing.
  Every other tool is read-only.
- ``net`` — two named lookups only, both opt-in by usage: resolving a drug
  that the local knowledge base does not carry (RxNorm/RxClass/CPIC, plus a
  translation service for non-Latin drug names) and rsID lookups (Ensembl).
  No key, no account, no telemetry; SCHOLION_OFFLINE=1 disables all of it.

Not a medical device: every answer is a second opinion for a conversation
with a physician, and the package's own safety rules travel inside it
(`scholion skill --rules`).
"""
from __future__ import annotations

from typing import Any, Dict

_PREFIX = "sch_"           # the classic tools-module namespace; the Hub host
_MAX_TIMEOUT = 120         # namespaces tools itself, so the prefix comes off


def register(api: Any) -> None:
    from scholion.ouroboros_tools import get_tools  # installed via install_specs

    for entry in get_tools():
        name = entry.name[len(_PREFIX):] if entry.name.startswith(_PREFIX) else entry.name
        schema: Dict[str, Any] = dict(entry.schema.get("parameters") or {})
        timeout = int(getattr(entry, "timeout_sec", 60) or 60)
        api.register_tool(
            name,
            entry.handler,
            description=str(entry.schema.get("description", "")),
            schema=schema,
            timeout_sec=max(1, min(timeout, _MAX_TIMEOUT)),
        )
