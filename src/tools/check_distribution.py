#!/usr/bin/env python3
"""Check built files for generated/private paths before exercising the sdist."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile

JUNK = {'__pycache__', 'node_modules', '.git', '.venv', '.mypy_cache', '.ruff_cache'}
PERSONAL = {'profile', 'genome', 'raw', 'work', 'reports', '_backups', '.personal_patterns', '.env'}


def check_name(name: str, sdist: bool) -> str:
    path = PurePosixPath(name)
    if '\\' in name or path.is_absolute() or '..' in path.parts or any(':' in p for p in path.parts):
        raise ValueError('Unsafe archive path: ' + name)
    parts = path.parts[1:] if sdist else path.parts
    if not parts:
        return ''
    if parts[0] in PERSONAL or JUNK.intersection(parts) or parts[-1].endswith(('.pyc', '.pyo')) or parts[-1] == '.DS_Store':
        raise ValueError('Private/generated archive path: ' + name)
    if parts[:4] == ('tests', 'fixtures', 'genome', 'cache'):
        raise ValueError('Generated genome fixture cache: ' + name)
    return '/'.join(parts)


def inspect(path: Path, extract_to: Path | None = None) -> dict:
    names = set()
    if path.name.endswith('.tar.gz'):
        with tarfile.open(path, 'r:gz') as archive:
            members = archive.getmembers()
            roots = {PurePosixPath(m.name).parts[0] for m in members if PurePosixPath(m.name).parts}
            if len(roots) != 1:
                raise ValueError('Source archive must have exactly one root')
            for member in members:
                check_name(member.name, True)
                if member.name in names or not (member.isfile() or member.isdir()):
                    raise ValueError('Duplicate or non-regular archive entry: ' + member.name)
                names.add(member.name)
            root = next(iter(roots))
            for needed in ('VERSION', 'pyproject.toml', 'tests/fixtures/genome/tiny.vcf.gz', 'tests/fixtures/genome/tiny.vcf.gz.tbi'):
                if root + '/' + needed not in names:
                    raise ValueError('Required source member missing: ' + needed)
            result = {'archive': str(path), 'entries': len(names), 'ok': True}
            if extract_to is not None:
                # No links, special entries or parent traversal can pass above.
                destination = extract_to.resolve()
                destination.mkdir(parents=True, exist_ok=False)
                if hasattr(tarfile, 'data_filter'):
                    archive.extractall(destination, filter='data')
                else:
                    archive.extractall(destination)
                result['source_root'] = str(destination / root)
            return result
    if extract_to is not None:
        raise ValueError('Extraction requires one source archive')
    if not path.name.endswith('.whl'):
        raise ValueError('Expected wheel or .tar.gz: ' + str(path))
    with zipfile.ZipFile(path) as wheel:
        for entry in wheel.infolist():
            check_name(entry.filename, False)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode) or entry.filename in names:
                raise ValueError('Duplicate or linked wheel entry: ' + entry.filename)
            names.add(entry.filename)
        if 'scholion/__init__.py' not in names or not any(n.endswith('.dist-info/METADATA') for n in names):
            raise ValueError('Wheel package or metadata is absent')
    return {'archive': str(path), 'entries': len(names), 'ok': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+', type=Path)
    parser.add_argument('--extract-to', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    if args.extract_to and len(args.archives) != 1:
        parser.error('Extraction requires exactly one source archive')
    result = {'ok': False, 'archives': []}
    try:
        for path in args.archives:
            result['archives'].append(inspect(path, args.extract_to))
        result['ok'] = True
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        result['error'] = str(error)
    if args.out:
        args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
