#!/usr/bin/env python3
"""Record checks and verify exact local evidence without silently skipping a gate.

    python3 src/tools/candidate_evidence.py record --out /tmp/check.json --level 2 -- python3 src/tools/run_tests.py --suite-only tests.test_view_lifecycle
    python3 src/tools/candidate_evidence.py verify /tmp/check.json

Records use the complete declared development input set, not mtimes or Git HEAD.
Verification is same-root, same-day and same-environment. It says which check was
performed, not that a whole release passed. Artifacts are explicit --artifact paths.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

from run_tests import ROOT, environment

DIRECTORIES = ('src', 'tests', 'knowledge', 'docs', 'demo', 'share',
               'agent-plugin', 'ouroboros_plugin', '.github', 'backlog')
EXCLUDED = {'__pycache__', 'node_modules', '.git', '.venv', '.pytest_cache',
            '.mypy_cache', '.ruff_cache', 'dist', 'build'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(root: Path) -> dict:
    """No personal profile or generated reports; every new/deleted public input counts."""
    paths = [p for p in root.iterdir() if p.is_file() and
             (p.suffix in ('.md', '.toml', '.sh', '.cff', '.json') or
              p.name in ('VERSION', 'NOTICE', 'LICENSE', 'LICENSE-DATA', '.gitignore', '.gitattributes', '.personal_patterns'))]
    for directory in DIRECTORIES:
        paths.extend(p for p in (root / directory).rglob('*') if p.is_file() and
                     not EXCLUDED.intersection(p.relative_to(root).parts) and
                     p.suffix not in ('.pyc', '.pyo') and p.name != '.DS_Store')
    result = {}
    for path in sorted(set(paths)):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('External input requires an explicit artifact: ' + str(path))
        result[path.relative_to(root).as_posix()] = {
            'sha256': digest(path), 'executable': bool(path.stat().st_mode & 0o111)}
    return result


def context(env: dict) -> dict:
    """Do not record credentials. Known execution switches and tool bytes are explicit."""
    tools = {}
    for name in ('python3', 'python', 'node', 'bash', 'uv', 'claude'):
        found = shutil.which(name, path=env.get('PATH'))
        if found:
            path = Path(found).resolve()
            tools[name] = {'path': str(path), 'sha256': digest(path)}
    keys = ('CI', 'LANG', 'LC_ALL', 'TZ', 'TMPDIR', 'PYTHONPATH', 'PYTHONHASHSEED',
            'PYTHONUTF8', 'PYTHONIOENCODING', 'SOURCE_DATE_EPOCH')
    switches = {k: v for k, v in env.items() if k in keys or k.startswith('SCHOLION_')}
    # Only the test runner's pins and skip flags are expected; do not retain any
    # credentials a caller happened to put under a product-prefixed variable.
    switches = {k: v for k, v in switches.items() if k in keys or k in
                ('SCHOLION_PROFILE_DIR', 'SCHOLION_OFFLINE', 'SCHOLION_LANG',
                 'SCHOLION_GENOME_VCF', 'SCHOLION_GENOME_DIR', 'SCHOLION_GENE_GFF3',
                 'SCHOLION_WORKSTATION') or k.startswith('SCHOLION_SKIP_')}
    packages = []
    for distribution in metadata.distributions():
        # RECORD and metadata change on installation even when a version label
        # was reused. Store digests, not local source URLs or package contents.
        content = '\n'.join(distribution.read_text(name) or '' for name in
                            ('METADATA', 'RECORD', 'direct_url.json'))
        packages.append({'name': distribution.metadata.get('Name', ''),
                         'version': distribution.version,
                         'metadata_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()})
    packages.sort(key=lambda item: (item['name'], item['version'], item['metadata_sha256']))
    return {'python': sys.version, 'executable': str(Path(sys.executable).resolve()),
            'python_sha256': digest(Path(sys.executable)), 'platform': platform.platform(),
            'day_utc': datetime.now(timezone.utc).date().isoformat(),
            'tools': tools, 'packages': packages, 'switches': switches,
            'environment_sha256': hashlib.sha256(
                json.dumps({k: v for k, v in env.items() if k in
                            (*keys, 'PATH', 'HOME', 'TMP', 'TEMP') or
                            k.startswith(('SCHOLION_', 'PYTHON', 'UV_', 'NODE_', 'LC_'))},
                           sort_keys=True).encode('utf-8')).hexdigest()}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def record(root: Path, output: Path, command: list[str], level: int,
           artifacts: list[Path], env: dict) -> int:
    root, output = root.resolve(), output.resolve()
    if not command:
        raise ValueError('A check command is required')
    if output.exists() or output.with_suffix('.log').exists():
        raise ValueError('Evidence is append-only; choose a new output filename')
    output.parent.mkdir(parents=True, exist_ok=True)
    before = inputs(root)
    runtime = context(env)
    executable = shutil.which(command[0], path=env.get('PATH'))
    if executable is None:
        raise ValueError('Check executable not found: ' + command[0])
    program = Path(executable).resolve()
    artifact_before = {str(p.resolve()): digest(p) for p in [*artifacts, program]}
    log = output.with_suffix('.log')
    started = time.time()
    evidence = {'schema': 1, 'state': 'running', 'root': str(root), 'level': level,
                'command': command, 'inputs': before, 'context': runtime,
                'artifacts': artifact_before, 'started': started,
                'release_acceptance': False}
    write_json(output, evidence)
    with log.open('wb') as stream:
        result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT)
    after = inputs(root)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    artifact_after = {name: digest(Path(name)) if Path(name).is_file() else None
                      for name in artifact_before}
    stable = not changed and artifact_before == artifact_after and runtime == context(env)
    evidence.update(state='complete', exit=result.returncode, finished=time.time(),
                    seconds=time.time() - started, changed_inputs=changed, stable=stable,
                    log=str(log), log_sha256=digest(log))
    write_json(output, evidence)
    return result.returncode or (0 if stable else 2)


def verify(root: Path, evidence: dict, env: dict) -> dict:
    reasons = []
    if evidence.get('schema') != 1 or evidence.get('state') != 'complete':
        reasons.append('Missing or incomplete record')
    if evidence.get('exit') != 0 or evidence.get('stable') is not True:
        reasons.append('Check failed or inputs changed during execution')
    if evidence.get('root') != str(root.resolve()):
        reasons.append('Different source/package root')
    current = inputs(root)
    saved = evidence.get('inputs', {})
    changed = sorted(k for k in current.keys() | saved.keys() if current.get(k) != saved.get(k))
    if changed:
        reasons.append('Input content or membership changed')
    if evidence.get('context') != context(env):
        reasons.append('Interpreter, tools, environment or UTC day changed')
    log = Path(evidence.get('log', ''))
    if not log.is_file() or digest(log) != evidence.get('log_sha256'):
        reasons.append('Missing or changed check log')
    for name, value in evidence.get('artifacts', {}).items():
        path = Path(name)
        if not path.is_file() or digest(path) != value:
            reasons.append('Missing or changed artifact: ' + name)
    return {'reusable': not reasons, 'reasons': reasons, 'changed_inputs': changed,
            'command': evidence.get('command'), 'level': evidence.get('level'),
            'seconds': evidence.get('seconds'), 'release_acceptance': False,
            'limitations': 'This verifies only the recorded command, including its skips; '
                          'it does not certify other levels, platforms or publication.'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('record')
    run.add_argument('--out', type=Path, required=True)
    run.add_argument('--level', type=int, choices=range(1, 6), required=True)
    run.add_argument('--artifact', type=Path, action='append', default=[])
    run.add_argument('command', nargs=argparse.REMAINDER)
    check = sub.add_parser('verify')
    check.add_argument('record', type=Path)
    args = parser.parse_args(argv)
    env = environment()
    if args.action == 'record':
        command = args.command[1:] if args.command[:1] == ['--'] else args.command
        status = record(ROOT, args.out, command, args.level, args.artifact, env)
        print('Recorded check:', args.out, 'exit:', status)
        return status
    report = verify(ROOT, json.loads(args.record.read_text(encoding='utf-8')), env)
    print(json.dumps(report, indent=2))
    return 0 if report['reusable'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
