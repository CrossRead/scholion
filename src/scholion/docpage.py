"""The documents of the package, as pages.

`scholion doc <name>` prints one at a terminal. The same nine files are what the
product's own output points at — «see PREPARING-THE-GENOME.md» — and a person
reading the interface has no terminal in front of them. So the local server
opens them too, and this is the part that turns one into a page.

The renderer is small on purpose and is not a Markdown implementation. It covers
what these nine documents actually use, measured rather than assumed: headings,
paragraphs, bullet and numbered lists, tables, fenced code, rules, links, bold,
italic and inline code. Anything it does not know survives as its own text
rather than disappearing — the failure mode of a partial renderer must be a line
that looks plain, never a line that is gone.

Nothing is fetched: the page carries its own style and no script at all. It
prints, which is the point — the clinician document exists to be handed over.
"""
from __future__ import annotations

import html
import re
from typing import List

from . import docs as _docs
from .i18n import t as _t

_STYLE = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#faf9f7;color:#23211d;
     font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:44rem;margin:0 auto;padding:2.4rem 1.25rem 5rem}
h1{font-size:1.85rem;line-height:1.25;margin:0 0 1.2rem}
h2{font-size:1.3rem;margin:2.2rem 0 .7rem;padding-bottom:.3rem;border-bottom:1px solid #e4e1db}
h3{font-size:1.08rem;margin:1.6rem 0 .5rem}
h4,h5,h6{font-size:1rem;margin:1.3rem 0 .4rem}
p,ul,ol{margin:0 0 1rem}
li{margin:.3rem 0}
a{color:#2f6ea8}
code{background:#efece6;border-radius:4px;padding:.1em .35em;font-size:.9em}
pre{background:#efece6;border-radius:8px;padding:.85rem 1rem;overflow-x:auto}
pre code{background:none;padding:0}
hr{border:0;border-top:1px solid #e4e1db;margin:2rem 0}
blockquote{margin:0 0 1rem;padding:.1rem 0 .1rem 1rem;border-left:3px solid #d8d4cc;color:#55524b}
.tw{overflow-x:auto;margin:0 0 1rem}
table{border-collapse:collapse;width:100%;font-size:.94rem}
th,td{border:1px solid #e4e1db;padding:.45rem .6rem;text-align:left;vertical-align:top}
th{background:#f2efe9}
.back{display:inline-block;margin-bottom:1.6rem;font-size:.92rem}
.foot{margin-top:3rem;padding-top:1rem;border-top:1px solid #e4e1db;color:#6b6862;font-size:.88rem}
@media print{.back{display:none}body{background:#fff}}
"""

_INLINE = (
    (re.compile(r"`([^`]+)`"), lambda m: "<code>" + m.group(1) + "</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"),
     lambda m: '<a href="' + m.group(2) + '">' + m.group(1) + "</a>"),
    (re.compile(r"\*\*([^*]+)\*\*"), lambda m: "<b>" + m.group(1) + "</b>"),
    (re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)"), lambda m: "<i>" + m.group(1) + "</i>"),
)


def _inline(s: str) -> str:
    """Escape first, then mark up. In that order nothing in the document can
    become a tag, and the markup this function adds is the only markup there is."""
    out = html.escape(s, quote=False)
    for pat, rep in _INLINE:
        out = pat.sub(rep, out)
    return out


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def render(md: str) -> str:
    """Markdown → the body of a page. Unknown constructs come through as text."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: List[str] = []
    i, n = 0, len(lines)
    para: List[str] = []

    def flush() -> None:
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < n:
        line = lines[i]
        if line.startswith("```"):
            flush()
            i += 1
            block: List[str] = []
            while i < n and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(block), quote=False) + "</code></pre>")
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", line):
            flush()
            out.append("<hr>")
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            flush()
            lvl = len(h.group(1))
            out.append(f"<h{lvl}>" + _inline(h.group(2).strip()) + f"</h{lvl}>")
            i += 1
            continue
        # a table: a header row, a separator of dashes, then rows
        if line.lstrip().startswith("|") and i + 1 < n \
                and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1]):
            flush()
            head = _cells(line)
            i += 2
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append(_cells(lines[i]))
                i += 1
            out.append('<div class="tw"><table><thead><tr>'
                       + "".join("<th>" + _inline(c) + "</th>" for c in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join("<td>" + _inline(c) + "</td>" for c in r)
                                 + "</tr>" for r in rows)
                       + "</tbody></table></div>")
            continue
        if re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*\d+[.)]\s+", line):
            flush()
            ordered = bool(re.match(r"^\s*\d+[.)]\s+", line))
            items: List[str] = []
            while i < n and (re.match(r"^\s*[-*+]\s+", lines[i])
                             or re.match(r"^\s*\d+[.)]\s+", lines[i])):
                items.append(_inline(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", lines[i])))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join("<li>" + x + "</li>" for x in items) + f"</{tag}>")
            continue
        if line.startswith(">"):
            flush()
            quote = []
            while i < n and lines[i].startswith(">"):
                quote.append(lines[i].lstrip("> ").rstrip())
                i += 1
            out.append("<blockquote>" + _inline(" ".join(quote)) + "</blockquote>")
            continue
        para.append(line.strip())
        i += 1
    flush()
    return "\n".join(out)


def page(name: str) -> str:
    """A whole self-contained page for one document, or the list of them."""
    p = _docs.path_of(name)
    if p is None:
        return _list_page()
    md = p.read_text(encoding="utf-8")
    # The document's own first heading, not the file name it was asked for by:
    # this page is handed over and printed, and «for-clinicians.md» in a browser
    # tab names our filing system rather than what the reader is holding.
    head = next((ln[2:].strip() for ln in md.split("\n") if ln.startswith("# ")), None)
    return _wrap(head or name, render(md))


def _list_page() -> str:
    items = "".join(f'<li><a href="/doc/{k}">{html.escape(k)}</a> '
                    f'<span style="color:#6b6862">{b // 1024} KB</span></li>'
                    for k, b in _docs.available())
    return _wrap(_t("web.doc.list_title"), f"<h1>{html.escape(_t('web.doc.list_title'))}</h1>"
                                           f"<ul>{items}</ul>")


def _wrap(title: str, body: str) -> str:
    return ("<!doctype html><html><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head><body><main>"
            f'<a class="back" href="/">\u2190 {html.escape(_t("web.doc.back"))}</a>'
            f"{body}"
            f'<div class="foot">{html.escape(_t("web.doc.foot"))}</div>'
            "</main></body></html>")
