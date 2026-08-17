#!/usr/bin/env python3
"""Cross-check of the EVOGEN report against the owner's own whole-genome VCF.

RUN ON THE MAC (network access for Ensembl and bcftools are required):

    cd "<project folder>"
    python3 src/ingest/verify_evogen.py \
        --rsids inbox/evogen_rsids.txt \
        --report inbox/evogen_merged.tsv \
        --vcf genome/<SAMPLE>.full.vcf.gz \
        --out genome/evogen_verify.tsv

What it does:
 1. Resolves every rsID into a GRCh38 coordinate through Ensembl REST (with a cache
    in genome/rs_coords_cache.json — a repeat run needs almost no network).
 2. Pulls the genotype out of the personal VCF (bcftools). An absent record = homozygous
    for the reference.
 3. Compares it with the genotype from the report, allowing for the fact that laboratories
    write alleles in arbitrary order AND sometimes from the opposite strand (complement).
 4. Writes a TSV with a status: match / match_complement / MISMATCH / no_coord /
    low_depth / not_in_vcf_norm.

Changes nothing in the profile. Read-only.
"""
import argparse, json, os, ssl, subprocess, sys, time, urllib.request, urllib.error

ENSEMBL = "https://rest.ensembl.org/variation/human/{}?content-type=application/json"
COMP = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', '-': '-'}


def comp(gt):
    return ''.join(COMP.get(c, c) for c in gt)


def norm(gt):
    """Genotype → canonical form: sorted alleles, upper case."""
    g = (gt or '').upper().replace('/', '').replace('|', '').strip()
    if not g or not all(c in 'ACGT' for c in g):
        return ''
    return ''.join(sorted(g))


def resolve(rsids, cache_path, sleep=0.12, insecure=False, tries=3):
    """rsID → GRCh38 coordinate. Network failures are NOT cached: otherwise one
    failed run would poison the cache and the next run would silently skip
    those positions. Only a trustworthy answer from Ensembl is cached (including
    a trustworthy "there is no mapping")."""
    ctx = None
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        print("WARNING: TLS certificate verification is disabled (--insecure). "
              "Only public rsID coordinates are requested; no personal data is sent.",
              file=sys.stderr)
    cache = {}
    if os.path.exists(cache_path):
        cache = json.load(open(cache_path, encoding='utf-8'))
    todo = [r for r in rsids if r not in cache]
    print(f"coordinates: {len(rsids) - len(todo)} in the cache, requesting {len(todo)}", file=sys.stderr)
    net_fail = 0
    for i, rs in enumerate(todo, 1):
        last = None
        for attempt in range(tries):
            try:
                with urllib.request.urlopen(ENSEMBL.format(rs), timeout=25, context=ctx) as fh:
                    d = json.load(fh)
                best = None
                for m in d.get('mappings', []):
                    name = str(m.get('seq_region_name', ''))
                    if m.get('assembly_name') == 'GRCh38' and (name.isdigit() or name in ('X', 'Y', 'MT')):
                        best = m
                        break
                cache[rs] = ({'chrom': str(best['seq_region_name']), 'pos': int(best['start']),
                              'alleles': best.get('allele_string', '')} if best else None)
                last = None
                break
            except urllib.error.HTTPError as e:
                if e.code in (400, 404):             # Ensembl has no such rsID — that is an answer, cache it
                    cache[rs] = None
                    last = None
                    break
                last = e
                time.sleep(1.5 * (attempt + 1))
            except Exception as e:                   # noqa: BLE001 — network/TLS, not cached
                last = e
                time.sleep(1.5 * (attempt + 1))
        if last is not None:
            net_fail += 1
            print(f"  ! {rs}: {last}", file=sys.stderr)
            if net_fail == 5:
                json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
                sys.exit("\nFive network failures in a row — aborting rather than spinning.\n"
                         "If this is a TLS certificate error: first try\n"
                         "  /Applications/Python*/Install\\ Certificates.command\n"
                         "or  pip3 install --upgrade certifi  and\n"
                         "  export SSL_CERT_FILE=$(python3 -c 'import certifi;print(certifi.where())')\n"
                         "As a last resort — the same run with the --insecure flag "
                         "(only public coordinates are requested; no personal data is sent).")
        else:
            net_fail = 0
        if i % 25 == 0:
            json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
            print(f"  ... {i}/{len(todo)}", file=sys.stderr)
        time.sleep(sleep)
    json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False)
    return cache


