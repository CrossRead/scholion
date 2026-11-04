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

  function cardCaveat(value, t) {
    const finding = t('finding.limitations');
    const specific = t('web.gene_card.finding_reading_limit');
    return text(value)
      .replace(finding, specific === 'web.gene_card.finding_reading_limit' ? '' : specific)
      .replace(t('interpretation.notice'), '')
      .replace(t('web.gene_card.literature_caution'), '')
      .replace(t('web.gene_card.diagnosis_caution'), '')
      .replace(t('web.gene_card.gout_caution'), '')
      .trim();
  }

  const geneName = row => text(row.gene || object(row.locus).gene || object(row.reference_context).canonical_symbol);
  function geneLink(gene, references, escape) {
    const plain = `<strong>${escape(gene)}</strong>`;
    const symbols = unique(references.map(r => text(r.canonical_symbol).trim().toUpperCase()));
    const symbol = symbols[0] || gene;
    if (symbols.length > 1 || references.some(r => r.gene_source_scope === 'genomic_annotation' || r.scope === 'catalogue_gene_set')
        || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/i.test(symbol)) return plain;
    const sources = unique(references.map(r => text(r.gene_source).trim().replace(/\/$/, '')));
    const ncbi = sources.filter(source => /^https:\/\/www\.ncbi\.nlm\.nih\.gov\/gene\/[1-9]\d*$/.test(source));
    const hgnc = sources.filter(source => /^https:\/\/(?:www|hgnc)\.genenames\.org\/data\/gene-symbol-report\/#!\/hgnc_id\/HGNC:[1-9]\d*$/.test(source));
    const direct = ncbi.length > 1 || hgnc.length > 1 ? '' : ncbi[0] || hgnc[0];
    const url = direct || 'https://www.ncbi.nlm.nih.gov/gene/?term='
      + encodeURIComponent(symbol + '[PREF] AND 9606[taxid]');
    return `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(gene)}</a>`;
  }
  const geneFunction = row => {
    const reference = object(row.reference_context);
    return reference.function_status === 'not_curated' ? '' : text(reference.gene_role || reference.gene_function || row.function);
  };

  function readingObservations(rows) {
    return list(rows).flatMap(row => [{source:text(object(row.source).file || row.evidence_file),
      genotype:text(row.genotype), depth:object(row.quality).depth ?? row.depth, date:text(row.date),
      selected:object(row.source).record_digest},
      ...readingObservations(row.underlying_observations)]);
  }

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

  /**
   * Normalize the existing API shapes into the card's view model. This is the
   * only place that selects between reading/result/genotype representations.
   * Scientific conclusions, coverage and carriership remain supplied facts.
   * See docs/GENE-CARD.md for the input, model and extension contracts.
   */
  function project(input, options = {}) {
    const p = input || {}, context = object(p.personal_context), reference = object(p.reference_context);
    const reading = Object.keys(object(p.reading)).length ? p.reading
      : Object.keys(object(p.result)).length ? p.result : object(p.genotype);
    const rawRecord = reading.reading_record ?? p.reading_record;
    const record = object(rawRecord);
    const resolved = record.schema === 1;
    const projection = reading.reading_record ? reading : p;
    const observation = record.selected_observation == null ? null
      : list(record.observations).find(row => row && object(row.source).record_digest === record.selected_observation);
    const invalidRecord = rawRecord != null && (!resolved || (record.selected_observation != null && !observation));
    const selected = observation ? {...observation, ...object(observation.quality),
      confidence:record.selected === 'recorded' ? 'reported' : observation.confidence,
      source:object(observation.source).file} : projection;
    const conflict = !!(reading.conflict || p.conflict || record.conflict);
    const projectionDisagrees = !!observation && [projection, p].some(value =>
      (typeof value.genotype === 'string' && value.genotype !== observation.genotype)
      || (value.depth != null && value.depth !== object(observation.quality).depth)
      || (value.read === false && !!observation.genotype));
    const readingBlocked = invalidRecord || projectionDisagrees;
    const interpretationBlocked = conflict || readingBlocked || reading.interpretation_applicable === false
      || p.interpretation_applicable === false || record.interpretation_applicable === false;
    const compound = !!(options.compound || p.epsilon || p.diplotype || p.rs429358 || p.rs7412);
    const position = text(p.rsid || p.hgvs || (p.chrom && p.pos ? p.chrom + ':' + p.pos : ''));
    const isVariant = !!(position || Object.keys(context).length || compound);
    const confidence = resolved ? selected.confidence : reading.confidence || p.confidence;
    const identity = object(observation?.identity);
    const chrom = identity.chrom || p.chrom, pos = identity.pos ?? reading.read_pos ?? p.pos;
    const assembly = identity.assembly || reading.assembly;
    const unavailable = invalidRecord || confidence === 'assumed_ref'
      || (observation ? !observation.genotype
        : p.status === 'no_genome' || p.read === false || reading.read === false || p.presumed === true);
    const genotype = unavailable || !isVariant ? '' : resolved && !compound ? text(selected.genotype) : text(p.display_genotype || p.epsilon || p.diplotype
      || (typeof p.genotype === 'string' ? p.genotype : '') || reading.genotype || context.genotype);
    const state = text(p.state || reading.state || p.zygosity);
    let zygosity = resolved ? '' : text(context.zygosity);
    if (!zygosity && !resolved) zygosity = ({het:'heterozygous',hom:'homozygous',hemi:'haploid',absent:'reference'})[state] || '';
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
    if (unavailable || !isVariant || compound || interpretationBlocked) copies = null;
    const interpretation = object(p.interpretation);
    const research = object(p.personal_meaning);
    const researchUsable = research.scope === "research_context" || (!readingBlocked && !conflict && !unavailable
      && research.reading_binding?.status === "verified" && research.reading_binding.genotype === genotype);
    const researchSummary = researchUsable ? text(research.summary) : "";
    const science = list(reference.scientific_review).find(row => row.scope === 'variant' && row.status !== 'review_stale');
    const study = list(reference.scientific_review).find(row => row.scope === 'study_membership');
    const scientificSummary = text(science?.patient_summary || study?.patient_summary);
    const referenceSummary = !reference.variant_status || reference.variant_status === 'described' ? text(reference.variant_context) : '';
    const suppliedSummary = [interpretation.summary,p.summary,p.text,p.note,p.label,options.fallback].map(text).find(Boolean) || '';
    const summary = researchSummary || scientificSummary || (interpretationBlocked || unavailable ? referenceSummary : suppliedSummary || referenceSummary);
    const selectedInterpretation = !interpretationBlocked && !unavailable
      && summary && summary === text(interpretation.summary);
    const comparisons = [text((researchSummary && research.comparator)
      || (selectedInterpretation && interpretation.study_effect)), text(options.comparisonText),
      interpretationBlocked || unavailable ? '' : text(options.personalComparisonText)];
    const mechanism = text((researchSummary && research.mechanism)
      || (selectedInterpretation && interpretation.mechanism));
    const scientificLimit = science?.status === 'allele_identity_unresolved' && !scientificSummary
      ? text(science.limitations) : '';
    const hasVariantGrade = isVariant && reference.variant_status !== 'not_supplied';
    const level = hasVariantGrade ? text((researchSummary && research.level) || interpretation.level || p.level || reference.level) : '';
    const status = readingBlocked ? '' : text(context.status);
    // `carrier` on catalogue rows means a named allele, not clinical carriage.
    const statusLabel = status && status !== 'classification_only' ? text(context.label) : '';
    const assertions = list(reference.gencc_assertions).length ? reference.gencc_assertions
      : list(p.assertions).length ? p.assertions : list(p.gencc);
    const modes = unique([text(context.inheritance_label), ...(!Object.keys(context).length
      ? [text(p.inheritance), text(p.moi), ...list(p.moi_codes)] : [])]);
    const readingNote = reading.note || (resolved ? projection.note : '') || (reading.read === true && genotype ? '' : reading.message);
    const quality = unique([text(readingNote), text(p.depth_note), text(p.read_why_text),
      text(p.reading_note), text(p.file_says_text), text(p.read_why_text ? '' : p.read_why), text(p.verdict_label)]);
    const qualityReading = resolved || !Object.keys(reading).length ? selected : reading;
    const flags = {...object(qualityReading.quality), ...qualityReading};
    const qualityKeys = unique(Object.entries({low_depth:'genlab.quality.low_depth',
      filtered:'genlab.quality.filtered', imputed:'genlab.quality.imputed',
      unverified_locus:'genlab.quality.locus', needs_confirmation:'genlab.quality.confirmation',
      strand_ambiguous:'genlab.quality.confirmation', depth_unverified:'genome.depth_unverified'})
      .filter(([key]) => (resolved || key === 'low_depth') && flags[key] === true).map(([,key]) => key));
    return {gene:geneName(p), position, compound, genotype, zygosity, copies,
      geneScreen:!isVariant && options.geneScreen ? object(options.geneScreen) : null,
      geneRegion:!isVariant && options.geneRegion ? object(options.geneRegion) : null,
      unavailable, isVariant, referenceOnly:options.referenceOnly === true,
      level, status, statusLabel, functionText:geneFunction(p),
      summary, comparisons, mechanism, research:researchSummary ? research : {}, scientificLimit, interpretationSummary:text(interpretation.summary), physicalGene:text(science?.physical_gene),
      contextTexts:interpretationBlocked || unavailable ? [] : list(options.contextTexts).map(text),
      limitationTexts:list(options.limitationTexts).map(text),
      assessment:text(options.assessment),
      inclusionReason:text(context.inclusion_reason), personalMeaning:interpretationBlocked || unavailable ? '' : text(context.summary),
      clinvarPhenotype:object(p.clinvar_phenotype),
      classification:text(p.clnsig || p.classification || (typeof p.clinvar === 'string' ? p.clinvar : (object(p.clinvar).classification || object(p.clinvar).clinical_significance))),
      condition:text(p.disease || p.phenotype || p.clndn || reference.disease_context?.name),
      assertions, modes, quality, qualityKeys, depth:invalidRecord ? null : resolved ? selected.depth : reading.depth ?? p.depth,
      source:invalidRecord ? '' : resolved ? text(selected.from_profile || object(selected.source_identity).file || selected.source)
        : text(reading.source || p.reading_source),
      conflict, interpretationBlocked, observations:readingObservations(resolved ? record.observations : []),
      selectedObservation:record.selected_observation,
      noEffectSource:isVariant && reference.variant_status === 'not_curated',
      readingFailure:!genotype ? text(reading.note || reading.message || p.message) : '',
      compoundReadings:compound?list(options.compoundReadings):[], compoundLabel:text(options.compoundLabel),
      referencePresumed:confidence === 'assumed_ref' && (reading.reference_presumed || p.presumed === true),
      fromBam:reading.source === 'bam' || p.source === 'bam',
      confidence, review:text(p.review_confidence || p.review), reviewCode:text(p.review),
      coordinate:chrom && pos ? [text(assembly), text(chrom) + ':' + text(pos)].filter(Boolean).join(' ') : '',
      protein:text(p.protein || p.star), readingMessage:text(p.reading_label),
      inheritance:object(context.inheritance), context, reference, annotation:object(reference.catalogue_annotation),
      levelShort:p.level_short, stars:p.stars, snapshot:p.clinvar_version || p.snapshot,
      calledDiplotype:!!p.diplotype};
  }

  function renderCard(input, options) {
    return renderModel(project(input, options), options);
  }

  function renderRegionDetails({regionDetails, t, escape: e}) {
    if (!regionDetails) return '';
    const {lazyGene, bodyHtml, actionsHtml, note} = regionDetails;
    const caption = note ? `<p class="cr-caption">${e(note)}</p>` : '';
    const readingLabel = e(t('web.gene_card.reading'));
    if (!lazyGene && !bodyHtml) return `<div class="gene-card-fold gene-card-region" data-gene-region-reading><div class="gene-card-label">${readingLabel}</div>${caption}${actionsHtml || ''}</div>`;
    return `<details class="gene-card-fold gene-card-region" data-gene-region-reading${lazyGene ? ` data-panel-region="${e(lazyGene)}"` : ''}><summary>${readingLabel} · ${e(t('thematic.region_details'))}</summary><div class="gene-card-fold-body">${caption}${lazyGene ? '<div data-panel-region-body></div>' : bodyHtml}${actionsHtml || ''}</div></details>`;
  }

  /** Render only the normalized model; never inspect an API payload here. */
  function renderModel(model, options) {
    const e = options.escape, t = options.t;
    const label = key => e(t('web.gene_card.' + key));
    const para = (value, cls = '') => value ? `<p${cls ? ` class="${cls}"` : ''}>${e(value)}</p>` : '';
    const link = value => /^https?:\/\/[^\s;]+$/i.test(value || '')
      ? `<a class="cr-source" href="${e(value)}" target="_blank" rel="noopener noreferrer">${e(value)}</a>` : e(value || '');
    const region = model.geneRegion;
    const location = object(region?.location);
    const interval = location.chrom && location.start && location.end
      ? [location.assembly, `${location.chrom}:${location.start}–${location.end}`].filter(Boolean).join(' · ') : '';
    const identityLabel = region ? e(t('thematic.region_reading')) : label(options.positionOnly ? 'position' : 'identity');
    const screen = model.geneScreen;
    const screenState = screen ? screen.scanStatus !== 'ok' || screen.read == null ? 'unknown' : screen.read ? 'checked' : 'limited' : '';
    const screenReasonKeys = {coverage_low:'low',coverage_thin:'low',coverage_not_measured:'not_measured',coverage_gene_not_in_table:'not_in_table',coverage_unavailable:'unavailable'};
    const reasonKey = screen?.why ? screenReasonKeys[screen.why] ? 'web.gene_card.screen_reason.' + screenReasonKeys[screen.why] : 'screen.why.' + screen.why : '';
    const reasonText = reasonKey ? t(reasonKey) : '';
    const screenReason = reasonKey && (reasonText === reasonKey || reasonText.startsWith('⟦')) ? t('web.gene_card.screen_reason_code',{reason:screen?.why}) : reasonText;
    const status = model.statusLabel || (model.referenceOnly ? t('web.gene_card.reference_status') : model.unavailable && !screen ? t('web.gene_card.unread_status') : '');
    const regionSummary = object(region?.reading_summary);
    const genotype = region ? t(region.status === 'ok' ? 'thematic.region_checked' : 'thematic.region_unavailable') : screen ? t('web.gene_card.screen_state.' + screenState) : model.referencePresumed ? t('genome.reference_presumed') : model.genotype || model.assessment || '—';
    const zygosity = region ? region.status === 'ok' ? regionSummary.vcf_message || t('thematic.region_counts',{n:region.variants?.total??0,ref:region.variants?.reference_calls?.length??0}) : region.message || region.reason || region.status : screen ? t('web.gene_card.screen_scope') : model.zygosity ? t('finding.zygosity.' + model.zygosity)
      : model.compound && model.compoundLabel ? model.compoundLabel
      : model.compound && model.genotype ? t('web.gene_card.combination')
      : model.genotype ? t('finding.zygosity.unknown') : model.assessment ? '' : model.referenceOnly ? t('web.gene_card.reference_reading')
      : !model.isVariant ? t('web.gene_card.no_personal_reading') : t('web.gene_card.not_read');
    const compoundReadings = model.compoundReadings.map(({position,genotype})=>para(`${position}: ${genotype||'—'}`,'cr-caption')).join('');
    const readingKind = region ? 'gene_region' : screen ? 'gene_screen' : model.genotype ? 'called' : !model.isVariant ? 'gene' : model.referenceOnly ? 'reference' : 'unread';
    const copies = model.copies != null ? t('web.gene_card.copies', {n:model.copies}) : '';
    const gene = model.gene ? geneLink(model.gene, [model.reference], e)
      : `<strong>${e(model.classification ? t('web.gene_card.gene_unassigned') : '—')}</strong>`;
    const functionShownAbove = !!model.functionText && model.functionText === options.functionAbove;
    const level = model.level ? options.grade(model.level, model.levelShort) : !model.isVariant ? e(t('science.gene_grade')) : '—';
    const inheritance = model.modes.length ? model.modes.join('; ')
      : model.isVariant ? t('web.gene_card.inheritance_unknown') : '';
    const compactKey = 'web.gene_card.meaning.' + model.status;
    const translatedMeaning = t(compactKey);
    const compactMeaning = model.personalMeaning && translatedMeaning !== compactKey && !translatedMeaning.startsWith('⟦')
      ? translatedMeaning : model.personalMeaning;
    const annotation = model.annotation;
    const shown = new Set([model.functionText]);
    const paragraphs = values => unique(values.map(value=>cardCaveat(value,t))).filter(value => {
      if (shown.has(value) || (value !== model.summary && model.summary.includes(value))) return false;
      shown.add(value);
      return true;
    }).map(value => para(value, 'gene-card-personal')).join('');
    const visibleMeaning = paragraphs([model.summary, annotation.claim, model.clinvarPhenotype?.description,
      ...model.comparisons, model.mechanism, compactMeaning, ...list(model.research?.context).map(c=>text(c.comparison)), ...model.contextTexts]);
    const researchLimit = model.research?.limitations_scope === 'genome' ? '' : model.research?.limitations;
    const limitations = paragraphs([researchLimit, model.scientificLimit, ...model.limitationTexts, model.readingFailure,
      model.noEffectSource && !model.summary && !compactMeaning ? t('web.gene_card.no_effect_source') : '']);
    const contextual = options.contextHtml ? `<section class="gene-card-context">${options.contextHtml}</section>` : '';
    const translated = (key, fallback) => {
      const value = t(key);
      return value === key || value.startsWith('⟦') ? fallback : value;
    };
    const classification = model.classification ? translated('clinvar.sig.' + normal(model.classification).replace(/[\s-]+/g,'_'), model.classification) : '';
    const condition = model.clinvarPhenotype?.phenotype || model.condition;
    const review = model.reviewCode ? translated('insight.database.' + model.reviewCode.replace(/,+/g,''), model.review) : model.review;
    const clinvarSummary = classification && (model.stars === 0 || !model.functionText || model.clinvarPhenotype?.phenotype)
      ? para([`ClinVar: ${classification}`,condition,model.stars!=null?t('web.gene_card.review_stars',{n:model.stars}):''].filter(Boolean).join(' · '), 'cr-caption') : '';
    const witnesses = list(model.inheritance.assertions).map(a => `<div data-inheritance-witness>${para(a.disease)}${para(a.mode)}${para(a.classification)}${link(a.source || '')}${para(a.date)}</div>`).join('');
    const baseAnnotations = (classification ? `<div class="gene-card-db" data-gene-db="ClinVar"><b>ClinVar</b><div>${para(classification)}${para(condition)}${para(review)}${model.stars!=null?para(t('web.gene_card.review_stars',{n:model.stars})):''}${para(model.snapshot)}${link(model.clinvarPhenotype?.source)}${link(model.clinvarPhenotype?.study)}</div></div>` : '')
      + groupAssertions(model.assertions).map(({claim:a,witnesses:rows}) => `<div class="gene-card-db" data-gene-db="GenCC"><b>GenCC</b><div>${para(a.disease_label || a.disease)}${para([a.classification_label || a.classification,a.moi_label || a.moi_code || a.moi].filter(Boolean).join(' · '))}<details data-gencc-submissions><summary>${e(t('web.gene_card.source_records',{n:rows.length}))}</summary>${rows.map(row=>`<div class="gene-card-witness" data-gencc-witness>${para(row.submitter)}${para(row.curated_on)}${unique([row.source,row.public_report]).filter(Boolean).map(value=>`<p>${link(value)}</p>`).join('')}${row.submission_ids?para(list(row.submission_ids).join(' · ') || text(row.submission_ids)):''}</div>`).join('')}</details></div></div>`).join('')
      + (model.reference.gencc_version ? para(model.reference.gencc_version) : '')
      + (model.reference.gencc_source ? link(model.reference.gencc_source) : '')
      + (/^rs\d+$/.test(model.position) ? `<div class="gene-card-db" data-gene-db="dbSNP"><b>dbSNP</b><div>${link('https://www.ncbi.nlm.nih.gov/snp/' + model.position)}</div></div>` : '');
    const sourceDetails = review => list(review.source_details).map(source => {
      const name = /^https:\/\/[^\s]+$/.test(source.url || '') ? `<a class="cr-source" href="${e(source.url)}" target="_blank" rel="noopener noreferrer">${e(source.name)}</a>` : e(source.name);
      const checked = source.checked_on ? para(t('science.source_checked',{date:source.checked_on}),'cr-caption') : '';
      const refresh = ['due','date_unknown'].includes(source.refresh_status)
        ? `<details data-source-refresh><summary>${e(t('science.source_' + source.refresh_status))}</summary>${para(t('science.source_refresh_steps'))}</details>` : '';
      return `<div data-gene-source>${name}${para(source.citation,'cr-caption')}${checked}${refresh}</div>`;
    }).join('');
    const researchSources = sourceDetails(model.research || {}) || list(model.research?.sources).map(source=>`<p>${link(source)}</p>`).join('');
    const science = researchSources + list(model.reference.scientific_review).map(review=>`<div class="gene-card-db" data-scientific-scope="${e(review.scope)}" data-scientific-status="${e(review.status)}"><b>${e(review.label)}</b><div>${para(review.summary)}${para(review.curation_notice,'cr-caption')}${para(review.database_assertion?.description)}${para(cardCaveat(review.limitations,t))}${sourceDetails(review) || list(review.sources).filter(Boolean).map(source=>`<p>${link(source)}</p>`).join('')}${para(review.version)}</div></div>`).join('');
    const annotationSources = annotation.title ? `<div class="gene-card-db" data-catalogue-sources>
      <b>${e(annotation.title)}</b><div>${annotation.stars ? para(t('web.gene_card.review_stars',{n:annotation.stars})) : ''}
      ${para(t('science.source_checked',{date:annotation.checked_on}),'cr-caption')}
      ${list(annotation.sources).map(source=>`<div>${link(source)}</div>`).join('')}</div></div>` : '';
    const annotations = baseAnnotations + annotationSources + science + (options.annotationHtml || '') + (options.detailHtml || '');
    const confidenceKeys={called:'genome.called',confirmed_ref:'genome.confirmed_ref_short',assumed_ref:'web.genome.assumed_ref'};
    const confidenceText=model.fromBam && model.genotype ? t('genome.bam_check.called')
      : confidenceKeys[model.confidence] ? t(confidenceKeys[model.confidence]) : '';
    const quality = unique([...model.quality, ...model.qualityKeys.map(key=>t(key))]);
    const lowDepth = model.qualityKeys.includes('genlab.quality.low_depth');
    const showDepth = model.depth != null && (!model.unavailable || model.confidence === 'no_call_in_vcf');
    const depthLine = showDepth ? t(lowDepth ? 'web.gene_card.low_depth' : 'web.gene_card.depth', {value:model.depth})
      : lowDepth ? t('genlab.quality.low_depth') : '';
    // Keep the original note in the disclosure. A VCF note can also include
    // independent information, so remove only its duplicate depth fragment.
    const visibleQuality = lowDepth ? unique(quality.map(note => {
      if (note === t('genlab.quality.low_depth')) return '';
      if (model.depth == null) return note;
      return note.replace(t('genome.low_depth_suffix', {depth:model.depth}), '')
        .replace(t('genome.low_depth', {depth:model.depth}), '').trim();
    })) : quality;
    const readingWarning = model.conflict ? t('genome.source_conflict')
      : model.interpretationBlocked && model.research?.scope !== 'genotype_hypothesis'
        ? t('web.gene_card.interpretation_blocked') : '';
    const warning = readingWarning && !visibleQuality.some(q => q.includes(readingWarning))
      ? para(readingWarning, 'cr-caption') : '';
    const observations = model.observations.length ? `<details data-reading-observations><summary>${label('observations')}</summary>${model.observations.map(row =>
      `<div data-reading-observation>${para(row.source)}${para(row.genotype || t('web.gene_card.not_read'))}${row.depth != null && (!showDepth || row.selected !== model.selectedObservation) ? para(t('web.genome.coverage',{value:row.depth}),'cr-caption') : ''}${para(row.date,'cr-caption')}</div>`).join('')}</details>` : '';
    const readingNotes = para(model.source, 'cr-caption') + para(model.coordinate, 'cr-caption') + para(model.readingMessage, 'cr-caption');
    const readingDetails = readingNotes || observations
      ? `<details class="gene-card-reading-details" data-reading-details><summary>${label('reading_details')}</summary>${readingNotes}${observations}</details>` : '';
    const repeat = options.showRepeat !== false && model.reference.separate_repeat ? para(t('web.gene_card.separate_repeat'), 'cr-caption') : '';
    const attribution = model.physicalGene && model.physicalGene !== model.gene
      ? para(t('web.gene_card.related_gene',{gene:model.physicalGene,related:model.gene}), 'cr-caption') : '';
    const role = functionShownAbove ? '' : model.functionText ? `<strong class="gene-card-function">${e(model.functionText)}</strong>` : para(t('science.function_missing_compact'), 'gene-card-function');
    const referenceInheritance=!Object.keys(model.context).length?model.assertions.filter(a=>a.moi_label||a.moi_code||a.moi).map(a=>para([a.disease_label||a.disease,a.moi_label||a.moi_code||a.moi,a.classification_label||a.classification].filter(Boolean).join(' · '))).join(''):'';
    const details = `<div class="gene-card-inheritance">${list(annotation.details).map(value=>para(value)).join('')}${inheritance || referenceInheritance ? `<b>${label('inheritance')}</b>` : ''}${para(inheritance)}${para(model.reference.gene_role_detail || (model.reference.gene_role && model.reference.gene_function!==model.functionText ? model.reference.gene_function : ''))}${unique([model.inclusionReason,model.personalMeaning,model.interpretationBlocked ? '' : model.interpretationSummary,model.reference.variant_context]).filter(value=>value!==model.summary).map(value=>para(cardCaveat(value,t))).join('')}${para(model.context.scope_note)}${para(cardCaveat(model.context.limitations,t))}${link(model.inheritance.source || '')}${para(model.inheritance.snapshot)}${witnesses}${referenceInheritance?para(t('web.gene_card.gene_inheritance'))+referenceInheritance:''}</div>`
      + (options.extraHtml || '');
    return `<article class="gene-card" ${model.calledDiplotype?'data-called-diplotype ':''}data-gene-card data-gene="${e(model.gene)}" data-position="${e(model.position)}" data-reading-kind="${readingKind}" data-card-kind="${model.compound ? 'combination' : model.isVariant ? 'variant' : 'gene'}">`
      + (options.positionOnly ? '' : `<div class="gene-card-name">${gene}</div>`)
      + role
      + (visibleMeaning || limitations || clinvarSummary ? `<div class="gene-card-description" data-gene-description${annotation.claim?' data-catalogue-annotation':''}><div class="gene-card-label">${e(t('meaning.personal'))}</div>${visibleMeaning}${contextual}${limitations}${clinvarSummary}</div>` : contextual)
      + (status ? `<div class="gene-card-tags"><span class="cr-badge cr-badge--plain" data-personal-status="${e(model.status || 'unread')}">${e(status)}</span></div>` : '')
      + `<div class="gene-card-grid"><div class="gene-card-confidence"><div class="gene-card-label">${label('confidence')}</div>${level}${model.level ? `<div class="cr-caption">${label('variant_scope')}</div>` : ''}</div>`
      + `<div class="gene-card-identity"><div class="gene-card-label">${identityLabel}</div>${attribution}${para(interval, 'cr-caption')}${annotation.title ? para(`GRCh38 · ${annotation.chrom}:${annotation.pos} ${annotation.ref}>${annotation.alt}`,'cr-caption') : ''}${/^rs\d+$/.test(model.position) ? `<p class="cr-caption"><a href="#variant/${e(model.position)}" data-rs-open="${e(model.position)}">${e(model.position)}</a></p>` : para(model.position, 'cr-caption')}${para(model.protein, 'cr-caption')}</div>`
      + `<div class="gene-card-reading"><div class="gene-card-label">${label('reading')}</div><span class="${model.genotype && !screen ? 'gene-card-genotype' : 'gene-card-no-reading'}">${e(genotype)}</span>${zygosity ? `<div class="gene-card-zygosity">${e(zygosity)}</div>` : ''}${compoundReadings}${options.readingHtml || ''}${screen ? para(screenReason,'cr-caption') + (screen.scanStatus==='ok' && Number.isInteger(screen.findings) ? para(t('screen.gene_findings',{n:screen.findings}),'cr-caption') : '') : ''}${region?.status==='ok' ? para(regionSummary.coverage_message || t('thematic.region_scope'),'cr-caption') : ''}${para(copies, 'cr-caption')}${para(confidenceText, 'cr-caption')}${warning}${para(depthLine,'cr-caption')}${visibleQuality.filter(q=>q!==model.readingFailure).map(q=>para(q,'cr-caption')).join('')}${repeat}${readingDetails}</div>`
      + '</div>'
      + (annotations ? `<details class="gene-card-fold" data-gene-annotations><summary>${label('annotations')}</summary><div class="gene-card-fold-body">${annotations}</div></details>` : '')
      + `<details class="gene-card-fold" data-gene-inheritance><summary>${label('details')}</summary><div class="gene-card-fold-body">${details}</div></details>`
      + renderRegionDetails(options) + '</article>';
  }

  /**
   * Bind application presentation services once. Callbacks stay live when the
   * language or register changes. The component performs no IO and owns no
   * profile state; callers supply already-guarded results on every render.
   *
   * Slots (annotationHtml, detailHtml, extraHtml, contextHtml, readingHtml, regionDetails) accept
   * trusted, escaped application markup only. They never alter the base model.
   */
  function create({t, escape:esc, grade:levelChip, formatDate:fmtDate,
    register:getRegister, passport:passportHtml, authorNote:authorNoteHtml,
    clinicalBasis:clinicalBasisHTML}) {
function referenceContextHtml(p,cardDetails=false){
  const c=p.reference_context;
  if(!c) return '';
  const caveat=value=>cardDetails?ScholionGeneCards.cardCaveat(value,t):value;
  return `<div class="why" data-reference-context>${cardDetails||c.function_status==='not_curated'?'':`<div><strong>${esc(c.gene_function)}</strong></div>`}`
    +`${cardDetails?'':`<div>${esc(t('reference.variant',{text:c.variant_context}))}</div>`}`
    +`${c.canonical_symbol&&p.gene&&c.canonical_symbol.toUpperCase()!==p.gene.toUpperCase()?`<p class="cr-caption">${esc(t('reference.resolved_gene',{gene:c.canonical_symbol}))}</p>`:''}`
    +`${c.gene_source&&!(cardDetails&&c.scientific_review?.length)?`<div class="why muted">${esc(t(c.gene_source_scope==='genomic_annotation'?'reference.region_source':'reference.gene_source',{source:c.gene_source}))}</div>`:''}`
    +`${(c.gene_additional_sources||[]).filter(u=>/^https:\/\//.test(u)).map(u=>`<div class="why muted"><a href="${esc(u)}" target="_blank" rel="noopener">${esc(t('genlab.source'))}</a></div>`).join('')}`
    +`${c.reference_identity?`<details class="fold"><summary>${esc(c.reference_identity.rsid)} · ${esc(c.reference_identity.variant_class)}</summary><p>${esc(c.reading_limit)}</p>${Object.entries(c.reference_identity.builds).map(([build,v])=>`<p class="cr-caption">${esc(t('reference.spdi',{build,accession:v.accession,start:v.position_zero_based,ref:v.reference,alt:v.alternatives.join('/')}))}</p>`).join('')}<a class="cr-source" href="${esc(c.reference_identity.source)}" target="_blank" rel="noopener">${esc(t('genlab.source'))}</a></details>`:''}`
    +`${c.variant_source&&!(cardDetails&&c.scientific_review?.some(row=>['variant','literature_direction','study_membership'].includes(row.scope)&&row.sources?.length))?`<div class="why muted">${esc(t('reference.variant_source',{source:c.variant_source}))}</div>`:''}`
    +`${(c.mechanistic_hypotheses||[]).length?`<details class="fold" data-mechanistic-hypotheses><summary>${esc(t('genlab.reference_patterns'))}</summary>${c.mechanistic_hypotheses.map(h=>`<p>${levelChip(h.association_level)} ${h.level_scope==='mechanism_reference_not_personal_variant'?esc(t('genlab.mechanism_level')):''}</p><p>${esc(h.summary)}</p><p class="meta">${esc(caveat(h.limitations))}</p><p>${(h.source_links||[]).filter(u=>/^https:\/\//.test(u)).map((u,i)=>`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t('genlab.source'))} ${i+1}</a>`).join(' · ')}</p>`).join('')}</details>`:''}`
    +`${c.disease_context?`<p><strong>${esc(c.disease_context.label)}</strong>: ${esc(c.disease_context.name)}</p><p class="cr-caption">${esc(caveat(c.disease_context.limitations))}</p><p><a class="cr-source" href="${esc(c.disease_context.source)}" target="_blank" rel="noopener">${esc(t('genlab.source'))}</a></p>`:''}`
    +`${c.limitations?`<div class="why muted">${esc(caveat(c.limitations))}</div>`:''}`
    +`${c.clinical_review?`<p class="cr-caption">${esc(caveat(c.clinical_review.limitations))}</p>`:''}`
    +`${(cardDetails?[]:c.gencc_assertions||[]).map(a=>`<div class="why" data-gencc-assertion>${esc(t('gencc.assertion',{disease:a.disease_label,classification:a.classification_label,moi:a.moi_label,submitter:a.submitter||'—',date:a.curated_on||'—'}))}</div>`).join('')}`
    +`${c.gencc_status==='no_assertions_in_snapshot'?`<div class="why muted">${esc(t('reference.gencc_not_in_snapshot',{version:c.gencc_version||'—'}))}</div>`:''}`
    +`${!cardDetails&&c.gencc_assertions?.length?`<div class="why muted">${esc(t('gencc.source',{version:c.gencc_version||'—',source:c.gencc_source}))}</div>`:''}`
    +`${c.function_status==='not_curated'?`<p class="cr-caption">${esc(c.gene_function)}</p>`:''}`
    +`<p class="cr-caption">${esc(c.variant_status==='not_supplied'?t('reference.gene_level'):t('reference.level',{level:c.level||'—'}))}</p></div>`;
}
function mechanismHtml(p,cardDetails=false){
  const assertion=p.interpretation?.database_assertion;
  const identity=(assertion?.description?`<p class="cr-caption">${esc(assertion.description)}</p>`:'')+(p.transcript?`<p class="cr-caption">${esc(p.transcript)} · ${esc(p.hgvs||'')}</p>`:'');
  const reference=identity+referenceContextHtml(p,cardDetails);
  const r=p.decision_route,workflow=r?`<div class="why muted" data-decision-route="${esc(r.kind)}">${esc(t('genome.route.line',{label:r.label,reason:r.reason}))}<div>${esc(r.notice)}</div></div>`:'';
  const fields=b=>b.missing?.length?t('web.gene_card.support_missing_fields',{missing:b.missing.map(k=>t('conclusion.missing.'+k)).join(', ')}):b.reason||'';
  const main=p.conclusion_basis?.status==='incomplete'?`<div data-conclusion-withheld><dt>${esc(t('web.gene_card.personal_conclusion'))}</dt><dd>${esc(fields(p.conclusion_basis))}</dd></div>`:'';
  const sub=Object.entries(p.subclaim_basis||{}).map(([name,b])=>`<div data-subclaim-basis><dt>${esc(t('conclusion.subclaim.'+name))}</dt><dd>${esc(b.status==='incomplete'?fields(b):b.mechanism+' — '+b.source)}</dd></div>`).join('');
  let clinical=(main||sub?`<div class="gene-support"><p>${esc(t('web.gene_card.support_scope'))}</p><dl class="gene-support-fields">${main}${sub}</dl>${main?`<p>${esc(t('web.gene_card.reference_separate'))}</p>`:''}</div>`:'')+workflow;
  if(!main&&p.mechanism&&p.source&&!reference) clinical=`<div class="why" data-mechanism>${esc(t('system.row.mechanism',{text:p.mechanism}))}</div>`
    +`<div class="why muted">${esc(t('decision.source',{source:p.source}))}</div>`+clinical;
  return reference+(reference&&clinical?`<details data-clinical-checks><summary>${esc(t('reference.analytics'))}</summary>${clinical}</details>`:clinical);
}

