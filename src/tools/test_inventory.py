#!/usr/bin/env python3
"""Inventory tests and optionally measure their cost without changing selection.

    python3 src/tools/test_inventory.py --out /tmp/tests.json
    python3 src/tools/test_inventory.py --run --out /tmp/timing.json tests.test_example

Identical method bodies and inherited methods are review candidates, not proof
of redundant scenarios. Reports contain test identifiers, never test output or
profile contents. Timing includes per-test setup/cleanup; total time additionally
includes discovery and class/module fixtures. No result is cached between runs.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import json
import os
from pathlib import Path
import sys
import time
import unittest

from run_tests import ROOT, environment


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def static_inventory(root: Path) -> dict:
    bodies = defaultdict(list)
    overwritten = []
    for path in sorted((root / 'tests').glob('test*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            seen = set()
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                name = f'{path.relative_to(root).as_posix()}:{cls.name}.{method.name}'
                if method.name in seen:
                    overwritten.append(name)
                seen.add(method.name)
                if not method.name.startswith('test'):
                    continue
                body = method.body
                if ast.get_docstring(method):
                    body = body[1:]
                key = ast.dump(ast.Module(body=body, type_ignores=[]), include_attributes=False)
                bodies[key].append(name)
    return {'identical_bodies_for_review': [v for v in bodies.values() if len(v) > 1],
            'overwritten_methods': overwritten}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('tests', nargs='*')
    args = parser.parse_args(argv)
    os.environ.update(environment())
    sys.path[:0] = [str(ROOT), str(ROOT / 'src'), str(ROOT / 'tests')]
    started = time.perf_counter()
    loader = unittest.TestLoader()
    suite = (loader.loadTestsFromNames(args.tests) if args.tests else
             loader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT)))
    tests = list(flatten(suite))
    ids, methods = defaultdict(list), defaultdict(list)
    for test in tests:
        ids[test.id()].append(test.id())
        method = getattr(type(test), getattr(test, '_testMethodName', ''), None)
        if method:
            methods[f'{method.__module__}.{method.__qualname__}'].append(test.id())
    rows = []

    class TimedResult(unittest.TextTestResult):
        def startTest(self, test):
            self.started = time.perf_counter()
            super().startTest(test)

        def stopTest(self, test):
            rows.append({'id': test.id(), 'seconds': time.perf_counter() - self.started})
            super().stopTest(test)

    result = unittest.TextTestRunner(resultclass=TimedResult).run(suite) if args.run else None
    modules = defaultdict(float)
    for row in rows:
        modules[row['id'].rsplit('.', 2)[0]] += row['seconds']
    report = {**static_inventory(ROOT), 'tests': len(tests), 'ids': list(ids),
              'duplicate_ids': [k for k, v in ids.items() if len(v) > 1],
              'inherited_methods_for_review': [v for v in methods.values() if len(v) > 1],
              'discovery_errors': loader.errors, 'python': sys.version, 'root': str(ROOT),
              'ran': args.run, 'ok': result.wasSuccessful() if result else None,
              'seconds': time.perf_counter() - started, 'rows': rows,
              'slow_modules': sorted(modules.items(), key=lambda x: -x[1])}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{len(tests)} tests; report: {args.out}')
    return int(bool(loader.errors) or bool(result and not result.wasSuccessful()))


if __name__ == '__main__':
    raise SystemExit(main())
