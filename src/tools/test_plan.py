#!/usr/bin/env python3
"""Explain a conservative development selection; never replace release gates.

    python3 src/tools/test_plan.py --changed src/scholion/web/measurements.js
    python3 src/tools/test_plan.py --changed tests/test_example.py --run
    python3 src/tools/test_plan.py --since HEAD --out /tmp/plan.json

The reviewed narrow boundary covers selected producers, shared UI assets and
Python tests. Unclassified core, data, packaging and removals require discovery.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from check_registry import FAMILIES, path_for, test_path
from run_tests import ROOT, environment

ASSETS = {
    'gene-cards.js', 'gene-cards.css', 'measurements.js',
    'system-views.js', 'system-views.css', 'view-lifecycle.js',
}
LEVELS = {
    '1': 'Core and data', '2': 'Components', '3': 'Browser scenarios',
    '4': 'Installed delivery', '5': 'CLI, MCP, Plugin and Web',
}


def changed_files(root: Path, since: str) -> list[str]:
    """Include tracked, staged, unstaged and untracked changes; never parse lines."""
    git = ['git', '--no-optional-locks']
    location = subprocess.run([*git, 'rev-parse', '--show-toplevel'], cwd=root,
                              capture_output=True, stdin=subprocess.DEVNULL)
    if location.returncode or Path(location.stdout.decode('utf-8').strip()).resolve() != root.resolve():
        raise ValueError('--since requires the actual Git checkout root; use --changed in an archive')
    commands = [
        ['git', '--no-optional-locks', 'diff', '--name-only', '-z', since, '--'],
        ['git', '--no-optional-locks', 'ls-files', '--others', '--exclude-standard', '-z'],
    ]
    paths = set()
    for command in commands:
        result = subprocess.run(command, cwd=root, check=True, capture_output=True,
                                stdin=subprocess.DEVNULL)
        paths.update(x.decode('utf-8') for x in result.stdout.split(b'\0') if x)
    return sorted(paths)


def test_dependencies(root: Path) -> dict[str, set[str]]:
    """Imports and literal file references, including helpers and relative imports.

    False positives are deliberate: a mentioned input is cheaper than an omitted
    check. Nonliteral Python imports in tests select full discovery below.
    """
    files = sorted((root / 'tests').rglob('*.py'))
    by_module = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        module = rel[:-3].replace('/', '.')
        by_module[module] = rel
        by_module[path.stem] = rel
    product_modules = {'scholion.' + path[:-3].replace('/', '.'): path_for(path)
                       for family in FAMILIES for path in family.producers if path.endswith('.py')}
    by_filename = {}
    for path in files:
        by_filename.setdefault(path.name, set()).add(path.relative_to(root).as_posix())
    graph = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding='utf-8'))
        deps = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                package = rel[:-3].split('/')[:-1]
                if node.level:
                    package = package[:len(package) - node.level + 1]
                    prefix = '.'.join([*package, node.module] if node.module else package)
                else:
                    prefix = node.module or ''
                names = [prefix, *[prefix + '.' + a.name for a in node.names]]
            else:
                names = []
            deps.update(by_module[n] for n in names if n in by_module)
            deps.update(product_modules[n] for n in names if n in product_modules)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Test helpers often open a JS/CSS file or import another test
                # by a literal path rather than through a Python import.
                for token in re.findall(r'[\w.-]+\.py', node.value):
                    deps.update(by_filename.get(token, ()))
                for asset in ASSETS | {'index.html'}:
                    if asset in node.value:
                        deps.add('src/scholion/web/' + asset)
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, 'attr', '')
                if name in ('import_module', '__import__'):
                    if not node.args or not isinstance(node.args[0], ast.Constant):
                        deps.add('*')
                    elif isinstance(node.args[0].value, str):
                        target = node.args[0].value
                        if target in by_module:
                            deps.add(by_module[target])
                        if target in product_modules:
                            deps.add(product_modules[target])
        graph[rel] = deps
    return graph


def plan(root: Path, changed: list[str]) -> dict:
    root = root.resolve()
    paths, reasons = [], []
    narrow = {path_for(p) for family in FAMILIES for p in family.narrow}
    for raw in changed:
        path = Path(raw)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('changed paths must be repository-relative: ' + raw)
        rel = path.as_posix()
        paths.append(rel)
        resolved = (root / rel).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            reasons.append('Missing, removed or external input: ' + rel)
        elif not ((rel.startswith('tests/') and path.suffix == '.py') or
                  (path.parent.as_posix() == 'src/scholion/web' and path.name in ASSETS) or rel in narrow):
            reasons.append('No reviewed narrow boundary: ' + rel)
    if not paths:
        reasons.append('No changed inputs supplied; empty selection is not a pass')
    graph = test_dependencies(root)
    changed_set = set(paths)
    # All page consumers are relevant when a shared component changes: styles,
    # slots, links and delegated calls also have tests on the containing page.
    if any(p.startswith('src/scholion/web/') for p in paths):
        changed_set.add('src/scholion/web/index.html')
    impact = {p: ['changed input'] for p in changed_set}
    families = [family for family in FAMILIES
                if (any(path_for(p) in changed_set for p in family.producers)
                    or any(test_path(stem) in changed_set for stem in family.tests))]
    for family in families:
        for stem in family.tests:
            test = test_path(stem)
            if test in graph:
                impact.setdefault(test, []).append('registered family: ' + family.key)
            elif any(path_for(p) in changed_set for p in family.narrow):
                reasons.append('Missing registered semantic test: ' + test)
    for name, deps in graph.items():
        if '*' in deps:
            impact[name] = ['dynamic dependency; always include']
    while True:
        additions = {name: sorted(deps & impact.keys()) for name, deps in graph.items()
                     if name not in impact and deps & impact.keys()}
        if not additions:
            break
        impact.update(additions)
    tests = sorted(p[:-3].replace('/', '.') for p in graph
                   if Path(p).name.startswith('test') and p in impact)
    if not tests:
        reasons.append('No dependent test found; full discovery required')
    full = bool(reasons)
    command = [sys.executable, 'src/tools/run_tests.py', '--suite-only']
    if not full:
        command.extend(tests)
    interface_commands = sorted({name for family in families for name in family.commands})
    interface = [sys.executable, 'src/tools/check_interfaces.py']
    if not full:
        interface = [*interface, '--commands', *interface_commands] if interface_commands else []
    return {'schema': 2, 'changed': sorted(set(paths)),
            'mode': 'full' if full else 'targeted', 'fallback_reasons': reasons,
            'tests': [] if full else tests,
            'why': {p: impact[p] for p in sorted(impact) if p in graph},
            'command': command, 'levels': LEVELS,
            'families': [family.key for family in families],
            'interface_commands': interface_commands,
            'interface_scope': 'all' if full else 'selected' if interface else 'none',
            'interface_command': interface,
            'release_acceptance': False,
            'limitations': ['Static selection is development feedback, not release acceptance.',
                            'Browser and installed delivery need their own evidence.',
                            'Full source and package gates remain mandatory.']}


def run_plan(root: Path, report: dict) -> int:
    """Run the registry, semantic tests and applicable interface checks in order."""
    started = time.perf_counter()
    env = environment()
    steps = {}
    report['executed'] = steps
    with tempfile.TemporaryDirectory(prefix='scholion-development-check-') as tmp:
        output = Path(tmp) / 'interfaces.json'
        interfaces = report['interface_command']
        commands = {
            'registry': [sys.executable, 'src/tools/check_registry.py'],
            'tests': report['command'],
            'interfaces': [*interfaces, '--out', str(output)] if interfaces else [],
        }
        for name, command in commands.items():
            if not command:
                steps[name] = {'status': 'not_applicable'}
                continue
            if report.get('exit'):
                steps[name] = {'status': 'blocked'}
                continue
            begin = time.perf_counter()
            result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                    capture_output=(name == 'registry'))
            if name == 'registry' and result.returncode:
                sys.stderr.write(result.stdout.decode('utf-8', errors='replace'))
                sys.stderr.write(result.stderr.decode('utf-8', errors='replace'))
            steps[name] = {'status': 'passed' if result.returncode == 0 else 'failed',
                           'exit': result.returncode, 'seconds': time.perf_counter() - begin}
            if name == 'interfaces' and output.is_file():
                steps[name]['evidence'] = json.loads(output.read_text(encoding='utf-8'))
            report['exit'] = result.returncode
    report['seconds'] = time.perf_counter() - started
    return report['exit']


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--changed', nargs='+')
    group.add_argument('--since', help='Git revision; also includes untracked inputs')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = plan(ROOT, args.changed if args.changed is not None else changed_files(ROOT, args.since))
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    if args.run:
        run_plan(ROOT, report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return report.get('exit', 0)


if __name__ == '__main__':
    raise SystemExit(main())
