"""The page's look comes from Crossread, and Pico only where it is fenced.

0.6.0 moves the local web page onto Crossread, the project's own design system
(`web/crossread.css`). The screens are redrawn one at a time, so for the
length of the release Pico stays for the ones not yet redrawn — fenced: it
styles bare elements only inside `.pico`. Three things keep that honest.

1. **One source of colour** (C33). Every colour on the page is a name, and the
   names are decided in the token blocks at the top of the style sheet, where
   they point at `--cr-*`. A literal anywhere else is a colour that does not
   follow the theme: the dark palette drawn on light paper is how the charts
   looked in the first render, before they asked the tokens.
2. **Pico is fenced and dies with its last screen** (C32). It is the scoped
   build, it adds no specificity, its variables point at the page's names, and
   when nothing on the page is inside `.pico` any more, the file must be gone.
3. **The palette holds in both themes** (C34). Status text is readable on its
   own soft ground and on the page, secondary text too, and the statuses stay
   apart from each other by more than hue.
"""
from __future__ import annotations

import colorsys
from html.parser import HTMLParser
import re
import unittest

import support

WEB = support.SRC / "scholion" / "web"
PAGE = WEB / "index.html"
CROSSREAD = WEB / "crossread.css"
PICO = WEB / "pico.scoped.min.css"

LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}(?![\w-])|\brgba?\(\s*\d|\bhsla?\(\s*\d")


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _style(page: str) -> str:
    return page[page.index("<style>"):page.index("</style>")]


def _without_token_blocks(page: str) -> str:
    """The page with the blocks that are ALLOWED to decide a colour cut out:
    the Crossread mapping (`:root{…}` right after the Crossread comment), the
    Pico mapping (`:root:root:root{…}`) and the print palette."""
    out = page
    for opener in ("  :root{\n    --plane:var(--cr-bg);", "  :root:root:root{", "    :root{--ink:#000;"):
        i = out.index(opener)
        j = out.index("}", i) + 1
        out = out[:i] + out[j:]
    # Inline images are data, not colours.
    return re.sub(r"data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+", "", out)


class TestOneSourceOfColour(unittest.TestCase):

    def test_no_colour_literal_outside_the_token_blocks(self):
        rest = _without_token_blocks(_page())
        found = []
        for m in LITERAL.finditer(rest):
            line = rest.count("\n", 0, m.start()) + 1
            found.append(f"~line {line}: {rest[max(0, m.start()-40):m.end()+20]!r}")
        self.assertEqual([], found, "a colour decided outside the token blocks")

    def test_the_page_names_point_at_crossread(self):
        style = _style(_page())
        block = style[style.index("--plane:var(--cr-bg)"):]
        block = block[:block.index("}")]
        for name in ("--plane", "--surface", "--ink", "--muted", "--accent", "--good",
                     "--warning", "--critical", "--border"):
            with self.subTest(name=name):
                m = re.search(re.escape(name) + r"\s*:\s*([^;]+);", block)
                self.assertIsNotNone(m, f"{name} is not declared in the token block")
                self.assertIn("--cr-", m.group(1))

    def test_a_chart_asks_the_tokens_when_it_draws(self):
        page = _page()
        self.assertIn("function tok(", page)
        self.assertIn("chartColours();", page)
        for literal in ('"#898781"', '"#a9a89f"', '"#2c2c2a"', '"#111"'):
            self.assertNotIn(literal, page)

    def test_the_theme_follows_the_system_unless_pinned(self):
        page = _page()
        self.assertNotIn('<html lang="en" data-theme=', page, "the page pins a theme")
        self.assertIn("localStorage.getItem('scholion-theme')", page)
        self.assertIn("web.menu.theme", page)


class TestPicoIsFenced(unittest.TestCase):

    def test_the_page_carries_crossread_and_only_the_fenced_pico(self):
        links = re.findall(r'<link rel="stylesheet" href="([^"]+)">', _page())
        self.assertIn("/crossread.css", links)
        self.assertTrue(set(links) <= {"/crossread.css", "/pico.scoped.min.css"}, links)
        self.assertFalse((WEB / "pico.min.css").exists(), "the unfenced Pico is still packaged")
        server = (support.SRC / "scholion" / "server.py").read_text(encoding="utf-8")
        self.assertNotIn('"/pico.min.css"', server)

    def test_nothing_in_the_style_layer_comes_from_the_network(self):
        style = _style(_page())
        self.assertIsNone(re.search(r"https?://", style))
        self.assertIsNone(re.search(r"@import\s+url\(\s*['\"]?https?:", CROSSREAD.read_text(encoding="utf-8")))

    def test_the_fence_adds_no_specificity(self):
        text = PICO.read_text(encoding="utf-8")
        body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        self.assertIsNone(re.search(r"(?<!:where\()\.pico(?![\w-])", body),
                          "a `.pico` scope that raises specificity: run src/tools/scope_pico.py")
        self.assertIn(":where(.pico)", body)
        self.assertIn("Licensed under MIT", text[:300], "Pico's licence banner must travel with it")

    def test_every_pico_variable_the_page_sets_reads_a_name(self):
        style = _style(_page())
        block = style[style.index(":root:root:root{"):]
        block = block[:block.index("}")]
        decls = re.findall(r"(--pico-[\w-]+)\s*:\s*([^;]+);", block)
        self.assertTrue(decls)
        for name, value in decls:
            with self.subTest(name=name):
                self.assertIn("var(--", value, f"{name} is set to a literal")

    def test_no_crossread_component_is_drawn_inside_the_fence(self):
        """The dynamic view can leave Pico without inheriting a parent's fence."""
        page = _page()
        class Placement(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.parents = None

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('id') == 'view':
                    self.parents = list(self.stack)
                if tag not in ('meta', 'link', 'img', 'input', 'br', 'hr'):
                    self.stack.append((tag, attrs.get('class', '')))

            def handle_endtag(self, tag):
                for index in range(len(self.stack) - 1, -1, -1):
                    if self.stack[index][0] == tag:
                        self.stack = self.stack[:index]
                        break

        parser = Placement()
        parser.feed(page)
        self.assertIsNotNone(parser.parents)
        self.assertFalse(any('pico' in classes.split() for _, classes in parser.parents))
        self.assertIn("if(el.id==='view') el.className='pico'", page)
        self.assertIn("v.className='intake-view'", page)

    def test_container_controls_are_rendered_only_outside_legacy_pico(self):
        class Placement(HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.parents = None

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get('id') == 'container-dialog':
                    self.parents = list(self.stack)
                if tag not in ('meta', 'link', 'img', 'input', 'br', 'hr'):
                    self.stack.append((tag, attrs.get('class', '')))

            def handle_endtag(self, tag):
                for index in range(len(self.stack) - 1, -1, -1):
                    if self.stack[index][0] == tag:
                        self.stack = self.stack[:index]
                        break

        parser = Placement()
        parser.feed(_page())
        self.assertIsNotNone(parser.parents)
        self.assertFalse(any('pico' in classes.split() for _, classes in parser.parents))
        script = _page().split('<script id="container-ui">')[1].split('</script>', 1)[0]
        self.assertIn("const dialog=$('#container-dialog')", script)
        self.assertNotIn("$('#view')", script)
        self.assertNotIn("$('#legacy')", script)

    def test_when_the_fence_is_empty_pico_leaves(self):
        if 'class="pico"' not in _page():
            self.assertFalse(PICO.exists(), "no screen is inside .pico any more: remove Pico "
                                            "from the package, the route and ATTRIBUTION.md")


def _tokens(css: str, selector_start: str) -> dict:
    i = css.index(selector_start)
    block = css[css.index("{", i) + 1:css.index("}", i)]
    return dict(re.findall(r"--(cr-[\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _lum(hexc: str) -> float:
    r, g, b = (int(hexc[k:k + 2], 16) / 255 for k in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TestThePaletteHoldsInBothThemes(unittest.TestCase):

    def themes(self):
        css = CROSSREAD.read_text(encoding="utf-8")
        return {"light": _tokens(css, ':root,[data-theme="light"]'),
                "dark": _tokens(css, '[data-theme="dark"]{')}

    def test_status_and_secondary_text_hold_four_and_a_half(self):
        for theme, t in self.themes().items():
            for text in ("cr-text", "cr-text-secondary", "cr-text-tertiary"):
                for ground in ("cr-bg", "cr-surface"):
                    with self.subTest(theme=theme, text=text, ground=ground):
                        self.assertGreaterEqual(_contrast(t[text], t[ground]), 4.5)
            for status in ("cr-success", "cr-warning", "cr-danger", "cr-info"):
                for ground in ("cr-bg", "cr-surface", status + "-soft"):
                    with self.subTest(theme=theme, status=status, ground=ground):
                        self.assertGreaterEqual(_contrast(t[status], t[ground]), 4.5)

    def test_statuses_differ_by_more_than_hue(self):
        """A reader who cannot tell hues apart still tells warning from danger:
        either the lightness or the hue is far apart."""
        for theme, t in self.themes().items():
            names = ("cr-success", "cr-warning", "cr-danger", "cr-info")
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    ha, la, _ = colorsys.rgb_to_hls(*(int(t[a][k:k + 2], 16) / 255 for k in (1, 3, 5)))
                    hb, lb, _ = colorsys.rgb_to_hls(*(int(t[b][k:k + 2], 16) / 255 for k in (1, 3, 5)))
                    dh = min(abs(ha - hb), 1 - abs(ha - hb)) * 360
                    with self.subTest(theme=theme, pair=(a, b)):
                        self.assertTrue(dh >= 40 or abs(la - lb) >= 0.08,
                                        f"{a} and {b}: hue {dh:.0f}°, lightness {abs(la-lb):.2f}")

    def test_the_accent_is_not_a_status(self):
        for theme, t in self.themes().items():
            ha = colorsys.rgb_to_hls(*(int(t["cr-accent"][k:k + 2], 16) / 255 for k in (1, 3, 5)))[0]
            for status in ("cr-success", "cr-warning", "cr-danger", "cr-info"):
                hs = colorsys.rgb_to_hls(*(int(t[status][k:k + 2], 16) / 255 for k in (1, 3, 5)))[0]
                dh = min(abs(ha - hs), 1 - abs(ha - hs)) * 360
                with self.subTest(theme=theme, status=status):
                    self.assertGreaterEqual(dh, 10, "the accent sits on a status hue")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
