"""Human-only container export and erasure, with a fail-closed ownership inventory.

Nothing runs over an inferred target. The caller supplies a registered ID; erase
also supplies that ID as confirmation and the digest of a previously shown plan.
External folders must declare their exclusive owner in .scholion-owner.json.
This module never creates that declaration on the user's behalf.
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import time
from typing import Any, Dict, Iterator, List, NoReturn, Tuple

from . import container, core
from .i18n import t

OWNER_FILE = '.scholion-owner.json'
JOURNAL = 'container-journal.jsonl'
SURFACES = frozenset({'cli-tty', 'cli-script', 'web', 'mcp', 'ouroboros'})
AGENT_SURFACE: ContextVar[str] = ContextVar('scholion_journal_surface', default='ouroboros')


def _refuse(reason: str) -> NoReturn:
    raise container.ContainerError('container.lifecycle_refused', reason=reason)


def _object(path: Path) -> Dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(result, dict):
            raise ValueError('expected object')
        return result
    except (OSError, ValueError) as exc:
        raise container.ContainerError('container.lifecycle_refused',
                                       reason=t('lifecycle.unreadable', path=path)) from exc


def _path(value: str) -> Path:
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        _refuse(t('lifecycle.absolute', path=raw))
    # /tmp and /var are system aliases on macOS, not user-controlled storage
    # declarations. The rest of the lexical chain must contain no symlink.
    for part in (raw, *raw.parents):
        try:
            attrs = getattr(part.lstat(), 'st_file_attributes', 0)
        except FileNotFoundError:
            attrs = 0
        # Windows junctions/reparse points need not report is_symlink(),
        # especially on the oldest supported Python. Do not walk through them.
        linked = part.is_symlink() or bool(attrs & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
        if linked and str(part) not in ('/tmp', '/var'):
            _refuse(t('lifecycle.symlink', path=part))
    return raw.resolve()


def _overlap(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def _roots(folder: Path, cid: str, *, ownership: bool) -> List[Tuple[str, Path]]:
    cfg_path = folder / 'profile/sources.json'
    cfg = _object(cfg_path) if cfg_path.exists() else {}
    for section in ('folders', 'external_sources'):
        if cfg.get(section) is not None and not isinstance(cfg[section], dict):
            _refuse(t('lifecycle.unreadable', path=cfg_path))
    settings = {**(cfg.get('external_sources') or {}), **(cfg.get('folders') or {})}
    if any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in settings.items()):
        _refuse(t('lifecycle.unreadable', path=cfg_path))
    roots: List[Tuple[str, Path]] = []
    for slot in core.DATA_SLOTS:
        local = folder / slot
        external = settings.get(slot) if slot in core.EXTERNAL_SLOTS else None
        selected = _path(external) if external else _path(str(local))
        if external and not selected.is_dir():
            _refuse(t('lifecycle.unavailable', path=selected))
        if selected.exists():
            roots.append((slot, selected))
        # The local cache remains local even when work/ is external.
        if external and local.exists() and selected != local:
            roots.append(('_local/' + slot, _path(str(local))))
    legacy_cache = folder / '.cache'
    if legacy_cache.exists():
        roots.append(('_local/cache', _path(str(legacy_cache))))
    for name, value in settings.items():
        if name in core.EXTERNAL_SLOTS:
            continue
        path = _path(value)
        if not path.is_dir():
            _refuse(t('lifecycle.unavailable', path=path))
        if any(path == root or root in path.parents for _, root in roots):
            continue
        # A per-domain folder owns one known file, not every neighboring file.
        filename = core._DOMAIN_FILE.get(name)
        if not filename:
            _refuse(t('lifecycle.ownership', path=path))
        file = path / filename
        if not file.is_file():
            _refuse(t('lifecycle.unavailable', path=file))
        roots.append(('external/' + name, file))
    # Individually selected inputs outside owned slots are not silently omitted
    # or assumed to be private. A shared reference belongs outside the container.
    for key in ('genome_bam', 'genome_vcf', 'genome_reference'):
        if not cfg.get(key):
            continue
        if not isinstance(cfg[key], str):
            _refuse(t('lifecycle.unreadable', path=cfg_path))
        path = _path(cfg[key])
        if not path.is_file():
            _refuse(t('lifecycle.unavailable', path=path))
        if not any(path == root or root in path.parents for _, root in roots):
            _refuse(t('lifecycle.ownership', path=path))
    declarations: List[Tuple[str, Path]] = []
    for index, (name, path) in enumerate(roots):
        if path == folder or path in folder.parents or path == Path.home().resolve():
            _refuse(t('lifecycle.ownership', path=path))
        for _, other in roots[index + 1:]:
            if _overlap(path, other):
                _refuse(t('lifecycle.overlap', path=path, other=other))
        if ownership and folder not in path.parents:
            declaration = (path if path.is_dir() else path.parent) / OWNER_FILE
            owner = _object(declaration) if declaration.is_file() else {}
            expected_scope = '.' if path.is_dir() else path.name
            if owner != {'container': cid, 'scope': expected_scope}:
                _refuse(t('lifecycle.ownership', path=path))
            if path.is_file():
                declarations.append((name + '-ownership', declaration))
    return roots + declarations


def _stamp(path: Path) -> Tuple[int, int, int, int, int]:
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        _refuse(t('lifecycle.special', path=path))
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _files(roots: List[Tuple[str, Path]]) -> List[Dict[str, Any]]:
    files: List[Dict[str, Any]] = []
    for name, root in roots:
        _path(str(root))
        if root.is_file():
            items = [(root, name + '/' + root.name)]
        else:
            items = []
            for base, dirs, names in os.walk(root, followlinks=False, onerror=lambda e: _refuse(str(e))):
                parent = Path(base)
                for child in dirs:
                    _path(str(parent / child))
                for child in names:
                    p = parent / child
                    if name == 'profile' and p == root / '.write.lock':
                        continue
                    items.append((p, name + '/' + p.relative_to(root).as_posix()))
        for path, member in items:
            stamp = _stamp(path)
            # Fail now on inaccessible/offline placeholders, not during deletion.
            with path.open('rb') as stream:
                stream.read(1)
            files.append({'path': str(path), 'member': member, 'size': stamp[2],
                          'identity': list(stamp)})
    return sorted(files, key=lambda row: row['member'])


def inventory(cid: str) -> Dict[str, Any]:
    """A complete read-only plan, refusing uncertain ownership before any action."""
    if container.explicit_environment() or any(
            os.environ.get('SCHOLION_' + name.upper() + '_DIR') for name in
            (*core.DATA_SLOTS, 'cache')) or os.environ.get('SCHOLION_GENOME_VCF'):
        _refuse(t('lifecycle.environment'))
    folder = _path(str(container.path_of(cid)))
    roots = _roots(folder, cid, ownership=True)
    protected = [container.workstation_path().resolve(),
                 container.workstation_path().parent.resolve() / 'clinic-journal.jsonl']
    for _, path in roots:
        if any(_overlap(path, p) for p in protected):
            _refuse(t('lifecycle.ownership', path=path))
    for other_id, other_folder in container.registry().items():
        if other_id == cid:
            continue
        other_folder = _path(str(other_folder))
        if _overlap(folder, other_folder):
            _refuse(t('lifecycle.overlap', path=folder, other=other_folder))
        if (container.read(other_folder) or {}).get('id') != other_id:
            _refuse(t('lifecycle.unreadable', path=other_folder))
        others = _roots(other_folder, other_id, ownership=False)
        for _, path in roots:
            if _overlap(path, other_folder) or any(_overlap(path, p) for _, p in others):
                _refuse(t('lifecycle.shared', path=path))
    roots.append(('', folder / container.CONTAINER_FILE))
    files = _files(roots)
    for file in files:
        if file['member'].startswith('/'):
            file['member'] = file['member'][1:]
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {'ok': True, 'container': {'id': cid}, 'root': str(folder),
            'roots': [{'slot': name, 'path': str(path)} for name, path in roots],
            'files': files, 'bytes': sum(f['size'] for f in files), 'digest': digest}


@contextlib.contextmanager
def _strict_lock(path: Path) -> Iterator[None]:
    core.mkdir_private(path.parent)
    _path(str(path))
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    except FileExistsError as exc:
        raise core.ProfileBusy(t('lifecycle.busy')) from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        path.unlink()


@contextlib.contextmanager
def _workstation_lock() -> Iterator[None]:
    with core._WRITE_TLOCK:
        with _strict_lock(container.workstation_path().parent / '.container.lock'):
            yield


@contextlib.contextmanager
def _profile_lock(folder: Path) -> Iterator[None]:
    path = folder / 'profile/.write.lock'
    core.mkdir_private(path.parent)
    if core._fcntl is None:
        with _strict_lock(path):
            yield
    else:
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            core._fcntl.flock(fd, core._fcntl.LOCK_EX)
            yield
        finally:
            core._fcntl.flock(fd, core._fcntl.LOCK_UN)
            os.close(fd)


def _append(path: Path, row: Dict[str, Any]) -> None:
    _path(str(path))
    if path.exists():
        _stamp(path)
    core.mkdir_private(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        payload = (json.dumps(row, ensure_ascii=True) + '\n').encode()
        with os.fdopen(fd, 'ab', closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def record(cid: str, action: str, surface: str, *, local: bool = True) -> None:
    """An ID, a fixed action, a time and a surface: no label, file name or content."""
    if surface not in SURFACES or action not in ('export', 'erase-started', 'erase-completed',
                                               'erase-failed', 'read', 'write', 'use', 'create'):
        raise ValueError('unknown journal action or surface')
    row = {'id': cid, 'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'action': action, 'surface': surface}
    if local:
        _append(container.path_of(cid) / 'profile' / JOURNAL, row)
    _append(container.workstation_path().parent / 'clinic-journal.jsonl', row)


def record_current(action: str, surface: str) -> None:
    """Record an access attempt on a registered workstation, without its arguments."""
    if not container.in_use():
        return
    with _workstation_lock():
        container.gate()
        cid = container.named()['id']
        if cid:
            record(cid, action, surface)
        container.gate()


def _same_file(row: Dict[str, Any]) -> None:
    path = _path(row['path'])
    if list(_stamp(path)) != row['identity']:
        _refuse(t('lifecycle.changed'))


def export(cid: str, destination: str, *, surface: str = 'cli-script') -> Dict[str, Any]:
    """Write a new private archive; never replace a file or export a partial view."""
    with _workstation_lock():
        initial = inventory(cid)
        folder = Path(initial['root'])
        with _profile_lock(folder):
            target = _path(destination)
            if target.exists() or not target.parent.is_dir():
                _refuse(t('lifecycle.destination'))
            if any(_overlap(target, Path(r['path'])) for r in initial['roots']):
                _refuse(t('lifecycle.destination'))
            for other_id, other_folder in container.registry().items():
                if _overlap(target, other_folder.resolve()) or any(
                        _overlap(target, path) for _, path in
                        _roots(other_folder.resolve(), other_id, ownership=False)):
                    _refuse(t('lifecycle.destination'))
            record(cid, 'export', surface)
            plan = inventory(cid)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.scholion-export-',
                                                 delete=False) as stream:
                    temporary = Path(stream.name)
                manifest = []
                with tarfile.open(temporary, 'w:gz', format=tarfile.PAX_FORMAT) as archive:
                    for row in plan['files']:
                        _same_file(row)
                        path = Path(row['path'])
                        with path.open('rb') as source:
                            info = tarfile.TarInfo(row['member'])
                            info.size, info.mode = row['size'], 0o600
                            archive.addfile(info, source)
                        _same_file(row)
                        manifest.append({'path': row['member'], 'size': row['size']})
                    receipt = json.dumps({'container': {'id': cid}, 'files': manifest,
                                          'inventory_digest': plan['digest']}, indent=2).encode()
                    info = tarfile.TarInfo('export-manifest.json')
                    info.size, info.mode = len(receipt), 0o600
                    archive.addfile(info, io.BytesIO(receipt))
                if inventory(cid)['digest'] != plan['digest']:
                    _refuse(t('lifecycle.changed'))
                # Atomic no-clobber publication on the local filesystem.
                os.link(temporary, target)
                return {'ok': True, 'container': {'id': cid}, 'archive': str(target),
                        'files': manifest, 'bytes': plan['bytes'], 'digest': plan['digest']}
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def erase(cid: str, *, confirm: str = '', digest: str = '',
          surface: str = 'cli-script') -> Dict[str, Any]:
    """Preview first; erase only an inactive, unchanged and explicitly confirmed ID.

    Partial I/O failure leaves an erasing marker and registry entry for manual
    recovery. It is never reported as complete. No recursive deletion is used.
    """
    with _workstation_lock():
        if container.workstation().get('active') == cid:
            _refuse(t('lifecycle.active'))
        plan = inventory(cid)
        if not confirm:
            return {**plan, 'preview': True, 'warning': t('lifecycle.erase_warning')}
        if confirm != cid or digest != plan['digest']:
            _refuse(t('lifecycle.confirm'))
        folder = Path(plan['root'])
        removed: List[str] = []
        started = False
        identity_path = folder / container.CONTAINER_FILE
        try:
            with _profile_lock(folder):
                if inventory(cid)['digest'] != digest:
                    _refuse(t('lifecycle.changed'))
                # The claim is held by background and foreground recomputation.
                if any(Path(f['path']).name == '.recompute.claim' for f in plan['files']):
                    _refuse(t('lifecycle.busy'))
                record(cid, 'erase-started', surface)
                plan = inventory(cid)
                identity = container.read(folder) or {}
                core.write_json(identity_path, {**identity, 'lifecycle': 'erasing'})
                started = True
                for row in plan['files']:
                    if Path(row['path']) == identity_path:
                        continue
                    _same_file(row)
                    Path(row['path']).unlink()
                    removed.append(row['member'])
            # Close the lock before unlinking it: Windows does not unlink an
            # open file. The erasing marker now refuses new reads and writes.
            for root in plan['roots']:
                path = Path(root['path'])
                if path.is_dir():
                    _path(str(path))
                    for base, dirs, _ in os.walk(path, topdown=False, followlinks=False):
                        for name in dirs:
                            (Path(base) / name).rmdir()
                    lock = path / '.write.lock'
                    if root['slot'] == 'profile' and lock.exists():
                        lock.unlink()
                    path.rmdir()
            identity_path.unlink()
            removed.append('container.json')
            ws = container.workstation()
            ws['containers'].pop(cid, None)
            container._write_workstation(ws)
            record(cid, 'erase-completed', surface, local=False)
            return {'ok': True, 'container': {'id': cid}, 'removed': removed,
                    'warning': t('lifecycle.not_secure_erase')}
        except (OSError, container.ContainerError) as exc:
            if started:
                record(cid, 'erase-failed', surface, local=False)
                return {'ok': False, 'container': {'id': cid}, 'removed': removed,
                        'error': t('lifecycle.partial', error=type(exc).__name__)}
            raise
