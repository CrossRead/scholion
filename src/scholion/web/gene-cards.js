/* One presentation of an existing gene/variant result. No clinical inference. */
(function (root) {
  'use strict';
  const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
  const list = value => Array.isArray(value) ? value : [];
  const unique = values => [...new Set(values.filter(Boolean))];
  const canonical = value => Array.isArray(value) ? value.map(canonical)
    : value && typeof value === 'object' ? Object.fromEntries(Object.keys(value).sort().map(k => [k, canonical(value[k])])) : value;
  const normal = value => text(value).trim().replace(/\s+/g, ' ').toLowerCase();

  function groupAssertions(assertions) {
    const groups = new Map();
    for (const assertion of assertions) {
      // Only equivalent claims share a heading. Different sources, dates and IDs
      // remain witnesses; neither a majority nor a preferred inheritance is inferred.
      const key = JSON.stringify([assertion.gene_symbol || assertion.gene,
        assertion.disease_id || normal(assertion.disease || assertion.disease_label),
        assertion.moi_code || assertion.moi || normal(assertion.moi_label),
        assertion.classification || normal(assertion.classification_label)]);
      if (!groups.has(key)) groups.set(key, {claim:assertion, witnesses:[], seen:new Set()});
      const group = groups.get(key), identity = JSON.stringify(canonical(assertion));
      if (!group.seen.has(identity)) { group.seen.add(identity); group.witnesses.push(assertion); }
    }
    return [...groups.values()].map(({claim, witnesses}) => ({claim, witnesses}));
  }

  function project(input, options = {}) {
    const p = input || {}, context = object(p.personal_context), reference = object(p.reference_context);
    const reading = Object.keys(object(p.reading)).length ? p.reading
      : Object.keys(object(p.result)).length ? p.result : object(p.genotype);
    const compound = !!(options.compound || p.epsilon || p.diplotype || p.rs429358 || p.rs7412);
    const position = text(p.rsid || p.hgvs || (p.chrom && p.pos ? p.chrom + ':' + p.pos : ''));
    const isVariant = !!(position || Object.keys(context).length || compound);
    const confidence = reading.confidence || p.confidence;
    const unavailable = p.status === 'no_genome' || p.read === false || reading.read === false || p.presumed === true || confidence === 'assumed_ref';
    const genotype = unavailable || !isVariant ? '' : text(p.display_genotype || p.epsilon || p.diplotype
      || (typeof p.genotype === 'string' ? p.genotype : '') || reading.genotype || context.genotype);
    const state = text(p.state || reading.state || p.zygosity);
    let zygosity = text(context.zygosity);
    if (!zygosity) zygosity = ({het:'heterozygous',hom:'homozygous',hemi:'haploid',absent:'reference'})[state] || '';
    // Technical zygosity may be read from an explicit call, never from absence.
    if (!zygosity && genotype && !compound) {
      const parts = /[/|]/.test(genotype) ? genotype.split(/[/|]/) : /^[ACGT]{1,2}$/i.test(genotype) ? genotype.split('') : [];
      if (parts.length && parts.every(x => /^(?:\d+|[ACGT])$/i.test(x))) {
        zygosity = parts.length === 1 ? 'haploid' : parts.length === 2
          ? (parts[0] === parts[1] ? 'homozygous' : 'heterozygous') : '';
      }
    }
    if (unavailable || !isVariant) zygosity = '';
    if (compound) zygosity = '';
    let copies = context.allele_identity_supported === false ? null : context.alternative_copies;
    if (copies == null && context.allele_identity_supported !== false && p.read === true) {
      copies = ({het:1,hom:2,hemi:1,absent:0})[state];
    }
    if (p.copies != null && copies == null && context.allele_identity_supported !== false && !unavailable) copies = p.copies;
    if (unavailable || !isVariant || compound) copies = null;
    const interpretation = object(p.interpretation);
    const summary = [interpretation.summary,p.summary,p.text,p.note,p.label,reference.variant_context,options.fallback].map(text).find(Boolean) || '';
    const hasVariantGrade = isVariant && reference.variant_status !== 'not_supplied';
    const level = hasVariantGrade ? text(interpretation.level || p.level || reference.level) : '';
    const status = text(context.status);
    // `carrier` on catalogue rows means a named allele, not clinical carriage.
    const statusLabel = status && status !== 'classification_only' ? text(context.label) : '';
    const assertions = list(reference.gencc_assertions).length ? reference.gencc_assertions
      : list(p.assertions).length ? p.assertions : list(p.gencc);
    const modes = unique([text(context.inheritance_label), ...(!Object.keys(context).length
      ? [text(p.inheritance), text(p.moi), ...list(p.moi_codes)] : [])]);
    const quality = unique([text(reading.note || reading.message), text(p.depth_note), text(p.read_why_text),
      text(p.reading_note), text(p.file_says_text), text(p.read_why_text ? '' : p.read_why), text(p.verdict_label)]);
    return {gene:text(p.gene || object(p.locus).gene || reference.canonical_symbol), position, compound, genotype, zygosity, copies,
      geneScreen:!isVariant && options.geneScreen ? object(options.geneScreen) : null,
      geneRegion:!isVariant && options.geneRegion ? object(options.geneRegion) : null,
      unavailable, isVariant, referenceOnly:options.referenceOnly === true,
      level, status, statusLabel, functionText:reference.function_status === 'not_curated' ? '' : text(reference.gene_function || p.function),
      summary, inclusionReason:text(context.inclusion_reason), personalMeaning:text(context.summary),
      classification:text(p.clnsig || p.classification || (typeof p.clinvar === 'string' ? p.clinvar : (object(p.clinvar).classification || object(p.clinvar).clinical_significance))),
      condition:text(p.disease || p.phenotype || p.clndn || reference.disease_context?.name),
      assertions, modes, quality, depth:reading.depth ?? p.depth,
      source:text(reading.source || p.reading_source), confidence, review:text(p.review_confidence || p.review),
      coordinate:p.chrom && p.pos ? text(p.chrom) + ':' + text(p.pos) : '',
      protein:text(p.protein || p.star), readingMessage:text(p.reading_label),
      inheritance:object(context.inheritance), context, reference};
  }

  function render(input, options) {
    const model = project(input, options), e = options.escape, t = options.t;
    const label = key => e(t('web.gene_card.' + key));
    const para = (value, cls = '') => value ? `<p${cls ? ` class="${cls}"` : ''}>${e(value)}</p>` : '';
    const link = value => /^https?:\/\/[^\s;]+$/i.test(value || '')
      ? `<a class="cr-source" href="${e(value)}" target="_blank" rel="noopener noreferrer">${e(value)}</a>` : e(value || '');
    const region = model.geneRegion;
    const screen = model.geneScreen;
    const screenState = screen ? screen.scanStatus !== 'ok' || screen.read == null ? 'unknown' : screen.read ? 'checked' : 'limited' : '';
    const screenReasonKeys = {coverage_low:'low',coverage_thin:'low',coverage_not_measured:'not_measured',coverage_gene_not_in_table:'not_in_table',coverage_unavailable:'unavailable'};
    const reasonKey = screen?.why ? screenReasonKeys[screen.why] ? 'web.gene_card.screen_reason.' + screenReasonKeys[screen.why] : 'screen.why.' + screen.why : '';
    const reasonText = reasonKey ? t(reasonKey) : '';
    const screenReason = reasonKey && (reasonText === reasonKey || reasonText.startsWith('⟦')) ? t('web.gene_card.screen_reason_code',{reason:screen?.why}) : reasonText;
    const status = model.statusLabel || (model.referenceOnly ? t('web.gene_card.reference_status') : model.unavailable && !screen ? t('web.gene_card.unread_status') : '');
    const genotype = region ? t(region.status === 'ok' ? 'thematic.region_checked' : 'thematic.region_unavailable') : screen ? t('web.gene_card.screen_state.' + screenState) : model.genotype || '—';
    const zygosity = region ? region.status === 'ok' ? t('thematic.region_counts',{n:region.variants?.total??0,ref:region.variants?.reference_calls?.length??0}) : region.message || region.reason || region.status : screen ? t('web.gene_card.screen_scope') : model.zygosity ? t('finding.zygosity.' + model.zygosity)
      : model.compound && model.genotype ? t('web.gene_card.combination')
      : model.genotype ? t('finding.zygosity.unknown') : !model.isVariant ? t('web.gene_card.no_position')
      : model.referenceOnly ? t('web.gene_card.reference_reading') : t('web.gene_card.not_read');
    const readingKind = region ? 'gene_region' : screen ? 'gene_screen' : model.genotype ? 'called' : !model.isVariant ? 'gene' : model.referenceOnly ? 'reference' : 'unread';
    const copies = model.copies != null ? t('web.gene_card.copies', {n:model.copies}) : '';
    const gene = options.geneHtml || `<strong>${e(model.gene || '—')}</strong>`;
    const level = model.level ? options.grade(model.level, input.level_short) : !model.isVariant ? e(t('science.gene_grade')) : '—';
    const inheritance = model.modes.length ? model.modes.join('; ') : t('web.gene_card.inheritance_unknown');
    const compactKey = 'web.gene_card.meaning.' + model.status;
    const compactMeaning = model.personalMeaning && t(compactKey) !== compactKey ? t(compactKey) : model.personalMeaning;
    const genericSummary = ['not_curated','not_supplied'].includes(model.reference.variant_status)
      && model.summary === model.reference.variant_context;
    const visibleMeaning = unique([genericSummary ? (compactMeaning || !model.isVariant ? '' : t('web.gene_card.variant_unresolved')) : model.summary,
      compactMeaning]).filter(value => value !== model.functionText).map(value => para(value, 'gene-card-personal')).join('');
    const witnesses = list(model.inheritance.assertions).map(a => `<div data-inheritance-witness>${para(a.disease)}${para(a.mode)}${para(a.classification)}${link(a.source || '')}${para(a.date)}</div>`).join('');
    const baseAnnotations = (model.classification ? `<div class="gene-card-db" data-gene-db="ClinVar"><b>ClinVar</b><div>${para(model.classification)}${para(model.condition)}${para(model.review)}${input.stars!=null?para(t('web.gene_card.review_stars',{n:input.stars})):''}${para(input.clinvar_version || input.snapshot)}</div></div>` : '')
      + groupAssertions(model.assertions).map(({claim:a,witnesses:rows}) => `<div class="gene-card-db" data-gene-db="GenCC"><b>GenCC</b><div>${para(a.disease_label || a.disease)}${para([a.classification_label || a.classification,a.moi_label || a.moi_code || a.moi].filter(Boolean).join(' · '))}<details data-gencc-submissions><summary>${e(t('web.gene_card.source_records',{n:rows.length}))}</summary>${rows.map(row=>`<div class="gene-card-witness" data-gencc-witness>${para(row.submitter)}${para(row.curated_on)}${unique([row.source,row.public_report]).filter(Boolean).map(value=>`<p>${link(value)}</p>`).join('')}${row.submission_ids?para(list(row.submission_ids).join(' · ') || text(row.submission_ids)):''}</div>`).join('')}</details></div></div>`).join('')
      + (model.reference.gencc_version ? para(model.reference.gencc_version) : '')
      + (model.reference.gencc_source ? link(model.reference.gencc_source) : '')
      + (/^rs\d+$/.test(model.position) ? `<div class="gene-card-db" data-gene-db="dbSNP"><b>dbSNP</b><div>${link('https://www.ncbi.nlm.nih.gov/snp/' + model.position)}</div></div>` : '');
    const science = list(model.reference.scientific_review).map(review=>`<div class="gene-card-db" data-scientific-scope="${e(review.scope)}" data-scientific-status="${e(review.status)}"><b>${e(review.label)}</b><div>${para(review.summary)}${para(review.database_assertion?.description)}${para(review.limitations)}${list(review.sources).filter(Boolean).map(source=>`<p>${link(source)}</p>`).join('')}${para(review.version)}</div></div>`).join('');
    const annotations = baseAnnotations + science + (options.annotationHtml || '') + (options.detailHtml || '');
    const confidenceKeys={called:'genome.called',confirmed_ref:'genome.confirmed_ref_short',assumed_ref:'web.genome.assumed_ref'};
    const confidenceText=confidenceKeys[model.confidence]?t(confidenceKeys[model.confidence]):'';
    const readingNotes = model.quality.map(q => para(q, 'cr-caption')).join('')
      + (model.depth != null && !model.unavailable ? para(t('web.genome.coverage', {value:model.depth}), 'cr-caption') : '')
      + para(region?.reading_summary?.message, 'cr-caption') + para(model.source, 'cr-caption') + para(model.coordinate, 'cr-caption') + para(model.readingMessage, 'cr-caption');
    const referenceInheritance=!Object.keys(model.context).length?model.assertions.filter(a=>a.moi_label||a.moi_code||a.moi).map(a=>para([a.disease_label||a.disease,a.moi_label||a.moi_code||a.moi,a.classification_label||a.classification].filter(Boolean).join(' · '))).join(''):'';
    const details = `<div class="gene-card-inheritance"><b>${label('inheritance')}</b>${para(inheritance)}${unique([model.inclusionReason,model.personalMeaning,genericSummary?model.summary:'',model.reference.variant_context!==model.summary?model.reference.variant_context:'']).filter(Boolean).map(value=>para(value)).join('')}${para(model.context.scope_note)}${para(model.context.limitations)}${link(model.inheritance.source || '')}${para(model.inheritance.snapshot)}${witnesses}${referenceInheritance?para(t('web.gene_card.gene_inheritance'))+referenceInheritance:''}</div>`
      + `<div class="gene-card-quality"><b>${label('quality')}</b>${readingNotes || para(t('web.gene_card.quality_unknown'))}</div>`
      + (options.extraHtml || '');
    return `<article class="gene-card" ${input.diplotype?'data-called-diplotype ':''}data-gene-card data-gene="${e(model.gene)}" data-position="${e(model.position)}" data-reading-kind="${readingKind}" data-card-kind="${model.compound ? 'combination' : model.isVariant ? 'variant' : 'gene'}">`
      + (status ? `<div class="gene-card-tags"><span class="cr-badge cr-badge--plain" data-personal-status="${e(model.status || 'unread')}">${e(status)}</span></div>` : '')
      + `<div class="gene-card-grid"><div class="gene-card-confidence"><div class="gene-card-label">${label('confidence')}</div>${level}${model.level ? `<div class="cr-caption">${label('variant_scope')}</div>` : ''}</div>`
      + `<div class="gene-card-identity"><div class="gene-card-label">${label('identity')}</div>${gene}${/^rs\d+$/.test(model.position) ? `<p class="cr-caption"><a href="#variant/${e(model.position)}" data-rs-open="${e(model.position)}">${e(model.position)}</a></p>` : para(model.position, 'cr-caption')}${para(model.protein, 'cr-caption')}</div>`
      + `<div class="gene-card-reading"><div class="gene-card-label">${label('reading')}</div><span class="${model.genotype && !screen ? 'gene-card-genotype' : 'gene-card-no-reading'}">${e(genotype)}</span><div class="gene-card-zygosity">${e(zygosity)}</div>${screen ? para(screenReason,'cr-caption') + (screen.scanStatus==='ok' && Number.isInteger(screen.findings) ? para(t('screen.gene_findings',{n:screen.findings}),'cr-caption') : '') : ''}${region?.status==='ok' ? para(t('thematic.region_scope'),'cr-caption') : ''}${para(copies, 'cr-caption')}${para(confidenceText, 'cr-caption')}${model.quality.map(q=>para(q,'cr-caption')).join('')}${model.depth != null && !model.unavailable ? para(t('web.genome.coverage',{value:model.depth}),'cr-caption') : ''}</div>`
      + `<div class="gene-card-description" data-gene-description><div class="gene-card-label">${label('meaning')}</div>${model.functionText ? `<strong class="gene-card-function">${e(model.functionText)}</strong>` : para(t('science.function_missing_compact'))}${visibleMeaning}</div></div>`
      + (annotations ? `<details class="gene-card-fold" data-gene-annotations><summary>${label('annotations')}</summary><div class="gene-card-fold-body">${annotations}</div></details>` : '')
      + `<details class="gene-card-fold" data-gene-inheritance><summary>${label('details')}</summary><div class="gene-card-fold-body">${details}</div></details>`
      + (options.contextHtml ? `<section class="gene-card-context">${options.contextHtml}</section>` : '') + '</article>';
  }

  const api = {project, render, groupAssertions};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.ScholionGeneCards = api;
}(typeof globalThis !== 'undefined' ? globalThis : this));
