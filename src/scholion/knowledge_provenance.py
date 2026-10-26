"""Small source witnesses, selected from the knowledge actually used.

This is not another knowledge store. A witness identifies an existing record;
it never downloads, updates, classifies or writes anything. A catalogue version
is provenance, while the selected record digest decides content continuity.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from . import core

_RAW_CACHE: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}


def _book(name: str) -> dict[str, Any]:
    """Do not parse a multi-megabyte gene catalogue once per displayed gene."""
    path = core.knowledge_path(name)
    try:
        stat = path.stat()
    except OSError:
        return {}
    key = str(path.resolve())
    signature = (stat.st_mtime_ns, stat.st_size, id(core._read_knowledge_raw))
    saved = _RAW_CACHE.get(key)
    if saved and saved[0] == signature:
        return saved[1]
    book = core._read_knowledge_raw(name)
    _RAW_CACHE[key] = (signature, book)
    return book


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    default=str).encode()).hexdigest()


def record(name: str, *selector: str) -> dict[str, Any]:
    """Select by stable keys/IDs; never substitute a neighbouring list entry."""
    book = _book(name)
    node: Any = book
    for key in selector:
        if isinstance(node, dict):
            node = node.get(key)
        elif isinstance(node, list):
            hits = [row for row in node if isinstance(row, dict) and any(
                str(row.get(field) or '') == key for field in ('association_id', 'id', 'rsid', 'gene'))]
            node = hits[0] if len(hits) == 1 else None
        else:
            node = None
        if node is None:
            break
    meta = book.get('_meta') or {}
    out = {'catalogue': name, 'selector': list(selector),
           'id': name + ':' + '/'.join(selector),
           'version': meta.get('version') or meta.get('updated') or meta.get('retrieved'),
           'status': 'recorded' if node is not None else 'not_recorded',
           'record_digest': digest(node) if node is not None else None}
    if isinstance(node, dict):
        out.update(source=node.get('source') or meta.get('source_url'),
                   checked_on=node.get('checked_on') or node.get('curated_on') or node.get('retrieved'))
    return out


def association(association_id: str) -> dict[str, Any]:
    """Single-link and multi-marker hypotheses share the same source witness."""
    for name, field in (('genetic_lab_links.json', 'links'), ('genetic_lab_patterns.json', 'patterns')):
        witness = record(name, field, association_id)
        if witness['status'] == 'recorded':
            return witness
    return {'id': association_id, 'record_digest': None, 'status': 'not_recorded',
            'source': None, 'version': None, 'checked_on': None}


def sources(value: Any) -> list[dict[str, Any]]:
    """Keep explicit rule citations and dates; do not infer a PMID's year."""
    found: dict[str, dict[str, Any]] = {}
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            source = node.get('source')
            if isinstance(source, str) and source:
                witness = {'source': source, 'version': node.get('version'),
                           'checked_on': node.get('checked_on') or node.get('curated_on') or node.get('retrieved')}
                found[digest(witness)] = witness
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    return list(found.values())
