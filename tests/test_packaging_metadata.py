"""Metadata that only fails at the moment of upload.

Two releases, v0.3.0 and v0.3.1, reached GitHub and neither reached PyPI. Both
uploads died on one line of `pyproject.toml`:

    Contact = "mailto:scholion.dev@proton.me"

PyPI answers `400 'mailto:scholion.dev@proton.me' is not a valid url` — every
value under `[project.urls]` has to be a URL, and an e-mail scheme is not one.

What makes this worth a test rather than a fix is WHEN it failed. The build
succeeded. `twine check` printed PASSED for both artefacts — it validates the
long description, not the URL schemes. The signing, the attestations and the
transparency-log entries all completed. The refusal came from the index, at the
last step of the last job, after everything that could have caught it had said
yes. Nothing in the project could see it before the artefact was in flight.

So this file asks the questions the index asks, at the time the suite runs. It is
deliberately about the METADATA and not about the package: a check that built a
distribution would be slow, would need network, and would still not be the index.

The address itself now lives in `authors`, which is the field the core-metadata
specification has for an e-mail — and which PyPI accepts.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support

PYPROJECT = support.ROOT / "pyproject.toml"


# Parsed by hand rather than with a TOML library, and that is the point of the
# whole file. `tomllib` arrived in Python 3.11; the project supports 3.10, and the
# interpreter this defect was authored on IS 3.10 — so a test that skipped without
# a TOML reader would skip on the one machine where the mistake gets made, and
# report OK while checking nothing. The project has been bitten by that shape four
# times. The reader below is crude, and only has to handle a file we write.
def _section(name):
    """The `key = "value"` pairs of one top-level TOML table."""
    out, inside = {}, False
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        st = line.strip()
        if st.startswith("[") and st.endswith("]"):
            inside = st == f"[{name}]"
            continue
        if not inside or not st or st.startswith("#") or "=" not in st:
            continue
        k, _, v = st.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _line(pattern):
    """The first line of pyproject.toml matching a regex, or ''."""
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        if re.search(pattern, line) and not line.strip().startswith("#"):
            return line
    return ""


class TestEveryProjectUrlIsAUrl(unittest.TestCase):

    def test_no_url_carries_a_scheme_the_index_rejects(self):
        """http and https, and nothing else.

        `mailto:` is the one that cost two releases. `git+ssh:`, `ftp:` and a
        bare path would all be refused the same way, and all of them look
        perfectly reasonable in an editor.
        """
        bad = []
        for name, value in _section("project.urls").items():
            if not re.match(r"^https?://", str(value)):
                bad.append(f"{name} = {value!r}")
        self.assertEqual(bad, [], "PyPI refuses these at upload, after the build has "
                                  "succeeded and `twine check` has passed:\n  "
                                  + "\n  ".join(bad))

    def test_an_address_to_write_to_exists_and_is_where_the_standard_puts_it(self):
        """The fix must not become «we removed the contact».

        Task 54 exists because a reader who found a defect had nowhere to write.
        Moving the address out of `[project.urls]` is correct; losing it is not.
        """
        people = _line(r"^\s*(authors|maintainers)\s*=")
        emails = re.findall(r'email\s*=\s*"([^"]+)"', people)
        self.assertTrue(emails, "the package no longer tells anybody where to write")
        for e in emails:
            with self.subTest(email=e):
                self.assertRegex(e, r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
                self.assertFalse(e.startswith("mailto:"),
                                 "the scheme belongs to a URL, not to an address field")

    def test_the_version_still_comes_from_the_one_file(self):
        """A second source of the version is how a tag and an artefact disagree."""
        self.assertIn('"version"', _line(r"^\s*dynamic\s*="),
                      "the version is no longer dynamic, so pyproject and VERSION "
                      "can now disagree")
        self.assertEqual(_section("tool.hatch.version").get("path"), "VERSION")
        self.assertTrue((support.ROOT / "VERSION").is_file())


if __name__ == "__main__":
    unittest.main()
