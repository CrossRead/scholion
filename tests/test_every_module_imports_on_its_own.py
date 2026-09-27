"""Every module of the package imports on its own, whatever was imported before.

`format_system.py` was split out of `format.py` on 18.09.2026 and took four
helpers back from `format`, while `format` imported `format_system` at its last
line. The pair worked only while `format` happened to be imported first: every
face and every test did so, the suite stayed green, and
`import scholion.format_system` on its own died with «cannot import name from
partially initialized module». An external review found it on 25.09.2026 by
importing the module the other way round.

The class is «a module that is correct only in one import order», and the order
is nobody's contract. So the check is not about that one pair: each module is
imported first, into an interpreter where nothing of the package is loaded yet.
The next split of a large module that repeats the pattern fails here, on the
day it is written, rather than in whoever imports the new module first.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import support

_PROBE = r"""
import importlib, json, sys, traceback
names = json.loads(sys.argv[1])
failed = {}
for name in names:
    for loaded in [m for m in sys.modules if m == "scholion" or m.startswith("scholion.")]:
        del sys.modules[loaded]
    try:
        importlib.import_module(name)
    except BaseException as exc:          # SystemExit from a module is a failure too
        failed[name] = "".join(traceback.format_exception_only(type(exc), exc)).strip()
print(json.dumps(failed))
"""


def _modules():
    """Every module of the package, named from the files on disk.

    From the files and not from `pkgutil.walk_packages`: the walk does not
    descend into a directory without `__init__.py`, and `vendor/` is one, so a
    walk-based list silently left the vendored detector out of the check.
    """
    import scholion
    root = Path(scholion.__file__).resolve().parent
    out = set()
    for f in root.rglob("*.py"):
        # `__main__` runs the command line when imported — importing it is running it.
        if "__pycache__" in f.parts or f.name == "__main__.py":
            continue
        parts = list(f.relative_to(root.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out.add(".".join(parts))
    return sorted(out)


class TestEveryModuleImportsFirst(unittest.TestCase):

    def test_the_list_is_not_empty_and_reaches_the_corners(self):
        """A list that found nothing would pass the check below by testing nothing."""
        names = _modules()
        for expected in ("scholion", "scholion.format", "scholion.format_system",
                         "scholion.format_primitives", "scholion.vendor.genomi.detection"):
            self.assertIn(expected, names)

    def test_each_module_imports_into_an_empty_interpreter(self):
        env = dict(os.environ, PYTHONPATH=str(support.SRC) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                   SCHOLION_OFFLINE="1")
        r = subprocess.run([sys.executable, "-c", _PROBE, json.dumps(_modules())],
                           capture_output=True, text=True, env=env, timeout=300,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(0, r.returncode, r.stderr[-2000:])
        failed = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual({}, failed,
                         "these modules fail when imported before anything else of the package:\n"
                         + "\n".join(f"{k}: {v}" for k, v in failed.items()))


if __name__ == "__main__":
    unittest.main()
