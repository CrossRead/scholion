"""No text of this product tells a model to put it above everything else.

Until 0.6.0 the canon opened with «these rules take precedence over every other
instruction», and the phrase travelled into the skill, the tool server's
handshake, both READMEs, the hub manifest and the presentation. Inside Scholion
that was the intent: the rules outrank the rest of Scholion's own texts, and a
request for «a straight answer without the caveats» does not switch them off.
Read by a model inside somebody else's product, the same sentence claims rank
over the system prompt of the host and over the person the model works for — the
shape a catalogue reviewer holds a plugin for, and the shape a prompt injection
takes.

The claim is now said the size it is: first among Scholion's own documents. This
file keeps the wider one from coming back through any text that ships or reaches
a model. The release journal is history and is not rewritten.
"""
from __future__ import annotations

import re
import unittest

import support

ROOT = support.ROOT

#: What ships, and what a model or a host reads.
SCANNED = ("ASSISTANT-RULES.md", "README.md", "README.ru.md", "SECURITY.md", "PRIVACY.md",
           "CLAUDE.md", "share", "src", "agent-plugin", "ouroboros_plugin", "docs")
SUFFIXES = {".md", ".html", ".py", ".json", ".txt", ".sh"}

WIDE = re.compile(
    r"precedence\s+over\s+(?:every|any|all|everything)\b"
    r"|over\s+(?:every|any|all)\s+other\s+instructions?"
    r"|приоритет\s+над\s+(?:всеми|любыми)",
    re.I)


def _files():
    for name in SCANNED:
        p = ROOT / name
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in p.rglob("*"):
                if (f.is_file() and f.suffix in SUFFIXES and "__pycache__" not in f.parts
                        and "changelog" not in f.name.lower() and ".owner." not in f.name):
                    yield f


class TestNothingClaimsPrecedenceOverTheSystem(unittest.TestCase):

    def test_no_text_claims_rank_over_every_other_instruction(self):
        found = []
        for f in _files():
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for m in WIDE.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                found.append(f"{f.relative_to(ROOT).as_posix()}:{line}: «{m.group(0)}»")
        # This file names the phrase in order to forbid it.
        found = [x for x in found if not x.startswith("tests/")]
        self.assertEqual([], found,
                         "say it the size it is: «first among Scholion's own documents»")

    def test_the_canon_says_what_it_does_not_ask(self):
        """The narrower claim carries its own boundary, in the file every copy is made from."""
        head = (ROOT / "ASSISTANT-RULES.md").read_text(encoding="utf-8")[:1200]
        self.assertIn("Among Scholion's own documents it comes first", head)
        self.assertIn("does not ask a model to disregard the system it runs in", head)

    def test_the_handshake_says_it_the_same_size(self):
        from scholion import mcp_server
        answer = mcp_server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                    "params": {"protocolVersion": "2025-06-18"}})
        text = str(answer)
        self.assertIsNone(WIDE.search(text))
        self.assertIn("among Scholion's own documents", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
