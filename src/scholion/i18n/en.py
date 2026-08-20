"""English messages — the reference catalogue.

This file is the source of truth for *which keys exist*. Every other catalogue is
checked against it: a key here and missing there is a defect, and a key there
that is absent here is dead weight left over from a rename.

Conventions, so that the file stays readable at a thousand entries:

  * keys read `screen.fragment` — `overview.title`, `genome.connected`;
  * plural forms end in `.one` / `.few` / `.many` and always take `{n}`;
  * placeholders are named, never positional: `{value}` survives a sentence
    being reordered by a translator, `{0}` does not;
  * no key holds a whole paragraph glued from fragments. A sentence that has to
    be assembled in code cannot be reordered for another language, and word
    order is the first thing that changes between English and Russian.

Three namespaces share the file, and the prefix says who prints the phrase:

  * no prefix — the reports: the CLI, the skill and the Ouroboros plugin print
    them through `format.py`;
  * `web.…` — the labels of the local web page. It fetches the whole catalogue
    from `GET /api/i18n` and looks keys up with a `t()` of its own, so a phrase
    cannot exist in a tab and be missing from a report;
  * `server.…` — what the local server answers a request with, plus the lines it
    prints into the console it was started from.

A handful of `web.…` values are not text at all but MATCH lists — the labels as
they arrive from the profile, which the page groups rows by. They are marked
where they stand and read identically in every language on purpose: translating
them would break the grouping rather than the wording.
"""
from __future__ import annotations

