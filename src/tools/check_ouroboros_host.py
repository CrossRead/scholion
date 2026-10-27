#!/usr/bin/env python3
"""Exercise the supported real host without a model, network or personal profile."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host', type=Path)
    parser.add_argument('--installed', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if not args.installed:
        sys.path.insert(0, str(root / 'src'))
    sys.path.insert(0, str(args.host.resolve()))
    with tempfile.TemporaryDirectory(prefix='scholion-host-check-') as directory:
        work = Path(directory).resolve()
        profile = work / 'profile'
        shutil.copytree(root / 'tests/fixtures/profile', profile)
        os.environ.update(SCHOLION_PROFILE_DIR=str(profile), SCHOLION_OFFLINE='1',
                          SCHOLION_LANG='en', SCHOLION_GENOME_VCF=str(work / 'missing.vcf.gz'),
                          SCHOLION_GENOME_DIR=str(work / 'no-genome'),
                          SCHOLION_GENE_GFF3=str(work / 'no-annotation.gff3'),
                          SCHOLION_WORKSTATION=str(work / 'no-workstation.json'))
        from scholion import ouroboros_tools as tools, mcp_server, core, i18n
        from ouroboros.tools.registry import ToolContext, ToolEntry
        import scholion
        origin = str(Path(scholion.__file__).resolve())
        if args.installed:
            assert 'site-packages' in origin and not os.environ.get('PYTHONPATH'), origin
        assert tools._HAVE_OURO and tools.ToolContext is not ToolContext
        entries = tools.get_tools()
        assert all(isinstance(entry, ToolEntry) for entry in entries)
        context = ToolContext(repo_dir=work, drive_root=work)
        checks = []
        for lang in ('en', 'ru'):
            i18n.set_lang(lang)
            for version in ('2024-11-05', '2025-11-25', '2026-07-28'):
                for name, arguments in [('sch_rules', {}), ('sch_analyze_labs', {}),
                                        ('sch_update', {'confirm': False}),
                                        ('sch_focus_log', {'date': '2026-01-01', 'note': 'Synthetic host integration check'})]:
                    result = mcp_server.call_tool(name, arguments, version)
                    assert not result.get('isError'), result
                    assert result.get('content'), result
                    checks.append({'lang': lang, 'protocol': version, 'tool': name})
        assert any('Synthetic host integration check' in path.read_text(encoding='utf-8')
                   for path in profile.glob('*.json'))
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in profile.glob('*.json')}
        refused = mcp_server.call_tool('sch_focus_log', {'date': '', 'note': 'refused'})
        assert refused['content']
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in profile.glob('*.json')}
        assert before == after
        assert next(t for t in entries if t.name == 'sch_rules').handler(context)
        assert core.profile_dir().resolve() == profile
        print(json.dumps({'origin': origin, 'registered': len(entries), 'checks': checks,
                          'synthetic_write_persisted': True, 'invalid_write_preserved_files': True,
                          'real_context_direct_call': True, 'model_used': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
