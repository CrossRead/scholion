"""Sourced multi-observation context; never a diagnosis, score or test order."""
from __future__ import annotations

from . import core
from .i18n import t
from . import genetic_comparison as gc


def catalogue() -> list[dict]:
    return core._read_knowledge('genetic_lab_patterns.json').get('patterns', [])


def reference_patterns(gene: str, rsid: str | None = None) -> list[dict]:
    """Sourced context remains readable even without a personal finding."""
    fields = ('association_id', 'summary', 'limitations', 'association_level', 'source', 'level_scope')
    return [{**{k: p.get(k) for k in fields}, 'source_links': gc.sources(p['source'])}
            for p in catalogue() if gene in p['genes'] and
            (not p['variants'] or any(v['rsid'] == rsid for v in p['variants']))]


def same_draw(observations: list[dict]) -> bool:
    """Same date alone is insufficient; collection identity must be recorded."""
    points = [o.get('point') or {} for o in observations]
    if not points or any(not p.get('date') for p in points):
        return False
    if len({p['date'] for p in points}) != 1:
        return False
    complete_identity = False
    for key in ('sample_id', 'draw_id'):
        values = [str(p[key]) for p in points if p.get(key)]
        if len(set(values)) > 1:
            return False
        if len(values) == len(points):
            complete_identity = True
    return complete_identity


def _variant_rows(spec: dict, rows: list[dict]) -> list[dict]:
    if spec['variants']:
        return [next((r for r in rows if r.get('rsid') == v['rsid'] and r.get('gene') == v['gene']), {})
                for v in spec['variants']]
    return [r for r in rows if r.get('gene') in spec['genes'] and not r.get('rsid')
            and (r.get('variant_records') or r.get('findings') or r.get('carrier'))]


def _molecular_reasons(spec: dict, rows: list[dict]) -> list[str]:
    reasons = []
    for variant, row in zip(spec['variants'], rows):
        reasons.extend(gc.genotype_quality(row)['reasons'])
        if row.get('risk_allele') != variant['risk_allele'] or row.get('hgvs') != variant['hgvs']:
            reasons.append('catalogue_identity')
        if (row.get('genotype') or {}).get('assembly') not in ('GRCh37', 'GRCh38'):
            reasons.append('assembly_unknown')
    return list(dict.fromkeys(reasons))


def _base(spec: dict, rows: list[dict], markers: dict) -> dict:
    row = next((r for r in rows if r), {})
    variant: dict = next(iter(spec['variants']), {})
    anchor = {**row, 'gene': row.get('gene') or spec['genes'][0], 'rsid': row.get('rsid') or ''}
    single = {'gene':anchor['gene'], 'rsid':anchor['rsid'], 'marker':next(iter(spec['markers']), ''),
              'systems':spec['systems'], 'states':['het','hom','hemi'],
              'association_id':spec['association_id'], 'relation_type':spec['kind'],
              'association_level':spec['association_level'], 'independent_claim':True,
              'evidence_type':row.get('mode') or 'monogenic', 'direction':'context',
              'status':'excluded' if spec['kind']=='excluded' else 'hypothesis',
              'catalogue_allele':variant.get('risk_allele'), 'catalogue_hgvs':variant.get('hgvs'),
              **{k:spec[k] for k in ('source','summary','limitations','checked_on','review_kind')}}
    result = gc._compare_spec(anchor, markers, single)
    result.update(id=spec['association_id'], relation_type=spec['kind'], qualified_context=False,
                  pattern_inputs=spec['markers'], variant_readings=rows,
                  level_scope=spec.get('level_scope', 'association'),
                  replaces=spec.get('replaces', []),
                  reference_system=row.get('reference_system'),
                  knowledge_status='excluded' if spec['kind']=='excluded' else 'hypothesis')
    result['applicable'] = False
    result['horizons'] = []
    result['contrary_observations'] = []
    result['state'] = next((r['state'] for r in rows if r.get('state') in ('het', 'hom', 'hemi')),
                           row.get('state') or ('finding' if any(r.get('variant_records') for r in rows) else None))
    result['variant_level'] = row.get('level')
    result['gene'] = ', '.join(dict.fromkeys(r['gene'] for r in rows if r.get('gene'))) or spec['genes'][0]
    result['genes'] = list(dict.fromkeys(r['gene'] for r in rows if r.get('gene')))
    result['reference_gene'] = row.get('gene') or spec['genes'][0]
    result['rsid'] = ' / '.join(dict.fromkeys(v['rsid'] for v in spec['variants']))
    result['facts']['variants'] = [r.get('genotype') or r.get('variant_records') or {} for r in rows]
    result['facts']['gencc_assertions'] = [a for r in rows for a in r.get('assertions', [])]
    return result


def _drug_context(result: dict) -> bool:
    meds = [m for m in core.active_medications() if 'thiopurine' in core.medication_classes(m)]
    if not meds:
        return False
    from .engine.pgx import compute_phenotype
    phenotypes = {gene:compute_phenotype(gene) for gene in ('TPMT','NUDT15')}
    result['facts']['treatment'] = meds
    result['facts']['pharmacogenetics'] = phenotypes
    if any(p.get('certainty') != 'called' or not (p.get('basis') or {}).get('source') for p in phenotypes.values()):
        result['reasons'].append('diplotype_unconfirmed')
    result['reasons'].append('treatment_not_causal')
    return True


