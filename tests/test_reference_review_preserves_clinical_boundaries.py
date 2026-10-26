"""The finite reference review never supplies an unverified clinical mechanism."""
from __future__ import annotations
import unittest
from unittest.mock import patch
import support  # noqa: F401
from scholion import core,i18n
from scholion.conclusion_basis import conclusion_basis,subclaim_bases
from scholion.engine.thematic_panels import thematic_reference,thematic_readings
from scholion.panel_reference import genome_context,reference_lines

class TestReviewedReferenceBoundaries(unittest.TestCase):
 def test_all_ab_positions_and_adjacent_claims_have_an_explicit_final_scope(self):
  reviews=core._read_knowledge_raw('clinical_reference_review.json')['entries'];count=0;subcount=0
  for name,field in [('system_gene_panels.json','systems'),('on_demand_panels.json','panels')]:
   for system,panel in core._read_knowledge_raw(name)[field].items():
    for spec in panel.get('positions') or []:
     if (spec.get('evidence') or {}).get('level') not in ('A','B'):continue
     count+=1;review=reviews[name+'|'+system+'|'+spec['gene']+'|'+spec['rsid']]
     self.assertFalse(review['automatic_eligibility_changed']);self.assertTrue(review['reference_context_retained'])
     for language in ('en','ru'):self.assertTrue(review['limitations'][language])
     basis=conclusion_basis(spec)
     if basis['status']!='complete':self.assertNotEqual(review['outcome'],'existing_supported_basis')
     adjacent=subclaim_bases(spec,spec['evidence']['level']);subcount+=len(adjacent)
     self.assertEqual(set(adjacent),set(review['subclaims']))
     for key,claim in adjacent.items():
      if claim['status']!='complete':self.assertEqual(review['subclaims'][key]['outcome'],'no_independent_instruction')
  self.assertEqual(count,160);self.assertEqual(subcount,57)

 def test_nat2_does_not_claim_that_no_guideline_exists_or_infer_a_diplotype(self):
  book=core._read_knowledge_raw('system_gene_panels.json')
  rows=[p for s in book['systems'].values() for p in s['positions'] if p.get('gene')=='NAT2']
  self.assertEqual(len(rows),3)
  for row in rows:
   self.assertIn('40974042',row['source']);self.assertIn('23150149',row['source'])
   self.assertNotIn('no CPIC',row['source']);self.assertEqual(row['clinical_review']['outcome'],'haplotype_reference_only')
   self.assertIn('mechanism',conclusion_basis(row)['missing'])

 def test_specialized_reference_is_visible_but_is_not_read_as_a_snp(self):
  identities=core._read_knowledge('variant_reference_identity.json')['variants']
  self.assertEqual(len(identities),7)
  self.addCleanup(i18n.set_lang,i18n.lang())
  for language in ('en','ru'):
   i18n.set_lang(language)
   for rs,entry in identities.items():
    row=genome_context(entry['gene'],rs);identity=row['reference_context']['reference_identity']
    self.assertFalse(identity['personal_call_supported']);self.assertIsNone(identity['effect_allele'])
    self.assertEqual(set(identity['builds']),{'GRCh37','GRCh38'})
    self.assertIn('SPDI','\n'.join(reference_lines(row)))
   liver=thematic_reference('hepatic_genetics')
   self.assertIn('rs72613567',{p['rsid'] for p in liver['positions']})
  from scholion import genome
  with patch.object(genome,'_gt_at',side_effect=AssertionError('specialized event passed to SNP reader')), \
       patch.object(genome,'available',return_value={'ready':False}),patch.object(core,'profile_genotypes',return_value={}):
   readings=thematic_readings('hepatic_genetics','clinician')
  row=next(p for p in readings['positions'] if p['rsid']=='rs72613567')
  self.assertFalse(row['reading']['read']);self.assertEqual(row['reading']['reason'],'indel_unsupported')

 def test_waiting_route_candidates_have_final_limits_and_no_active_rule(self):
  book=core._read_knowledge_raw('correction_routes.json')
  self.assertNotIn('waiting',book['_meta'])
  final=book['_meta']['reviewed_candidates'];self.assertEqual(len(final),3)
  for row in final.values():self.assertEqual(row['status'],'not_eligible_for_automatic_route')
  active={r['key'] for r in book['rules']}
  self.assertFalse(active&set(final))