def vcf_lookup(vcf, chrom, pos):
    """→ (genotype_str, depth, ref, alt), or None if there is no record."""
    for c in (chrom, 'chr' + chrom):
        try:
            out = subprocess.run(
                ['bcftools', 'query', '-r', f'{c}:{pos}-{pos}',
                 '-f', '%REF\t%ALT\t[%GT]\t[%DP]\n', vcf],
                capture_output=True, text=True, timeout=60).stdout.strip()
        except FileNotFoundError:
            sys.exit("bcftools not found — install it (brew install bcftools) and retry")
        if out:
            ref, alt, gt, dp = out.split('\n')[0].split('\t')
            alleles = [ref] + alt.split(',')
            idx = [a for a in gt.replace('|', '/').split('/')]
            try:
                g = ''.join(alleles[int(i)] for i in idx if i != '.')
            except (ValueError, IndexError):
                g = ''
            return g, dp, ref, alt
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rsids', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--vcf', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cache', default=None)
    ap.add_argument('--insecure', action='store_true',
                    help='do not verify the Ensembl TLS certificate (a corporate proxy)')
    a = ap.parse_args()
    cache_path = a.cache or os.path.join(os.path.dirname(a.vcf), 'rs_coords_cache.json')

    rsids = [l.strip() for l in open(a.rsids, encoding='utf-8') if l.strip()]
    coords = resolve(rsids, cache_path, insecure=a.insecure)

    # report: rsID → (genotype, page, trait, gene, colour)
    rep = {}
    with open(a.report, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        ix = {c: i for i, c in enumerate(head)}
        for line in fh:
            p = line.rstrip('\n').split('\t')
            rs = p[ix['rsid']]
            rep.setdefault(rs, p)

    n = dict(match=0, comp=0, mismatch=0, nocoord=0, absent=0)
    with open(a.out, 'w', encoding='utf-8') as out:
        out.write('rsid\tgene\tsection\ttrait\tpage\treport_gt\treport_color\t'
                  'chrom\tpos\tvcf_gt\tdepth\tstatus\n')
        for rs in rsids:
            c = coords.get(rs)
            p = rep.get(rs, [''] * len(ix))
            rgt = p[ix['genotype']] if p else ''
            if not c:
                n['nocoord'] += 1
                out.write(f"{rs}\t{p[ix['gene']]}\t{p[ix['section']]}\t{p[ix['trait']]}\t"
                          f"{p[ix['page']]}\t{rgt}\t{p[ix['genotype_color']]}\t\t\t\t\tno_coord\n")
                continue
            hit = vcf_lookup(a.vcf, c['chrom'], c['pos'])
            if hit is None:
                ref = (c['alleles'] or '/').split('/')[0]
                vgt, dp = (ref * 2 if len(ref) == 1 else ref), 'ref'
                status_base = 'hom_ref_assumed'
                n['absent'] += 1
            else:
                vgt, dp = hit[0], hit[1]
                status_base = 'called'
            nr, nv = norm(rgt), norm(vgt)
            if nr and nv and nr == nv:
                status, key = 'match', 'match'
            elif nr and nv and norm(comp(rgt)) == nv:
                status, key = 'match_complement', 'comp'
            elif not nr or not nv:
                status, key = f'uncomparable:{status_base}', 'nocoord'
            else:
                status, key = f'MISMATCH:{status_base}', 'mismatch'
            n[key] = n.get(key, 0) + 1
            out.write(f"{rs}\t{p[ix['gene']]}\t{p[ix['section']]}\t{p[ix['trait']]}\t{p[ix['page']]}\t"
                      f"{rgt}\t{p[ix['genotype_color']]}\t{c['chrom']}\t{c['pos']}\t{vgt}\t{dp}\t{status}\n")
    print(json.dumps(n, ensure_ascii=False), file=sys.stderr)
    print(f"done → {a.out}", file=sys.stderr)


if __name__ == '__main__':
    main()
