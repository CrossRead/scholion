"""Gene biology fills catalogue gaps without assigning variant effects."""
from __future__ import annotations

import json
import shutil
import unittest
from unittest import mock

import gene_card_support
from scholion import core, i18n
from scholion.panel_reference import gene_reference_context, genome_context, reference_context, reference_lines


class TestSourcedGeneFunctions(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_refused_personal_reading_keeps_known_biology_and_gencc_in_agent_text(self):
        from scholion import format as fmt
        for language in ('en','ru'):
            i18n.set_lang(language)
            reference=genome_context('C10ORF71')
            expected=reference['reference_context']['gene_function']
            for status in ('no_genome','unindexed','unresolved_gene'):
                result={**reference,'status':status,'region':{'synthetic':True},
                        'location':{'chrom':'10','start':1,'end':2,'assembly':'GRCh38'},
                        'message':'Synthetic reading refusal','coverage':{'why':'Synthetic missing alignment'}}
                text=fmt.genome_report(result)
                self.assertIn(expected,text,status)
                self.assertIn('GenCC',text,status)
                self.assertIn('2026-10-14',text,status)
                self.assertNotIn('variants in the gene: 0',text)
            position={**genome_context('C10ORF71','rsSynthetic'),'status':'no_genome',
                      'message':'Synthetic no genome','chrom':'10','pos':1}
            text=fmt.genome_report(position)
            self.assertIn(expected,text)
            self.assertIn('GenCC',text)

    def test_known_functions_cross_the_same_three_reference_paths(self):
        for language, fragment in (("en", "telomerase"), ("ru", "\u0442\u0435\u043b\u043e\u043c\u0435\u0440\u0430\u0437\u044b")):
            i18n.set_lang(language)
            for context in (gene_reference_context("TERC", []), reference_context({"gene": "TERC"}, "E"),
                            genome_context("TERC", "rsSynthetic")["reference_context"]):
                self.assertIn(fragment, context["gene_function"])
                self.assertTrue(context["gene_source"].startswith("https://www.ncbi.nlm.nih.gov/gene/"))
                self.assertNotEqual(context.get("variant_status"), "described")
                self.assertIn(context["gene_source"], "\n".join(reference_lines({"reference_context": context})))
            self.assertEqual(genome_context("TERC", "rsSynthetic")["level"], "E")

    def test_alias_identity_history_and_pseudogenes_do_not_invent_enzymes(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            alias = genome_context("C20orf194")["reference_context"]
            self.assertEqual(alias["canonical_symbol"], "DNAAF9")
            self.assertIn("DNAAF9", alias["gene_function"])
            self.assertEqual(genome_context("PPARG2")["reference_context"]["canonical_symbol"], "PPARG")
            for symbol, status in (("CMAHP", "pseudogene_identity"), ("LOC101059906", "withdrawn_model")):
                context = genome_context(symbol, "rsSynthetic")["reference_context"]
                self.assertEqual(context["function_status"], status)
                self.assertTrue(context["limitations"])
                self.assertFalse(context["function_support"])
                self.assertEqual(context["level"], "E")
            self.assertIn("inactive" if language == "en" else "\u043d\u0435\u0430\u043a\u0442\u0438\u0432\u043d\u044b\u0439",
                          genome_context("ART3")["reference_context"]["gene_function"])

    def test_text_retains_resolved_identity_and_additional_primary_sources(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            alias = genome_context("C20orf194")
            self.assertIn(i18n.t("reference.resolved_gene", gene="DNAAF9"), reference_lines(alias))
            row = genome_context("ANKRD55")
            additional = row["reference_context"]["gene_additional_sources"]
            self.assertGreater(len(additional), 0)
            report = "\n".join(reference_lines(row))
            for source in additional:
                self.assertIn(source, report)

    def test_every_longevity_symbol_has_sourced_biology_or_explicit_identity(self):
        catalogue = core._read_knowledge("longevitymap.json")
        symbols = {part.strip() for row in catalogue["variants"].values() for part in str(row.get("gene") or "").split(",") if part.strip()}
        self.assertGreater(len(symbols), 700)
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for symbol in symbols:
                context = genome_context(symbol)["reference_context"]
                self.assertTrue(context["gene_source"], symbol)
                self.assertNotEqual(context["gene_function"], i18n.t("reference.gene_unknown"), symbol)

    def test_study_gene_set_does_not_assign_every_variant_to_every_gene(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            group = genome_context("TERC,SIRT3,TERC")
            self.assertEqual(group["catalogue_genes"], ["TERC", "SIRT3"])
            self.assertEqual([r["gene"] for r in group["gene_contexts"]], ["TERC", "SIRT3"])
            self.assertEqual(group["reference_context"]["scope"], "catalogue_gene_set")
            variant = genome_context("TERC,SIRT3", "rsSynthetic")
            self.assertEqual(variant["gene_contexts"], [])
            self.assertEqual(variant["reference_context"]["variant_status"], "not_curated")
            self.assertEqual(variant["level"], "E")
            self.assertNotIn("telomerase", variant["reference_context"]["gene_function"])

    def test_longevity_count_is_symbols_not_study_gene_sets(self):
        from scholion.engine.genomics import longevity_findings
        data = {"_meta": {"synthetic": True}, "known": [{"gene": "TERC", "rsid": "rsSynthetic"}],
                "significant_by_gene": {"SIRT3": [], "TERC,SIRT6": [], "TERC": []}}
        with mock.patch.object(core, "longevity_data", return_value=data):
            result = longevity_findings()
        self.assertEqual(result["stats"]["significant_genes"], 3)
        self.assertEqual(result["stats"]["catalogue_gene_sets"], 3)

    def test_gene_set_biology_reaches_the_assistants_text_report(self):
        from scholion import format as fmt
        for language in ("en", "ru"):
            i18n.set_lang(language)
            group = genome_context("TERC,SIRT6")
            group["variants"] = [genome_context("TERC,SIRT6", "rsSynthetic")]
            report = fmt.longevity_report({"available": True, "significant_genes": [group]})
            for gene in group["gene_contexts"]:
                self.assertIn(gene["reference_context"]["gene_function"], report)
                self.assertIn(gene["reference_context"]["gene_source"], report)
            self.assertIn(group["reference_context"]["limitations"], report)
            self.assertEqual(group["variants"][0]["level"], "E")

    def test_unindexed_gene_reading_retains_reference_biology(self):
        from scholion import genome, gene_region
        from scholion.engine.genomics import genome_lookup
        def attach(answer, gene):
            answer["region_report"] = {"gene": gene, "status": "unindexed"}
        with mock.patch.object(genome, "lookup", return_value={"gene": "APOE", "loci": []}), mock.patch.object(gene_region, "attach_reading", side_effect=attach):
            answer = genome_lookup(gene="APOE")
        self.assertEqual(answer["region_report"]["reference_context"], answer["reference_context"])
        self.assertTrue(answer["reference_context"]["gene_source"])
        self.assertEqual(answer["region_report"]["status"], "unindexed")

    def test_secondary_findings_genes_do_not_lose_known_function(self):
        from scholion.engine.screening import _panel
        from scholion.panel_reference import gene_function_entry
        genes = _panel()["genes"]
        self.assertGreaterEqual(len(genes), 80)
        for gene in genes:
            self.assertTrue(gene_function_entry(gene).get("source"), gene)

    def test_intake_typo_uses_only_the_exact_curated_locus_for_biology(self):
        context = reference_context({"gene": "COL1R1", "rsid": "rs1800012"}, "E")
        self.assertEqual(context["canonical_symbol"], "COL1A1")
        self.assertTrue(context["gene_source"])
        self.assertEqual(context["variant_status"], "not_curated")
        unknown = reference_context({"gene": "COL1R1", "rsid": "rsSynthetic"}, "E")
        self.assertEqual(unknown["function_status"], "not_curated")

    def test_annotations_have_human_identity_and_non_negated_provenance(self):
        entries = core._read_knowledge_raw("gene_function_context.json")["genes"]
        self.assertGreater(len(entries), 650)
        for symbol, entry in entries.items():
            self.assertEqual(entry["scope"], "genomic_annotation" if entry.get("gene_type") == "BIOLOGICAL_REGION" else "gene_function", symbol)
            self.assertTrue(entry.get("source"), symbol)
            self.assertEqual(set(entry["description"]), {"en", "ru"}, symbol)
            self.assertNotIn("level", entry, symbol)
            if entry.get("tax_id"):
                self.assertEqual(entry["tax_id"], "9606", symbol)
            for selected in entry.get("function_support", []):
                for annotation in selected["annotations"]:
                    self.assertNotIn("NOT", annotation["qualifier"], symbol)
                    self.assertNotEqual(annotation["evidence_code"], "ND", symbol)
        self.assertIn("CC BY 4.0", core._read_knowledge_raw("gene_function_context.json")["_meta"]["go_attribution"])

    def test_official_previous_symbols_reuse_canonical_function_without_a_variant_claim(self):
        from scholion.panel_reference import gene_function_entry
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for alias, canonical in (("ARNTL", "BMAL1"), ("CALC", "MICU1"), ("GIF", "CBLIF")):
                previous = gene_function_entry(alias)
                current = gene_function_entry(canonical)
                self.assertEqual(previous["description"], current["description"])
                self.assertEqual(previous["canonical_symbol"], canonical)
                self.assertTrue(previous["identity_source"].startswith("https://www.genenames.org/"))
                card = genome_context(alias, "rsSynthetic")
                self.assertEqual(card["level"], "E")
                self.assertEqual(card["reference_context"]["variant_status"], "not_curated")
            # Family names and misspellings do not become official aliases.
            for unknown in ("F13", "LRP", "COL1R1", "LPR1"):
                self.assertFalse(gene_function_entry(unknown), unknown)

    def test_expanded_functions_reach_both_languages_without_inventing_readings(self):
        for language, fragments in (("en", {"CNDP1": "carnosinase", "MICU1": "calcium",
                                            "BMAL1": "circadian", "ACADM": "fatty acids",
                                            "HSD17B13": "predicted"}),
                                    ("ru", {"CNDP1": "карнозиназу", "MICU1": "кальция",
                                            "BMAL1": "суточные", "ACADM": "жирных кислот",
                                            "HSD17B13": "предсказанная"})):
            i18n.set_lang(language)
            for symbol, fragment in fragments.items():
                card = genome_context(symbol, "rsSynthetic")
                context = card["reference_context"]
                self.assertIn(fragment, context["gene_function"], symbol)
                self.assertTrue(context["gene_source"], symbol)
                self.assertEqual(card["level"], "E")
                self.assertEqual(context["variant_status"], "not_curated")
                self.assertNotIn("genotype", card)
                self.assertIn(context["gene_function"], "\n".join(reference_lines(card)))

    def test_panel_effects_and_provenance_follow_the_output_language(self):
        def values(node, field):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == field:
                        yield value
                    else:
                        yield from values(value, field)
            elif isinstance(node, list):
                for value in node:
                    yield from values(value, field)
        for name in ("system_gene_panels.json", "on_demand_panels.json"):
            i18n.set_lang("ru")
            data = core._read_knowledge(name)
            effects = list(values(data, "effect_size"))
            self.assertGreater(len(effects), 20)
            for effect in effects:
                self.assertIsInstance(effect, str)
                self.assertRegex(effect, "[\u0400-\u04ff]")
            for source in values(data, "source"):
                self.assertIsInstance(source, str)
                self.assertNotIn("panel author's", source)
            i18n.set_lang("en")
            for effect in values(core._read_knowledge(name), "effect_size"):
                self.assertIsInstance(effect, str)
                self.assertNotRegex(effect, "[\u0400-\u04ff]")

    @unittest.skipUnless(shutil.which("node"), "requires node for the actual page renderers")
    def test_genome_cards_and_longevity_disclosures_use_shared_format(self):
        page = gene_card_support.source()
        names = ("referenceContextHtml", "geneticPreviewHtml", "geneticBriefHtml", "genomeGeneTable", "genomeCard", "renderLongevity")
        functions = []
        for name in names:
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start)+2])
        i18n.set_lang("en")
        context = genome_context("TERC")
        script = r"""
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=(k,a)=>k+' '+Object.values(a||{}).join(' '),DISPLAY_MODE='patient';
const badge=(c,x)=>x,levelChip=x=>x||'',mechanismHtml=()=>'',passportHtml=()=>'',authorNoteHtml=()=>'',clinicalBasisHTML=()=>'';
""" + "\n".join(functions) + r"""
const row=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const unknown={reference_context:{gene_function:'Function unavailable',function_status:'not_curated',variant_context:'Variant context'}};
assert.ok(!referenceContextHtml(unknown).includes('<strong>Function unavailable</strong>'));
assert.ok(referenceContextHtml(unknown).includes('Function unavailable'));
for(const data of [row,{...row,status:'no_genome',locus:{gene:'TERC'}},
 {...row,loci:[{...row,result:{confidence:'assumed_ref',genotype:'AA',depth:0}}]}]){
 const html=genomeCard(data);
 assert.ok(html.includes('<strong class="gene-card-function">'+row.reference_context.gene_function+'</strong>'));
 assert.ok(html.includes('data-gene-description'));
 if(data.loci)assert.ok(!html.includes('>AA<'));
}
const html=renderLongevity({available:true,known:[{...row,rsid:'rsSynthetic'}],
 significant_genes:[{...row,variants:[row]}],stats:{significant_genes:1,significant_carriers:1}});
assert.equal((html.match(/summary class="cr-btn"/g)||[]).length,2);
assert.ok(!html.includes('Literature catalogue'));
assert.ok(html.includes('data-gene-description'));
const geneOnly=genomeGeneTable([row]);
assert.ok(geneOnly.includes('web.gene_card.no_position'));
"""
        script = gene_card_support.javascript() + script
        result = gene_card_support.run(script, input=json.dumps(context),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
