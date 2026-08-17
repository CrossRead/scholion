"""Message catalogue: one text, two languages, chosen at print time.

Why a catalogue at all. The reports *are* the product — `overview`, `labs`,
`second-opinion` are what a person reads and what an assistant quotes. Until now
they existed only in Russian, which made "an English project" untrue no matter
what the README said. From now on English is the default and Russian is a
choice, and both live side by side instead of one being a translation branch of
the other.

Why not gettext. The project runs on the standard library and nothing else —
that is a property, not an accident. `.po`/`.mo` files would add a compilation
step, a toolchain and a build artefact nobody can read in a diff. Two plain
dictionaries are greppable, diffable, and checked by a test that no compiler
can replace.

Resolution order, most explicit first:

  1. `set_lang()` — an explicit choice inside one *thread* (see below);
  2. `SCHOLION_LANG` — the environment, for shells and shortcuts;
  3. `en` — the default.

Why the choice is per thread and not per process. The web server is a
`ThreadingHTTPServer`: two browser tabs — one Russian, one English — are served
at the same time by two threads. With the language in a module-level global the
second request would overwrite the first one's choice half-way through
rendering, and a report would come out in two languages at once. The choice is
therefore stored in `threading.local()`: it belongs to the request being served,
not to the process. For the CLI, which is single-threaded, nothing changes.

Fallback is deliberate and quiet: a key missing from `ru` is answered from `en`.
A person reading a Russian report should see one English sentence rather than a
crash or a raw identifier. A key missing from *both* is a defect, not a
language problem, and is returned as `⟦key⟧` so it cannot be mistaken for text.

Keys are a contract. They are quoted in tests and, indirectly, in anything that
parses reports — renaming one is the same kind of change as renaming a CLI
command, and `tests/test_i18n.py` will not let the two catalogues drift apart.
"""
from __future__ import annotations

import os
import threading
from typing import Dict, Tuple

from . import en as _en
from . import ru as _ru

CATALOGUES: Dict[str, Dict[str, str]] = {"en": _en.MESSAGES, "ru": _ru.MESSAGES}
DEFAULT = "en"

# The chosen language belongs to the thread that is doing the printing, not to the
# process: see the note about ThreadingHTTPServer at the top of the module.
_state = threading.local()


def available() -> Tuple[str, ...]:
    """Language codes this build can print in."""
    return tuple(sorted(CATALOGUES))


def lang() -> str:
    """The language in effect right now."""
    current = getattr(_state, "current", "")
    if current:
        return current
    env = (os.environ.get("SCHOLION_LANG") or "").strip().lower()[:2]
    return env if env in CATALOGUES else DEFAULT


def set_lang(code: str | None) -> str:
    """Choose a language for the current thread. `None` or an unknown code resets to the default.

    Unknown codes are not an error: a shortcut carrying `SCHOLION_LANG=de` should
    print English, not fail. Refusing to start because of a display preference
    would be a worse answer than quietly printing the language everyone reads.
    """
    code = (code or "").strip().lower()[:2]
    _state.current = code if code in CATALOGUES else ""
    return lang()


def messages(code: str | None = None) -> Dict[str, str]:
    """The whole catalogue of one language, ready to hand to a client.

    The web page looks its labels up in a copy of this dictionary instead of
    asking the server for a phrase at a time. The fallback of the single-key
    lookup is reproduced here: the reply for `ru` is English overlaid with
    Russian, so a key missing from `ru` arrives as an English sentence rather
    than as a hole in the interface.
    """
    code = (code or "").strip().lower()[:2]
    if code not in CATALOGUES:
        code = DEFAULT
    return {**CATALOGUES[DEFAULT], **CATALOGUES[code]}


def t(key: str, /, **kw) -> str:
    """Look up `key` in the current language and substitute `kw`.

    Substitution failures are not swallowed: a placeholder that the caller did
    not supply means the catalogue and the call site disagree, and printing a
    half-formatted sentence into a medical report is worse than a loud error.

    `key` is positional-only, and that slash is load-bearing. A catalogue phrase
    may contain any placeholder name, including `{key}` and `{n}` — and a phrase
    that happened to use `{key}` made `t("brief.no_metric", key=key)` collide
    with this function's own parameter and raise TypeError at the call site.
    The report then died on a marker that simply had no value, which is the most
    ordinary case there is. Placeholder names belong to the catalogue; the
    signature must not reserve any of them.
    """
    catalogue = CATALOGUES.get(lang(), CATALOGUES[DEFAULT])
    text = catalogue.get(key)
    if text is None:
        text = CATALOGUES[DEFAULT].get(key)
    if text is None:
        return f"⟦{key}⟧"
    return text.format(**kw) if kw else text


def plural(n: int, key: str, /, **kw) -> str:
    """Plural forms by suffix: `key.one` / `key.few` / `key.many`.

    English needs two forms, Russian three, and the rule differs — so the choice
    is made here rather than by the caller, and a language that needs only two
    simply repeats itself in the catalogue.
    """
    if lang() == "ru":
        hundreds, units = n % 100, n % 10
        if 11 <= hundreds <= 14:
            form = "many"
        elif units == 1:
            form = "one"
        elif 2 <= units <= 4:
            form = "few"
        else:
            form = "many"
    else:
        form = "one" if n == 1 else "many"
    return t(f"{key}.{form}", n=n, **kw)
