"""Run equivalent synthetic scenarios through the product's real adapters.

This is a developer acceptance tool, not an alternate product entry point.
No scenario may read the owner's profile. Installed mode imports only the wheel;
the test driver and fixture may be copied from the sanitized build.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request


@dataclass(frozen=True)
class Scenario:
    name: str
    command: tuple
    route: str
    arguments: dict
    query: str = ''
    expected_refusal: str | None = None
    web_field: str | None = None


READS = (
    Scenario('metrics', ('metrics',), 'GET /api/metrics', {}),
    Scenario('lifestyle', ('lifestyle',), 'GET /api/lifestyle', {}),
    Scenario('overview', ('overview',), 'GET /api/overview', {}),
    Scenario('visit-sheet', ('overview', '--visit-sheet', '--compact'),
             'GET /api/visit-sheet', {'visit_sheet': True, 'compact': True}, 'compact=1'),
    Scenario('system-patient', ('system', 'lipids'), 'GET /api/system',
             {'key': 'lipids'}, 'key=lipids'),
    Scenario('system-clinician', ('system', 'lipids', '--register', 'clinician'),
             'GET /api/system', {'key': 'lipids', 'register': 'clinician'}, 'key=lipids&register=clinician'),
    Scenario('medications', ('medications',), 'GET /api/medications', {}),
    Scenario('labs', ('labs',), 'GET /api/labs', {}),
    Scenario('clinvar', ('clinvar',), 'GET /api/clinvar', {}),
    Scenario('genome-recorded', ('genome', 'rs1801133'), 'GET /api/genome',
             {'rsid': 'rs1801133'}, 'rsid=rs1801133'),
    Scenario('drug', ('drug', 'clopidogrel'), 'GET /api/drug',
             {'drug': 'clopidogrel'}, 'name=clopidogrel'),
    Scenario('prescription', ('prescription', 'clopidogrel'), 'GET /api/prescription-check',
             {'drug': 'clopidogrel'}, 'name=clopidogrel'),
    Scenario('acmg', ('acmg',), 'GET /api/acmg', {}),
    Scenario('insight-review-preview', ('insight-snapshot',), 'GET /api/insight-snapshot', {}),
    Scenario('prs', ('prs',), 'GET /api/prs', {}),
    Scenario('goal', ('goal',), 'GET /api/goal', {}),
    Scenario('goal-suggest', ('goal-suggest',), 'GET /api/goal-suggest', {}),
    Scenario('focus', ('focus',), 'GET /api/focus', {}),
    Scenario('brief', ('brief',), 'GET /api/lifestyle-brief', {}),
    Scenario('suggest-tests', ('suggest-tests',), 'GET /api/suggest-tests', {}),
    Scenario('second-opinion', ('second-opinion',), 'GET /api/second-opinion', {}),
    Scenario('radar', ('radar',), 'GET /api/radar', {}),
    Scenario('systems-list', ('system',), 'GET /api/systems', {}),
    Scenario('limits', ('limits',), 'GET /api/limits', {}),
    Scenario('limits-bed', ('limits', '--bed', '--panel', 'ACMG'), 'GET /api/limits/bed',
             {'bed': True, 'panel': 'ACMG'}, 'panel=ACMG', expected_refusal='never_computed'),
    Scenario('screen', ('screen',), 'GET /api/screen', {}),
    Scenario('screen-cardio', ('screen', 'cardio'), 'GET /api/screen',
             {'disease_class': 'cardio'}, 'class=cardio'),
    Scenario('longevity', ('longevity',), 'GET /api/longevity', {}),
    Scenario('lipid-genetics', ('lipid-genetics',), 'GET /api/lipid-genetics', {}),
    Scenario('genome-status', ('genome-status',), 'GET /api/genome-status', {}),
    Scenario('sources', ('sources',), 'GET /api/sources', {}, web_field='data_sources'),
    Scenario('recompute-preview', ('recompute',), 'GET /api/recompute', {}),
)


def select(commands, parity, plugins):
    """Select by capability, failing closed for unimplemented scenarios."""
    known = {s.command[0] for s in READS} | {'focus-log'}
    requested = set(commands) if commands else known
    if requested - known:
        raise ValueError('No executable scenario: ' + ', '.join(sorted(requested - known)))
    cases = [s for s in READS if s.command[0] in requested]
    mappings = [(s.route, s.command[0]) for s in cases]
    if 'focus-log' in requested:
        mappings.append(('POST /api/focus/log', 'focus-log'))
    if 'insight-snapshot' in requested:
        mappings.append(('POST /api/insight-snapshot', 'insight-snapshot'))
    for route, command in mappings:
        if parity.get(route) != command or command not in plugins:
            raise ValueError('Scenario no longer matches contract: ' + route)
    return cases, 'focus-log' in requested


def payload(data):
    # Transport envelope only. Dates, paths, values and qualifications stay exact.
    return {k: v for k, v in data.items() if k != 'container'}


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(label + ': unequal semantic payloads' +
                             ('; differing keys: ' + ', '.join(str(k) for k in set(actual) | set(expected)
                               if actual.get(k) != expected.get(k))
                              if isinstance(actual, dict) and isinstance(expected, dict) else ''))


def hashes(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}


def rpc(command, name, arguments, env):
    from scholion import mcp_server
    frames = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': mcp_server.PROTOCOL_VERSION}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
         'params': {'name': name, 'arguments': arguments}},
    ]
    result = subprocess.run(command, input=''.join(json.dumps(f) + '\n' for f in frames),
                            env=env, text=True, encoding='utf-8', capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError('MCP process failed: ' + result.stderr[-1500:])
    replies = {r['id']: r for r in map(json.loads, result.stdout.splitlines()) if 'id' in r}
    if 'error' in replies.get(1, {}) or 'result' not in replies.get(1, {}):
        raise AssertionError('MCP initialization failed')
    if 'result' not in replies.get(2, {}):
        raise AssertionError('MCP tool failed: ' + str(replies.get(2)))
    return replies[2]['result']


@contextmanager
def http_server():
    from scholion import server
    srv = server._Server(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(srv.server_address[1])
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def request(base, route, body=None, headers=None):
    req = urllib.request.Request(base + route, headers=headers or {},
                                 data=None if body is None else json.dumps(body).encode())
    if body is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=90) as reply:
            return reply.status, json.load(reply)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def cli(arguments, env, as_json=True, allow_failure=False):
    result = subprocess.run([sys.executable, '-m', 'scholion', *arguments,
                             *(['--json'] if as_json else [])], env=env, stdin=subprocess.DEVNULL,
                            text=True, encoding='utf-8', capture_output=True, timeout=90)
    if result.returncode and not allow_failure:
        raise RuntimeError('CLI process failed (' + ' '.join(arguments) + '): ' + result.stderr[-1500:])
    if as_json:
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f'CLI {arguments[0]} returned no valid JSON (exit {result.returncode}): '
                + result.stderr[-1500:]
            ) from error
    return result.stdout.strip()


def read_case(case, base, env, plugin_entries, agent_command):
    from scholion import contract, i18n, mcp_server, ouroboros_tools
    data = cli(case.command, env, allow_failure=case.expected_refusal is not None)
    if case.expected_refusal is not None:
        equal((data.get('ok'), data.get('reason')), (False, case.expected_refusal), case.name + ' CLI refusal')
    if data.get('error'):
        raise AssertionError(case.name + ': CLI returned an error')
    if case.command[0] in ('metrics', 'lifestyle') and not data.get('metrics'):
        raise AssertionError(case.name + ': fixture measurements disappeared')
    route = case.route.split(' ', 1)[1] + '?' + case.query + '&lang=' + env['SCHOLION_LANG']
    status, web = request(base, route)
    equal(status, 200, 'HTTP status')
    equal(payload(web), payload(data[case.web_field] if case.web_field else data), case.name + ' CLI/Web')
    if 'container' in web:
        equal(web['container']['id'], data['container']['id'], 'Web container identity')
    name = contract.PLUGIN[case.command[0]]
    args = {**contract.PLUGIN_ARGS.get(case.command[0], {}), **case.arguments}
    reply = rpc([sys.executable, '-m', 'scholion', 'mcp'], name, args, env)
    if reply.get('isError'):
        raise AssertionError(case.name + ': MCP refused valid scenario')
    plugin = plugin_entries[name].handler(ouroboros_tools.ToolContext(), **args)
    equal(reply['content'][0]['text'], plugin, case.name + ' MCP/Plugin')
    if 'structuredContent' in reply:
        structured = dict(reply['structuredContent'])
        structured.pop(mcp_server.REPORT_FIELD, None)
        if 'container' in structured:
            equal(structured['container']['id'], data['container']['id'], 'MCP container identity')
        equal(payload(structured), payload(data), case.name + ' MCP/CLI structure')
    text = cli(case.command, env, as_json=False, allow_failure=case.expected_refusal is not None)
    suffix = '\n\n' + i18n.t('tool.container_line', id=data['container']['id'])
    if not plugin.endswith(suffix):
        raise AssertionError('Plugin container identity missing or different')
    report = plugin[:-len(suffix)].strip()
    # The system tool appends its required assistant retelling rule.
    if case.command[0] == 'system':
        if text not in report:
            raise AssertionError('System text lost from tool report')
    else:
        equal(text, report, case.name + ' CLI/Plugin text')
    if agent_command:
        equal(rpc(agent_command, name, args, env), reply, case.name + ' agent launcher')
    return {'scenario': case.name, 'language': env['SCHOLION_LANG'],
            'structured_mcp': 'structuredContent' in reply, 'agent_launcher': bool(agent_command)}


def write_cases(base, env, entries, agent_command, profile):
    """Equivalent dictated writes, invalid input and stale-screen preservation."""
    from scholion import core, ouroboros_tools
    original = hashes(profile)
    log = profile / 'focus_log.json'
    saved = log.read_bytes() if log.exists() else None
    tool = entries['sch_focus_log']
    commands = {'cli': None, 'web': None, 'plugin': None,
                'mcp': [sys.executable, '-m', 'scholion', 'mcp']}
    if agent_command:
        commands['agent_launcher'] = agent_command
    expected = None
    for surface, command in commands.items():
        for valid in (False, True):
            date = '2026-01-02' if valid else ''
            args = {'date': date, 'note': 'Synthetic interface acceptance'}
            if surface == 'cli':
                result = cli(['focus-log', date, '--note', args['note']], env, allow_failure=True)
                equal(bool(result.get('ok')), valid, 'CLI write status')
            elif surface == 'web':
                _, result = request(base, '/api/focus/log?lang=' + env['SCHOLION_LANG'], args)
                equal(bool(result.get('ok')), valid, 'Web write status')
            elif surface == 'plugin':
                tool.handler(ouroboros_tools.ToolContext(), **args)
            else:
                rpc(command, 'sch_focus_log', args, env)
            if not valid:
                equal(hashes(profile), original, surface + ' invalid write preserved bytes')
            else:
                # Compare persisted content, not the adapters' different acknowledgements.
                current = json.loads(log.read_text(encoding='utf-8'))
                if expected is None:
                    expected = current
                equal(current, expected, surface + ' persisted record')
                if 'Synthetic interface acceptance' not in log.read_text(encoding='utf-8'):
                    raise AssertionError('Dictated note was not saved')
        if saved is None:
            log.unlink()
        else:
            log.write_bytes(saved)
        core.reset_cache()
        equal(hashes(profile), original, surface + ' only expected file changed')
    status, result = request(base, '/api/focus/log', {'date': '2026-01-02'},
                             {'X-Scholion-View-Profile': 'stale-synthetic-view'})
    equal(status, 409, 'Stale view refusal')
    equal(result['reason'], 'profile_changed', 'Stale view reason')
    equal(hashes(profile), original, 'Stale view preserved bytes')
    return {'scenario': 'focus-log', 'language': env['SCHOLION_LANG'],
            'surfaces': list(commands), 'invalid_input_preserved': True,
            'equal_persisted_records': True, 'stale_view_preserved': True}


def review_writes(base, env, entries, agent_command, profile):
    from scholion import core, insight_history, mcp_server, ouroboros_tools

    original = hashes(profile)
    path = profile / insight_history.FILENAME
    _, preview = request(base, '/api/insight-snapshot?lang=' + env['SCHOLION_LANG'])
    confirmation = preview['confirmation']
    name = 'sch_insight_snapshot'
    context = ouroboros_tools.ToolContext()
    tool = entries[name].handler
    expected = None
    surfaces = {
        'cli': lambda token: cli(['insight-snapshot', '--confirm', token], env, allow_failure=True),
        'web': lambda token: request(base, '/api/insight-snapshot?lang=' + env['SCHOLION_LANG'],
                                     {'confirm': token})[1],
        'mcp': lambda token: rpc([sys.executable, '-m', 'scholion', 'mcp'], name,
                                 {'confirm': token}, env),
    }
    if agent_command:
        surfaces['agent_launcher'] = lambda token: rpc(agent_command, name, {'confirm': token}, env)
    for surface, call in surfaces.items():
        invalid = call('stale-synthetic-fingerprint')
        result = invalid.get('structuredContent', invalid)
        equal((result['ok'], result['saved']), (False, False), surface + ' stale confirmation')
        equal(hashes(profile), original, surface + ' stale confirmation preserved bytes')
        valid = call(confirmation)
        result = valid.get('structuredContent', valid)
        equal((result['ok'], result['saved']), (True, True), surface + ' confirmation')
        if 'content' in valid:
            # Repeating a confirmation through the host handler must be idempotent.
            committed = hashes(profile)
            equal(tool(context, confirm=confirmation), valid['content'][0]['text'],
                  surface + ' confirmation matches host handler')
            equal(hashes(profile), committed, 'Repeated confirmation preserved bytes')
            report = result.get(mcp_server.REPORT_FIELD)
            if not report:
                raise AssertionError('Snapshot lost its assistant report')
        history = json.loads(path.read_text(encoding='utf-8'))['reviews']
        equal(len(history), 1, surface + ' stored exactly one review')
        review = dict(history[0])
        review.pop('saved_at')
        if expected is None:
            expected = review
        equal(review, expected, surface + ' persisted review')
        path.unlink()
        core.reset_cache()
        equal(hashes(profile), original, surface + ' only review history changed')
    return {'scenario': 'insight-review-save', 'language': env['SCHOLION_LANG'],
            'surfaces': [*surfaces, 'plugin'], 'stale_confirmation_preserved': True,
            'equal_persisted_reviews': True}


def execute(root, commands, installed=False, agent_plugin=None):
    # Clear inherited user state before importing any product module.
    for key in list(os.environ):
        if key.startswith(('SCHOLION_', 'OUROBOROS_')):
            del os.environ[key]
    if installed:
        if os.environ.get('PYTHONPATH'):
            raise ValueError('Installed acceptance requires an empty PYTHONPATH')
    else:
        sys.path.insert(0, str(root / 'src'))
        os.environ['PYTHONPATH'] = str(root / 'src')
    with tempfile.TemporaryDirectory(prefix='scholion-interface-check-') as directory:
        work = Path(directory).resolve()
        profile = work / 'profile'
        shutil.copytree(root / 'tests/fixtures/profile', profile)
        # POSIX retains the flock file after writing. Windows takes an exclusive
        # lockfile, so precreating one there would block every fixture write.
        if os.name == 'posix':
            (profile / '.write.lock').touch()
        os.environ.update(SCHOLION_PROFILE_DIR=str(profile), SCHOLION_OFFLINE='1',
                          SCHOLION_GENOME_VCF=str(work / 'missing.vcf.gz'),
                          SCHOLION_GENOME_DIR=str(work / 'no-genome'),
                          SCHOLION_GENE_GFF3=str(work / 'no-annotation.gff3'),
                          SCHOLION_WORKSTATION=str(work / 'no-workstation.json'))
        import scholion
        from scholion import container, contract, core, i18n, ouroboros_tools
        origin = Path(scholion.__file__).resolve()
        if installed and ('site-packages' not in origin.parts or root in origin.parents):
            raise ValueError('Expected independently installed module: ' + str(origin))
        cases, write = select(commands, contract.PARITY, contract.PLUGIN)
        doors = contract.access()['doors']
        required = {'cli', 'web', 'mcp', 'ouroboros_tools', 'agent_plugin', 'ouroboros_hub', 'agent_skills'}
        equal(set(doors), required, 'New access door needs an acceptance decision')
        agent_command = None
        if agent_plugin:
            manifest = json.loads((agent_plugin / '.mcp.json').read_text(encoding='utf-8'))
            entry = manifest['mcpServers']['scholion']
            launcher = Path(entry['command'].replace('${CLAUDE_PLUGIN_ROOT}', str(agent_plugin)))
            # Never allow the launcher's fallback to select an unrelated local install.
            executable = Path(sys.executable).parent / ('scholion.exe' if os.name == 'nt' else 'scholion')
            if not installed or not executable.is_file():
                raise ValueError('Agent launcher requires this environment\'s installed console script')
            os.environ['PATH'] = str(executable.parent) + os.pathsep + os.environ.get('PATH', '')
            if os.name == 'nt':
                raise ValueError('Run the launcher with an explicitly accepted POSIX shell on Windows')
            agent_command = [str(launcher), *entry.get('args', [])]
        container.ensure()
        ouroboros_tools.unpin_session()
        entries = {entry.name: entry for entry in ouroboros_tools.get_tools()}
        before = hashes(profile)
        checks = []
        with http_server() as base:
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                env = {**os.environ, 'SCHOLION_LANG': language}
                for case in cases:
                    checks.append(read_case(case, base, env, entries, agent_command))
                equal(hashes(profile), before, 'Read-only scenarios preserved profile')
                if write:
                    checks.append(write_cases(base, env, entries, agent_command, profile))
                if any(case.name == 'insight-review-preview' for case in cases):
                    checks.append(review_writes(base, env, entries, agent_command, profile))
        core.reset_cache()
        selected = sorted({s.command[0] for s in cases} | ({'focus-log'} if write else set()))
        return {'origin': str(origin), 'python': sys.executable, 'version': scholion.__version__,
                'installed': installed, 'doors': sorted(doors), 'commands': selected,
                'unexercised_commands': sorted(set(contract.PARITY.values()) - set(selected)),
                'checks': checks, 'profile_preserved': hashes(profile) == before,
                'limitations': ['Native host GUI and AI dialogue not exercised by this runner',
                                'Browser rendering, native printing and Windows need separate evidence',
                                'Recompute preview is not a completed genome recalculation',
                                'Ouroboros handler is not the host proxy; run its separate acceptance']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commands', nargs='+', help='Affected contract command names; default: all supported scenarios')
    parser.add_argument('--installed', action='store_true')
    parser.add_argument('--agent-plugin', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('Evidence already exists; choose a new output file')
    started = time.monotonic()
    result = {'ok': False}
    try:
        result.update(execute(Path(__file__).resolve().parents[2], args.commands,
                              args.installed, args.agent_plugin.resolve() if args.agent_plugin else None))
        result['ok'] = True
    except (AssertionError, ValueError, RuntimeError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        result['error'] = str(error)
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'ok': result['ok'], 'checks': len(result.get('checks', [])),
                      'elapsed_seconds': result['elapsed_seconds'], 'error': result.get('error')}))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