MESSAGES = {

    # ── overview ─────────────────────────────────────────────────────────
    "overview.title": "**Overview.**",
    "overview.counts": "markers: {total}; current abnormalities: {abnormal}",
    "overview.stale_note": " (plus {n} older than 12 months — not a current status)",
    "overview.high": "**Above range ({n}):**",
    "overview.low": "**Below range ({n}):**",
    "overview.suggestions": "**Worth testing:** {n} item(s)",
    "overview.suggestions_priority": ", {n} of them a priority",
    "overview.genome": "**Genome:** {state}",
    "overview.genome_gaps": "; gaps: {genes}",
    "overview.medications": "**Prescriptions in the regimen:** {n}",
    "overview.lifestyle_watch": "**Lifestyle — worth watching:** {items}",

    # ── shared vocabulary ────────────────────────────────────────────────
    "genome.connected": "connected",
    "genome.not_connected": "not connected",
    "common.none": "none",
    "common.no_data": "no data",

    # ── data layout and external storage ─────────────────────────────────
    "layout.header": "Where the data lives:",
    "layout.missing": "  ✗ {slot}: source not connected, expected at {path}",
    "layout.external": "  ↗ {slot}: {path} (external storage)",

    # ── first run ────────────────────────────────────────────────────────
    "init.empty_profile": "⚠ profile is empty: {path}",
    "init.empty_hint_files": "  lay out the files:  scholion init",
    "init.empty_hint_demo": "  see the demo:       scholion init --demo",

    # ── suffixes shared by every marker line ─────────────────────────────
    "common.trend": "trend {arrow}{pct}",
    "common.stale": "older data",
    "near.upper": "upper",
    "near.lower": "lower",
    "near.at_edge": "at the edge: {margin} % from the {side} bound {bound}",
    "near.corridor": "{pct} % of the corridor width",
    "decision.sex_unknown_most_cautious": "sex is not recorded, so the more sensitive of the two published bounds was used for this threshold — a decision limit errs towards asking, unlike a reference interval",
    "decision.crossed": "threshold crossed: {label} ({sign} {value})",
    "decision.not_reached": "action threshold {value} ({label}) — not reached",

    # ── reference corridors, printed next to a value ────────────────────
    "ref.sex_unknown": "⚠ this interval differs by sex and the profile has none recorded — it may be the wrong corridor (`scholion profile --sex …`)",
    "ref.sex_unknown_no_range": "· no interval shown: this marker's range differs by sex and the profile has none recorded, so a corridor here would be a guess",
    "profile.recorded": "recorded: {fields}",
    "markers.none_local": "no locally added marker entries yet",
    "markers.local_header": "Locally added marker entries — {n}. A `proposed` one is read and shown but makes no claim about the norm; `confirmed` means a person vouched for it.",
    "markers.local_footer": "file: {path} — one line of JSON per entry, checkable by eye and shareable upstream",
    "markers.entry_status": "{key}: {status}",
    "markers.need_marker_and_unit": "a marker key and the unit as printed are both needed",
    "markers.need_factor_or_reason": "propose either a conversion factor or a reason the form cannot be converted",
    "markers.need_pattern": "a pattern is needed",
    "markers.need_example": "an example row is required: a pattern without the line that produced it cannot be reviewed and cannot become a regression fixture",
    "markers.bad_rule_kind": "{kind} is not a rule kind — use `alien` (the row belongs to somebody else) or `label` (the row IS a labelled row)",
    "markers.bad_pattern": "that is not a valid regular expression: {why}",
    "markers.unit_proposed_not_applied": "A proposed conversion for this unit exists and was NOT applied: an unconfirmed factor would change the number itself, not just the corridor. Confirm it with `scholion marker --confirm '{key}'` and re-run the import.",
    "markers.need_key": "a canonical key is needed (latin, lower case, underscores)",
    "markers.need_names": "at least one printed name is needed — that is what recognises the row",
    "markers.already_shipped": "{key} already exists in the shipped dictionary; a local entry never shadows a reviewed one",
    "markers.no_such_proposal": "there is no local entry called {key}",
    "markers.proposed_no_flag": "read by a locally proposed rule, not yet confirmed — the value is kept, no statement about the norm is made (`scholion marker --confirm {key}`)",
    "ref.range": "normal {low}–{high}",
    "ref.max": "normal <{high}",
    "ref.min": "normal >{low}",

    # ── drug × gene check ────────────────────────────────────────────────
    "drug.reference": "Reference: {url}",
    "drug.headline": "**{drug}** → gene **{gene}** ({drug_class}) — level: **{level}**",
    "drug.why_gene": "Why the gene matters: {text}",
    "drug.cpic_header": "CPIC, verbatim — {phenotype}, strength of recommendation: {classification}:",
    "drug.co_phenotype": "Also {gene}: {phenotype} — {label}",
    "drug.driven_by": "The caution above is driven by {gene} (the more severe of the genes for this drug).",
    "drug.phenotype": "Patient phenotype: **{phenotype}** — {label}",
    "drug.discuss": "**What to discuss with the doctor:** {text}",
    "drug.markers_header": "Patient markers for this gene:",
    "drug.marker_computed": "variant copies: {copies}, function: {function}",

    # ── a single locus in the genome ─────────────────────────────────────
    "genome.unknown_gene": "Gene {gene} is not in the coordinate reference.",
    "genome.no_database": "the full genome database is not connected yet.",
    "genome.loci": "**{gene}** — loci:",
    "genome.called": "called from the VCF",
    "genome.assumed_ref": "reference (the site is not variant)",
    "genome.depth": "depth {value}",
    "genome.gene_at": "gene **{gene}** ({chrom}:{pos})",
    "genome.genotype": "genotype **{genotype}**",
    "genome.significance": "Clinical significance (ClinVar/Ensembl): {values}",
    "genome.consequence": "Consequence: {text}",
    "genome.resolved_by": "coordinate obtained: {source}",

    # ── ClinVar block inside a drug report ───────────────────────────────
    "clinvar_block.header": "ClinVar for this drug:",
    "clinvar_block.via_gene": "gene {gene}",
    "clinvar_block.via_name": "by drug name",
    "clinvar_block.genotype": "genotype {genotype}",

    # ── second opinion on a new prescription ─────────────────────────────
    "source.local": "project database",
    "source.none": "not recognised",
    "common.in_range": "in range",
    "unresolved.pgx": "the phenotype — not read: {names}; a full VCF closes this",
    "unresolved.drug_not_classified": "the drug's class was not determined, so interactions were not checked",
    "unresolved.no_baseline": "there are no current prescriptions to compare against",
    "unresolved.baseline_partial": "part of the current list was not recognised and took no part "
                                   "in the comparison: {names}",
    "prescription.unresolved_h": "⚪ Not determined — and what would close it:",
    "prescription.unresolved_gene": "{detail} ({gene})",
    "drug.phenotype_not_determined": "The {gene} phenotype was not determined from your data — what follows is the general rule, not a statement about you.",
    "drug.no_guidance_for_phenotype": "The catalogue records no recommendation for the phenotype {phenotype} of {gene} for this drug. This is a gap in the reference data, not a finding about you — take the question to the doctor.",
    "basis.read": "Read {read} of {total} markers of the model.",
    "basis.missing": "Not read: {names}.",
    "basis.obtainable": "These positions are in the locus catalogue: a full genome (VCF) built from your own reads, or a targeted pharmacogenetic test that covers them, would close this gap and turn the general rule into a statement about this person.",
    "basis.not_in_catalogue": "They are not in the locus catalogue either — a laboratory test is needed.",
    "basis.not_called": "The VCF is connected, but {names} have no row in it — that is either the reference or no coverage, and the file cannot tell them apart. Building another VCF changes nothing; those positions have to be genotyped from the aligned reads, and until they are they count as unread.",
    "basis.not_modelled": "The project's catalogue knows {names} for this gene and the interpretation model does not use that yet — so even a full VCF leaves this part unanswered.",
    "phenotype.from_called_diplotype": "from the called diplotype {diplotype} (PyPGx/PharmCAT — copy number and phase resolved), which outranks a tag-SNP estimate",
    "phenotype.assumed": "{label} — ASSUMED, not every marker was read",
    "prescription.title": "**Second opinion: {drug}** — verdict: **{overall}**",
    "prescription.class": "class: {value}",
    "prescription.source": "source: {value}",
    "prescription.genome_header": "Your genome:",
    "prescription.pgx_unchecked": "Pharmacogenetics was NOT checked against CPIC — {why}. "
                                 "That is not the same as «this drug has none».",
    "pgx_unchecked.offline": "the network is switched off (SCHOLION_OFFLINE)",
    "pgx_unchecked.unreachable": "the database did not answer",
    "pgx_unchecked.not_identified": "the drug was not identified in RxNorm, so there was no "
                                    "identifier to ask by",
    "prescription.labs_no_rule": "The catalogue holds no lab-monitoring rule for this class "
                                 "({classes}) — which is not the same as «no monitoring is needed».",
    "prescription.labs_class_unknown": "The class of this drug was not determined, so nothing "
                                       "can be said about lab monitoring.",
    "unresolved.pgx_source": "Pharmacogenetics: CPIC was not queried — {why}.",
    "unresolved.labs_no_rule": "Lab monitoring: the catalogue has no rule for the class {classes}.",
    "prescription.no_pgx": "No significant pharmacogenetics for this drug (CPIC): "
                           "no genes affecting the dose or the effect were found.",
    "prescription.actionable": "important",
    "prescription.gene_phenotype": "your phenotype **{phenotype}** — {label}",
    "prescription.variants": "variants: {list}",
    "prescription.labs_header": "Your labs:",
    # ── red flags from the owner's own profile ───────────────────────────
    "prescription.safety_h": "A red flag from your own profile:",
    "prescription.safety_factor": "**Factor:** {text}",
    "prescription.safety_why": "Why it matters: {text}",
    "prescription.safety_pro": "What argues for a low risk: {text}",
    "prescription.safety_unknown": "What is unknown: {text}",
    "prescription.safety_action": "**Action:** {text}",
    "prescription.safety_source": "Source: {text}",

    "prescription.no_lab_control": "No lab monitoring specific to this class is required.",
    "prescription.monitor": "Monitor: {text}",
    "prescription.already_abnormal": "You are already out of range on: **{names}** — "
                                     "that matters with this drug.",
    "prescription.threshold_crossed": "{name} {value} — the clinical action threshold "
                                      "{threshold} ({label}) has been crossed.",
    "prescription.source_ref": "source: {source}",
    "prescription.near_edge": "In range, but at the edge of the corridor: **{names}** — "
                              "watch these especially closely on this drug.",
    "prescription.not_tested": "not tested yet",
    "prescription.interactions_header": "Your prescriptions:",
    "prescription.interaction": "with **{meds}** — {effect} (mechanism: {mechanism}).",
    "prescription.what_to_do": "What to do: {text}",
    "prescription.no_interactions_partial": "No explicit interactions were found with the part "
                                            "of the current list that was recognised. NOT compared, "
                                            "because the class could not be determined: {names}.",
    "prescription.no_interactions": "No explicit interactions with the current "
                                    "prescriptions were found.",
    "prescription.dose_header": "Dose and critical-claim context:",
    "prescription.doses": "Doses: nutraceutical {nutritional} · pharmacologic {pharmacologic}.",
    "prescription.effect": "effect: {text}",
    "prescription.by_dose": "on dose: {text}",
    "prescription.not_measured": "{name}: not measured",
    "prescription.your_numbers": "your numbers: {items}",
    "prescription.forms": "Forms: {text}",
    "prescription.alternative": "alternative: **{name}**",
    "prescription.alt_melatonin": "melatonin / sleep",
    "prescription.alt_metabolic": "metabolic",
    "prescription.alt_caveat": "caveat",

    # ── labs ─────────────────────────────────────────────────────────────
    "labs.header": "**Labs:** {abnormal} out of range among {total}",
    "labs.near_more": "{n} more at the edge of the corridor",
    "labs.crossed": "clinical action thresholds crossed: {n}",
    "labs.draw_context_saved": "recorded for {day}: {context} — applied to {n} markers measured twice that day",
    "labs.fasting_after_event": "⚠ the thresholds below presume a fasting sample; this draw followed — {text} — so a crossing here is not the labelled condition",
    "labs.condition_unknown": "⚠ this is the second draw of the day and the thresholds below presume a fasting sample — until it is said what stood between the two, treat the labelled crossing as unconfirmed",
    "labs.same_day_repeat": "two measurements on {day}: {points} — a repeat, not a disagreement in the data",
    "labs.same_day_context": "between them: {text}",
    "labs.same_day_ask": "why was it taken twice that day, and what happened between the two — a procedure, a dose, a load? `scholion lab-draw --day <date> --reason … --between …`",
    "labs.near_limit_is_flat": "«At the edge» uses a flat 10 % of the bound for every analyte. That is a heuristic, not a reference change value: between draws sodium moves a fraction of a per cent and CRP moves tens, so this zone is too lax for some markers and too strict for others.",
    "labs.ref_from_reference_base": "the interval is the general reference one, not printed on your form",
    "labs.genome_link": "genome: {text}",
    "count.abnormal.one": "{n} value",
    "count.abnormal.few": "{n} values",
    "count.abnormal.many": "{n} values",
    "count.markers_of.one": "{n} marker",
    "count.markers_of.few": "{n} markers",
    "count.markers_of.many": "{n} markers",

    # ── medications ──────────────────────────────────────────────────────
    "medications.empty": "The regimen is empty — there are no prescriptions in the profile.",
    "medications.header": "**Regimen ({n}):**",

    # ── markers (the profile's catalogue) ────────────────────────────────
    "markers.empty": "There are no markers in the profile yet.",
    "markers.header": "**Markers in the profile: {n}**",
    "markers.note": "An empty corridor is not a mistake: it is taken from your own lab form, "
                    "and without it the marker is printed WITHOUT an out-of-range flag.",

    # ── health radar ─────────────────────────────────────────────────────
    "radar.overall": "**Overall health index: {score}/100**",
    "radar.delta": "{delta} against the previous measurement",
    "radar.domain_counts": "{abnormal} out of range of {total}",
    "radar.domain_partial": "{abnormal} out of range of the {measured} measured — "
                            "the domain declares {total}",

    # ── second look before a doctor's visit ──────────────────────────────
    "second_opinion.title": "**A second look before the doctor's visit**",
    "second_opinion.abnormal": "**Out of range ({n}):**",
    "second_opinion.no_abnormal": "**Nothing is out of range.**",
    "second_opinion.stale": "older data, not a current status",
    "second_opinion.pgx": "**Pharmacogenetics — for the future ({n}):**",
    "second_opinion.pgx_none": "**Pharmacogenetics:** no notable flags.",
    "second_opinion.tests": "**Worth testing ({n}):**",
    "second_opinion.tests_none": "**Nothing further to order.**",
    "second_opinion.note": "This is a list of questions for the doctor, not a prescription.",

    # ── personal health metrics ──────────────────────────────────────────
    "metrics.title": "**Personal health metrics**",
    "metrics.age": "age {value}",
    "metrics.height": "height {value} cm",
    "metrics.bmi": "BMI {value} ({category})",
    "metrics.empty": "Nothing filled in yet.",
    "metrics.empty_hint": "Add weight, sleep and steps on the «Metrics» tab.",

    # ── suggested tests ──────────────────────────────────────────────────
    "tests.none": "The current rules suggest no further tests.",
    "tests.header": "**Suggested further tests** ({n}):",
    "tests.specialist": "who to see: {name}",
    "tests.why": "why: {text}",
    "tests.nothing_pending": "Nothing to order right now — what was ordered has been done; "
                             "only results that are not ready yet are outstanding.",
    "tests.rule_error": "rule {id}: error ({error})",
    "tests.routine_header": "**Routine follow-up — already done, tracked by interval:**",
    "tests.done": "{name} — measured {date}, repeat in ~{months} months.",

    # ── goal ─────────────────────────────────────────────────────────────
    "goal.not_set": "No goal has been set yet. profile/health_goals.json carries a "
                    "worked example under `_meta._example` — copy it to the top level "
                    "and rewrite it for your own goal.",
    "goal.title_default": "Goal",
    "goal.as_of": "data as of {date}",
    "goal.headline": "In one sentence: {text}",
    "goal.targets_header": "Target values (now → goal · best):",
    "goal.best": "best {value}",
    "goal.live_note": "Values and series are LIVE from the single data model "
                      "(labs.json + wearable_trends.json).",
    "goal.progress_rule": "Progress = fat down while muscle holds.",

    # ── ClinVar findings ─────────────────────────────────────────────────
    "clinvar.how_to_run": "The ClinVar annotation is part of preparing the genome, which "
                          "runs from the project's source tree rather than the installed "
                          "package. `scholion doc preparing-the-genome` describes the whole "
                          "route.",
    "capabilities.title": "**What this build can do** — Scholion {version}, {n} commands",
    "capabilities.how_to_read": "Generated from the command parser and the entry-point map, so "
                                "it cannot fall behind them. If the instruction you were given "
                                "and this list disagree, this list is the build in front of you. "
                                "Every command takes `--json`.",
    "capabilities.reads_h": "Reads only — {n} commands. Safe to call to answer a question.",
    "capabilities.writes_h": "CHANGES something — {n} commands. Not to be called to answer a "
                             "question. Two kinds, marked on each line: one AUTHORS values into "
                             "the profile and is never handed to a model as a tool; the other "
                             "TRANSCRIBES the person's own documents into the profile and "
                             "invents nothing — that one a model may hold.",
    "capabilities.kind.authors": "authors values — never a model's tool",
    "capabilities.kind.transcribes": "transcribes the person's own documents",
    "capabilities.face.web": "in the web interface",
    "clinvar.low_confidence": "low-confidence (0-1 stars): the review level does not support this at the strength its class implies",
    "clinvar.low_confidence_note": "{n} of these rest on a 0-1 star ClinVar review — a pathogenic call at that review level is the single most over-reported class for consumer sequencing; treat as a lead to confirm, not a finding.",
    "clinvar.empty": "No significant ClinVar variants were extracted from your VCF.",
    "clinvar.header": "**Clinically significant findings (ClinVar): {n}**",
    "clinvar.shown": "(first {n} shown)",
    "clinvar.how_to_read": "**How to read this.**",

    # ── ACMG secondary findings ──────────────────────────────────────────
    "acmg.unread_header": "Not read deeply enough to decide — {n} genes of the panel. A negative result in these is not a statement:",
    "acmg.needs_phase_header": "{n} hits in genes that need BOTH copies affected, found as two heterozygous variants. Whether they sit on different chromosomes — which is what would make them biallelic — an unphased file cannot say; in cis the person is an ordinary carrier. A parent's genotype or long reads settle it:",
    "acmg.needs_class_header": "{n} hits in genes ACMG reports only for a narrow class of variant — the class has to be established before any of these is a finding:",
    "acmg.how_to_run": "Run `python3 src/ingest/acmg_sf_scan.py` — it checks your VCF "
                       "against the ACMG Secondary Findings gene list.",
    "acmg.header": "**Secondary findings — {version}** ({genes} genes, {scanned} checked)",
    "acmg.reportable": "**Worth discussing with a geneticist: {n}**",
    "acmg.coverage_unknown": "coverage of these genes has never been measured on this genome, so «none found» here means «none found in what was read», and how much was read is unknown. `scholion limits` says what closes that.",
    "acmg.negative_qualified": "⚠ this answer rests on partial reading: of {genes} genes, {weak} are covered below {threshold} % at 10× and {unmeasured} were not measured at all. A negative over a gene that was not read is not a negative about the gene — it is a negative about the file.",
    "acmg.no_reportable": "No actionable findings.",
    "acmg.carriers": "Carrier status (not significant for you, significant for family "
                     "planning): {n}",
    "acmg.caveat": "An empty result does not mean «there are no genetic risks»: short reads "
                   "miss structural variants, repeat expansions and regions with pseudogenes.",

    # ── polygenic risks ──────────────────────────────────────────────────
    "prs.not_ready": "Polygenic scores have not been computed yet.",
    "prs.title": "**Polygenic risks (PGS)**",
    "prs.reliable": "{reliable}/{total} reliable",
    "prs.population_not_stated": "⚠ these percentiles were computed against the {population} reference population, which is a DEFAULT — nobody asked you. A percentile is a position within a population; against the wrong one it is not your position. `scholion profile --ancestry EUR|AFR|EAS|SAS|AMR`",
    "prs.reference": "reference {population}",
    "prs.above_average": "Noticeably above average (screening):",
    "prs.withheld_by_sex": "not shown: this trait exists only for the {sex} sex, and a percentile about an organ the reader does not have is not a smaller error for being printed politely",
    "prs.withheld_sex_unknown": "not shown: this trait exists only for the {sex} sex and no sex is recorded in the profile — the answer to «we do not know» is «then we do not say», not a default",
    "prs.caveat.strand_ambiguous": "a variant whose two alleles are each other's complement (A/T, C/G) matches either strand, so a strand flip in the source file is indistinguishable from a correct call — this build identifies such loci for a genotyping array and cannot do so inside a score it does not sum itself",
    "prs.caveat.missing_as_zero": "a variant of the model that is absent from your file is not added to the sum, which is arithmetically an imputed zero dose and biases the score downward; how much of the model's WEIGHT was actually present is measured and shown, and a percentile below the threshold is withdrawn from trust rather than footnoted",
    "prs.caveat.hard_genotypes": "hard genotypes only: an uncertain call is counted as a certain one, with no dosage",
    "prs.caveat.reference_panel": "the percentile is a position within a reference sample; the scoring package is pinned by version rather than by hash, and the reference panel it downloads on first use is not pinned at all — two machines can in principle place the same genome against different reference data",
    "prs.no_model": "no model",
    "prs.evidence_legend": "Level of evidence: ✚ clinically validated · · supporting context · "
                           "no mark — research grade",

    # ── longevity layer ──────────────────────────────────────────────────
    "longevity.not_ready": "The longevity layer has not been built yet.",
    "longevity.title": "**Longevity — the genetic layer (LongevityMap)**",
    "longevity.apoe": "APOE: **{epsilon}** (rs429358={rs429358}, rs7412={rs7412})",
    "longevity.key_markers": "Key markers:",
    "longevity.carries": "carries the allele",
    "longevity.significant": "Significant carrier states: {carriers} across {genes}.",
    "longevity.genes_first": "Genes (first ones): {genes}",
    "count.genes_in.one": "{n} gene",
    "count.genes_in.few": "{n} genes",
    "count.genes_in.many": "{n} genes",

    # ── lifestyle (wearables) ────────────────────────────────────────────
    "lifestyle.empty": "There is no lifestyle data (wearable devices) yet.",
    "lifestyle.title": "**Lifestyle (wearable devices)**",
    "lifestyle.fitness_score": "overall fitness score: {score}/100",
    "lifestyle.improving": "improving",
    "lifestyle.worsening": "getting worse",
    "lifestyle.comparable_from": "the series is comparable from {date} "
                                 "(earlier — a different device)",
    "lifestyle.workouts": "Workouts of all time (top): {items}",

    # ── reconciliation of lab forms against the profile ──────────────────
    "reconcile.title": "**Lab forms ↔ profile (labs.json)**",
    "reconcile.folder": "Folder: {path}",
    "reconcile.pdf_total": "PDFs in total: {n}",
    "reconcile.pdf_non_lab": "non-lab / other: {n}",
    "reconcile.points_matched": "points matched: {n}",
    "reconcile.markers_seen": "markers recognised: {n}",
    "reconcile.unreadable": "NOT READ ({n}) — data may be lost; open the files on the Mac "
                            "(so iCloud materialises them) and run this again:",
    "reconcile.bytes": "{n} bytes",
    "reconcile.all_readable": "No unreadable files — every PDF gave up its text.",
    "reconcile.missing": "MISSING from the profile ({n}) — present on the form, absent "
                         "from labs.json:",
    "reconcile.no_missing": "No missing points — every value recognised on the forms "
                            "is in the profile.",
    "reconcile.mismatch": "DISCREPANCIES ({n}) — same date, different value (a recognition "
                          "error or a unit conflict → check by hand):",
    "reconcile.mismatch_row": "{marker} {date}: {pdf} on the form ≠ {profile} in the profile",
    "reconcile.provenance": "Provenance recorded: {path}.",
    "reconcile.read_only": "The tool only reads — labs.json is not changed.",
    "reconcile.how_to_fill": "Enter the missing points with the ingest-labs command, "
                             "or by hand after checking.",

    # ── lifestyle brief ──────────────────────────────────────────────────
    "brief.not_compiled": "The brief has not been compiled: {reason}",
    "brief.title_default": "Lifestyle brief",
    "brief.compiled": "compiled {date}",
    "brief.needs_review": "NEEDS REVIEW (new data has arrived since the last edit):",
    "brief.stale_block": "{title} — last edited {reviewed}, fresh data {newest}",
    "brief.review_hint": "what to revisit: {text}",
    "brief.actions": "WHAT TO DO",
    "brief.dropped": "ALARMS DROPPED",

    # ── focus of attention ───────────────────────────────────────────────
    "focus.not_set": "No focus has been set.",
    "focus.title": "**Focus of attention: {title}**",
    "focus.since": "since {date}",
    "focus.now": "**{label}:** now {value}",
    "focus.as_of": "as of {date}",
    "focus.last_nights_export": "last {nights} of the export "
                                "({window_from} → {window_to}): {value} {unit}",
    "focus.last_nights": "last {nights}: {value} {unit}",
    "focus.baseline": "baseline {value} ({note})",
    "focus.shift": "shift {delta} ({direction})",
    "focus.target": "target {value} {unit} — {note}",
    "focus.levers": "**Levers** (observations on one's own data, not prescriptions):",
    "focus.lever": "{title} — expected effect {expected}",
    "focus.lever_now": "now: {text}",
    "focus.journal": "**Episode log:**",
    "focus.tracks": "**GOALS ({n}):**",
    "focus.closed": "closed: {text}",
    "focus.evidence": "**Already done instrumentally ({n}):**",
    "focus.does_not_answer": "does not answer: {text}",
    "focus.open": "**Still open:**",
    "focus.questions": "**Questions:**",
    "count.nights.one": "{n} night",
    "count.nights.few": "{n} nights",
    "count.nights.many": "{n} nights",

    # ── genome status ────────────────────────────────────────────────────
    "genome_status.connected": "**Genome connected.**",
    "genome_status.several_files": "**{count} genome files are lying in that folder, and none of them is «the» one until you say so.** Reading whichever sorts first is how a per-chromosome set answers APOE from chromosome 1, and how a folder holding two people answers about whichever name comes earlier in the alphabet. Both of those look like answers.",
    "genome_status.several_files_fix": "Name the one that is yours: {cmd}",
    "genome_status.several_samples": "**This file holds {count} samples — {names} — and the tenth column is not a person's name.** A trio or a joint call puts several people side by side; reading the first one silently reports somebody, possibly a relative, as you.",
    "genome_status.several_samples_fix": "Say which sample is yours: {cmd}",
    "genome_status.sample": "Sample: {name}",
    "genome_status.sample_not_found": "**The sample you named is not in this file.** It holds: {names}.",
    "genome_status.sample_not_found_fix": "Name one of them: {cmd}",
    "genome.refused_head.sample_not_found": "the sample named in SCHOLION_GENOME_SAMPLE is not in this file.",
    "genome.refused_head.sample_not_chosen": "the file holds several samples and none was chosen.",
    "genome.refused.sample_not_found": "The coordinate was found, and so is your file. The sample named in `SCHOLION_GENOME_SAMPLE` is not one of the samples in it — `scholion genome-status` lists the names the file does carry.",
    "genome.refused.sample_not_chosen": "The coordinate was found. The file holds several samples and none was chosen; `SCHOLION_GENOME_SAMPLE` says which one is yours.",
    "genome_status.foreign_head": "**No readable VCF — but the folder is not empty, and what is in it is genomic data.**",
    "genome_status.foreign_bcf": "  · {path} — a BCF. Convert it once: `bcftools view -Oz -o <file>.vcf.gz {path} && tabix -p vcf <file>.vcf.gz`",
    "genome_status.foreign_vcf_container": "  · {path} — a VCF in a container the readers cannot seek into. Recompress it with bgzip and index it.",
    "genome_status.foreign_gvcf": "  · {path} — a gVCF: it carries reference blocks rather than one row per site, and a position inside a block is not a row. Convert it to a plain VCF first (`bcftools convert --gvcf2vcf`).",
    "genome_status.foreign_alignment": "  · {path} — an alignment (BAM/CRAM), not variant calls. This is the input to the pipeline, not its output: see `scholion doc preparing-the-genome`, §5.",
    "genome_status.foreign_reads": "  · {path} — raw reads (FASTQ). They have to be aligned and called first; the route is in `scholion doc preparing-the-genome`.",
    "genome_status.foreign_archive": "  · {path} — an archive. Unpack it and leave the file itself in the folder; archives are not opened blind here.",
    "genome_status.foreign_array": "  · {path} — a consumer array export that could not be read as one. `scholion genome-status` names the vendor when it recognises the file.",
    "genome.sample_not_chosen": "the file holds several samples ({names}) and none was chosen — SCHOLION_GENOME_SAMPLE says which one is yours",
    "genome.no_coordinate": "no coordinate",
    "genome.no_row_and_build_unknown": "There is no row at this position, and the build this file was called against has not been established. Those two produce the same silence: a position read in the wrong coordinate system is empty for the same reason an unvaried position is. Naming the build settles it in one variable — `SCHOLION_GENOME_ASSEMBLY=GRCh37 scholion genome <rsid>`.",
    "genome.refused_head.no_row_and_build_unknown": "nothing at this position, and the build of the file is not established.",
    "genome.refused_head.sample_not_chosen_result": "the file holds several samples and none was chosen.",
    "genome.refused_head.no_file": "the full genome database is not connected yet.",
    "genome.refused_head.unreadable_file": "the genome file is there and cannot be read.",
    "genome.refused_head.assembly_unsupported": "the file is in a build this catalogue cannot answer in.",
    "genome.refused_head.several_files": "there is more than one genome file and none was chosen.",
    "genome.refused_head.several_samples": "the file holds several samples and none was chosen.",
    "genome.refused_head.foreign_input": "there is genomic data in the folder, but no readable VCF.",
    "genome.refused_head.no_engine": "the genome file is there and no reader is installed.",
    "genome.refused.no_file": "The coordinate was found, but the full genome database is not connected yet (genome/*.vcf.gz + .tbi are needed).",
    "genome.refused.no_answer": "The coordinate was found and the file is connected, but the reader returned nothing at that position — most often a missing or broken index (`.tbi`/`.csi`). `scholion genome-status` says which. An empty answer is not a reference call and is not reported as one.",
    "genome.refused.unreadable_file": "The coordinate was found. The file in the genome folder is not readable as it stands — `scholion genome-status` prints the one command that fixes it. Nothing is missing; nothing needs to be obtained.",
    "genome.refused.assembly_unsupported": "The coordinate was found, and so is your file: it is connected and indexed. It is called against a build this catalogue carries no coordinates for, and nothing is converted on the fly, because a converted position points at a real base that is the wrong one. `scholion genome-status` names the build and what to do.",
    "genome.refused.several_files": "The coordinate was found. There is more than one genome file in the folder, and which of them is yours is not ours to guess — `SCHOLION_GENOME_VCF` says so in one variable.",
    "genome.refused.several_samples": "The coordinate was found. The file holds several samples — a trio or a joint call — and reading the first column would report somebody else as you. `SCHOLION_GENOME_SAMPLE` says which one is yours.",
    "genome.refused.foreign_input": "The coordinate was found. The folder holds genomic data that is not a readable VCF — `scholion genome-status` names each file and what it needs.",
    "genome.refused.no_engine": "The coordinate was found and the file is in place, but no reader is installed: bcftools, pysam, or a working `.tbi` index beside the file.",
    "genome_status.file": "File: {path}",
    "genome_status.reader": "Reader: {reader}",
    "genome_status.not_ready": "**Genome found, but not ready to read:** {reason}",
    "genome_status.no_index": "no .tbi index",
    "genome_status.assembly_unknown_actions": "Three ways to settle it, cheapest first:\n  1. **If you know who sequenced you** — the build is named in their report, and one variable is enough: `SCHOLION_GENOME_ASSEMBLY=GRCh37 scholion genome-status` (or GRCh38, or T2T-CHM13v2.0).\n  2. **Read it off the header:** `bcftools view -h {path} | grep -E '##(contig|reference)'` — a `length=` beside chr1 answers it: 249250621 is GRCh37, 248956422 is GRCh38, 248387328 is T2T.\n  3. **Write the contigs in once**, so the file answers for itself from now on: `bcftools reheader -f <reference>.fai {path}`.",
    "genome_status.assembly_mismatch": "**The genomic layer is off: this file is called against {found}, and the coordinate catalogue is in {want}.** The same variant sits at different positions in different builds — APOE rs429358, for instance, is at 19:44,908,684 in GRCh38 and at 19:45,411,941 in GRCh37. Asking one coordinate of the other file lands in a different gene, and the answer would be wrong without looking wrong.",
    "genome_status.assembly_fix": "Lift the file over to {want} (`CrossMap` or `bcftools +liftover` with the chain file), or re-call from the alignment against that build. Nothing is lifted over on the fly here on purpose: converting coordinates silently would add the kind of error this layer exists to remove. Everything outside the genome — labs, prescriptions, wearables — is unaffected.",
    "genome_status.coordinates_secondary": "read at {assembly} coordinates — the catalogue carries {have} of its {total} loci in that build, and the rest are not read out of this file rather than guessed at. Nothing is converted between builds.",
    "genome_status.assembly_ok": "Assembly: {found}",
    "genome_status.assembly_unknown": "**Assembly: not established.** The header carries no contig lengths and no `##reference` line, and no variant turned up past the end of chromosome 1 in GRCh38 — so the data did not settle it either. Answers are being computed as if the file were {want}; if it is not, every genomic answer is about the wrong position.",
    "genome_status.unusable_plain": "**A genome file is right there and cannot be read yet:** {path} — it is a plain `.vcf`. The readers seek into the file, so it has to be block-compressed and indexed first. This is one command, not a different file.",
    "genome_status.unusable_gzip_not_bgzip": "**A genome file is right there and cannot be read yet:** {path} — it was compressed with ordinary gzip rather than bgzip. It looks right and `tabix` will refuse it with a message about the format that explains nothing.",
    "genome_status.unusable_fix": "Fix it with: {cmd}",
    "genome_status.build_index": "Build the index: tabix -p vcf <file>",
    "genome_status.no_vcf": "**The full VCF is not connected** — the genome side answers "
                            "«the database is not connected».",
    "genome_status.how_to_get": "How to obtain one: `scholion doc preparing-the-genome`.",
    "genome_status.gaps": "Gaps (target genes with no data): {genes}",

    # ── genome updates (a fresh ClinVar against the personal VCF) ────────
    "genome_updates.not_run": "No check against a fresh ClinVar has been run yet "
                              "(there is no genome/whats_new.json).",
    "genome_updates.last_checked": "**Last check:** {date}",
    "genome_updates.release": "ClinVar release: {release}",
    "genome_updates.new": "New",
    "genome_updates.changed": "Changed",

    # ── result of a writing command ──────────────────────────────────────
    "write.failed": "not done",
    "write.saved": "Saved",

    # ── plural examples, kept because the mechanism needs at least one ──
    "count.markers.one": "{n} marker",
    "count.markers.many": "{n} markers",
    "count.markers.few": "{n} markers",

    # ── the CLI: what a command prints when it is done ────────────────
    "init.dir_created": "✓ data directory: {path}",
    "init.written": "  created: {files}",
    "init.skipped": "  already there, left alone: {files} — to overwrite: --force",
    "init.demo_notice": "  This is a FICTIONAL person, not anybody's real data.",
    "init.demo_next": "  Have a look:  scholion overview   ·   scholion serve",
    "init.why_sex_asked": "Two questions now save a wrong number later: six reference intervals (testosterone, ferritin, creatinine, haematocrit, haemoglobin, uric acid) differ by sex, and lab forms print age-banded rows. Press Enter to skip either.",
    "init.ask_sex": "  sex (male / female, Enter to skip): ",
    "init.ask_birth_year": "  year of birth (Enter to skip): ",
    "init.sex_not_recorded": "Sex and year of birth are not recorded. Six markers will be shown WITHOUT a reference interval rather than against a possibly wrong one — `scholion profile --sex male|female --birth-year YYYY` when you want them back.",
    "init.next_steps": "  Next — whichever you have:\n"
                       "     lab PDFs in a folder   scholion ingest-labs \"<folder>\"\n"
                       "     a prescription list    scholion add-med \"<name>\" --dose \"...\"\n"
                       "     nothing yet            scholion demo   (a fictional person, to look around)\n"
                       "  Then:  scholion serve   opens the whole thing in a browser.",
    "tools.only_for_genome": "\nThe rest of this message is about the GENOME track only — building a VCF "
                             "from raw reads.\nLab results, prescriptions and a consumer-array file need "
                             "none of it; the application already works.",
    "skill.file_missing": "✗ the instruction file was not found: {path}\n  The package looks "
                          "incompletely built — reinstall it.",
    "assistant.context_saved": "Context saved: {path} ({chars} characters).",
    "assistant.context_personal": "⚠️ The file contains personal medical data.",
    "ingest.not_ingested_header": "Nothing was taken from {n} files — each is named, with the reason:",
    "ingest.not_ingested_more": "… and {n} more",
    "ingest.conflict": "conflict: {marker} on {date} — kept {kept}, the other form said {other}",
    "ingest.repeat": "repeat: {marker} was measured twice on {day} ({first} and {second}) — `scholion lab-draw --day {day}` records what stood between them",
    "ingest.labs_done": "Files processed: {files}, points: {points}, skipped: {skipped}.",
    "ingest.no_folder": "no folder of PDFs was given",
    "ingest.studies_done": "Conclusions in total: {total}; {added} added, {updated} updated, "
                           "{seen} files looked through. {hint}",
    "ingest.garmin_done": "✓ Lifestyle rebuilt: {metrics} metrics, range {range}. Written to {out}",
    "ingest.garmin_backup": " (backup: {path})",

    # ── the assistant layer: the status board and the audit of its own code ───
    "common.yes": "yes",
    "common.no": "no",
    "assistant.scan_core": "core: {files} files, {lines} lines",
    "assistant.scan_ingest": "data preparation: {files} files, {lines} lines",
    "assistant.scan_ingest_absent": "data preparation: not in this build",
    "assistant.verdict_clean": "no calls to language models",
    "assistant.verdict_hits": "calls found — worth a look",
    "assistant.engine.parsing": "reading PDF forms and entering the markers (an ordinary "
                                "parser, not a model)",
    "assistant.engine.flags": "flags against the corridors printed on your own forms, trends, "
                              "«at the edge»",
    "assistant.engine.genome": "genome: ClinVar findings, ACMG SF, polygenic risks, the "
                               "longevity layer",
    "assistant.engine.pgx": "pharmacogenetics: CPIC phenotypes, star alleles, HLA",
    "assistant.engine.second_opinion": "a second opinion on a drug: genome × labs × "
                                       "interactions × ClinVar",
    "assistant.engine.checklist": "the checklist for the next blood draw, biological age, "
                                  "n-of-1 experiments",
    "assistant.engine.goals": "goals, the dashboard of movement towards them, lifestyle and "
                              "body composition",
    "assistant.adds.narrative": "a coherent reading instead of a table: what matters here and "
                                "what is noise",
    "assistant.adds.provenance": "an explanation of where a conclusion came from, with the "
                                 "source named",
    "assistant.adds.what_if": "answers to «what if» — from your data, not in general",
    "assistant.adds.questions": "a list of questions for the doctor before the appointment",
    "assistant.adds.curated": "updates to the profile's curated texts (the brief, the focus, "
                              "the goal)",
    "assistant.curated.brief": "Lifestyle brief",
    "assistant.curated.focus": "Focus of attention",
    "assistant.curated.goal": "Goal for the metrics",
    "assistant.curated.absent": "there is no text — the tab will show the numbers alone, with "
                                "no wording",
    "assistant.curated.unreadable": "the file does not read as JSON",
    "assistant.curated.stale": "data newer than the wording has appeared — the blocks are "
                               "marked as needing a review",
    "assistant.ep.skill.title": "Claude skill",
    "assistant.ep.skill.installed": "installed: {path}",
    "assistant.ep.skill.ready": "present in the project, but not installed",
    "assistant.ep.skill.missing": "the skill file was not found",
    "assistant.ep.skill.what": "the assistant sees the instruction and calls the project's "
                               "commands itself",
    "assistant.ep.ouroboros.title": "Ouroboros plugin",
    "assistant.ep.ouroboros.ready": "the plugin file is in the project: {path}",
    "assistant.ep.ouroboros.missing": "the plugin file was not found",
    "assistant.ep.ouroboros.how": "point the Ouroboros configuration at this file (get_tools() "
                                  "→ sch_*)",
    "assistant.ep.ouroboros.what": "the sch_* tools become available to whichever model "
                                   "Ouroboros is configured with",
    "assistant.ep.any.title": "Any other model",
    "assistant.ep.any.detail": "works through the context: a text holding a snapshot of the "
                               "state and a list of commands",
    "assistant.ep.any.what": "paste the collected text into a conversation with any model — "
                             "Claude, ChatGPT, Gemini, a local one. The model gets no access "
                             "to the machine: it asks you to run a command and reads the output",
    "assistant.planned": "connecting a third-party model by API key straight from the "
                         "application is the next stage; for now the core deliberately does "
                         "not go to the network for its conclusions",
    "assistant.disclaimer": "The assistant neither prescribes nor withdraws therapy. "
                            "Everything it puts into words is material for a conversation with "
                            "the treating doctor.",
    "assistant.works_without": "The application works without an assistant: {answer}",
    "assistant.code_check": "Code check: {scanned} — {verdict}",
    "assistant.network_lead": "Where the application may reach (only on your command, and only "
                              "the query itself leaves — not the profile and not the genome):",
    "assistant.network_detail": "    a drug name — RxNorm/RxClass, and a translator for "
                                "Russian brand names; rsID — Ensembl; pharmacogenetics — CPIC",
    "assistant.ingest_hosts": "  · data preparation, run by hand: {hosts}",
    "assistant.engine_does_h": "Computed by code:",
    "assistant.adds_h": "Added by the assistant:",
    "assistant.curated_h": "Curated texts:",
    "assistant.entrypoints_h": "Entry points:",

    # ── the assistant layer: the context you paste into any model ─────
    "assistant.ctx.rules": """RULES (mandatory):
1. You do not prescribe therapy and you do not withdraw it. A reading ends in
   questions for the doctor.
2. The numbers below have already been computed by local code from primary data.
   Do not recompute them and do not replace them with «typical» values: if
   something is missing, say so — it is missing.
3. Name the source of every conclusion: the marker and the date, or the command
   that produced it.
4. The reference corridors are taken from this person's printed forms. Do not
   substitute anybody else's.
5. A finding that is absent is not the same as a normal one: the genome has
   coverage, the labs have an age.
""",
    "assistant.ctx.title": "# Scholion context for an assistant\n",
    "assistant.ctx.collected": "Collected: {date}. Below is a snapshot of the state, computed "
                               "by local code.\n",
    "assistant.ctx.personal": "⚠️ This text contains personal medical data. Paste it only "
                              "where you are content for it to be kept.\n",
    "assistant.ctx.connected_h": "\n## What is connected\n",
    "assistant.ctx.markers": "— markers in the profile: {n}\n",
    "assistant.ctx.pgx_genes": "— genes with pharmacogenetics: {n}\n",
    "assistant.ctx.genome": "— the full genome: {state}\n",
    "assistant.ctx.meds_h": "\n## Prescriptions\n",
    "assistant.ctx.no_meds": "— there are no prescriptions in the profile\n",
    "assistant.ctx.med_since": "since {date}",
    "assistant.ctx.ref_range": " (normal {low}–{high})",
    "assistant.ctx.ref_max": " (normal <{high})",
    "assistant.ctx.ref_min": " (normal >{low})",
    "assistant.ctx.ref_none": " (the form carries no corridor — there must be no flag)",
    "assistant.ctx.abnormal_h": "\n## Abnormalities ({abnormal} of {total} markers)\n",
    "assistant.ctx.abnormal_row": "— {name}: {value} {unit}{ref} · {date} · flag {flag}\n",
    "assistant.ctx.truncated": "— … the first {shown} of {total} are shown. The full list: "
                               "python3 -m scholion labs\n",
    "assistant.ctx.none_row": "— none\n",
    "assistant.ctx.tests_h": "\n## Worth testing ({n})\n",
    "assistant.ctx.test_row": "— {suggest} — {why} [{priority}]\n",
    "assistant.ctx.focus_h": "\n## Focus of attention\n— {title}\n",
    "assistant.ctx.commands": """
## Commands whose output you can ask the person for
python3 -m scholion overview             a summary: red flags, gaps, counters
python3 -m scholion second-opinion       a second look before a doctor's visit
python3 -m scholion radar                the health index by body system (0–100)
python3 -m scholion labs                 lab analysis: flags and trends
python3 -m scholion medications          the current treatment regimen
python3 -m scholion markers              the catalogue of markers and their corridors
python3 -m scholion genome-status        is the genome connected, what is missing
python3 -m scholion drug "<drug>"         the drug against the pharmacogenetics
python3 -m scholion prescription "<drug>"  a check of a new prescription
python3 -m scholion suggest-tests        what is worth testing
python3 -m scholion genome --gene <GENE>  a search in the full VCF
python3 -m scholion clinvar | acmg | prs | longevity
python3 -m scholion metrics | lifestyle | goal | focus | brief
python3 -m scholion phenoage --panels    the completeness of the biological-age panels
python3 src/ingest/draw_checklist.py           the form for the next blood draw (steps, tubes)

Do not invent the output of these commands — ask for them to be run and the result sent.
A reading is not a diagnosis but material for a conversation with the treating doctor.
""",

    # ── the Ouroboros tools: what a model reads before it calls one ───
    "tool.sch_check_drug_gene.description": "Check a prescribed drug against the "
                                            "pharmacogenetics in the owner's profile "
                                            "(profile/pharmacogenomics.json: genotypes[] from "
                                            "the BAM + PyPGx star-allele diplotypes in "
                                            "star_alleles, the PharmCAT CPIC report in "
                                            "profile/pharmcat/). Returns the level of "
                                            "significance, the gene involved, the computed "
                                            "phenotype and what to discuss with the doctor. "
                                            "Not a prescription.",
    "tool.sch_check_drug_gene.param.drug": "the name of the drug (Russian/English)",
    "tool.sch_analyze_labs.description": "A reading of the owner's lab results: flags for "
                                         "abnormalities, trends over time, links to the "
                                         "genome. markers is an optional comma-separated list "
                                         "of keys.",
    "tool.sch_analyze_labs.param.markers": "marker keys, comma-separated; empty means all of them",
    "tool.sch_suggest_tests.description": "Suggest further tests based on the current lab "
                                          "data, the prescriptions and the gaps in the genome. "
                                          "Material for a conversation with the doctor.",
    "tool.sch_genome_lookup.description": "Find the genotype of any locus in the owner's full "
                                          "genome database (VCF) by rsID or by gene. The "
                                          "coordinates come from a public reference/Ensembl, "
                                          "the genotype from the personal VCF. If the database "
                                          "is not connected, returns the status no_genome.",
    "tool.sch_genome_lookup.param.rsid": "rsID, e.g. rs4149056",
    "tool.sch_genome_lookup.param.gene": "the name of a gene (all of its loci)",
    "tool.sch_check_prescription.description": "A PERSONAL second opinion on a drug against "
                                               "the owner's data: 🧬 their genome (the genes "
                                               "CPIC considers important for the drug + their "
                                               "genotypes and phenotypes), 🧪 their labs (what "
                                               "to monitor and what is already out of range), "
                                               "🔗 their current prescriptions (interactions). "
                                               "Works for ANY drug (recognised through RxNorm, "
                                               "the genes through CPIC by rxcui). Russian "
                                               "names are accepted.",
    "tool.sch_check_prescription.param.drug": "the name of the drug (Russian/English)",
    "tool.sch_ingest_labs.description": "Extract lab markers with their dates from the PDF "
                                        "reports in a given folder (e.g. a «Lab reports» "
                                        "folder) and add them to profile/labs.json. "
                                        "Incremental: only new or changed files are read.",
    "tool.sch_ingest_labs.param.folder": "the path to the folder of lab PDFs",
    "tool.sch_health_metrics.description": "The owner's personal health metrics "
                                           "(profile/metrics.json): age, BMI, sleep, weight, "
                                           "steps, activity and trends. For the «lifestyle» "
                                           "context.",
    "tool.sch_lifestyle.description": "This profile's historical lifestyle data, from "
                                      "whichever wearable and scales fed it "
                                      "(profile/wearable_trends.json): MONTHLY trends (3-month "
                                      "smoothing) of weight, BMI, body fat share, muscle mass, "
                                      "VO2max, resting heart rate, HRV, stress, Body Battery, "
                                      "steps and activity, plus a summary of workouts and a "
                                      "fitness score. Worth taking into account when reading "
                                      "metabolic risk and advising on training load.",
    "tool.sch_clinvar_findings.description": "The owner's clinically significant findings from "
                                             "ClinVar × the personal VCF "
                                             "(genome/clinvar_hits.tsv, produced by "
                                             "annotate_clinvar.sh). Pathogenic and risk "
                                             "variants the patient carries. If it has never "
                                             "been run, returns not_run.",
    "tool.sch_prs.description": "The owner's polygenic risks (PGS Catalog, "
                                "profile/prs_results.json): percentiles across 74 traits (12 "
                                "categories) — a position in the population, NOT a probability "
                                "of disease. The models are built on European cohorts. Every "
                                "trait carries a level of evidence "
                                "(clinical/supportive/research) — an extreme percentile at the "
                                "research level is no reason to act. The models are pinned by "
                                "the registry knowledge/prs_models.json; the field "
                                "model_changed_from marks a break in the percentile series (a "
                                "different model is a different scale — do not draw a trend "
                                "across it). An extreme percentile may carry a validity_note — "
                                "an audit of the model against the owner's data (coverage, "
                                "misses, the MHC share, the drivers); reliable=false with a "
                                "note means the percentile is not to be trusted. «Above "
                                "average» (P≥80) is a reason to screen, not a diagnosis.",
    "tool.sch_longevity.description": "The owner's genetic longevity layer (LongevityMap × "
                                      "VCF, profile/longevity_findings.json): APOE ε status "
                                      "and the well-studied markers (FOXO3 and others) plus "
                                      "significant carrier states by gene. A catalogue of the "
                                      "literature, not a risk estimate.",
    "tool.sch_phenoage.description": "The owner's biological age (PhenoAge, Levine 2018) from "
                                     "9 routine markers. STRICTLY from a single panel: every "
                                     "marker from one blood draw. If a marker is missing from "
                                     "the panel the tool does NOT compute and returns the list "
                                     "of what to add to the next draw (substituting values "
                                     "from earlier panels is forbidden). panel: 'YYYY-MM', "
                                     "'latest' (the default) or 'panels' — an overview of how "
                                     "complete every panel is.",
    "tool.sch_phenoage.param.panel": "YYYY-MM | latest | panels",
    "tool.sch_provenance.description": "The reverse check of the labs: for EVERY point in "
                                       "profile/labs.json a printed source form is looked for "
                                       "(or the point is verified as a correctly computed "
                                       "derivative). Complements sch_ingest_labs/reconcile, "
                                       "which go the other way. The verdict «manual» means "
                                       "«confirmed by nothing» — such a point must not be "
                                       "presented as a fact. refresh=true re-reads every PDF "
                                       "from scratch (slow).",
    "tool.sch_provenance.param.refresh": "re-read every form instead of taking labs_coverage.json",
    "tool.sch_overview.description": "The main screen of this profile: how many markers are "
                                    "measured, how many are outside their range and in which "
                                    "direction, what tests are pending, what the genome layer "
                                    "knows. Start here when the question is broad — it names "
                                    "the parts worth asking about next.",
    "tool.sch_second_opinion.description": "One page for a conversation with a doctor: the "
                                          "health index by body system, the current lab "
                                          "abnormalities grouped by the system they belong to, "
                                          "the pharmacogenetic watch list against the "
                                          "prescriptions on file, and the tests still worth "
                                          "taking. Says of each drug whether the genotype was "
                                          "read or the general rule is being printed.",
    "tool.sch_limits.description": "WHAT THIS DATA CANNOT ANSWER, and what would close each "
                                  "gap. Read it before making any negative statement: «nothing "
                                  "found» is only meaningful next to what was looked at. Names "
                                  "the cell of the input × trait-architecture matrix the answer "
                                  "sits in, the measured coverage, and every claim the profile "
                                  "does not support.",
    "tool.sch_radar.description": "The health index by body system, 0–100 each, with the change "
                                 "since the previous measurement and the markers that moved. "
                                 "The denominator is the panel declared for the system, not the "
                                 "part of it that happens to be measured — a system with two "
                                 "values out of nine says so.",
    "tool.sch_focus.description": "The one task this profile is concentrating on right now: the "
                                 "live metric, the path baseline → now → target, the levers "
                                 "drawn from the person's own data, and the episode log. Empty "
                                 "when nothing is set, which is a legitimate answer.",
    "tool.sch_brief.description": "The lifestyle brief: live numbers from the wearable and the "
                                 "scales together with the curated wordings from the profile, "
                                 "each marked as fresh or stale against its own watch interval.",
    "tool.sch_acmg.description": "ACMG SF v3.3 secondary findings — the actionable minimum "
                                "across 84 genes, with the reporting rules applied (recessive "
                                "genes only when biallelic, and so on). Says plainly when the "
                                "scan has not been run, which is not the same as a clean result.",
    "tool.sch_goal_suggest.description": "Proposes a target for each marker there is enough "
                                        "evidence to propose one for, and says where each number "
                                        "came from: a clinical association with its citation, "
                                        "the person's own best with the date and the count behind "
                                        "it, or the laboratory corridor. Lists what it declined "
                                        "to propose for, and why. READ-ONLY — it writes nothing.",
    "tool.sch_lipid_genetics.description": "The inherited side of the lipid profile: carriage of "
                                          "a PCSK9 loss-of-function variant and the Lp(a) value, "
                                          "in one answer because each is misread alone. Carries "
                                          "the population caveat where carriage means little, and "
                                          "the reason a polygenic estimate of Lp(a) cannot stand "
                                          "in for measuring it.",
    "tool.sch_goal.description": "The goal set in this profile (profile/health_goals.json): "
                                 "the now→goal table and the reference points. The CURRENT "
                                 "values are LIVE, from the single model (labs.json + "
                                 "wearable_trends.json). Use it to judge how close the profile "
                                 "is to its own goal and what is holding it back. The goal and "
                                 "the measure of progress are whatever that file says they are; "
                                 "if it is absent, no goal has been set.",

    # ── the Ouroboros tools: what a call reports back ─────────────────
    "tool.ingest_labs.done": "Files processed: {files}, points added: {points}, skipped: "
                             "{skipped}.",

    # ── verdicts and status lines computed by the engine ──────────────
    "disclaimer.general": "Not a diagnosis and not a prescription. Material for a conversation "
                          "with the treating doctor. The assistant does not change therapy "
                          "(see ASSISTANT-RULES.md).",
    "disclaimer.short": "Not a diagnosis. Material for a conversation with the treating doctor.",
    "disclaimer.prs": "A polygenic score is a statistical proxy, not a diagnosis. The models "
                      "are trained mostly on European cohorts; a percentile is a position in "
                      "the population, NOT a probability of disease. To be discussed with a "
                      "doctor.",
    "common.na": "n/a",
    "phenotype.not_covered": "the gene is not covered by the patient's data (a further test is "
                             "needed)",
    "phenotype.no_model": "there is no phenotype model for the gene — see the markers found",
    "phenotype.no_markers": "the gene's markers are absent from the patient's data",
    "phenotype.normal_default": "normal (by default)",
    "drug.no_name": "No drug was named.",
    "drug.nothing_notable": "Nothing notable in the markers available.",
    "drug.nothing_notable_ask": "Nothing notable in the markers available; check with the doctor.",
    "drug.not_found": "The drug «{drug}» was found neither in the project database nor in the "
                      "international RxNorm database (there may be no network, a typo, or a "
                      "narrow brand name). Enter the international name (INN) or discuss it "
                      "with the doctor / the package leaflet.",
    "drug.class_unknown": "class not determined",
    "drug.online_headline": "«{drug}» was found in the international RxNorm "
                            "database{class_note}. There is no direct pharmacogenetic marker "
                            "for it in the project database{tail}",
    "drug.online_class_note": " (class: {classes})",
    "drug.online_check_interactions": ". Interactions by class are checked below.",
    "drug.online_ask_doctor": "; to be assessed with the doctor.",
    "interactions.no_rules": "The drug was recognised (class: {atc}), but the database holds "
                             "no interaction rules for that class yet. Assess it with the "
                             "doctor.",
    "interactions.unknown_drug": "The drug was recognised neither locally nor in the "
                                 "international database. Check the spelling or discuss it "
                                 "with the doctor.",
    "prescription.class_undefined": "not determined",
    "gene.covered_by_vcf": "the full genome database covers the gene; the phenotype by star "
                           "alleles comes through PyPGx",
    "gene.vcf_pending": "the full genome database is being prepared (Track 2) — your variants "
                        "for this gene will be pulled in then",
    "near.no_history": "no history",
    "near.moved_from_baseline": "{delta} % against the personal baseline {baseline}",
    "bmi.under": "underweight",
    "bmi.normal": "normal",
    "bmi.over": "overweight",
    "bmi.obese": "obesity",
    "prs.from_a_genome_not_attached": "Computed on {date} from a genome file that is not "
                                      "attached right now. The numbers are stored results, not "
                                      "a live reading — which is why they can sit beside a "
                                      "«no data» mark for the VCF without either being wrong. "
                                      "Reconnect the file to recompute them.",
    "prs.not_computed": "The polygenic scores have not been computed yet (there is no "
                        "profile/prs_results.json).",
    "prs.weight_mass_low": "the model's variants were mostly found, but they carry only {pct} % of its WEIGHT — the percentile would be computed from a different model than the one published",
    "prevalence.flag.abnormal": "outside the reference interval",
    "prevalence.flag.near_limit": "inside the interval but pressed against its edge",
    "prevalence.flag.norange": "no corridor to compare against",
    "prevalence.flag.threshold": "a clinical action threshold crossed",
    "prevalence.title": "**How often each flag fires** — the check this project asks for before any interpretation",
    "prevalence.how_to_read": "A flag that marks nearly every object carries no information, however plausible its formula. This is arithmetic, not a verdict: a person whose panel really is all abnormal should see every marker flagged, and a rule that hid those flags because there were many would be worse than the defect it fixed.",
    "prevalence.row": "{what} — {hit} of {looked_at} ({pct} %)",
    "prevalence.notable": "⚠ fires on {pct} % of what it looked at — worth asking whether the rule is describing the person or the ruler",
    "prevalence.none": "nothing to measure yet: no laboratory markers are loaded",
    "prs.integrity_double": "coverage >1 — positions in the target VCF were counted twice (a "
                            "SNP and an indel at one coordinate); rebuild the input with "
                            "prs_genotype_sites.sh and recompute",
    "prs.category_other": "Other",
    "longevity.not_built": "The longevity layer has not been built yet (there is no "
                           "profile/longevity_findings.json).",
    "sources.chosen_folder": "chosen folder · {path}",
    "sources.local_folder": "local folder · {path}",
    "sources.labs": "Laboratory studies",
    "sources.medications": "Doctor's prescriptions",
    "sources.metrics": "Personal health metrics",
    "sources.lifestyle": "Lifestyle (wearable devices)",
    "sources.genome_vcf": "Full genome (VCF)",
    "sources.clinvar": "Clinically significant variants",
    "sources.clinvar_origin": "the international ClinVar database (NCBI)",
    "sources.ensembl": "rsID coordinates and annotations",
    "sources.ensembl_origin": "the international Ensembl REST database (GRCh38)",
    "sources.pgx": "Pharmacogenetics gene↔drug",
    "sources.pgx_origin": "the international CPIC / PharmGKB guidelines (a curated copy)",
    "sources.interactions": "Drug interactions",
    "sources.interactions_origin": "a curated database by class (CPIC / package leaflets)",
    "sources.catalog": "Catalogue of loci (coordinates)",
    "sources.catalog_origin": "the international Ensembl GRCh38 database",
    "sources.test_rules": "Rules for suggesting tests",
    "sources.test_rules_origin": "the project's rules (curated)",
    "radar.domain.lipids": "Lipids",
    "radar.domain.glucose": "Carbohydrate metabolism",
    "radar.domain.inflammation": "Inflammation",
    "radar.domain.hormones": "Hormones",
    "radar.domain.liver": "Liver",
    "radar.domain.micronutrients": "Vitamins",
    "radar.domain.renal": "Kidneys",
    "radar.domain.fitness": "Fitness",
    "lifestyle.metric.Weight": "Weight",
    "lifestyle.metric.BodyFat": "Fat",
    "lifestyle.metric.MuscleMass": "Muscle",
    "lifestyle.metric.VO2Max": "Fitness (VO₂max)",
    "lifestyle.metric.IntensityMinutesDaily": "Activity",
    "lifestyle.metric.StepsDaily": "Steps",
    "lifestyle.metric.HRV": "Recovery (HRV)",
    "lifestyle.metric.BodyBatteryHigh": "Body Battery",
    "lifestyle.metric.RestingHeartRate": "Resting heart rate",
    "brief.no_marker": "[no marker {key}]",
    "brief.no_metric": "[no metric {key}]",
    "brief.no_data": "no data",
    "brief.ref_range": " (ref {low}–{high})",
    "brief.ref_max": " (ref up to {high})",
    "brief.ref_min": " (ref from {low})",
    "brief.goal_now": "{now} → goal {target}",
    "brief.section_other": "Other",
    "brief.not_available": "the profile holds no profile/lifestyle_brief.json — the brief has "
                           "not been compiled yet",
    "focus.direction.up": "up",
    "focus.direction.down": "down",
    "focus.direction.flat": "unchanged",
    "focus.bedtime_share": "over the last {n} nights of the export the threshold was met "
                           "{share} % of the time, average lights-out {clock}",
    "focus.awake_mean": "over the last {n} nights of the export, time awake in bed averaged "
                        "{mean} min",
    "focus.journal_not_ready": "the log has been kept for {nights}; to tell alcohol and "
                               "atenolol apart at least {need} episodes of each kind are "
                               "needed (now {a} and {b})",
    "focus.journal_split": "alcohol without atenolol {a} min, alcohol with atenolol {b} min "
                           "(difference {delta})",
    "focus.not_set_reason": "the profile holds no profile/focus.json — no focus has been set",

    # ── the reverse check: a profile point against its source form ────
    "provenance.expr.homa_ir": "insulin × glucose / 22.5",
    "provenance.expr.atherogenic_index": "(TC − HDL) / HDL",
    "provenance.expr.free_androgen_index": "testosterone / SHBG × 100",
    "provenance.expr.ag_ratio": "albumin / (total protein − albumin)",
    "provenance.expr.non_hdl": "TC − HDL",
    "provenance.expr.ldl": "Friedewald: TC − HDL − TG/2.2",
    "provenance.expr.omega6_omega3_ratio": "omega-6 / omega-3",
    "provenance.no_labs": "labs.json is empty or was not found",
    "provenance.no_coverage": "there is no profile/labs_coverage.json — run reconcile (or "
                              "provenance --refresh)",
    "provenance.alt_form": "this month's forms give {values}; the marker has a preferred "
                           "method ({prefer}) — the value comes from it",
    "provenance.conflict": "the form(s) give {values}, the profile holds {value}",
    "provenance.no_form": "there is no form for this marker in this month",
    "provenance.derived_skipped": "not applicable (the formula's precondition)",
    "provenance.derived_mismatch": "the profile holds {value}, the components of the same "
                                   "month give {expected} ({expr})",
    "provenance.derived_nothing": "nothing to check against: the components {missing} are absent",
    "provenance.derived_orphan": "a derived index: this month's forms do not hold it, and "
                                 "there is nothing to recompute it from — the profile lacks "
                                 "{missing}",
    "provenance.derived_orphan_partial": " (only {present} is present)",
    "provenance.title": "# Reverse check: a profile point → the source form",
    "provenance.total": "Points in total: **{n}**",
    "provenance.count_form": "- ✅ confirmed by a form: {n}",
    "provenance.count_alt_form": "- ✅ a second method from the same draw (the preferred form): {n}",
    "provenance.count_derived_ok": "- ✅ a derived index that agrees with its components: {n}",
    "provenance.count_manual": "- ⚪ no form (manual entry / a paper conclusion): {n}",
    "provenance.count_conflict": "- 🔴 conflict with the form: {n}",
    "provenance.count_derived_bad": "- 🔴 a derived index that does not follow: {n}",
    "provenance.count_derived_orphan": "- 🔴 a derived index with no grounds (neither a form "
                                       "nor components): {n}",
    "provenance.defects_header": "## 🔴 Defects (need a decision)",
    "provenance.unverified_header": "## ⚪ Without provenance ({n}) — not a fact but «needs "
                                    "checking»",

    # ── writing commands and the notes left in the data directory ─────
    "store.unknown_source": "unknown source",
    "store.folder_not_found": "folder not found: {path}",
    "store.sources_purpose": "The data source folders the user chose. Personal.",
    "store.need_day_and_context": "a day and at least one of --reason / --between are needed",
    "store.no_repeat_that_day": "no marker on {day} has two measurements, so there is nothing to explain",
    "store.no_labs": "there is no laboratory history in the profile yet",
    "store.need_marker_date": "marker and date are required",
    "redact.no_file": "no file at {path}",
    "redact.no_patterns": "There is no .personal_patterns file, so only the structural classes were removed — your name and your sample number were not, because nothing here knows them. Create the file (it is outside git): printf '%s\n' 'Surname' 'SAMPLE-ID' 'mail@example.com' > .personal_patterns",
    "redact.title": "**Redacted text**",
    "redact.replaced": "Replaced: {what}.",
    "redact.replaced_none": "Nothing matched a rule. That is not a clean bill of health — see below.",
    "redact.notices_head": "**What this tool did NOT touch, because it cannot decide for you:**",
    "redact.notice_genotype": "genotype-shaped tokens — {n}. rsIDs, alleles and star alleles are your genome, and they are also what a bug report is usually about: decide each one.",
    "redact.notice_measurement": "numbers with a unit beside them — {n}. Those are your results.",
    "redact.footer": "Read the text below before you post it. A tool cannot tell a lab value from a version number, and an issue is public from the second it is filed.",
    "limits.prs_both_closes": "Two things withdrew this score and only one is yours to fix: re-genotyping the scoring sites from the BAM (src/ingest/prs_genotype_sites.sh) closes the coverage part, and leaves the rest exactly as it is — the reason above is about the model, not about the reading.",
    "limits.prs_model_why": "The score is withdrawn from trust by the model's own validity, not by the reading.",
    "limits.prs_measured_closes": "Nothing needs closing here: the quantity this model "
                                  "estimates has been measured in you directly — {name} {value} "
                                  "{unit} ({date}). A measurement outranks a percentile computed "
                                  "from variants; the score adds nothing to it.",
    "limits.prs_model_closes": "Nothing in your own data closes this — the limitation is in the model, not in what was read. Only a different model would, and where the trait is measured directly, the measurement answers the question outright.",
    "limits.interval_basis_locus": "measured over gene loci with a margin, not over the coding sequence: a small dropout inside a large gene barely moves this number, and a small dropout inside a large gene is the case it is usually consulted about",
    "limits.interval_basis_unknown": "what these percentages were measured over is not recorded — over the coding sequence and over a whole locus they mean different things, and the difference is not small",
    "limits.coverage_unknown": "The coverage of your genome has never been measured, so «nothing found» in a gene cannot be told apart from «not read».",
    "limits.coverage_closes": "Run `bash src/ingest/qc_callability.sh` — it needs mosdepth and the BAM, and it writes profile/callability.tsv.",
    "limits.coverage_what": "No negative genomic conclusion can be relied on.",
    "limits.no_genome_what": "Nothing can be said about the genome at all.",
    "limits.assembly_what": "Nothing can be said about the genome: the file is in {found}.",
    "limits.assembly_why": "The coordinate catalogue is written in {want}, and this file was called against {found}. Every locus would be looked up at the wrong position, so the genomic layer is switched off rather than allowed to answer.",
    "limits.assembly_closes": "Lift the file over to {want} (CrossMap, or bcftools +liftover with a chain file), or re-call the variants from the alignment against that build.",
    "limits.assembly_unknown_what": "The build of the genomic file has not been established.",
    "limits.assembly_unknown_why": "Neither the header nor the data settled it: no contig lengths, no `##reference`, and no variant past the end of chromosome 1 in GRCh38. Answers are computed as if the file were {want}; if it is not, every one of them is about the wrong position — and it will not look wrong.",
    "limits.assembly_unknown_closes": "Set `SCHOLION_GENOME_ASSEMBLY` to the build named in the sequencing report (GRCh37 · GRCh38 · T2T-CHM13v2.0) — that is the whole fix, and it takes one line. If nobody remembers, read it off the file: `bcftools view -h <file> | grep '##contig' | head -1`, where chr1 at 249250621 is GRCh37 and 248956422 is GRCh38. To settle it permanently: `bcftools reheader -f <reference>.fai <file>`.",
    "limits.no_genome_why": "No VCF is connected: every genomic answer would be about the absence of a file rather than about you.",
    "limits.no_genome_closes": "What closes it: a VCF built from your own reads, or an export from a laboratory. The route is described in `scholion doc preparing-the-genome`.",
    "limits.weak_gene_what": "A negative result in {gene} is not a statement.",
    "limits.weak_gene_why": "Only {pct} % of the gene's bases were read deeply enough to decide a heterozygote (>=10x); the rest was not read, and an unread base yields the same «no findings» as a clean one.",
    "limits.weak_gene_closes": "Deeper sequencing, or a targeted test of {gene} — the under-covered regions can be exported as a BED for it.",
    "limits.gene_not_read_what": "The pharmacogenetic phenotype of {gene} is not determined.",
    "limits.gene_not_read_why": "The gene's markers were not read.",
    "limits.gene_not_read_closes": "See the basis above: it names the positions and the way to genotype them.",
    "limits.no_corridor_what": "{n} markers are printed without a reference range and therefore without a flag.",
    "limits.no_corridor_why": "Neither your form nor the dictionary gives bounds for: {markers}. Showing them against somebody else's range would be worse than showing no flag.",
    "limits.no_corridor_closes": "Enter the range printed on your own form: `add-lab <marker> <date> <value> --unit ... --ref-low ... --ref-high ...`.",
    "limits.no_labs_what": "Nothing can be said about the laboratory layer.",
    "limits.no_labs_why": "There is not a single marker in the profile.",
    "limits.no_labs_closes": "`import-labs panel.csv` for a whole panel, or `add-lab` for one value; a folder of PDFs goes through `ingest-labs`.",
    "limits.prs_what": "The percentile for «{trait}» is withdrawn from trust.",
    "limits.prs_why": "Only {pct} % of the model's variants were called — a percentile computed on that is a number without a population behind it.",
    "limits.prs_closes": "Re-genotype the scoring sites from the BAM (src/ingest/prs_genotype_sites.sh), or pick a model with better coverage.",
    "limits.no_meds_what": "Nothing can be said about drug interactions or monitoring.",
    "limits.no_meds_why": "The list of prescriptions is empty, so «no interactions found» would mean «nothing was compared».",
    "limits.no_meds_closes": "`add-med` for each drug you take, with its dose.",
    "limits.no_wearables_what": "Nothing can be said about sleep, load or the trend of resting pulse.",
    "limits.no_wearables_why": "No wearable export has been loaded.",
    "limits.no_wearables_closes": "`ingest-garmin <export folder>`; Apple Health goes through the same layer.",
    "limits.title": "**What cannot be said from this data**",
    "limits.scope.title": "**What class of question this data can answer**",
    "limits.scope.input_wgs": "Input: a whole genome — every base the sequencing reached, so both single variants and polygenic scores are computable.",
    "limits.scope.input_array": "the input is a {vendor} genotyping array — {markers} chosen positions, not a genome",
    "limits.scope.array_monogenic": "NOT supported. A chip carries a probe for a handful of known variants per gene and nothing else, so «no pathogenic variant found» says only that these few probes were negative. A positive is a reason to order a confirmatory test, not a finding: measured predictive value for rare pathogenic variants on consumer arrays is low (BMJ 2021: 4.2 % for BRCA1/2; Moscarello 2019: 40 % of submitted variants false).",
    "limits.scope.array_oligogenic": "partly. Common pharmacogenetic tag SNPs are on most chips and are called reliably; star alleles that need copy number or phase (CYP2D6) are not resolvable from an array at all.",
    "limits.scope.array_polygenic": "partly. Polygenic scores were largely built on array data, so this is the architecture a chip suits best — with the ancestry caveat that applies to every score.",
    "limits.scope.input_none": "Input: no genomic file. Nothing below applies to the genome — only to labs, prescriptions and wearables.",
    "limits.scope.input_wrong_build": "Input: a genomic file in {found}, and the catalogue is in another build — the genomic layer is off. Everything below about the genome is unavailable until the file is lifted over; labs, prescriptions and wearables are unaffected.",
    "limits.scope.monogenic": "Monogenic traits (one variant decides): ClinVar and the ACMG secondary-findings layer. A positive finding is a reason for a clinical test, not a substitute for one; large deletions are not called by short reads at all.",
    "limits.scope.oligogenic": "Oligogenic traits (a handful of variants carry most of the effect): partially — the catalogued loci are read, the interaction between them is not modelled.",
    "limits.scope.polygenic": "Polygenic traits (many variants, each weak): a score plus what is actually measured in your labs. Where a direct measurement exists it outweighs the score, and the score is withdrawn from trust rather than argued with.",
    "limits.scope.heritability": "A percentile is not a probability, and inheritance explains only part of the variance of any of these traits — the rest is environment, behaviour and chance. The share differs by trait and is rarely the larger half.",
    "limits.none": "Every layer the system knows about is present and readable. That is not a promise that the answers are complete — it is a statement that nothing is missing that this check knows how to look for.",
    "limits.coverage_line": "Coverage: {genes} genes measured, on average {mean} % of bases at >=10x; ACMG SF panel {acmg_genes} genes at {acmg_pct} %.",
    "limits.coverage_weak_line": "Below 90 %: {n} genes.",
    "limits.closes_label": "closes it",
    "limits.summary": "{count} limitations, {closable} of them with a stated way to close.",
    "import.row": "row {row}",
    "import.dry_ok": "the file is clean: {n} rows would be imported. Nothing was written — this was a dry run.",
    "import.written": "imported: {n} rows",
    "import.markers": "Markers: {markers}",
    "import_csv.empty": "the file has no header row",
    "import_csv.missing_columns": "required columns are missing: {columns}. The header found: {seen}. Expected: marker, date, value, and optionally unit, ref_low, ref_high, note.",
    "import_csv.need_marker_date": "no marker or no date",
    "import_csv.value_not_number": "the value «{value}» is not a number",
    "import_csv.unknown_marker": "no such marker. Did you mean: {did_you_mean}",
    "import_csv.bad_unit": "the unit «{unit}» is not one this marker takes; accepted: {accepted}",
    "import_csv.file_not_found": "no file at {path}",
    "import_csv.unreadable": "{path} does not open as UTF-8 text: {error}",
    "import_csv.nothing_written": "{n} rows did not pass — NOTHING was written. A file is imported whole or not at all: half a panel in the profile looks like a whole one.",
    "import_csv.write_failed": "row {row} passed the check and failed on the write: {detail}. Nothing further was imported.",
    "store.marker_unknown": "no marker «{marker}» is known, and creating one silently is how a single test ends up as two series under two spellings — nothing was written. Did you mean: {did_you_mean}. To create it deliberately, pass --new together with a unit.",
    "store.no_candidates": "nothing close enough to suggest",
    "store.need_metric_date": "metric and date are required",
    "store.value_not_number": "value must be a number",
    "store.unit_not_accepted": "the unit «{unit}» is not one this marker takes, and a value stored in the wrong unit is compared against thresholds that belong to another scale — nothing was written. Marker {marker} accepts: {accepted}.",
    "store.unit_required": "a new series needs its unit: without one the number cannot be compared with anything, and assuming the usual unit is what this check exists to prevent. Marker {marker} accepts: {accepted}.",
    "store.need_name": "name is required",
    "store.no_medications_file": "medications.json was not found",
    "store.need_date": "a date is required",
    "store.focus_log_what": "A log of episodes for the focus of attention. PERSONAL.",
    "store.demo_occupied": "the directory holds data with no synthetic mark — it looks like a "
                           "real profile; the demo will not be written there (--force is "
                           "needed)",
    "store.templates_missing": "the templates were not found: {path} (the package is "
                               "incompletely built)",
    "store.slot_external": "{slot}/ (external storage)",
    "layout.readme.raw": """# raw — what came from outside

Lab forms, device exports, raw reads, reference databases.
**Nothing here is rewritten, only added to.** A source that gets edited
stops being a source: there is then no way to learn that a reading
was wrong.

The application does not write here, and reads only on an explicit command.

- `lab/` — the laboratory's forms and reports (PDF, DOCX)
- `sequencing/` — FASTQ, BAM and indices
- `wearables/` — Garmin, Apple Health and CGM exports
- `reference/` — the reference genome, ClinVar snapshots

The directory may live on another disk: `profile/sources.json`, key `raw`.
""",
    "layout.readme.raw_lab": """# The laboratory's forms and reports

PDF and DOCX exactly as they arrived. The parsed values go into `profile/`, the original stays here.
""",
    "layout.readme.raw_sequencing": """# Raw sequencing data

FASTQ, BAM and indices. Tens of gigabytes is normal here; the directory is meant
for an external disk.
""",
    "layout.readme.raw_wearables": """# Wearable device exports

Garmin archives, the Apple Health export, CGM screenshots — as the device handed them over.
""",
    "layout.readme.raw_reference": """# Reference databases

The comparison genome, ClinVar snapshots and everything else downloaded from public sources.
""",
    "layout.readme.work": """# work — the intermediate

**This directory can be deleted whole.** That is a definition, not a wish:
everything here is obliged to be recomputable by a command. A file that cannot
be restored does not belong here — its place is in `raw/` or `profile/`.

`cache/` lives here too — the answers of public reference books.

The directory may live on another disk: `profile/sources.json`, key `work`.
""",
    "layout.readme.archive": """# archive — what used to be

Retired versions of the profile's files. Code is under version control in git anyway;
the point of the archive is only `profile/`, which will never get into git.

Put one snapshot per meaningful change here, not one snapshot per save:
eleven versions of one file in a row are impossible to read, and nobody
will go through them later.
""",

    # ── why a gene matters for a drug class ───────────────────────────
    "gene_why.statin": "the risk of myopathy depends on the SLCO1B1 transporter",
    "gene_why.anticoagulant_vka": "sensitivity to warfarin (VKORC1/CYP2C9)",
    "gene_why.antiplatelet_p2y12": "the activation of clopidogrel depends on CYP2C19",
    "gene_why.ppi": "the metabolism of PPIs depends on CYP2C19",
    "gene_why.thiopurine": "the toxicity of thiopurines depends on TPMT/NUDT15",
    "gene_why.opioid_codeine": "the activation of codeine and tramadol depends on CYP2D6",

    # ── biological age (PhenoAge) ─────────────────────────────────────
    "phenoage.marker.albumin": "albumin",
    "phenoage.marker.creatinine": "creatinine",
    "phenoage.marker.glucose": "glucose",
    "phenoage.marker.crp": "hs-CRP",
    "phenoage.marker.lymph": "lymphocytes, %",
    "phenoage.marker.mcv": "MCV (CBC)",
    "phenoage.marker.rdw": "RDW (CBC)",
    "phenoage.marker.alp": "alkaline phosphatase",
    "phenoage.marker.wbc": "leukocytes (CBC)",
    "phenoage.unit.albumin": "g/L",
    "phenoage.unit.creatinine": "µmol/L",
    "phenoage.unit.glucose": "mmol/L",
    "phenoage.unit.crp": "mg/L",
    "phenoage.unit.lymph": "%",
    "phenoage.unit.mcv": "fL",
    "phenoage.unit.rdw": "%",
    "phenoage.unit.alp": "U/L",
    "phenoage.unit.wbc": "10⁹/L",
    "phenoage.rule": "PhenoAge is computed only from a complete panel of a single draw; "
                     "substituting values from other months is forbidden.",
    "phenoage.no_data": "There is no data in profile/labs.json.",
    "phenoage.incomplete": "Panel {panel}: PhenoAge cannot be computed — {n} of the 9 markers "
                           "are missing. Substituting them from earlier panels is forbidden; "
                           "order them with the next draw.",
    "phenoage.implausible": "PhenoAge not computed: {markers} look like a different unit than the formula expects — check the unit on the form. A wrong unit gives a confidently wrong age.",
    "phenoage.compute_failed": "PhenoAge not computed: the inputs did not yield a valid result (most likely a value in an unexpected unit).",
    "phenoage.no_age": "The age is unknown: add birth_date to profile/metrics.json.",
    "phenoage.history_header": """# History of the biological age (PhenoAge)

> Complete panels only: all 9 markers from one draw.

| Date | Chrono | PhenoAge | Δ | 10-yr risk |
|---|---|---|---|---|
""",
    "phenoage.panels_title": "## PhenoAge — completeness of the panels",
    "phenoage.panels_lead": "Only panels where all 9 markers come from one draw are counted.",
    "phenoage.panel_complete": "- **{panel}** [9/9] ✅ complete",
    "phenoage.panel_incomplete": "- {panel} [{have}/9] ❌ missing: {missing}",
    "phenoage.cannot_title": "## ❌ PhenoAge for panel {panel}: cannot be computed",
    "phenoage.cannot_missing": "{n} of the 9 markers are missing: {missing}.",
    "phenoage.have_in_panel": "Present in the panel: {items}.",
    "phenoage.request_next": "**Add to the next panel** (in the same draw as everything else):",
    "phenoage.no_substitution": "These values must not be substituted from earlier panels — "
                                "the result would be untrustworthy (the formula is sensitive "
                                "to albumin and creatinine).",
    "phenoage.title": "## PhenoAge — panel {panel}",
    "phenoage.chrono_age": "- Chronological age: **{value}**",
    "phenoage.value": "- PhenoAge: **{value}**  (Δ {delta} years)",
    "phenoage.mortality": "- Modelled 10-year mortality risk: **{value}%**",
    "phenoage.source": "Source — this panel alone: {items}.",
    "phenoage.caveat": "Not a diagnosis: PhenoAge is a population model over 9 routine markers "
                       "(Levine 2018) and is sensitive to one-off swings (glucose, CRP, "
                       "creatinine).",
    "phenoage.tracked": "→ written to profile/biological_age_history.md",

    # ── reconciliation of the lab forms: reasons, assay methods, the self-check banner ───
    "reconcile.candidate_hint": "A folder that looks like forms lies next to the data directory: {path}. It is NOT read on a guess — name it once: SCHOLION_LABS_DIR='{path}', or pass --lab-dir, or move the forms into raw/lab/.",
    "reconcile.no_folder": "The folder of forms was not found: {path}. Give --lab-dir PATH or "
                           "set SCHOLION_LABS_DIR.",
    "reconcile.autodetect_failed": "(the automatic search found nothing)",
    "reconcile.no_text_layer": "no text layer (a scan?)",
    "reconcile.empty_file": "an empty or unreadable file",
    "reconcile.marker_absent": "the marker is absent from the profile",
    "reconcile.point_absent": "there is no point for this date",
    "reconcile.coverage_note": "Provenance: marker → month → source file and the exact draw "
                               "date. Regenerated.",
    "reconcile.coverage_not_written": "(not written: {error})",
    "form.lcms": "LC-MS/MS",
    "form.clia": "CLIA",
    "form.elisa": "ELISA",
    "form.icpms": "ICP-MS",
    "form.biochemistry": "biochemistry",
    "form.cbc": "CBC",
    "form.urine": "urine",
    "selfcheck.failed": "⚠️ The lab self-check did not run: {error}",
    "selfcheck.unreadable": "⚠️ Lab integrity: {n} UNREADABLE form(s) — data may be lost.",
    "selfcheck.unreadable_hint": "   → open these files on the Mac (iCloud will materialise "
                                 "them), then run the check again.",
    "selfcheck.ok": "✅ Lab integrity: OK — there are no unreadable forms.",
    "selfcheck.counters": "   forms: {files} · points matched: {covered} · for a manual check: "
                          "{missing} omission(s) / {mismatch} discrepanc(ies) (in detail: "
                          "scholion reconcile)",

    # ── the Garmin export ─────────────────────────────────────────────
    "garmin.builder_missing": "{path} was not found",
    "garmin.candidate_hint": "A wearable export lies next to the data directory: {path}. It is NOT read on a guess — name it once with `scholion set-folder garmin '{path}'`, pass the folder as an argument, or move it into raw/wearables/.",
    "garmin.no_export": "No garmin_export folder (holding DI_CONNECT) was found. Download a "
                        "fresh Garmin GDPR export (Connect → Account settings → Export data), "
                        "unpack it into garmin_export next to the project — or give the path "
                        "explicitly.",
    "garmin.parse_failed": "Garmin parsing failed: {error}",
    "garmin.nothing_recognised": "No recognisable Garmin data was found in {path}.",
    "garmin.nightly_source": "Garmin Connect (GDPR export), sleepData.json",
    "garmin.nightly_note": "Sleep phases before 2022 are not comparable with the current ones: "
                           "the old device marked up to 81 % of the night as «deep sleep». "
                           "bedtime_min_from_20 is minutes from 20:00 local time (MSK).",

    # ── the full genome: calls, coordinates, ClinVar tiers ────────────
    "genome.confirmed_ref_short": "the reference confirmed by a call at the site (0/0)",
    "genome.no_coordinates_for_assembly": "the catalogue has no {assembly} coordinate for {rsid}, and this file is called against {assembly}. Nothing is converted between builds here: the offset is not constant even within one chromosome, so a converted position would point at a real base that is the wrong one. This locus stays unread until its {assembly} coordinate is added from a primary source.",
    "genome.confirmed_ref": "the reference was confirmed by a call at the site (0/0), not "
                            "inferred from a missing row",
    "genome.low_depth_suffix": "; depth is low ({depth} reads) — the call is unreliable",
    "genome.low_depth": "depth is low ({depth} reads) — the call is unreliable",
    "array.not_on_chip": "this position is not on the {vendor} array at all — it was never interrogated, so nothing about it has been ruled in or out",
    "array.no_call": "the array carries this position but the call failed — no genotype, and that is not the same as no variant",
    "array.strand_ambiguous": "⚠ this locus ({gene}) has alleles {ref}/{alt} — its own complement. If the export reported the other strand the call would look correct and be wrong, and an array gives no way to tell. Treat it as needing confirmation, not as a result.",
    "array.path_closed": "This path is closed for a genotyping array. A chip carries a probe for a handful of known variants per gene and no depth at all, so «nothing found» would mean only that those few probes were negative — and a positive would more often be wrong than right (BMJ 2021: 4.2 % predictive value for BRCA1/2 on consumer arrays; Moscarello 2019: 40 % of submitted variants false). It stays closed until a frequency floor and an input-quality label exist.",
    "array.open_instead": "What an array DOES answer: the locus catalogue — common pharmacogenetic and trait variants, the register a chip is built for. `scholion genome --gene CYP2C19`, `scholion drug <name>`, `scholion array` for the coverage of this chip against the catalogue.",
    "array.coverage_title": "**This array against the locus catalogue**",
    "array.coverage_line": "{called} of {total} catalogue loci called ({pct} %) · {no_call} failed to call · {absent} not on the chip",
    "array.absent_header": "Not carried by this chip — nothing is ruled in or out for these:",
    "array.ambiguous_header": "Called, but ambiguous by strand — treat as needing confirmation:",
    "array.unreadable": "a {vendor} export is here and not one row could be read from it — that is a failure to read the file, NOT a statement about the chip. Nothing is ruled in or out until it parses: check that the file is complete, and if it was opened and re-saved in a spreadsheet, keep the original download.",
    "array.no_array": "no genotyping array found (set SCHOLION_ARRAY_FILE, or put the export in the genome folder)",
    "array.assembly_declared": "the export states its build in its own header: {assembly} — loci are matched by rsID, which does not depend on it",
    "array.called": "called from a {vendor} genotyping array",
    "array.what_it_cannot_do": "A genotyping array reads a few hundred thousand chosen positions, not a genome. It cannot find a variant it does not carry a probe for, its rare-variant calls are unreliable enough that a positive needs confirmation by another method, and it says nothing about the positions it lacks. Anything this build reports from an array carries that ceiling.",
    "array.summary": "Genotyping array: {vendor}, {markers} positions. Not a sequenced genome — see the ceiling below.",
    "genome.assumed_ref_note": "the site is not in the variant VCF: this is either the "
                               "reference or a lack of coverage — to tell them apart, genotype "
                               "the positions from the BAM (src/ingest/loci_sites_bed.py + "
                               "prs_genotype_sites.sh)",
    "genome.rsid_unknown": "rsID {rsid} was found neither in the catalogue nor in Ensembl (or "
                           "there is no network).",
    "genome.coordinate_only": "The coordinate was found, but the full genome database is not "
                              "connected yet (genome/*.vcf.gz + .tbi are needed).",
    "genome.need_rsid_or_gene": "an rsid or a gene is required",
    "genome.clinvar_not_run": "Your VCF has not been annotated against ClinVar yet. The "
                              "annotation is part of preparing the genome — "
                              "`scholion doc preparing-the-genome`.",
    "genome.conflict": "The laboratory report and your own reads disagree here: the report says "
                       "{reported}, the reads say {called}. Shown above is what the reads say — "
                       "they carry a depth and can be re-examined, and the report was made from "
                       "them. A disagreement of this kind is worth taking to whoever issued the "
                       "report.",
    "genome.confirmed_by_report": "Your own reads and a laboratory report agree at this position.",
    "genome.acmg_not_run": "Your VCF has not been checked against the ACMG SF list yet. The "
                           "scan is part of preparing the genome — "
                           "`scholion doc preparing-the-genome`.",
    "genome.apoe_ambiguous": "Both SNPs are heterozygous, and that genotype is {a} or {b} depending on which allele sits on which chromosome — a fact this file does not carry. {a} is far more common in every studied population, which is a reason to say which is likely, not a reason to print it as the answer. Phasing, or a parent's genotype, settles it.",
    "genome.apoe_unexpected": "rs429358 {a} with rs7412 {b} is not a combination the epsilon haplotypes produce — check the calls before reading anything into them",
    "genome.indels_not_left_aligned": "⚠ Insertions and deletions in this list were matched WITHOUT left-alignment: the annotation ran with no reference FASTA, so an indel spelled differently from ClinVar's copy was not found rather than found and dismissed. Substitutions are unaffected. Set SCHOLION_REFERENCE_FASTA and re-run `annotate_clinvar.sh` to close this.",
    "genome.apoe_note": "the ε status is approximate without phasing; confirm it for clinical use.",
    "clinvar.tier.pathogenic": "Pathogenic / likely pathogenic",
    "clinvar.tier.pathogenic.hint": "worth knowing: a link to a disease, or carrier status",
    "clinvar.tier.drug": "Pharmacogenetics",
    "clinvar.tier.drug.hint": "affects the choice or the dose of medicines — to be discussed "
                              "with the doctor (see «Drugs»)",
    "clinvar.tier.risk": "Risk factors",
    "clinvar.tier.risk.hint": "raise the risk moderately — context for screening, not a diagnosis",
    "clinvar.tier.protective": "Protective",
    "clinvar.tier.protective.hint": "a variant with a protective effect",
    "clinvar.tier.association": "Weak associations (GWAS)",
    "clinvar.tier.association.hint": "a statistical link of little strength; not something to "
                                     "act on",
    "clinvar.tier.uncertain": "Ambiguous / uncertain",
    "clinvar.tier.uncertain.hint": "the experts did not agree — as a rule, not a risk",

    # ── instrumental studies and doctors' conclusions ─────────────────
    "studies.kind_default": "a study",
    "studies.from_conclusion": "from the conclusion",
    "studies.no_pdf_reader": "No PDF reader was found: pip3 install pdfplumber",
    "studies.folder_not_found": "Folder not found: {path}",
    "studies.meta_what": "PERSONAL instrumental studies and doctors' conclusions.",
    "studies.hint": "The loader does NOT fill in the answers/does_not_answer fields — that is "
                    "a judgement. Go through the new entries and write down which questions "
                    "the study answers and which it does not.",

    # ── ingest of lab PDFs ────────────────────────────────────────────
    "ingest_labs.reason_several_dates": "the table carries {n} different draw dates ({first} … {last}); this importer places a whole file at one date, and choosing one of several would be a guess about someone's results",
    "ingest_labs.reason_ambiguous_date": "the form carries «{raw}», which is either {first} or {second} — nothing on the page says which order this laboratory prints, and a point filed under the wrong month joins a series and moves a trend. Enter the draw date yourself with `scholion add-lab`, or use an export that states it in full",
    "ingest_labs.date_from_filename": "the date {date} was taken from the FILE NAME, not from the form — the page itself states none. A file is named by whoever saved it, often on the day they downloaded it",
    "ingest_labs.reason_no_date": "no draw date could be found on the form",
    "ingest_labs.reason_no_text": "the file carries no extractable text (a scan without OCR)",
    "ingest_labs.reason_table_labels": "{n} row labels in this table match no marker in the dictionary — they are listed rather than stored under an approximate name",
    "ingest_labs.reason_no_marker": "the date was read, but not one row matched a known marker",
    "fhir.title": "**FHIR bundle:** {path} — {observations} observations",
    "fhir.dry_run": "would take {n} results (nothing written)",
    "fhir.added": "taken into the profile: {n}",
    "fhir.refused": "{label} — not written: {reason}",
    "fhir.not_taken": "**Not taken, by reason:**",
    "fhir.reason.no_quantity": "no numeric value in the resource (a coded result, a panel that only groups its members, an attachment)",
    "fhir.reason.loinc_not_in_catalogue": "the LOINC code is not in this build's dictionary — matching by display name instead would be a guess about which analyte it is",
    "fhir.reason.no_loinc": "the observation carries no LOINC code at all",
    "fhir.reason.no_date": "no effective date, and a result without a date has no place in a series",
    "fhir.reason.not_final": "the source itself has not finalised this result (status other than final/amended/corrected)",
    "fhir.profile_facts": "the bundle also states {facts} about its patient. NOT applied: a file may hold a relative, a sample or two people, and taking an identity from a file is the error that then contaminates everything downstream. Set them yourself if they are yours: `scholion init --sex … --birth-year …`",
    "fhir.unreadable": "{path} could not be read as JSON: {error}",
    "fhir.not_a_bundle": "this is a FHIR resource of type «{kind}», not a Bundle. Export the whole bundle — a single resource carries no history",
    "ingest_labs.folder_empty": "there is no result file in {path} — neither a PDF nor a CSV/TSV/TXT export",
    "ingest_labs.no_pdf_reader": "No PDF reader was found. Install one from the terminal: pip3 "
                                 "install pdfplumber",
    "ingest_labs.folder_not_found": "Folder not found: {path}",

    # ── network access from this Python ───────────────────────────────
    "net.offline": "SCHOLION_OFFLINE=1 — network requests are switched off",
    "server.remote_bind_refused": "refusing to bind {host}: only loopback is allowed, because the profile would otherwise be exposed to the network. Set SCHOLION_ALLOW_REMOTE=1 to override deliberately.",
    "prs.offline": "SCHOLION_OFFLINE=1 — the polygenic-score server is not started (uvx would fetch it from PyPI)",
    "sources.kind.mirror": "Carried in this build, and updated upstream — {n}",
    "sources.kind.pipeline": "Downloaded by the genome pipeline — {n}",
    "sources.kind.live": "Asked at query time, nothing stored — {n}",
    "sources.license_line": "licence: {license}",
    "sources.line_bundled_stamped": "the copy that shipped with the package ({date})",
    "sources.manual.reference": "the reference genome and its annotation are tens of gigabytes; the genome pipeline fetches them once",
    "sources.manual.live": "nothing is stored, so there is nothing to import: the address is asked only when a drug or a locus is missing from the local base, and only that name is sent",
    "sources.title": "**Reference sources** — what this build mirrors, and when it was last brought in",
    "sources.how_to_read": "A source that updates upstream needs an import path, or the mirror drifts away from what it claims. `scholion sources --refresh` brings in the ones that can be automated; the rest name what has to be done by hand and why.",
    "sources.auto_header": "Imported automatically — {n}",
    "sources.manual_header": "By hand — {n}",
    "sources.line_local": "refreshed on this machine ({date})",
    "sources.line_bundled": "the copy that shipped with the package",
    "sources.cadence": "changes upstream: {text}",
    "sources.offline": "SCHOLION_OFFLINE=1 — an import would have to reach the network, so it is not started",
    "sources.fetch_failed": "could not read {url}",
    "sources.refreshed": "{source}: {n} allele definitions checked, {changed} changed",
    "sources.no_changes": "{source}: checked, nothing had drifted",
    "sources.manual.generic": "this source cannot be imported automatically",
    "sources.manual.mane": "Not imported automatically because it changes the SHAPE of a measurement rather than a value in the base: callability is currently computed over the gene locus with a 10 kb margin, and MANE Select would move it onto the coding sequence of one agreed transcript plus the splice sites. That is a pipeline change with its own reference files, and it has to be a deliberate step with the old and new numbers compared side by side — not a background refresh that quietly changes what a percentage means.",
    "sources.manual.clinvar": "ClinVar is annotated against your own genome, which needs bcftools and the genome pipeline rather than a catalogue download",
    "sources.manual.pgs": "a PGS model is pinned deliberately: adopting a new one breaks the series, so it is a decision, not a refresh",
    "sources.manual.eflm": "this would replace the flat 10 % «at the edge» zone with a per-analyte reference change value — the numbers are within-person biological variation coefficients, which come from this database and from nobody's memory. Registration and a per-analyte review are what stand between here and there.",
    "sources.manual.loinc": "LOINC requires a registered account and accepting its terms, and the mapping of a code to a marker needs medical verification",
    "sources.manual.acmg": "the ACMG secondary-findings list is published in a paper; a person reads it and records the version",
    "sources.manual.longevitymap": "the licence forbids bundling, so the build script fetches it into your own copy",
    "sources.init_hint": "Reference sources: `scholion sources` shows what this build mirrors; `scholion sources --refresh` brings in what can be imported automatically (CPIC today). Nothing is fetched without that command.",
    "net.diag_host_refused": "the connectivity check only probes the reference hosts this tool uses, over https — an arbitrary address is not fetched",
    "net.offline_deliberate": "SCHOLION_OFFLINE=1 — network requests are switched off deliberately",
    "net.offline_hint": "unset the SCHOLION_OFFLINE environment variable if the network is wanted",
    "net.certificates_hint": "This looks like Python on a Mac having no root certificates. Run "
                             "once in the terminal: /Applications/Python\\ 3.13/Install\\ "
                             "Certificates.command (or: pip3 install --upgrade certifi).",
    "net.tls_verify_failed": "Certificate verification failed — the request was cancelled. An "
                             "answer over an unverified channel can be substituted, and the drug "
                             "class and the gene↔drug pair are taken from it. To skip the check "
                             "deliberately: SCHOLION_TLS_INSECURE=1.",
    "net.tls_insecure_warning": "⚠ SCHOLION_TLS_INSECURE=1 — the certificate is NOT verified, "
                                "the answer can be substituted.",

    # ── computing polygenic scores against the PGS Catalog ────────────
    "prs.no_uvx": "uvx was not found — install uv (https://docs.astral.sh/uv)",
    "prs.server_silent": "the just-prs server exited without an answer",
    "prs.search_empty": "search_scores: an empty answer",
    "prs.no_coverable_models": "no coverable models (all of them genome-wide or without metadata)",
    "prs.fallback_chosen": "    fallback search_scores → {pgs_id} ({variants} variants), "
                           "match_rate={rate}",
    "prs.no_traits": "no traits (prs_traits.json is empty, or the --only filter matched nothing)",
    "prs.vcf_not_found": "VCF not found: {path}",
    "prs.normalising": "→ normalising the genome into genotypes (a full VCF takes minutes; the "
                       "result is cached)…",
    "prs.normalised": "  ✓ normalised: {path}",
    "prs.normalise_failed": "  ⚠ normalisation failed ({error}) — computing from the raw VCF "
                            "(slower)",
    "prs.args_rejected": "    ⚠ the server did not accept {args} — retrying without them",

    # ── reading the tabix index ───────────────────────────────────────
    "genome.bad_tabix": "{path}: this does not look like a tabix index",

    # ── the language switcher: every language is named in itself ─────────
    "web.lang.en": "English",
    "web.lang.ru": "Русский",

    # ── web: the page frame ──────────────────────────────────────────────
    "web.header.subtitle": "genome · labs · prescriptions",
    "web.header.local_badge": "runs locally · the assistant is optional",
    "web.header.local_badge_hint": "Why this matters and how to connect a model — the «Assistant» "
                                   "tab",
    "web.header.disclaimer": "Not a diagnosis and not a prescription. Material for a conversation "
                             "with your doctor. The assistant does not change therapy.",
    "web.header.build": "build {version}",
    "web.header.language": "Interface language",

    # ── web: the tabs ────────────────────────────────────────────────────
    "web.tab.overview": "Overview",
    "web.tab.labs": "Labs",
    "web.tab.drugs": "Drugs",
    "web.tab.genome": "Genome",
    "web.tab.lifestyle": "Lifestyle",
    "web.tab.tests": "What to test",
    "web.tab.second_opinion": "Second opinion",
    "web.tab.prescriptions": "Prescriptions",
    "web.tab.assistant": "Assistant",

    # ── web: words shared by every screen ────────────────────────────────
    "web.common.loading": "loading…",
    "web.common.error": "error",
    "web.common.error_prefix": "Error: ",
    "web.common.failed": "did not work out",
    "web.common.failed_prefix": "Did not work out: ",
    "web.common.canceled": "Cancelled",
    "web.common.folder_chosen": "Folder chosen ✓",
    "web.common.folder_reset": "Folder reset",
    "web.common.opening_picker": "Opening the folder picker…",
    "web.common.added": "Added ✓",
    "web.common.saved": "Saved ✓",

    # ── web: the source chips ────────────────────────────────────────────
    "web.source.release": "version {release}",
    "web.source.updated": "updated {date}",
    "web.source.synced": "synced {date}",
    "web.source.absent": "no data",
    "web.source.pick_btn": "folder",
    "web.source.pick_title": "Choose the folder with the data on disk",
    "web.source.reset_title": "Return to the default folder (profile)",
    "web.source.local_label": "Local profile",
    "web.source.local_kinds": "labs, prescriptions, metrics, genome",
    "web.source.profile_updated": "updated {date}",
    "web.source.public_label": "International databases",

    # ── web: the status vocabulary of the badges ─────────────────────────
    "web.flag.high": "above range",
    "web.flag.low": "below range",
    "web.flag.ok": "within range",
    "web.flag.near": "at the edge",
    "web.flag.unknown": "no data",
    "web.level.high": "important",
    "web.level.moderate": "attention",
    "web.level.low": "ok",
    "web.level.unknown": "no data",
    "web.severity.high": "high risk",
    "web.severity.moderate": "attention",
    "web.severity.low": "low",
    "web.near.margin": "{pct}% to the {side} bound {bound}",
    "web.near.corridor": "{pct}% of the corridor width",
    "web.decision.crossed": "action threshold crossed: {label} ({sign} {value})",
    "web.decision.not_reached": "action threshold {value} ({label}) — not reached",

    # ── web: the goal dashboard ──────────────────────────────────────────
    "web.goal.not_set": "No goal has been set yet. The shape of one, filled in, is in "
                        "profile/health_goals.json under `_meta._example`.",
    "web.goal.title": "Your goal for the indicators",
    "web.goal.as_of": "data as of {date}",
    "web.goal.in_one_phrase": "In one phrase:",
    "web.goal.targets_h": "Target values",
    "web.goal.col_marker": "Marker",
    "web.goal.col_now": "Now",
    "web.goal.col_best": "Your best (year)",
    "web.goal.col_target": "Goal",
    "web.goal.lg_now": "now",
    "web.goal.lg_best": "historical best",
    "web.goal.lg_target": "goal",
    "web.goal.lg_window": "your reference window",
    "web.goal.body_h": "Weight and body composition",
    "web.goal.weight": "Weight",
    "web.goal.bodycomp": "Body composition",
    "web.goal.metabolism_h": "Metabolism and hormones",
    "web.goal.fitness_h": "Aerobic fitness and the liver",
    "web.goal.aerobic": "Aerobic fitness",
    "web.goal.ldl_alt": "LDL/ALT",
    "web.goal.ds_fat": "Fat %",
    "web.goal.ds_muscle": "Muscle",
    "web.goal.note": "The data is live, from the same model the rest of the application reads "
                     "(labs + wearable + scales). After a new lab panel or a weigh-in the points "
                     "appear on their own; read them against the yellow target lines and the green "
                     "reference window, both of which come from the goal you set in "
                     "health_goals.json. Where body composition is the goal, the key metric is "
                     "{key_metric}, not the number on the scales alone.",
    "web.goal.note_key": "fat down with muscle held",
    "web.goal.chart_nodata": "No series here yet — the chart appears once there are "
                             "measurements to draw.",
    "web.goal.charts_unavailable": "Charts are unavailable (chart.min.js did not load). Restart "
                                   "the application and refresh the page.",

    # ── web: overview ────────────────────────────────────────────────────
    "web.header.subject": "subject {subject}",
    "web.header.genome_gaps": "{n} target genes not read from a genome",
    "web.header.demo_banner": "DEMO — a fictional person. Nothing on these screens is about "
                              "you: the numbers, the prescriptions and the genotypes are "
                              "generated. Run «scholion init» for your own profile.",
    "count.prescriptions.one": "{n} prescription",
    "count.prescriptions.few": "{n} prescriptions",
    "count.prescriptions.many": "{n} prescriptions",
    "web.overview.focus_h": "Focus of attention",
    "web.overview.watched_h": "Markers under control",
    "web.overview.stat_above": "of them above the ceiling",
    "web.overview.stat_below": "of them below the floor",
    "web.overview.stat_abnormal": "out of range, of markers measured",
    "web.overview.stat_suggested": "tests to take",
    "web.overview.stat_note": "The second and third numbers split the first by direction — "
                              "below a floor is not milder than above a ceiling. The fourth "
                              "is the list on the «What to test» tab.",
    "web.overview.red_h": "Out of range now",
    "web.overview.red_window": "over the last 12 months",
    "web.overview.stale_hidden": "Another {count} older than 12 months is hidden — see the «Labs» "
                                 "tab.",
    "web.overview.tests_h": "What to take",
    # Two different facts, and the old sentence covered both with the reassuring
    # one: nothing is flagged because nothing is out of range, or because nothing
    # has been measured. The count is what tells them apart.
    "web.overview.no_red": "Nothing outside its range among the {n} markers measured.",
    "web.overview.no_red_nodata": "Nothing has been measured yet, so there is nothing to "
                                  "flag. Load lab results and this line will mean something.",
    # Same defect as `web.tests.none_pending`, and on the FIRST screen.
    "web.overview.no_priority_tests": "No new order comes out of what is in the profile right "
                                      "now. Routine control and repeat intervals are on the "
                                      "«What to test» tab.",

    # ── web: focus of attention ──────────────────────────────────────────
    "web.focus.track_tip": "baseline {base} · now {now} · target {target}",
    "web.focus.baseline": "baseline {value}",
    "web.focus.target": "target {value} {unit}",
    "web.focus.since": "since {date}",
    "web.focus.vs_baseline": "{delta} vs baseline",
    "web.focus.mean_over": "mean of {n} nights {from} → {to}",
    "web.focus.levers_h": "Levers — what your own data shows",
    "web.focus.expected_prefix": "expected ",
    "web.focus.now": "now: {text}",
    "web.focus.journal_h": "Episode log",
    "web.focus.journal_count": "· {n} entries",
    "web.focus.journal_empty": "· still empty",
    "web.focus.alcohol_none": "no alcohol",
    "web.focus.alcohol_light": "1–2 drinks",
    "web.focus.alcohol_heavy": "more",
    "web.focus.atenolol": "atenolol 50 mg",
    "web.focus.late_meal": "late heavy dinner",
    "web.focus.note_placeholder": "note",
    "web.focus.save": "Log it",
    "web.focus.questions_h": "The questions that follow from this",
    "web.focus.entry_removed": "Entry removed ✓",
    "web.focus.entry_saved": "Logged ✓ · {n} in total",
    "web.focus.save_failed": "Could not log it",

    # ── web: labs ────────────────────────────────────────────────────────
    "web.labs.within_h": "Inside their range ({n})",
    "web.labs.title": "Labs: {abnormal} out of range of {total}",
    "web.labs.pick_docs": "Folder of studies (PDF)",
    "web.labs.reingest": "Refresh from the folder",
    "web.labs.add_manually": "Add by hand",
    "web.labs.docs_folder_set": "Folder of studies: {path}. The «Refresh» button makes the "
                                "application parse the PDFs and rebuild the lab summary itself — "
                                "labs.json is created automatically, there is nothing to pick.",
    "web.labs.docs_folder_unset": "Point at ONE folder with the source PDFs (e.g. «Laboratory "
                                  "studies»). The application will extract the markers with their "
                                  "dates and build the lab summary itself — there is no separate "
                                  "labs.json to pick.",
    "web.labs.reading_pdf": "Reading the PDFs from the folder…",
    "web.labs.ingest_files": "Files processed: {n}",
    "web.labs.ingest_points": ", points added: {points}, skipped (unchanged / not lab reports): "
                              "{skipped}.",
    "web.labs.ingest_nothing_new": "No new markers found (it may all be loaded already).",
    "web.labs.points_added": "{n} points added ✓",
    "web.labs.no_new_data": "There is no new data",
    "web.labs.add_note": "The new point goes into labs.json (profile). The tools and the trends "
                         "update immediately.",
    "web.labs.genome_link": "genome: {text}",

    # ── web: the add forms ───────────────────────────────────────────────
    "web.form.marker": "Marker",
    "web.form.new_option": "— new —",
    "web.form.date_month": "Date (YYYY-MM)",
    "web.form.date_day": "Date (YYYY-MM-DD)",
    "web.form.value": "Value",
    "web.form.save": "Save",
    "web.form.key": "Key",
    "web.form.name": "Name",
    "web.form.name_placeholder": "My marker",
    "web.form.unit": "Unit",
    "web.form.ref_from": "Normal from",
    "web.form.ref_to": "Normal to",
    "web.form.fill_required": "Fill in the marker, the date and the value",

    # ── web: the drug check ──────────────────────────────────────────────
    "web.drug.title": "Prescription check",
    "web.drug.intro": "«Full check» = pharmacogenetics + interactions with your current "
                      "prescriptions + monitoring. It prepares a second opinion for the "
                      "conversation with the doctor.",
    "web.drug.placeholder": "drug name, e.g. metformin or aspirin",
    "web.drug.full_check": "Full check",
    "web.drug.pgx_only": "Pharmacogenetics only",
    "web.drug.names_note": "Local names are resolved automatically: the local database first, "
                           "then the international RxNorm (translation / active substance). Only "
                           "that second step goes to the network, and the only thing sent is the "
                           "drug name you typed — never your profile, your labs or your genome. "
                           "Without a connection the local database answers alone.",
    "web.drug.checking_full": "checking (including the international database)…",
    "web.drug.checking": "checking…",
    "web.drug.found_online": "found online",
    "web.drug.gene": "gene",
    "web.drug.resolved_online": "resolved online",
    "web.drug.phenotype_label": "Patient phenotype:",
    "web.drug.discuss": "What to discuss with the doctor:",
    "web.drug.rxnorm_source": "source: RxNorm/RxClass (the international NLM database)",
    "web.diag.no_internet": "The application has no internet access",
    "web.diag.online_search_off": "Online lookup of drugs and genes is unavailable right now:",

    # ── web: dose and critical context ───────────────────────────────────
    "web.dose.title": "Dose and critical context",
    "web.dose.subtitle": "numbers and references, not «the right direction»",
    "web.dose.doses": "Doses: nutritional {nutritional} · pharmacological {pharmacologic}",
    "web.dose.effect": "effect: {text}",
    "web.dose.by_dose": "on the dose: {text}",
    "web.dose.your_numbers": "your numbers:",
    "web.dose.not_measured": "not taken",
    "web.dose.forms": "Forms: {text}",
    "web.dose.alternatives_h": "What is discussed as an alternative",
    "web.dose.melatonin": "melatonin/sleep: {text}",
    "web.dose.metabolic": "metabolic: {text}",
    "web.dose.caveat": "caveat: {text}",

    # ── web: the second opinion on one prescription ──────────────────────
    "web.rx.title": "Second opinion: {drug}",
    "web.rx.overall": "verdict: {level}",
    "web.rx.class": "class: {name}",
    "web.rx.not_identified": "not recognised in the databases",
    "web.rx.local_db": "local database",
    "web.rx.pgx_unchecked": "Pharmacogenetics was NOT checked against CPIC — {why}. That is not "
                            "the same as «this drug has none».",
    "web.rx.labs_no_rule": "The catalogue holds no lab-monitoring rule for this class ({classes}) — "
                           "which is not the same as «no monitoring is needed».",
    "web.rx.labs_class_unknown": "The class of this drug was not determined, so nothing can be said "
                                 "about lab monitoring.",
    "web.rx.no_pgx": "No meaningful pharmacogenetics for this drug (CPIC): there are no genes that "
                     "affect the dose or the effect.",
    # Not a phrase but a sentinel: `engine.py` writes exactly this word into `cpic_level`
    # to mark a gene that came from the project's own base rather than from a CPIC level,
    # and the page compares against it before printing «local database» instead. It is the
    # same word in both catalogues because it is compared, never shown; translating it here
    # would leave the comparison unmatched and print the sentinel as if it were a CPIC level.
    "web.rx.curated_value": "куратор",
    "web.rx.actionable": "matters",
    "web.rx.your_phenotype": "your phenotype:",
    "web.rx.your_variants": "your variants:",
    "web.rx.no_lab_control": "No specific laboratory monitoring is required for this class.",
    "web.rx.not_taken_yet": "not taken yet",
    "web.rx.monitor_while": "Monitor while taking it: {text}",
    "web.rx.near_note": "Within range, but at the wall of the corridor: {names} — worth watching "
                        "especially closely on this drug.",
    "web.rx.watch_note": "You already have these out of range: {names} — that matters for this "
                         "drug.",
    "web.rx.with_yours": "with yours:",
    "web.rx.mechanism": "mechanism: {text}",
    "web.rx.what_to_do": "what to do: {text}",
    "web.rx.no_interactions_partial": "No explicit interactions were found with the part of your "
                                      "current list that was recognised. NOT compared, because the "
                                      "class could not be determined: {names}.",
    "web.rx.no_interactions": "No explicit interactions with your current prescriptions were "
                              "found.",
    "web.rx.via_gene": "gene {gene}",
    "web.rx.via_drug_name": "by the drug name",
    "web.rx.genotype": "genotype {genotype}",
    "web.rx.clinvar_h": "ClinVar for this drug",
    "web.rx.clinvar_note": "your variants from a fresh ClinVar that relate to this medicine",
    "web.rx.h_genome": "Your genome",
    "web.rx.h_labs": "Your labs",
    "web.rx.h_meds": "Your prescriptions",

    # ── web: what to test ────────────────────────────────────────────────
    "web.tests.title": "Test suggestions ({n})",
    "web.tests.done": "taken",
    "web.tests.done_why": "already measured ({date}) — routine control, not a new order; a repeat "
                          "in roughly ~{months} months.",
    "web.tests.specialist": "who to see: {name}",
    "web.tests.why": "what for: {text}",
    # An empty list of suggestions means the rules produced nothing from what is in
    # the profile. It does NOT mean anything about what was ordered or taken —
    # a profile with no labs at all yields exactly the same empty list, and the
    # previous wording told that person their results were on the way.
    "web.tests.none_pending": "No new order comes out of what is in the profile right now. "
                              "That is a statement about these rules and this data — not "
                              "about what you have or have not had taken.",
    "web.tests.routine_h": "Routine control — already taken, watched by interval",

    # ── web: the health radar and the second look ────────────────────────
    "web.delta.unchanged": "unchanged",
    "web.delta.better": "better by {n}",
    "web.delta.worse": "worse by {n}",
    "web.radar.not_enough": "Not enough data for the diagram (at least 3 systems with labs are "
                            "needed). Load the labs from the folder on the «Labs» tab.",
    "web.radar.tip": "{label}: {score}/100 ({ok}/{total} within range)",
    "web.radar.tip_partial": "{label}: {score}/100 ({ok} of the {measured} measured within "
                             "range; the domain declares {total})",
    "web.radar.was": "was {score}/100 over the {compared} markers that have an earlier "
                     "point ({date}) — {word}",
    "web.radar.prev_measurement": "previous measurement",
    "web.radar.no_previous": "there is no previous measurement to compare with",
    "web.radar.now": "now",
    "web.radar.previous": "previous measurement",
    "web.second.title": "A second look before the doctor's visit",
    "web.second.print": "Print / PDF",
    "web.second.overall": "Overall health index:",
    "web.second.was": "was {score} ({date})",
    "web.second.stale_lead": "old (not re-measured for ≥1.5 years) — not the current status:",
    "web.second.vs_prev": "against the previous measurement ({date}: {score}/100)",
    "web.second.no_current": "there are no current abnormalities",
    "web.second.factors_h": "The important factors — what to discuss with the doctor",
    "web.second.no_domain_issues": "No clear abnormalities among the {n} body systems "
                                   "there was enough data to judge.",
    "web.second.no_domain_data": "No body system has enough measured to be judged yet. "
                                 "The radar shows the shape; the verdicts wait for data.",
    "web.second.print_title": "Scholion — material for a conversation, prepared at home",
    "web.second.print_name": "Name",
    "web.second.print_dob": "Date of birth",
    "web.second.print_date": "Date",
    "web.second.print_foot": "This sheet is generated on the patient's own computer from files "
                             "the patient maintains. It is not a laboratory report and carries no "
                             "accession number: every value on it should be checked against the "
                             "original before it is acted on. It is not a diagnosis, not a "
                             "prescription, and asks for nothing except that the questions on it "
                             "be considered.",
    "web.second.pgx_h": "Pharmacogenetics — for the future",
    "web.second.no_drug_flags": "None of the {n} watch-list drugs there was a genotype for "
                                "raised a flag.",
    "web.second.pgx_basis": "{k} of {n} could be judged from the genotypes on file. The rest "
                            "print the general rule for the drug — not a statement about you.",
    "web.second.pgx_basis_none": "None of the {n} could be judged from the genotypes on file: "
                                 "what follows is the general rule for each drug, not a "
                                 "statement about you.",
    "web.second.no_drug_data": "None of the {n} watch-list drugs could be judged — the profile "
                               "carries no genotype for the genes they depend on. This is a "
                               "statement about the data, not about the drugs.",
    "web.second.tests_h": "What is worth taking",
    "web.second.routine_elsewhere": "Another {n} are routine control — already taken, watched "
                                    "by interval. They are on the tab",

    # ── proposing a goal ─────────────────────────────────────────────────
    # Three sources, and the wording of each says what kind of claim it is. The
    # personal best is deliberately «where you have been», not «where you should
    # be»: nobody recommended that number, the person's own body produced it.
    "goalgen.why.guideline": "{body} publishes this target ({year}).",
    "goalgen.why.guideline_conditional": "{body} publishes this target ({year}) for people "
                                         "with {condition}. Whether that is you is not "
                                         "something this profile can confirm.",
    "goalgen.why.no_target": "{body} looked at this marker and declined to set a target. "
                             "That is the finding, not a gap — no number is proposed here.",
    "goalgen.why.personal_best": "The best you have reached — {date}, out of {n} readings "
                                 "over {months} months. Nobody recommended it; your own "
                                 "measurements did.",
    "goalgen.why.reference": "The wall of the laboratory corridor. Weaker than the other two: "
                             "«inside the range» is where most people already are, and is "
                             "not an aim.",
    "goalgen.how_to_read": "A proposal, not a prescription. Where a clinical association has "
                           "published a target it is quoted with its source; otherwise the "
                           "proposal is your own best result, which is a fact about you and "
                           "not advice. Change any of them, and take the ones that matter to "
                           "your doctor.",
    "goalgen.skip.no_series": "nothing measured",
    "goalgen.skip.no_direction": "the catalogue does not record which direction is better "
                                 "for this marker, so no goal is proposed rather than one "
                                 "pointing the wrong way",
    "goalgen.skip.too_few_points": "fewer than three readings — that is not a trend",
    "goalgen.skip.too_short_a_window": "every reading falls inside six months",
    "goalgen.skip.already_there": "your best is where you are now",
    "goalgen.skip.society_withdrew_the_target": "the society that set the target withdrew it",
    "goalgen.skip.nothing_to_go_on": "no published target, no usable series, no corridor",
    "goalgen.title": "Proposed goals",
    "goalgen.none": "Nothing here can carry a goal yet. Load more lab results and this "
                    "answers differently.",
    "goalgen.skipped_h": "Not proposed for, and why",
    "goalgen.src.guideline": "clinical guideline",
    "goalgen.src.personal_best": "your own best",
    "goalgen.src.reference": "laboratory corridor",
    "web.goalgen.h": "Let the application propose a goal",
    "web.goalgen.intro": "It reads what you have measured and what the clinical associations "
                         "publish, and proposes a target for each marker there is enough to "
                         "propose one for. Every line says where its number came from. "
                         "Nothing is written until you press «Save».",
    "web.goalgen.btn": "Propose a goal",
    "web.goalgen.save": "Save the ones ticked",
    "web.goalgen.saved": "Saved to profile/health_goals.json — {n} target(s).",
    "web.goalgen.now": "now",
    "web.goalgen.reached": "you have been here before",
    "web.goalgen.pick": "source",

    # ── the genetic side of the lipid profile (PCSK9 + Lp(a)) ────────────
    "lipidgen.title": "The genetic side of the lipid profile",
    "lipidgen.headline.carrier": "A protective loss-of-function variant of PCSK9 is carried. "
                                 "Part of the LDL-C picture is inheritance rather than habit — "
                                 "which explains a low value, and does not replace measuring one.",
    "lipidgen.headline.not_carrier": "No protective PCSK9 variant among those read. That is the "
                                     "common answer, not a finding: it means the LDL-C measurement "
                                     "stands on its own.",
    "lipidgen.headline.unread": "The PCSK9 positions have not been read, so nothing can be said "
                                "about them yet — which is different from saying there is nothing "
                                "there.",
    "lipidgen.how_to_read": "Two facts that are misread apart. Carrying a PCSK9 loss-of-function "
                            "variant says how much of the LDL-C picture is fixed at birth. Lp(a) "
                            "is invisible to the rest of a lipid panel — it is set at birth too, "
                            "it does not move with the things LDL-C moves with, and a normal panel "
                            "with a high Lp(a) is a normal panel that has missed the finding. "
                            "Neither is a risk calculation and neither is a reason to start or "
                            "stop a therapy.",
    "lipidgen.copies.0": "not a carrier — no buffer from this variant; the LDL-C measurement stands on its own",
    "lipidgen.copies.1": "one copy — lower LDL-C through life, and a materially lower risk of coronary heart disease",
    "lipidgen.copies.2": "two copies — the same effect, stronger; very rare, and worth confirming by another method",
    "lipidgen.lpa.h": "Lipoprotein(a)",
    "lipidgen.lpa.order_it": "Not measured. Lp(a) is worth measuring ONCE in a lifetime — the "
                             "level is largely fixed at birth and barely moves afterwards — and "
                             "the moment for it is BEFORE a decision about lipid therapy, not "
                             "after. Ask for it in nmol/L: the mg/dL conversion is not exact, "
                             "because the apo(a) isoform differs in size from person to person.",
    "lipidgen.lpa.estimate_limit": "A polygenic score for Lp(a) is a genetic ESTIMATE and cannot "
                                   "stand in for the measurement. The level is driven mostly by "
                                   "the number of KIV-2 repeats inside LPA — a copy-number "
                                   "variant that short-read sequencing and SNP arrays see poorly. "
                                   "The catalogue's own «Moderate» mark on this model is that "
                                   "limit, not a gap in the catalogue.",
    "lipidgen.lpa.measured": "measured {value} {unit} · {date}",
    "lipidgen.lpa.above": "above the reference bound of {ref}",
    "lipidgen.waiting_h": "Read, but not interpreted here",
    "lipidgen.unread": "not read",
    "lipidgen.carrier": "carrier",
    "lipidgen.not_carrier": "not a carrier",
    "web.genome.lipidgen_h": "Lipids — the part that is inherited",
    "web.genome.nav_lipids": "Lipids",

    # ── web: prescriptions ───────────────────────────────────────────────
    "web.meds.title": "Prescriptions (editable)",
    "web.meds.note": "Prescriptions added here go into medications.json and take part in the "
                     "checks and the test suggestions. The doctor's full regimen is in "
                     "medications.md.",
    "web.meds.drug": "Drug",
    "web.meds.drug_placeholder": "e.g. Atorvastatin",
    "web.meds.dose": "Dose",
    "web.meds.dose_placeholder": "20 mg",
    "web.meds.comment": "Note",
    "web.meds.comment_placeholder": "indication/comment",
    "web.meds.add": "Add",
    "web.meds.remove": "remove",
    "web.meds.empty": "Nothing here yet.",
    "web.meds.enter_name": "Enter a drug",
    "web.meds.added_attention": "Added — there is something to pay attention to",
    "web.meds.removed": "Removed",

    # ── web: personal metrics ────────────────────────────────────────────
    "web.metrics.title": "Personal health metrics",
    "web.metrics.sex": "sex",
    "web.metrics.sex_label": "Sex",
    "web.metrics.male": "male",
    "web.metrics.female": "female",
    "web.metrics.age": "age",
    "web.metrics.height": "height, cm",
    "web.metrics.height_label": "Height, cm",
    "web.metrics.bmi": "BMI",
    "web.metrics.profile_btn": "Profile (height/year/sex)",
    "web.metrics.add_btn": "Add a measurement",
    "web.metrics.birth_year": "Year of birth",
    "web.metrics.profile_note": "Goes into metrics.json (profile). The BMI is computed from the "
                                "height and the latest weight.",
    "web.metrics.profile_saved": "Profile saved ✓",
    "web.metrics.name_placeholder": "HRV",
    "web.metrics.add_note": "Goes into metrics.json (profile). The trends and the BMI update "
                            "immediately.",

    # ── web: the bullet board "now → goal" ───────────────────────────────
    "web.bullet.title": "Now → goal",
    "web.bullet.good": "the goal is reached or the value is within range",
    "web.bullet.warn": "within the corridor, but the goal is not reached",
    "web.bullet.crit": "outside the reference corridor",
    "web.bullet.none": "no data",
    "web.bullet.no_target": "no goal",
    "web.bullet.target": "goal {value}",
    "web.bullet.src_goal": "the goal you set",
    "web.bullet.src_ref": "the wall of the laboratory corridor",
    "web.bullet.src_norm": "general advice",
    "web.bullet.src_own": "derived from your own data",
    "web.bullet.legend_notch": "the notch is the goal",
    "web.bullet.legend_zone": "the goal zone",
    "web.bullet.group.body": "Body composition",
    "web.bullet.group.metabolism": "Metabolism",
    "web.bullet.group.bones": "Bones",
    "web.bullet.group.fitness": "Fitness and recovery",
    "web.bullet.group.other": "Other",
    # The `match` lists below are NOT text: they are the labels as they arrive from
    # `profile/lifestyle_brief.json`, and the page groups the rows by matching them exactly.
    # Nothing here is printed — an entry that matches no label simply groups nothing.
    # The label's language is the language of the person's own forms, not of the interface,
    # so both spellings are listed: with the Russian ones alone every row of the English demo
    # profile («VO2max», «Resting pulse», «Steps», «Sleep») fell into «Other» and the groups
    # stood empty, while dropping them would do the same to a Russian profile read in English.
    "web.bullet.match.body": "Weight|Body fat|Muscle mass|BMI|"
                             "Вес|Доля жира|Мышечная масса|ИМТ",
    "web.bullet.match.metabolism": "HOMA-IR|Fasting insulin|Triglycerides|LDL|Apolipoprotein B|"
                                   "Uric acid|"
                                   "Инсулин натощак|Триглицериды|ЛПНП|Аполипопротеин "
                                   "B|Мочевая кислота",
    "web.bullet.match.bones": "Ionised calcium|Osteocalcin|Parathyroid hormone|25-OH vitamin D3|"
                              "Ионизир. кальций|Остеокальцин|Паратгормон|25-OH витамин D3",
    "web.bullet.match.fitness": "VO2max|VO₂max|Resting pulse|HRV|HRV (rMSSD)|Steps|Sleep|"
                                "Deep sleep|Time to fall asleep|"
                                "Пульс покоя|ВСР (rMSSD)|Шаги в день|Сон|Глубокий сон|Время "
                                "засыпания",
    "web.bullet.match.hero": "Body fat|Muscle mass|HOMA-IR|Доля жира|Мышечная масса",

    # ── web: lifestyle ───────────────────────────────────────────────────
    "web.life.title": "Lifestyle",
    "web.life.ok": "within range",
    "web.life.warn": "attention",
    "web.life.bad": "below the goal",
    "web.life.none": "—",
    "web.life.stable": "steady",
    "web.life.trend_3m": "{delta} over 3 months",
    "web.life.card_meta": "latest {date} · smoothed {smooth} · since {since}",
    "web.life.garmin_btn": "Refresh from the Garmin export",
    "web.life.garmin_note": "rebuilds from a fresh Garmin GDPR export (garmin_export), with a "
                            "backup",
    "web.life.rebuilding": "rebuilding…",
    "web.life.garmin_done": "Garmin refreshed: {metrics} metrics ({range})",
    "web.life.garmin_nights": "nights of sleep {n}",
    "web.life.garmin_preserved": "kept from the previous file {n} points",
    "web.life.fitness_score": "fitness score /100",
    "web.life.hero": "{label} · goal {target}",
    "web.life.no_wearable": "There is no wearable data yet (profile/wearable_trends.json).",
    "web.life.shifted_h": "What moved over 3 months",
    "web.life.right_way": "In the right direction:",
    "web.life.needs_attention": "Needs attention:",
    "web.life.no_trends": "There is not enough data for trends yet.",
    "web.life.waist": "Waist, cm",
    "web.life.waist_placeholder": "e.g. 104",
    "web.life.date": "Date",
    "web.life.date_placeholder": "YYYY-MM-DD",
    "web.life.waist_save": "Log it",
    "web.life.waist_note": "the only metric entered by hand → into metrics.json",
    "web.life.waist_metric": "Waist",
    "web.life.waist_unit": "cm",
    "web.life.enter_waist": "Enter the waist circumference, cm",
    "web.life.group_anthro": "Anthropometry and body composition",
    "web.life.group_activity": "Activity",
    "web.life.group_recovery": "Recovery and the autonomic system",
    "web.life.workouts_h": "Workouts, all time",
    "web.life.wk_last_year": "last year: {year}",
    "web.life.wk_hours_total": "{hours} h in total",
    "web.life.wk_hours": "{hours} h",

    # ── web: the lifestyle brief ─────────────────────────────────────────
    "web.brief.sections_h": "The reasoning — why exactly this",
    "web.brief.review_badge": "review",
    "web.brief.actions_h": "What to do",
    "web.brief.needs_review": "the brief needs a review",
    "web.brief.new_data": "New data has arrived since the wording was last edited:",
    "web.brief.block_dates": "text from {reviewed}, data from {newest}",
    "web.brief.numbers_note": "The numbers are recomputed automatically — it is the conclusions "
                              "that need a review. Ask the assistant to update the brief.",
    "web.brief.dropped_h": "Alarms called off — what not to do",
    "web.brief.compiled": "Wording from {date}; the numbers are substituted from the profile every "
                          "time it is opened.",

    # ── web: genome ──────────────────────────────────────────────────────
    "web.genome.title": "Genome — the full picture",
    "web.genome.nav_summary": "Summary",
    "web.genome.nav_updates": "Updates",
    "web.genome.nav_risks": "Risks (PGS)",
    "web.genome.nav_longevity": "Longevity",
    "web.genome.nav_clinvar": "ClinVar",
    "web.genome.nav_locus": "Locus lookup",
    "web.genome.db_connected": "database connected",
    "web.genome.db_not_connected": "database not connected",
    "web.genome.db_after_script": "the genome side answers once a full VCF is connected — "
                                 "`scholion doc preparing-the-genome` describes how",
    "web.genome.intro": "Everything about your genome in one place: the advantages as well as the "
                        "risks. Below: what is new in the databases, polygenic risks, longevity, "
                        "clinically significant ClinVar findings and a lookup for any locus. "
                        "Nothing leaves the machine. Not a diagnosis — material for the doctor.",
    "web.genome.updates_h": "Database updates",
    "web.genome.updates_note": "check the genome against a fresh ClinVar and show what is new",
    "web.genome.prs_h": "Polygenic risks (PGS)",
    "web.genome.longevity_h": "Longevity",
    "web.genome.clinvar_h": "Clinically significant findings (ClinVar)",
    "web.genome.locus_h": "Look up any locus",
    "web.genome.locus_placeholder": "rsID, e.g. rs4149056",
    "web.genome.find": "Find",
    "web.genome.unknown_gene": "The gene is not in the coordinate reference.",
    "web.genome.loci": "loci:",
    "web.genome.genotype": "genotype",
    "web.genome.coverage": "coverage {value}",
    "web.genome.assumed_ref": "reference (not a variant site)",

    # ── web: polygenic scores ────────────────────────────────────────────
    "web.prs.not_ready": "The polygenic scores have not been computed yet.",
    "web.prs.above_average": "above the population average ({pop})",
    "web.prs.low_coverage": "coverage below 90% — approximate",
    "web.prs.stat_traits": "traits",
    "web.prs.stat_reliable": "reliable",
    "web.prs.stat_high": "above average (≥80)",
    "web.prs.scale_note": "The scale is a position in the population (0–100 percentile), NOT a "
                          "probability of disease.",
    "web.prs.high_h": "Noticeably above average (screening)",
    "web.prs.all_h": "All traits by category",
    "web.prs.legend": "Green ≤20 · blue in the middle · orange ≥80.",
    "web.prs.no_model": "no model",

    # ── web: longevity ───────────────────────────────────────────────────
    "web.longevity.not_ready": "The longevity layer has not been built yet.",
    "web.longevity.apoe_status": "APOE — status",
    "web.longevity.apoe_favourable": "A favourable genotype: a lower risk of Alzheimer's, "
                                     "associated with longevity, usually lowers LDL.",
    "web.longevity.apoe_e4": "There is an ε4 component — a raised risk of Alzheimer's and "
                             "cardiovascular disease; discuss it with the doctor.",
    "web.longevity.apoe_generic": "ε2/ε3/ε4 are determined from these two SNPs.",
    "web.longevity.carries": "carries the allele",
    "web.longevity.stat_checked": "variants checked",
    "web.longevity.stat_carrier": "significant — carrier",
    "web.longevity.stat_genes": "genes",
    "web.longevity.key_markers_h": "Key markers",
    "web.longevity.by_gene_h": "Significant carrier status by gene",
    "web.longevity.by_gene_note": "A catalogue from the literature: you carry a variant that has "
                                  "been studied in the context of longevity. The direction of most "
                                  "associations is not encoded — this is a navigator across genes, "
                                  "not a risk estimate.",

    # ── web: ClinVar findings ────────────────────────────────────────────
    "web.clinvar.not_run": "The ClinVar annotation has not been run yet.",
    "web.clinvar.nothing": "No significant findings were extracted",
    "web.clinvar.experts": "experts",
    "web.clinvar.several_labs": "several laboratories",
    "web.clinvar.actionable_of": "actionable findings out of {total}",
    "web.clinvar.intro": "Your variants marked up against a fresh ClinVar. The important ones on "
                         "top: {pathogenic} (carrier status/disease), {pgx} (drugs), {risk}. The "
                         "remaining {n} (weak/ambiguous) are behind the fold and are usually not a "
                         "risk. Not a diagnosis.",
    "web.clinvar.w_pathogenic": "pathogenic",
    "web.clinvar.w_pgx": "pharmacogenetics",
    "web.clinvar.w_risk": "risk factors",
    "web.clinvar.show_weak": "Show the weak and ambiguous ones ({n})",

    # ── web: checking the databases for updates ──────────────────────────
    "web.updates.never": "There have been no checks yet. Press «Check for updates» — the "
                         "application will compare your genome against a fresh ClinVar and show "
                         "what is new.",
    "web.updates.last_check": "Last check:",
    "web.updates.nothing_new": "Nothing new since the last check.",
    "web.updates.new_h": "New findings ({n})",
    "web.updates.changed_h": "The classification changed ({n})",
    "web.updates.check_btn": "Check for updates",
    "web.updates.in_progress": "the check is running…",
    "web.updates.downloading": "Downloading a fresh ClinVar and comparing it with your genome — "
                               "this takes a few minutes.",
    "web.updates.failed": "The check did not finish (code {code}).",

    # ── web: the assistant tab ───────────────────────────────────────────
    "web.assistant.title": "The assistant — an optional layer",
    "web.assistant.works_without": "the application works without an assistant",
    "web.assistant.everything_local": "All the numbers, flags, trends, pharmacogenetics, the "
                                      "«second opinion» and the checklist for the next blood draw "
                                      "are computed by code on your machine. Neither the internet "
                                      "nor a language model is needed for that.",
    "web.assistant.scan_lead": "Verified by a scan of its own code when the tab was opened:",
    "web.assistant.network_lead": "The application can reach outside only on your command, and "
                                  "what leaves is the query itself — a drug name, an rsID — not "
                                  "the profile and not the genome:",
    "web.assistant.ingest_hosts": "The data preparation scripts that you run by hand (assembling "
                                  "the genome, updating the reference books) download from: "
                                  "{hosts}.",
    "web.assistant.engine_does": "Computed by code",
    "web.assistant.adds": "Added by the assistant",
    "web.assistant.curated_h": "The texts the assistant writes",
    "web.assistant.curated_note": "The wording is curated by the assistant, the numbers inside it "
                                  "are substituted by the engine at the moment of display — which "
                                  "is why the figures in these texts do not go stale, while the "
                                  "wording is marked as needing a review once data newer than it "
                                  "appears.",
    "web.assistant.connect_h": "How to connect a model",
    "web.assistant.connected": "connected",
    "web.assistant.ready": "ready to connect",
    "web.assistant.missing": "not found",
    "web.assistant.absent": "absent",
    "web.assistant.stale": "needs a review",
    "web.assistant.fresh": "fresh",
    "web.assistant.updated": "updated {date}",
    "web.assistant.no_date": "no date",
    "web.assistant.tab_of": "the «{tab}» tab",
    "web.assistant.review_blocks": "review: {blocks}",
    "web.assistant.collect_btn": "Collect the context and copy it",
    "web.assistant.context_warning": "The collected text contains your personal medical data — "
                                     "paste it only where you are content for it to be kept.",
    "web.assistant.collecting": "collecting…",
    "web.assistant.collect_failed": "did not work out",
    "web.assistant.copied": "copied to the clipboard",
    "web.assistant.collected": "{chars} characters · saved: {path}",
    "web.assistant.toast_clipboard": "The context is in the clipboard — paste it into the "
                                     "conversation with the model",
    "web.assistant.toast_file": "The context has been saved to a file",

    # ── web: the guide tab ─────────────────────────────────────────────
    "web.tab.guide": "Guide",
    "web.guide.title": "Guide",
    "web.guide.intro": "What every screen in this application shows, in one place — so none "
                       "of it has to stay unexplained just because the source is not at hand. "
                       "Everything below describes the interface itself: colours, labels, "
                       "terms. What your own numbers mean is explained on the screen that "
                       "shows them, next to the number.",

    "web.guide.sources_h": "Where a number comes from",
    "web.guide.sources_body": "Most tabs open with a row of small chips above the content. "
                              "A chip marks where that tab's data was read from: your own "
                              "files on this machine, or a public reference database consulted "
                              "over the network (ClinVar, RxClass, Ensembl). Nothing is asserted "
                              "without one of these two origins, and the two are never rendered "
                              "the same colour. Whether the Assistant tab has a language model "
                              "connected or not, this distinction does not change: the "
                              "underlying numbers are always computed by code on your machine.",

    "web.guide.status_h": "Colours and badges",
    "web.guide.status_intro": "The same five badges recur on almost every tab. Colour is never "
                              "the only signal — a number and a caption always sit next to it, "
                              "so the badge stays readable even where colour is not.",
    "web.guide.status_good_label": "good",
    "web.guide.status_good_why": "The goal is reached, or there is no goal and the value sits "
                                 "inside the reference range.",
    "web.guide.status_warning_label": "warning",
    "web.guide.status_warning_why": "Inside the reference range, but a personal goal is not yet "
                                    "reached — or a pharmacogenetic effect worth a moment's "
                                    "attention, not a red flag.",
    "web.guide.status_critical_label": "critical",
    "web.guide.status_critical_why": "Outside the laboratory reference range, or a safety flag "
                                     "raised from your own profile.",
    "web.guide.status_near_label": "at the edge",
    "web.guide.status_near_why": "Formally inside the range, but pressed against its wall. "
                                 "Rendered in blue rather than amber on purpose — so a "
                                 "colour-blind reader sees a difference from «warning» in the "
                                 "tone itself, not only in the caption.",
    "web.guide.status_unknown_label": "no data",
    "web.guide.status_unknown_why": "Nothing to judge yet — not measured, or not present in "
                                    "your files.",
    "web.guide.status_three_note": "Judgement itself uses three levels, not five: good, warning, "
                                   "critical. A fourth, near-identical level was tried and "
                                   "dropped — at normal contrast it was indistinguishable from "
                                   "«warning» to normal vision. «At the edge» and «no data» are "
                                   "not severity levels; they mark a different kind of thing — "
                                   "a value's position, or its absence.",

    "web.guide.tour_h": "What each tab is for",
    "web.guide.tour_overview": "The first screen: one focus-of-attention card — what is most "
                               "worth looking at right now, and why — above the goal dashboard, "
                               "if you have set a shape target.",
    "web.guide.tour_labs": "Every lab marker on file, flagged against its reference range, with "
                           "a trend line where enough measurements exist.",
    "web.guide.tour_drugs": "Check a medication by name before you take it: a quick "
                            "pharmacogenetics-only pass, or the full check — genome, current "
                            "labs, interactions with what you already take, and ClinVar.",
    "web.guide.tour_genome": "Polygenic scores as population percentiles, longevity-linked "
                             "variants, ClinVar findings in your genome, a check for what "
                             "changed since ClinVar was last read, and a lookup by gene or "
                             "rsID.",
    "web.guide.tour_lifestyle": "Wearable-derived metrics against a personal goal, a bullet bar "
                                "per metric, and workout history.",
    "web.guide.tour_tests": "What is worth measuring next, and what was measured recently enough "
                            "to skip.",
    "web.guide.tour_second_opinion": "One page combining the domain radar, pharmacogenetic "
                                     "flags on current prescriptions and suggested tests — built "
                                     "to be printed and taken to an appointment.",
    "web.guide.tour_prescriptions": "The medications you take. Adding one runs the same "
                                    "interaction check as the drug-check tab, against the rest "
                                    "of the list.",
    "web.guide.tour_assistant": "Whether a language model is connected, what it is and is not "
                                "allowed to see, and how to connect one if you want richer "
                                "wording on top of the same numbers.",

    "web.guide.terms_h": "Terms",
    "web.guide.term_prs_label": "PRS, percentile",
    "web.guide.term_prs_body": "A polygenic score turned into a position in a reference "
                               "population, 0 to 100. Not a diagnosis and not a probability of "
                               "disease — a percentile says where you sit in a distribution, "
                               "nothing more. Built mostly from European-ancestry cohorts; "
                               "outside that ancestry the percentile is less exact.",
    "web.guide.term_pgx_label": "Pharmacogenetics (PGx)",
    "web.guide.term_pgx_body": "How your own genotype at a handful of well-studied genes "
                               "(CYP2C9, CYP2C19, SLCO1B1 and others) changes how a specific "
                               "drug is likely to be processed — faster, slower, or with a "
                               "raised chance of a side effect. A pharmacogenetic flag is a "
                               "reason to ask a prescriber a specific question, not an "
                               "instruction to change a dose yourself.",
    "web.guide.term_clinvar_label": "ClinVar tiers",
    "web.guide.term_clinvar_body": "Findings in your genome are grouped by what ClinVar says "
                                   "about them: pathogenic (disease-causing), drug response, "
                                   "risk factor, or protective are shown first; association and "
                                   "uncertain significance — the weakest, least actionable tiers "
                                   "— sit behind a «show more» so they do not crowd out the "
                                   "rest.",
    "web.guide.term_confidence_label": "Genome read confidence",
    "web.guide.term_confidence_body": "A genotype can be called directly from the sequencing "
                                      "data, or — at a site with no variant on record — "
                                      "confirmed as reference by an explicit 0/0 call, which is "
                                      "not the same as a site simply missing from the file. Low "
                                      "read depth at a called site is flagged in place, next to "
                                      "the number it affects.",
    "web.guide.term_sources_label": "Local vs public",
    "web.guide.term_sources_body": "«Local» is a file already on this machine: your labs, your "
                                   "genome, your prescriptions. «Public» is a reference database "
                                   "read over the network to interpret them — ClinVar for "
                                   "variant significance, RxClass for drug classes, Ensembl for "
                                   "coordinates. The engine never sends your file contents to a "
                                   "public source — only the query, such as a drug name or an "
                                   "rsID.",

    "web.guide.footer": "Every screen carries its own note on what it can and cannot tell you. "
                        "This page is the map to the interface, not a substitute for those "
                        "notes, and not medical advice.",

    # ── web: workout types (the key is the identifier Garmin sends) ──────
    "web.workout.Running": "Running",
    "web.workout.Tennis": "Tennis",
    "web.workout.Swimming": "Swimming",
    "web.workout.Cycling": "Cycling",
    "web.workout.Walking": "Walking",
    "web.workout.Hiking": "Hiking",
    "web.workout.SnowSports": "Skiing/snowboarding",
    "web.workout.HighIntensityIntervalTraining": "Strength training",
    "web.workout.TraditionalStrengthTraining": "Strength training",
    "web.workout.FunctionalStrengthTraining": "Functional",
    "web.workout.Pickleball": "Pickleball",
    "web.workout.Golf": "Golf",
    "web.workout.Rowing": "Rowing",
    "web.workout.Yoga": "Yoga",
    "web.workout.Pilates": "Pilates",
    "web.workout.MindAndBody": "Mind and body",
    "web.workout.MixedCardio": "Cardio",
    "web.workout.Elliptical": "Elliptical",
    "web.workout.PaddleSports": "Paddle",
    "web.workout.Other": "Other",

    # ── the local server: what it answers a request with ─────────────────
    "server.pick.labs": "Choose the folder with the labs.json file",
    "server.pick.labs_docs": "Choose the folder with the laboratory study PDFs",
    "server.pick.medications": "Choose the folder with the doctor's prescriptions",
    "server.pick.med_docs": "Choose the folder with the prescription PDFs",
    "server.pick.metrics": "Choose the folder with the health metrics",
    "server.pick.genome": "Choose the folder with the genome data (VCF)",
    "server.pick.default": "Choose the folder with the data",
    "server.pick.macos_only": "The native dialog is available on macOS only — type the path in by "
                              "hand.",
    "server.pick.failed": "could not open the dialog",
    "server.pick.empty_path": "empty path",
    "server.deny.foreign_host": "the request is addressed to a name that is not local",
    "server.deny.cross_site": "cross-site request rejected",
    "server.bad_content_length": "malformed Content-Length",
    "server.body_too_large": "the request body is larger than {bytes} bytes",
    "server.internal_error": "internal server error; the details are in the console where scholion "
                             "serve is running",
    "server.no_studies_folder": "No folder of studies has been chosen.",
    "server.no_labs_folder": "No folder of studies has been chosen. Press «📁 Folder of studies».",
    "server.context_not_saved": "could not save: {error}",
    "server.update.no_bcftools": "bcftools is not in the application's PATH. Run update_check.sh "
                                 "from a terminal where brew is available.",
    "server.selfcheck_skipped": "(the lab self-check was skipped: {error})",
    "server.already_running": "Scholion is already running: {url} — opening it in the browser.",
    "server.no_free_port": "Could not take a port in the range {first}–{last}. Close the extra "
                           "application windows and start it again.",
    "server.port_busy": "Port {wanted} is taken — starting on the free port {chosen}.",
    "server.listening": "Scholion: {url}  (Ctrl+C to stop)",
    "server.profile": "Profile: {path}",
    "server.stopped": "Stopped.",
    # --- external command-line tools (scholion tools) ---------------------
    # Appended at the end deliberately: another branch is editing the middle of
    # this file, and a block on its own tail stays a separable change.
    "tools.title": "**External tools**",
    "tools.intro": "The analysis runs on the standard library. Preparing genome data does not: "
                   "reading a VCF, indexing it and measuring coverage are done by separate "
                   "programs. Below is what is here and what is not.",
    "tools.manager_found": "package manager: {name}",
    "tools.no_manager": "No supported package manager found. This command drives Homebrew "
                        "(brew.sh) and conda/mamba, because both install into your own home "
                        "directory. Install one of them, or install the tools the way your "
                        "system normally does.",
    "tools.sudo_never": "Nothing here asks for administrator rights.",
    "tools.state_missing": "missing: {n}",
    "tools.optional": "  (optional)",
    "tools.system": "part of the system; on macOS it comes with `xcode-select --install`",
    "tools.all_present": "Everything is in place.",
    "tools.will_run": "These commands would install what is missing:",
    "tools.routes_header": "Known ways to install what is missing — whichever manager you end up with:",
    "tools.other_route": "✗ {tool} — no {manager} package for it. Another way: {command}",
    "tools.no_route": "✗ {tool}: no verified install command — this one is installed by hand.",
    "tools.later": "`scholion tools` shows this picture again, `scholion tools --install` "
                   "installs the base set.",
    # Printed instead of the four ✗ after `init --demo`. The demo needs no external
    # program at all, and a list of what is missing, directly under «Have a look»,
    # reads as «installed halfway» to somebody thirty seconds into the product.
    "doc.list_header": "Documents carried inside the package:",
    "doc.list_hint": "  scholion doc <name>          print one\n"
                     "  scholion doc <name> --path   where it is on disk",
    "doc.unknown": "There is no document «{name}» in this build. There are: {known}",
    "tools.see_later": "Nothing else to install for the demo. When you bring a real genome, "
                       "`scholion tools` says which external programs it needs.",
    # A bare `scholion` used to answer with a usage dump of forty-four commands and
    # «error: the following arguments are required: cmd». It is the first thing a
    # curious person types, and it was answered with an error.
    "cli.bare_hint": "Scholion — your medical data, read against itself, on your own machine.\n\n"
                     "  scholion init --demo   lay out a synthetic profile and look around\n"
                     "  scholion overview      the main screen, once you have a profile\n"
                     "  scholion --help        all commands",
    "tools.not_confirmed": "Installation was not confirmed — nothing was run.",
    "tools.offline": "SCHOLION_OFFLINE is set: installing needs the network, so nothing was run.",
    "tools.running": "→ {command}",
    # Counted separately from the sentence: Russian needs three forms and the
    # genitive after «нет», and a sentence built by pasting a bare number into it
    # comes out agreeing with nothing.
    "count.programs.one": "{n} external program",
    "count.programs.few": "{n} external programs",
    "count.programs.many": "{n} external programs",
    "tools.init_intro": "Not on this machine yet: {programs}. Without the full set a VCF can "
                        "be neither read nor indexed:",
    "tools.not_a_tty": "Not asking — this is not an interactive terminal. Run "
                       "`scholion tools --install` when convenient.",
    "tools.ask": "Install them now? [y/N] ",
    "tools.yes_words": "y,yes",
    "tools.declined": "Skipped. `scholion tools --install` does it later; nothing else changes.",
    "tools.installed_ok": "✓ installed: {tools}",
    "tools.install_failed": "✗ still missing: {tools}",
}