def comparisons(rows: list[dict], markers: dict, system: str) -> list[dict]:
    results = []
    for spec in catalogue():
        if system not in spec['systems'] or spec.get('reference_only'):
            continue
        relevant = _variant_rows(spec, rows)
        if not relevant or not any(relevant):
            continue
        kind = spec['kind']
        if not spec['variants'] and not any(r.get('findings') or r.get('carrier') or r.get('variant_records') for r in relevant):
            continue
        if spec['variants'] and kind not in ('apoe','apoe_mixed','drug_context') and not any(
                r.get('state') in ('het','hom','hemi') for r in relevant):
            continue
        item = _base(spec, relevant, markers)
        observations = [gc.observation(markers.get(key)) for key in spec['markers']]
        # A measured ratio/bias context does not require an invented normal
        # interval. Invalid or withheld intervals and censored values stay out.
        if kind in ('ratio', 'bias'):
            for obs in observations:
                point = obs.get('point') or {}
                if (obs['reasons'] == ['not_comparable'] and gc._number(point.get('value'))
                        and point.get('ref_low') is None and point.get('ref_high') is None
                        and not any(point.get(k) for k in ('reference_withheld', 'censored', 'comparator'))):
                    obs.update(status='current', current=True, reasons=[])
        item['observations'] = [{'marker':key, **obs} for key,obs in zip(spec['markers'], observations)]
        item['facts']['laboratories'] = [o.get('point') for o in observations]
        reasons = _molecular_reasons(spec,relevant)
        for key,obs in zip(spec['markers'],observations):
            reasons.extend(obs['reasons'])
            reasons.extend(gc.collection_reasons(spec.get('endpoint', {}).get(key, {}),obs))
        if spec.get('requires_same_draw') and not same_draw(observations):
            reasons.append('draw_identity')
        if spec.get('requires_sex') and core.profile_sex() not in ('male','female'):
            reasons.append('sex_scope')
        if kind == 'iron' and relevant[0].get('state') != 'hom':
            reasons.append('genotype_scope')
        if kind in ('apoe','apoe_mixed'):
            from .genome import _apoe_from_readings
            apo = _apoe_from_readings(*(r.get('genotype') or {} for r in relevant))
            item['facts']['diplotype'] = apo
            item['display_genotype'] = apo.get('genotype')
            if apo['status'] != 'ok':
                reasons.append('diplotype_unconfirmed')
            diplotype = apo.get('genotype')
            if kind == 'apoe_mixed':
                if diplotype != 'ε2/ε2':
                    continue
                reasons.append('clinical_context_required')
            elif not reasons:
                direction = {'ε2/ε3':'lower','ε3/ε4':'higher','ε4/ε4':'higher'}.get(diplotype)
                if direction:
                    obs=observations[0]
                    position=obs['position']
                    status='within' if position=='within' else 'concordant' if (
                        (position=='above') == (direction=='higher')) else 'different_direction'
                    item.update(eligible=True, applicable=True, knowledge_status='supported',
                                expected_direction=direction, relation=status, status=status,
                                qualified_context=True, state='diplotype')
                else:
                    reasons.append('diplotype_context_only')
        elif kind == 'ratio' and not reasons:
            numerator, denominator = [o['point']['value'] for o in observations]
            if denominator > 0:
                item['derived']={'kind':'ratio','value':numerator/denominator,'unit':'ratio',
                                 'markers':spec['markers'],'reference':None,'abnormal':None}
                item.update(qualified_context=True,status='context_available')
            else:
                reasons.append('not_comparable')
        elif kind == 'iron' and not reasons:
            item.update(qualified_context=True, status='compatible_pattern' if all(
                o['position']=='above' for o in observations) else 'context_available')
        elif kind == 'bias' and not reasons:
            item.update(qualified_context=True,status='bias_possible')
        elif kind == 'drug_context':
            if not _drug_context(item):
                continue
            reasons.extend(item['reasons'])
        elif kind == 'excluded':
            item.update(status='excluded')
        else:
            reasons.append(spec.get('hypothesis_reason') or 'clinical_context_required')
        item['reasons'] = list(dict.fromkeys(reasons))
        item['reason_labels'] = [t('genlab.quality.'+r) for r in item['reasons']]
        if not item['qualified_context'] and kind != 'excluded':
            item['status'] = 'hypothesis' if any(r.get('read') for r in relevant) else 'context_only'
        item['status_label'] = t('genlab.status.'+item['status'])
        item['comparison'] = item['status_label']
        if item['eligible']:
            point = observations[0]['point']
            item['comparison'] = t('insight.context.' + item['status'],
                gene=item['gene'], rsid=item.get('display_genotype') or item['rsid'],
                level=item['level'], marker=markers[spec['markers'][0]].get('name') or spec['markers'][0],
                value=point['value'], unit=core.unit_label(point.get('unit') or ''), date=point['date'])
        item['applicable'] = item['qualified_context']
        item['hypothesis'] = spec['summary'] if item['knowledge_status']=='hypothesis' else None
        item['interpretation'] = spec['summary'] if item['qualified_context'] else None
        item['question'] = None
        results.append(item)
    return results
