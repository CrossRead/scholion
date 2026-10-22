"""Content witnesses and explicit verification for a saved ACMG table.

A read checks a cheap local witness. A changed witness requires an explicit
content check, never an automatic genome pass and never a guessed identity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import core
from .i18n import t

RULES_VERSION = '1'


class DigestReader:
    """Hash the compressed bytes while the scanner reads them exactly once."""
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.digest.update(data)
        return data

    def tell(self):
        return self.stream.tell()

    def seek(self, offset: int, whence: int = 0):
        # The witness covers one sequential read; rewinding would hash bytes twice.
        if (whence == 0 and offset == self.tell()) or (whence == 1 and offset == 0):
            return self.tell()
        raise OSError('content hashing requires sequential reads')


def catalogue_digest() -> str:
    data = core._read_knowledge_raw('acmg_sf.json')
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def fingerprint(path, progress=None) -> tuple[str, dict]:
    from .acmg_scan import source_identity
    before = source_identity(path)
    digest = hashlib.sha256()
    done = 0
    with Path(path).open('rb') as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
            done += len(block)
            if done > before['st_size']:
                raise OSError('source grew while verifying its content')
            if progress:
                progress(done, before['st_size'], 'ACMG source verification')
    if before != source_identity(path):
        raise OSError('source changed while verifying its content')
    return digest.hexdigest(), before


def knowledge(meta: dict) -> dict:
    """Recorded version and local applicability, without a registry request."""
    result = {'status': 'recorded' if meta.get('catalogue_sha256') else 'unverified',
              'catalogue_version': meta.get('catalogue_version'),
              'rules_version': meta.get('rules_version'),
              'clinvar_file_date': meta.get('clinvar_file_date'),
              'scanned': meta.get('scanned'), 'latest_remote_version_checked': False}
    if meta.get('catalogue_sha256') and (meta['catalogue_sha256'] != catalogue_digest()
                                        or meta.get('rules_version') != RULES_VERSION):
        result['status'] = 'update_required'
        result['reason'] = 'knowledge_changed'
        return result
    from .coverage import clinvar_path
    from .acmg_scan import source_identity
    local = clinvar_path()
    if local is None:
        candidate = Path(meta.get('clinvar_path') or '.')
        local = candidate if candidate.is_file() else None
    result['local_clinvar_available'] = local is not None
    if local is not None and meta.get('clinvar_identity'):
        try:
            if source_identity(local) != meta['clinvar_identity']:
                result['status'] = 'verification_required'
                result['reason'] = 'clinvar_verification_needed'
        except OSError:
            result['local_clinvar_available'] = False
    return result


def saved_rows(table: Path) -> list[dict]:
    """Historical strings only: never classified, eligible or counted as findings."""
    try:
        content = table.read_bytes()
        if len(content) > 8 * 1024 * 1024:
            return []
        lines = content.decode('utf-8').splitlines()
        header = lines[0].split('\t')
        if not {'gene', 'ref', 'alt', 'reportable'} <= set(header):
            return []
        return [dict(zip(header, line.split('\t'))) for line in lines[1:501] if line.strip()]
    except (OSError, ValueError, IndexError):
        return []


def state() -> dict:
    from . import acmg_scan, genome
    table = next((b / acmg_scan.OUT_NAME for b in core.genome_bases()
                  if (b / acmg_scan.OUT_NAME).is_file()), None)
    if table is None:
        return {'status': 'missing'}
    meta = acmg_scan.read_meta(table)
    try:
        reason = acmg_scan.table_refusal(table, meta, genome.vcf_path(), table.read_bytes())
    except OSError:
        reason = 'table_changed'
    return {'status': 'current' if reason is None else 'unverified', 'reason': reason,
            'operation': 'verify' if reason in ('source_verification_needed',
                                                'clinvar_verification_needed') else 'scan',
            'knowledge': knowledge(meta) if meta else {'status': 'unverified'}}


def verify(out_dir=None, progress=None) -> dict:
    """Explicitly bind unchanged content to a new local witness; preserve the table."""
    from . import acmg_scan, genome
    table = (Path(out_dir) / acmg_scan.OUT_NAME if out_dir else next(
        (b / acmg_scan.OUT_NAME for b in core.genome_bases()
         if (b / acmg_scan.OUT_NAME).is_file()), core.genome_bases()[0] / acmg_scan.OUT_NAME))
    meta = acmg_scan.read_meta(table)
    personal = genome.vcf_path()
    def refusal(reason):
        return {'status': 'verification_refused', 'reason': reason,
                'message': t('acmg.verify.refused', reason=t('genome.acmg_stale.' + reason))}
    if not meta or not meta.get('personal_sha256'):
        return refusal('metadata_unverified')
    if not personal:
        return refusal('source_unavailable')
    old_meta = json.dumps(meta, sort_keys=True)
    try:
        old_table = table.read_bytes()
        if hashlib.sha256(old_table).hexdigest() != meta.get('table_sha256'):
            return refusal('table_changed')
        column = genome.sample_index(str(personal))
        samples = genome.samples_of(str(personal))
        if column is None or samples[column] != meta.get('sample'):
            return refusal('sample_changed')
        if genome.assembly_of(str(personal)) != meta.get('assembly'):
            return refusal('source_changed')
        digest, identity = fingerprint(personal, progress)
        if digest != meta['personal_sha256']:
            return refusal('source_changed')
        current = knowledge(meta)
        if current['status'] == 'update_required':
            return refusal('knowledge_changed')
        if current.get('reason') == 'clinvar_verification_needed':
            from .coverage import clinvar_path
            clinical = clinvar_path() or Path(meta['clinvar_path'])
            cv_digest, cv_identity = fingerprint(clinical, progress)
            if cv_digest != meta.get('clinvar_sha256'):
                return refusal('knowledge_changed')
            meta['clinvar_identity'] = cv_identity
            meta['clinvar_path'] = str(Path(clinical).resolve())
        if current.get('reason') == 'clinvar_verification_needed' and cv_identity != acmg_scan.source_identity(clinical):
            return refusal('clinvar_verification_needed')
        if genome.vcf_path() != personal or genome.sample_index(str(personal)) != column:
            return refusal('sample_changed')
        if meta.get('catalogue_sha256') != catalogue_digest():
            return refusal('knowledge_changed')
        if json.dumps(acmg_scan.read_meta(table), sort_keys=True) != old_meta or table.read_bytes() != old_table:
            return refusal('table_changed')
        # Recheck after potentially hashing a second source. Reading a changing
        # source may not certify an earlier snapshot as the current file.
        if identity != acmg_scan.source_identity(personal):
            return refusal('source_changed')
        meta.update(personal_identity=identity, personal_path=str(Path(personal).resolve()))
        acmg_scan._atomic_bytes(table.parent / acmg_scan.META_NAME,
                               (json.dumps(meta, ensure_ascii=False, indent=2)+'\n').encode())
    except (OSError, ValueError, IndexError):
        return refusal('source_unavailable')
    return {'status': 'ok', 'operation': 'verify', 'table': str(table),
            'message': t('acmg.verify.done')}
