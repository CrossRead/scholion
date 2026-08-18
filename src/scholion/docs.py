"""The documents that travel inside the package, and where they are.

The output of this product names files: `limits` sends the reader to
`PREPARING-THE-GENOME.md`, the skill to `README.md`, the data layer to
`DATA-LAYOUT.md`. In the repository they are all there. After `pip install` they
are not: the wheel carries `src/scholion` and nothing else, and while the
repository is private there is no second place to go and read them.

Advice to open a file somebody cannot open is worse than no advice — it reads as
a broken installation rather than as a closed door. So the documents ship, and
`scholion doc <name>` prints one. `src/tools/sync_docs.py` keeps the copies equal
to their sources and `run_tests.sh` fails if they drift.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

_DIR = Path(__file__).resolve().parent / "docs"


def available() -> List[Tuple[str, int]]:
    """(name, size in bytes) for every document in this build, alphabetically.

    Read off the disk rather than from a list in the code: a list would go on
    promising a document a partial build does not carry, which is the failure
    this whole module exists to prevent.
    """
    if not _DIR.is_dir():
        return []
    return sorted((f.stem, f.stat().st_size) for f in _DIR.glob("*.md"))


def path_of(name: str) -> Optional[Path]:
    """The file for a name, or None. Tolerant about how the name is typed.

    `DATA-LAYOUT`, `data_layout` and `data-layout.md` are the same request, and
    refusing two of them teaches nothing except the exact spelling.
    """
    if not name:
        return None
    key = name.strip().lower().replace("_", "-")
    if key.endswith(".md"):
        key = key[:-3]
    p = _DIR / f"{key}.md"
    return p if p.is_file() else None
