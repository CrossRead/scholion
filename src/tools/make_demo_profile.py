#!/usr/bin/env python3
"""A compatibility wrapper: the demo-profile generator has moved into the package.

The code itself now lives in `scholion/demo.py` — otherwise it does not get into the
wheel and the `scholion demo` command does not find it. This file is kept so as not
to break the tests, the documentation and the habit of running the generator
directly.

    python3 src/tools/make_demo_profile.py        # still works
    scholion demo                                 # the same thing from the package
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scholion.demo import *          # noqa: F401,F403  — re-export for the tests
from scholion.demo import main

if __name__ == "__main__":
    sys.exit(main())
