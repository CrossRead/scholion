"""Assembly evidence shared by ClinVar readers and the preparation toolkit."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


LENGTH_TO_ASSEMBLY = {
    249250621: "GRCh37", 248956422: "GRCh38", 248387328: "T2T-CHM13v2.0",   # chr1
    243199373: "GRCh37", 242193529: "GRCh38", 242696752: "T2T-CHM13v2.0",   # chr2
    155270560: "GRCh37", 156040895: "GRCh38", 154259566: "T2T-CHM13v2.0",   # chrX
}

def header_metadata(lines):
    lengths, references = set(), set()
    date = None
    known = LENGTH_TO_ASSEMBLY
    for line in lines:
        if not line.startswith('#'):
            break
        if line.startswith('##contig='):
            match = re.search(r'length=(\d+)', line)
            if match and int(match[1]) in known:
                lengths.add(known[int(match[1])])
        elif line.startswith('##reference='):
            for build, alias in (('GRCh37', 'hg19'), ('GRCh38', 'hg38')):
                if build in line or alias in line:
                    references.add(build)
        elif line.startswith('##fileDate='):
            date = line.split('=', 1)[1].strip() or None
    evidence = lengths or references
    return {'assembly': next(iter(evidence)) if len(evidence) == 1 else None,
            'file_date': date}


def table_assembly(metadata):
    """Prefer recorded builds; accept the old official URL as legacy evidence."""
    if not isinstance(metadata, dict):
        return None
    declared = {metadata[k] for k in ('assembly', 'personal_assembly', 'clinvar_assembly')
                if metadata.get(k)}
    if declared:
        return next(iter(declared)) if len(declared) == 1 and declared <= {'GRCh37', 'GRCh38'} else None
    url = str(metadata.get('url') or '')
    return next((b for b in ('GRCh37', 'GRCh38') if f'/vcf_{b}/' in url), None)



def select_sample(header, requested=''):
    names = next((line.split('\t')[9:] for line in header if line.startswith('#CHROM\t')), [])
    selected = requested if requested in names else names[0] if len(names) == 1 and not requested else None
    if selected is None:
        raise ValueError('Select one existing sample with SCHOLION_GENOME_SAMPLE; previous results preserved.')
    return selected


def cached_reference(cache, assembly=None):
    """Resolve one complete generation; retain compatibility with legacy caches."""
    root = Path(cache).expanduser().resolve()
    pointer = root / assembly / 'current.json' if assembly in ('GRCh37', 'GRCh38') else root / 'current.json'
    if pointer.exists():
        try:
            metadata = json.loads(pointer.read_text(encoding='utf-8'))
            path = (root / metadata['path']).resolve(strict=True)
            if not path.is_relative_to(root) or assembly and metadata['assembly'] != assembly:
                return None
            for suffix, key in (('', 'identity'), ('.tbi', 'index_identity')):
                current = Path(str(path) + suffix).stat()
                if any(getattr(current, name) != value for name, value in metadata[key].items()):
                    return None
            return path
        except (OSError, ValueError, KeyError, TypeError):
            return None
    legacy = root / 'clinvar.vcf.gz'
    return legacy if legacy.is_file() else None


def promote_generation(cache_work, cache, work, genome, sample):
    """Commit a complete per-build reference generation, with rollback on failure."""
    import hashlib
    import os
    import shutil
    import tempfile
    cache_work, cache, work, genome = map(Path, (cache_work, cache, work, genome))
    meta = json.loads((work / 'clinvar_meta.json').read_text(encoding='utf-8'))
    assembly = meta['assembly']
    if assembly not in ('GRCh37', 'GRCh38'):
        raise ValueError('Unsupported reference assembly')
    generation = cache / assembly / 'generations' / cache_work.name
    generation.parent.mkdir(parents=True, exist_ok=True)
    def digest(path):
        result = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                result.update(block)
        return result.hexdigest()
    names = (sample + '.clinvar.vcf.gz', sample + '.clinvar.vcf.gz.tbi',
             'clinvar_norm.json', 'clinvar_hits.tsv', 'clinvar_meta.json')
    for path in [cache_work / 'clinvar.vcf.gz', cache_work / 'clinvar.vcf.gz.tbi'] + [work / n for n in names]:
        if not path.is_file():
            raise OSError('Missing staged ClinVar output: ' + path.name)
    cv_hash = digest(cache_work / 'clinvar.vcf.gz')
    index_hash = digest(cache_work / 'clinvar.vcf.gz.tbi')
    existing = cached_reference(cache, assembly)
    previous_pointer = cache / assembly / 'current.json'
    pointer = None
    if existing is not None and previous_pointer.is_file():
        candidate = json.loads(previous_pointer.read_text(encoding='utf-8'))
        if candidate.get('sha256') == cv_hash:
            pointer = candidate
            index_hash = candidate['index_sha256']
            generation = existing.parent
            shutil.rmtree(cache_work)
    if pointer is None:
        os.replace(cache_work, generation)
    def witness(path):
        info = path.stat()
        return {k: getattr(info, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')}
    pointer = pointer or {'version': 1, 'assembly': assembly,
               'path': str((generation / 'clinvar.vcf.gz').relative_to(cache)),
               'sha256': cv_hash, 'index_sha256': index_hash,
               'file_date': meta['clinvar_date'],
               'identity': witness(generation / 'clinvar.vcf.gz'),
               'index_identity': witness(generation / 'clinvar.vcf.gz.tbi')}
    meta.update(clinvar_sha256=cv_hash, clinvar_index_sha256=index_hash, reference_generation=pointer['path'])
    (work / 'clinvar_meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    pairs = [(work / n, genome / n) for n in names]
    # Stage pointers in their destination filesystem, even for external genomes.
    for name, target in (('build', cache / assembly / 'current.json'), ('active', cache / 'current.json')):
        staged = generation / (name + '.json')
        staged.write_text(json.dumps(pointer, indent=2), encoding='utf-8')
        pairs.insert(0, (staged, target))
    previous, applied = {}, []
    try:
        for src, dst in pairs:
            if dst.exists():
                fd, filename = tempfile.mkstemp(prefix='.clinvar-backup-', dir=dst.parent)
                os.close(fd)
                previous[dst] = Path(filename)
                shutil.copy2(dst, previous[dst])
        try:
            for src, dst in pairs:
                os.replace(src, dst)
                applied.append(dst)
        except BaseException:
            for dst in reversed(applied):
                if dst in previous:
                    os.replace(previous[dst], dst)
                else:
                    dst.unlink()
            raise
    finally:
        for saved in previous.values():
            saved.unlink(missing_ok=True)


if __name__ == '__main__':
    if sys.argv[1] == '--cached':
        print(cached_reference(sys.argv[2], sys.argv[3]) or '')
    elif sys.argv[1] == '--sample':
        header = Path(sys.argv[2]).read_text(encoding='utf-8').splitlines()
        print(select_sample(header, sys.argv[3] if len(sys.argv) > 3 else ''))
    elif sys.argv[1] == '--promote':
        import signal
        def interrupted(signum, frame):
            raise InterruptedError('ClinVar publication interrupted')
        signal.signal(signal.SIGTERM, interrupted)
        promote_generation(*sys.argv[2:])
    else:
        metadata = header_metadata(Path(sys.argv[1]).read_text(encoding='utf-8').splitlines())
        if metadata['assembly']:
            print(metadata['assembly'])
        else:
            raise SystemExit('Cannot establish a unique VCF assembly from its header.')
