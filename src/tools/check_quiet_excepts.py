#!/usr/bin/env python3
"""A broad `except` that swallows the error must say why that is safe (task 209).

The class this guards against: an error turned into an answer. A genome reader
that failed came back as an empty list, an empty list read as «no variant here»,
and «no variant» read as «the person carries the reference» (0.5.9, finding A of
the external review). Nothing crashed and nothing was logged — the silence WAS
the answer. Every broad handler that stays silent is a place where that can
happen again, and whether it can is decided by reading it, once, and writing the
decision down where the next reader will see it.

A handler counts as **broad** when it catches `Exception`, `BaseException` or
everything (a bare `except:`), and as **silent** when its whole body is `pass`,
`continue`, a docstring-like constant, or a `return` of a constant or an empty
container. A silent broad handler passes when a comment starting with `quiet:`
stands on its `except` line or on the line of its body, and names why nothing
the person reads is made from the failure:

    except Exception:  # quiet: a cache miss — the value is read again from the file
        pass

A handler where silence COULD become a statement about the person is not given a
comment — it is changed to say that it failed (a named refusal, `None` rather
than an empty answer, or a raise). This tool cannot tell the two apart; the
review can, and the comment is its record.

    python3 src/tools/check_quiet_excepts.py            # the table and the unexplained ones
    python3 src/tools/check_quiet_excepts.py --strict   # exit 1 if any is unexplained

Standard library only; it runs inside the published package as well.
"""
from __future__ import annotations

import ast
import io
import sys
import tokenize
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
#: Where the product's own code lives. `vendor/` is somebody else's code, held to
#: its upstream and changed only as `UPSTREAM.md` records.
SCOPES = ("src/scholion", "src/ingest", "src/tools", "src/annotate")
SKIP_PARTS = {"vendor", "__pycache__"}
MARK = "quiet:"


def _is_broad(h: ast.ExceptHandler) -> bool:
    if h.type is None:
        return True
    nodes = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
    for n in nodes:
        name = n.id if isinstance(n, ast.Name) else (n.attr if isinstance(n, ast.Attribute) else "")
        if name in ("Exception", "BaseException"):
            return True
    return False


def _is_empty(v: ast.AST) -> bool:
    if isinstance(v, (ast.List, ast.Tuple, ast.Set)):
        return not v.elts
    if isinstance(v, ast.Dict):
        return not v.keys
    if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in ("dict", "list", "set", "tuple"):
        return not v.args and not v.keywords
    return False


def _is_silent(h: ast.ExceptHandler) -> bool:
    if len(h.body) != 1:
        return False
    s = h.body[0]
    if isinstance(s, (ast.Pass, ast.Continue)):
        return True
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
        return True
    if isinstance(s, ast.Return):
        return s.value is None or isinstance(s.value, ast.Constant) or _is_empty(s.value)
    return False


def _comment_lines(text: str) -> Dict[int, str]:
    out: Dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass  # quiet: an untokenisable file is reported by ast.parse below, not here
    return out


def scan_file(path: Path) -> Tuple[int, List[int], List[int]]:
    """(broad handlers, silent explained lines, silent unexplained lines) of one file."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    comments = _comment_lines(text)
    broad = 0
    explained: List[int] = []
    unexplained: List[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not _is_broad(node):
            continue
        broad += 1
        if not _is_silent(node):
            continue
        lines: Set[int] = {node.lineno, node.body[0].lineno}
        if any(MARK in comments.get(n, "") for n in lines):
            explained.append(node.lineno)
        else:
            unexplained.append(node.lineno)
    return broad, sorted(explained), sorted(unexplained)


def files(root: Path = ROOT) -> List[Path]:
    out: List[Path] = []
    for scope in SCOPES:
        base = root / scope
        if base.is_dir():
            out += [p for p in sorted(base.rglob("*.py")) if not (SKIP_PARTS & set(p.parts))]
    return out


def scan(root: Path = ROOT) -> Dict[str, Dict[str, object]]:
    report: Dict[str, Dict[str, object]] = {}
    for p in files(root):
        broad, explained, unexplained = scan_file(p)
        if broad:
            report[p.relative_to(root).as_posix()] = {
                "broad": broad, "explained": explained, "unexplained": unexplained}
    return report


def main(argv: List[str]) -> int:
    strict = "--strict" in argv
    report = scan()
    broad = sum(int(v["broad"]) for v in report.values())  # type: ignore[call-overload]
    explained = sum(len(v["explained"]) for v in report.values())  # type: ignore[arg-type]
    bad = [(f, n) for f, v in report.items() for n in v["unexplained"]]  # type: ignore[attr-defined]
    print(f"broad handlers: {broad}; silent and explained (`# quiet:`): {explained}; "
          f"silent and unexplained: {len(bad)}")
    for f, n in bad:
        print(f"  ✗ {f}:{n} — a broad handler swallows the error and does not say why that is safe")
    if bad:
        print("\n  Read it: if the silence can become a statement about the person, make it say it\n"
              "  failed; otherwise write `# quiet: <why>` on the `except` line.")
        return 1 if strict else 0
    print("✓ every silent broad handler says why its silence is safe")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
