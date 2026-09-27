"""An annotation that names a type nobody imported runs — and fails the public linter.

Every module here postpones the evaluation of annotations, so `-> Optional[str]`
in a module that imports only `Dict` is never looked at while the program runs:
the suite is green, the command works, and the first reader to object is the
linter of the public matrix, after publication. It happened while 0.5.10 was
being written, and it was caught by accident.

So the annotations are evaluated here, once, for every function of the package.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import typing
import unittest

import support  # noqa: F401
import scholion


def undefined_in_annotations():
    found = []
    seen = 0
    for m in pkgutil.walk_packages(scholion.__path__, "scholion."):
        if ".vendor." in m.name or m.name.endswith("__main__"):
            continue
        try:
            mod = importlib.import_module(m.name)
        except Exception:                                            # noqa: BLE001
            continue          # a module that does not import has a test of its own
        for obj in list(vars(mod).values()):
            if getattr(obj, "__module__", None) != m.name:
                continue
            if inspect.isfunction(obj):
                functions = [obj]
            elif inspect.isclass(obj):
                functions = [f for f in vars(obj).values() if inspect.isfunction(f)]
            else:
                continue
            for f in functions:
                seen += 1
                try:
                    typing.get_type_hints(f)
                except NameError as exc:
                    found.append(f"{m.name}.{f.__qualname__}: {exc}")
                except Exception:                                    # noqa: BLE001
                    pass      # a forward reference to a local class is not this defect
    return seen, found


class TestNoAnnotationNamesWhatWasNeverImported(unittest.TestCase):

    def test_the_reader_sees_what_it_is_for(self):
        scope: dict = {}
        exec("from __future__ import annotations\n"
             "def f(x) -> Optional[str]:\n    return x\n", scope)
        with self.assertRaises(NameError):
            typing.get_type_hints(scope["f"])

    def test_in_the_package(self):
        seen, found = undefined_in_annotations()
        self.assertGreater(seen, 1000, "the walk found next to nothing")
        self.assertEqual([], found)


if __name__ == "__main__":
    unittest.main()
