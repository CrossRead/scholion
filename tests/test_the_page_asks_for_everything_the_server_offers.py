"""A capability that reaches the engine and the command line and not the browser.

`test_parity` holds the rule one level up: a route exists, and a command exists
beside it. What it cannot see is whether any face RENDERS what that route
returns. A route the server answers and the page never asks for is a capability
that exists in the JSON, in the command line and in the assistant's tools — and
not for the person who opened the application.

That is not hypothetical. `/api/limits` — «what this data cannot answer, and what
would close it», one of the sentences this product is sold on — was served, was
in the parity map with a command beside it, and was never called by the page at
all. Nothing failed, because nothing asked. It was found by a person wondering
aloud whether the new work reached the web, which is exactly the question a test
should be answering.

The `POST` side is listed rather than demanded: a write the page cannot trigger
is a real gap, and naming it is how it stays visible instead of being discovered
the same way.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import contract, engine

WEB = Path(engine.__file__).resolve().parent.parent / "web" / "index.html"

#: Writes the page does not offer, by name and with the reason. Neither is a
#: silent exception: one is superseded and kept only because the contract may not
#: shrink, and the other is a capability the interface has not been given yet.
POST_NOT_IN_THE_PAGE = {
    "/api/ingest-garmin":
        "superseded by /api/ingest-wearable when a second device arrived. The name "
        "survives because the public contract may not shrink; the page uses the "
        "one that asks which device it is looking at.",
    "/api/ingest-studies":
        "a real gap: doctors' conclusions can be loaded from the command line and "
        "not from the page. Recorded here so that it is a known absence rather "
        "than a discovery.",
}


class TestEveryReadReachesTheBrowser(unittest.TestCase):

    def setUp(self):
        if not WEB.exists():
            self.skipTest("this build carries no web page")
        self.page = WEB.read_text(encoding="utf-8")
        self.called = set(re.findall(r"""['"](/api/[a-z0-9/-]+)""", self.page))

    def test_the_page_asks_for_every_get_route(self):
        gets = {r.split(" ", 1)[1] for r in contract.server_routes()
                if r.startswith("GET /api/")}
        never = sorted(gets - self.called)
        self.assertEqual([], never,
                         "the server answers these and the page never asks — they exist for "
                         "every face except the one most people use: " + ", ".join(never))

    def test_the_scan_is_finding_routes_at_all(self):
        """A regex that matches nothing would pass the test above for ever."""
        self.assertGreater(len(self.called), 20,
                           "the page appears to call almost no routes — the scan is broken")

    def test_every_write_the_page_cannot_do_is_named_with_a_reason(self):
        posts = {r.split(" ", 1)[1] for r in contract.server_routes()
                 if r.startswith("POST /api/")}
        unexplained = sorted((posts - self.called) - set(POST_NOT_IN_THE_PAGE))
        self.assertEqual([], unexplained,
                         "the page cannot perform these writes and nobody said why: "
                         + ", ".join(unexplained))

    def test_no_reason_outlives_the_route_it_is_about(self):
        posts = {r.split(" ", 1)[1] for r in contract.server_routes()}
        stale = sorted(set(POST_NOT_IN_THE_PAGE) - posts)
        self.assertEqual([], stale,
                         "these are excused and no longer exist: " + ", ".join(stale))

    def test_a_route_that_gained_a_renderer_stops_being_excused(self):
        """An exception kept after it stopped applying is a lie with a reason
        attached."""
        wrong = sorted(set(POST_NOT_IN_THE_PAGE) & self.called)
        self.assertEqual([], wrong,
                         "the page does call these — remove them from the list: "
                         + ", ".join(wrong))


class TestWhatTheNewWorkRendersInParticular(unittest.TestCase):
    """The two sentences that prompted all of this, pinned where they are shown."""

    def setUp(self):
        if not WEB.exists():
            self.skipTest("this build carries no web page")
        self.page = WEB.read_text(encoding="utf-8")

    def test_the_profile_tab_shows_what_the_profile_is_missing(self):
        self.assertIn("/api/limits", self.page)
        self.assertIn("web.metrics.missing_head", self.page,
                      "the page fetches the limits and says nothing about them")

    def test_the_percentiles_carry_the_panel_they_are_a_position_inside(self):
        self.assertIn("method_caveats", self.page,
                      "the caveats travel in every answer and reach no reader")
        self.assertIn("panel_", self.page,
                      "the page does not single out the caveat about the reference panel")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