function geneticPreviewHtml(p,fallback=''){
  const c=p.reference_context, i=p.interpretation;
  const sentence=p.personal_meaning ? ScholionGeneCards.project(p,{fallback}).summary
    : (typeof i?.summary==='string'&&i.summary?i.summary:(p.text||p.passport?.reported||c?.variant_context||fallback||''));
  const parts=[...new Set([c?.function_status==='not_curated'?null:c?.gene_function,sentence].filter(Boolean))];
  return `<span class="gen-context-preview">${parts.map((x,j)=>j===0&&(c?.function_status!=='not_curated'||i?.summary||p.text)?`<strong>${esc(x)}</strong>`:`<span>${esc(x)}</span>`).join(' ')}</span>`;
}
function geneticBriefHtml(p,register='patient',fallback='',detailOnly=false,readingHtml='',cardDetails=false){
  const i=p.interpretation;
  const model=ScholionGeneCards.project(p,{fallback}),research=model.research;
  const notice=cardDetails?ScholionGeneCards.cardCaveat(i?.notice,t):i?.notice||t('interpretation.notice');
  const catalogueGaps=(i?.missing||[]).filter(k=>!(p.conclusion_basis?.status==='incomplete'&&p.conclusion_basis.missing?.includes(k)));
  const interpretation=typeof i?.summary==='string'&&i.summary?`<div data-catalogue-interpretation>${cardDetails?'':esc(i.summary)}${i.mechanism&&(!cardDetails||(!model.interpretationBlocked&&model.mechanism!==i.mechanism))&&!i.summary.includes(i.mechanism)&&!p.reference_context?.variant_context?.includes(i.mechanism)?`<div class="why">${esc(t('system.row.mechanism',{text:i.mechanism}))}</div>`:''}${notice?`<div class="why muted">${esc(notice)}</div>`: ''}${['evidence_reason','population','study_effect','reading_note'].map(k=>i[k]&&!(cardDetails&&k==='study_effect'&&(model.interpretationBlocked||model.comparisons.includes(i[k])))?`<p class="cr-caption">${esc(i[k])}</p>`:'').join('')}${i.source?`<div class="why muted">${esc(t('decision.source',{source:i.source}))}</div>`:''}${catalogueGaps.length?`<div class="why muted" data-catalogue-support>${esc(t('web.gene_card.catalogue_gaps',{missing:catalogueGaps.map(k=>t('conclusion.missing.'+k)).join(', ')}))}</div>`:''}</div>`:'';
  const text=!p.reference_context&&!interpretation&&(p.text||fallback)?`<div>${esc(p.text||fallback)}</div>`:'';
  const researchDetails=research?.summary?`<div data-research-meaning>${[...(cardDetails?[]:[research.summary,research.comparator,research.mechanism,...(research.context||[]).map(c=>c.comparison),research.limitations]),research.study_scope].filter(Boolean).map(value=>`<p>${esc(value)}</p>`).join('')}</div>`:'';
  const body=`<div class="gen-context-body">${researchDetails||interpretation}${text}${mechanismHtml(p,cardDetails)}${p.passport?passportHtml(p,register,!!i?.summary):''}${authorNoteHtml(p,register)}${clinicalBasisHTML(p,true)}</div>`;
  const c=p.reference_context, level=research?.level||i?.level||(c?.variant_status==='not_supplied'?null:(p.level||c?.level));
  return detailOnly?body:`<div class="gen-description" data-gene-description>${geneticPreviewHtml(p,fallback)}${readingHtml}
    ${level?`<div class="gen-evidence">${esc(t('web.gen.evidence_link'))} ${levelChip(level)}</div>`:''}
    <details class="gen-context" data-genetic-context><summary>${esc(t('web.gen.context_details'))}</summary>${body}</details></div>`;
}
function geneDisplayCard(p,options={}){
  const register=options.register||getRegister();
  return renderCard(p,{t,escape:esc,grade:levelChip,
    detailHtml:geneticBriefHtml(p,register,options.fallback||'',true,'',true),...options});
}
function genePositionCards(rows,options={}){
  const distinct=[...new Map(rows.map(row=>[JSON.stringify(canonical(row)),row])).values()];
  const card=(row,positionOnly,functionAbove,regionDetails,showRepeat)=>geneDisplayCard(row,{...options,
    ...options.rowOptions?.(row),positionOnly,functionAbove,regionDetails,showRepeat,
    ...(options.includeReferenceExtras?{extraHtml:geneReferenceExtras(row)}:{})});
  const groups=new Map();
  distinct.forEach((row,index)=>{
    const gene=geneName(row);
    const key=gene||index;
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(row);
  });
  return [...groups].map(([gene,positions])=>{
    if(positions.length===1)return card(positions[0],false,options.functionAbove,options.regionDetails);
    const functions=positions.map(geneFunction);
    const shared=functions.every(value=>value===functions[0])?functions[0]:'';
    const name=`<div class="gene-position-name">${geneLink(gene,positions.map(row=>object(row.reference_context)),esc)}</div>`;
    const heading=shared&&shared!==options.functionAbove?`<strong class="gene-card-function">${esc(shared)}</strong>`:'';
    return `<div class="gene-position-list" data-gene-positions="${esc(gene)}">${name}${heading}${positions.map((row,index)=>card(row,true,shared||options.functionAbove,null,index===0)).join('')}${renderRegionDetails({regionDetails:options.regionDetails,t,escape:esc})}</div>`;
  }).join('');
}
function geneRegionRows(rows,positions=[],assembly){
  const chrom=value=>text(value).replace(/^chr/i,'').toUpperCase();
  const key=(c,pos,ref,gt,depth,alleles)=>JSON.stringify([chrom(c),pos,ref,gt,depth??null,alleles]);
  const selected=new Set(positions.flatMap(row=>{
    const r=row.reading||row.result||{}, at=r.variant_identity;
    const alleles=text(r.genotype).replace(/[/|]/g,'');
    return r.source==='vcf'&&!r.conflict&&r.raw_genotype&&at?.chrom&&at.pos!=null
      &&assembly&&at.assembly===assembly&&/^[ACGT]{1,2}$/.test(alleles)
      ? [key(at.chrom,at.pos,at.ref,r.raw_genotype,r.depth,alleles)] : [];
  }));
  const records=new Map();
  for(const row of rows){
    const alleles=list(row.personal_alleles);
    if(alleles.every(base=>/^[ACGT]$/.test(base))
      &&selected.has(key(row.chrom,row.pos,row.ref,row.genotype,row.depth,alleles.join(''))))continue;
    const position=row.chrom&&row.pos!=null?`${row.chrom}:${row.pos}`:'—';
    const rsid=text(row.rsid), call=alleles.join(row.genotype?.includes('|')?'|':'/')||text(row.genotype);
    const protein=text(row.protein?.hgvs_p||row.protein?.kind);
    const id=JSON.stringify([position,rsid,call,row.depth,row.genotype_quality,protein]);
    records.set(id,{position,rsid,call,depth:row.depth,quality:row.genotype_quality,protein});
  }
  if(!records.size)return `<p>${esc(t('web.gene_card.region_no_calls'))}</p>`;
  const showProtein=[...records.values()].some(row=>row.protein);
  const columns=['position','region_genotype','region_depth','region_gq'].map(key=>t('web.gene_card.'+key));
  if(showProtein)columns.push(t('gene.protein_annotation'));
  return `<div class="gene-region-table"${records.size>8?` tabindex="0" role="region" aria-label="${esc(t('web.gene_card.reading'))}"`:""}><table class="cr-table cr-table--compact" data-gene-region-records><thead><tr>${columns.map(label=>`<th scope="col">${esc(label)}</th>`).join('')}</tr></thead><tbody>${[...records.values()].map(row=>
    `<tr><th scope="row">${esc(row.position)}${row.rsid?`<br>${esc(row.rsid)}`:''}</th><td>${esc(row.call||'—')}</td><td>${row.depth==null?'—':esc(row.depth)+'×'}</td><td>${esc(row.quality??'—')}</td>${showProtein?`<td>${esc(row.protein||'—')}</td>`:''}</tr>`).join('')}</tbody></table></div>`;
}
function geneFindingCards(hit,options={}){
  const rows=hit.gene_contexts?.length?hit.gene_contexts:[{gene:hit.gene||'',reference_context:hit.reference_context}];
  return rows.map(row=>geneDisplayCard({...hit,...row,genotype:hit.genotype,personal_context:hit.personal_context,
    clnsig:hit.clnsig,disease:hit.disease||hit.clndn,review:hit.review,review_confidence:hit.review_confidence},options)).join('');
}
function geneReferenceExtras(p){
  const summaries=typeof p.interpretation?.summary==='object'?p.interpretation.summary:typeof p.text==='object'?p.text:{};
  return ['het','hom','hemi'].filter(key=>summaries[key]).map(key=>`<p><b>${esc(t('panel.state.'+key))}</b>: ${esc(summaries[key])}</p>`).join('')
    +(p.expect?`<p>${esc(t('panel.expect',{marker:p.expect.marker||'—',direction:t('system.panel.dir.'+(p.expect.direction||'lower')),note:p.expect.note||'—'}))}</p>`:'')
    +(p.effect_size?`<p>${esc(t('panel.effect',{effect:p.effect_size}))}</p>`:'')
    +(p.source?`<p class="cr-caption">${esc(t('panel.source_row',{source:p.source,study:p.study||'—'}))}</p>`:'')
    +(p.disposition?`<p>${esc(t('panel.intake.'+p.disposition))}${p.reason?' — '+esc(p.reason):''}</p>`:'')
    +(p.signature?`<p class="cr-caption">${esc(t('panel.signed.'+p.signature,{on:fmtDate(p.signed_on)||'—',curated:fmtDate(p.curated_on)||'—'}))}</p>`:'');
}
    return Object.freeze({render:geneDisplayCard, positions:genePositionCards, regionRows:geneRegionRows, findings:geneFindingCards,
      referenceExtras:geneReferenceExtras, reference:referenceContextHtml,
      mechanism:mechanismHtml, preview:geneticPreviewHtml, brief:geneticBriefHtml});
  }

  const api = {project, render:renderCard, renderModel, groupAssertions, cardCaveat, create};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.ScholionGeneCards = api;
}(typeof globalThis !== 'undefined' ? globalThis : this));
