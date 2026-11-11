# Gene card component

The gene card is a reusable presentation component, owned by
`src/scholion/web/gene-cards.js` and `gene-cards.css`. All web entry points use
it: genome findings, ClinVar, screening, thematic panels, Radar, gene and region
details, pharmacogenetics and visit reports. A page chooses which results to
show; the component decides how a card presents them. No page builds its own
card anatomy or overrides its typography.

## Boundaries

```
Core result (unchanged public API)
    -> create(services).render(result, options)
        -> compose reference, scientific and clinical details
        -> project(result, options): card view model
        -> renderModel(model, options): HTML
    -> insert HTML in the page; existing delegated navigation handles links
```

`project` normalizes existing result shapes without changing them. `renderModel`
reads only that model, never a raw API response. Neither operation performs IO,
mutates a result, reads the active profile, caches a genotype or establishes a
clinical conclusion. The backend remains the source of scientific support,
inheritance, clinical applicability and coverage. CLI, MCP and plugin consumers
continue to receive the same core results; this browser model is not a new
public data schema.

`create` binds the application's translation, escaping, confidence badge, date,
register, passport, author-note and clinical-basis presentation services once.
The register is a callback, and translation stays live: switching language or
patient/clinician mode must not reuse stale output. Input is supplied afresh for
each render. Existing page function names are thin compatibility delegates to
this instance; do not add content logic to those delegates.

## Input and view model

Pass the complete guarded result, retaining its reference and personal context.
The normalizer handles existing flat catalogue rows, `reading`, `result` and
object-valued `genotype` shapes. Do not duplicate their precedence at call sites.

When a reading carries `reading_record.schema == 1`, it is the result of the
shared observation resolver (see [Variant readings](VARIANT-READINGS.md)). Its
selected genotype and quality take precedence over legacy outer display fields;
missing depth must not be filled from a different observation. The card does not
select a source, validate a call or recompute an effect. It displays the core's
conflict/applicability restriction next to the reading and suppresses allele-copy
claims when that restriction is present. Gene function, reference information and
database assertions remain available. Source observations, including underlying
scoring-site calls, are accessible in the reading-details disclosure. Hashes and
internal profile identifiers are not displayed.

| View-model group | Responsibility |
| --- | --- |
| `gene`, `position`, `coordinate`, `protein` | Identity, including gene-only results |
| `genotype`, `zygosity`, `copies`, `compound`, `calledDiplotype` | Existing technical reading; no clinical carriage inferred from an allele |
| `unavailable`, `referenceOnly`, `geneScreen`, `geneRegion` | Distinct unread, reference, screening and region states |
| `quality`, `depth`, `source`, `confidence`, `readingMessage` | Reading provenance and limitations |
| `level`, `levelShort`, `functionText`, `summary` | Supplied confidence, gene function and interpretation |
| `status`, `statusLabel`, `personalMeaning`, `context` | Supplied personal interpretation and qualifications |
| `classification`, `condition`, `review`, `stars`, `snapshot` | ClinVar annotation, separate from Scholion confidence |
| `assertions`, `modes`, `inheritance`, `reference` | Independent database assertions, inheritance and scoped scientific review |

`geneScreen` is used only for gene-level screening, with `read`, `why`,
`findings` and `scanStatus`. `geneRegion` is used only for gene-level interval
results. Neither is a surrogate genotype. Compound readings keep their compound
identity rather than being labelled as single-position zygosity.

## Component interface and extension points

Use the bound instance's `render(result, options)` for one card and
`findings(hit, options)` for a finding with one or more gene contexts. The latter
preserves the finding's shared reading and personal interpretation when adding
each gene's reference annotation. `referenceExtras` renders catalogue-specific
explanations. `reference`, `mechanism`, `preview` and `brief` also serve existing
non-card presentations; their meaning and output remain shared.

The component owns the gene title link on single cards and grouped positions.
It opens an exact NCBI Gene or HGNC record when the reference supplies one,
otherwise it searches NCBI Gene by the preferred human gene symbol.
For grouped positions it checks all available references; changing the row
order cannot change the title destination. Conflicting direct records use the
symbol search only if the symbol is unambiguous.
Unresolved gene sets and regions use a text title. Variant position links
retain their local navigation.

The explanation uses one heading. It presents the supplied meaning, direction
and comparison, mechanism, relevant personal context, then limitations. It
shows only applicable fields and leaves evidence and sources separately
accessible. Research reference context does not substitute for a withheld
personal interpretation.

General cautions belong in the Genome tab's shared interpretation note. The
card omits a research limitation explicitly scoped to that note
(`limitations_scope: genome`); standalone reports retain the supplied text.
Keep limitations specific to the study, variant or reading on the card.

Options include `register`, `fallback`, `referenceOnly`, `compound`,
`geneScreen` and `geneRegion`. A supplied `assessment` is a reading label
for a gene assessment such as a drug phenotype; it is not a genotype.
Use `comparisonText`, `contextTexts` and `limitationTexts` for existing
view-specific explanation facts; the component escapes and places them in
the same order as the corresponding fields of the result. Use
`personalComparisonText` for a comparison tied to the reading; it is
suppressed with `contextTexts` when personal interpretation is withheld.
Optional HTML slots are deliberate boundaries:

| Slot | Placement and caller responsibility |
| --- | --- |
| `annotationHtml` | Additional annotation content inside the annotation disclosure |
| `detailHtml` | Override for composed reference/clinical details; normally supplied by the component |
| `extraHtml` | Additional reading/inheritance details inside that disclosure |
| `contextHtml` | Personal or screen context after the main explanation and before its limitations |
| `readingHtml` | Additional reading facts, e.g. a prescription gene assessment's marker links and genotypes |

Slots contain trusted application-rendered HTML, not raw user or API strings.
Escape dynamic data before filling a slot. Ordinary text is escaped by the
component. Slots must not replace the four-column card, invent a clinical
conclusion or conceal a refused interpretation. Database annotations and
inheritance details start collapsed. Navigation attributes and print selectors
are part of the presentation contract.

## Styles and changes

`gene-cards.css` follows the page's style block, preserving the cascade. It uses
existing Crossread aliases and owns the card, support fields and comparison-slot
styles, including responsive and print rules. It is served locally and packaged
alongside the script; no network or additional runtime is required.

For a card change, edit the component and its stylesheet, then exercise the bound
instance with synthetic data in both languages and registers. Verify gene-only,
called, unread, reference, compound, screening and interval results; test the
affected slots and disclosures. Keep scientific qualifications and distinct
source assertions. For a new API result shape, extend `project` and test it
there rather than adding another layout in a page. Page-specific data fetching,
filtering and surrounding navigation remain page responsibilities.

`test_gene_card_component_boundary.py` checks component ownership and the actual
bound API. Existing gene-card, scientific-support, panel and screening tests
retain semantic coverage. An architectural refactor also needs before/after
HTML and computed-style comparison, plus a check that the sanitized installed
wheel serves both component assets.

## Gene curation and source review

### Supported reference sources

The following sources are supported for the stated curation purposes. The
delivery column distinguishes a retained record, a local pipeline and a source
consulted during curation. The runtime inventory and available import commands
are shown by `scholion sources`.

| Source | What to verify | How Scholion uses it |
| --- | --- | --- |
| [HGNC](https://hgnc.genenames.org/help/symbol-report/index.html) | Approved human symbol, HGNC ID, aliases, previous symbols and gene type | Curated identity and alias records |
| [NCBI Gene / RefSeq](https://www.ncbi.nlm.nih.gov/guide/howto/find-func-gene/) | Human Gene ID, gene or RNA function and curated gene summary | Sourced gene descriptions retained in the catalogue |
| [UniProtKB / Swiss-Prot](https://www.uniprot.org/help/uniprotkb) | Reviewed human protein accession, molecular activity, substrate or binding partner and evidence | Curated citations and checked protein-function descriptions |
| [Gene Ontology](https://geneontology.org/docs/guide-go-evidence-codes/) | Term ID, evidence code, qualifier, taxon and supporting reference | Selected annotations with evidence and attribution retained |
| [dbSNP / RefSNP](https://www.ncbi.nlm.nih.gov/snp/) | rsID status, assembly placement and reference and alternate alleles | Curated variant identity and coordinate references |
| [MANE](https://www.ncbi.nlm.nih.gov/refseq/MANE/) and [Ensembl](https://rest.ensembl.org/) | Assembly, transcript accession and version or exact variant placement | Local reference and annotation pipeline; Ensembl REST for permitted public locus lookups |
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/) | Classification for the exact allele and condition, review status, conflicts and record version | Locally annotated findings and scoped catalogue annotations |
| [GenCC](https://thegencc.org/) | Gene–disease relationship, disease identifier, inheritance, submitter and classification | Retained submissions from a dated export |
| [ClinGen](https://www.clinicalgenome.org/docs/gene-disease-validity-classification-information/) | Relevant expert gene–disease assessment and its scope | Consult during curation and identify ClinGen as a submitter when citing its GenCC assertion |
| [CPIC](https://cpicpgx.org/guidelines/) | Applicable gene–drug guideline, allele or diplotype, phenotype and guideline version | Retained pharmacogenetic guidance and supported data importer |
| [LongevityMap](https://genomics.senescence.info/longevity/) | Membership in a published study and its cited literature | Local catalogue import; verify effect claims against the primary study |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) / [Europe PMC](https://europepmc.org/) | Find the primary article and verify its design, participants, allele, outcome and limits | Literature discovery. Cite the study by PMID, DOI or stable publisher link |

### Checks for each new or changed entry

1. Confirm human gene identity in HGNC and NCBI Gene. Resolve an ambiguous
   label only when the exact locus, assembly or transcript identifies the
   intended gene. Record the identifiers used.
2. Check gene or RNA function in NCBI Gene / RefSeq. For a protein, consult
   reviewed human UniProt when available. Use GO only with its evidence code
   and qualifiers. Record which sources were checked, including unavailable
   records and disagreements. Use the evidence that supports the actual
   wording.
3. For a variant, check exact alleles and assembly in RefSNP or the
   corresponding reference record, and check MANE or Ensembl when the
   explanation depends on a transcript. For a clinical classification, check
   ClinVar. For a gene–disease or inheritance claim, check GenCC and an
   applicable ClinGen expert assessment. For a gene–drug claim, check CPIC.
   Verify a stated variant mechanism or measured effect in the primary study.
4. Write a short patient explanation of the gene's role. Put the specific
   mechanism and evidence scope in the clinician disclosure. Identify what
   was measured, and state the concrete gap if evidence is missing. Keep
   gene function, variant effect, database classification and individual
   interpretation separate.

### What a card must show

In the shared **Database annotations and sources** disclosure, show the name of
each database actually used, a link to the exact record or publication, and
what the source supports. Separate the source of the patient and clinician gene
descriptions from sources for variant effects, inheritance, classification or
drug guidance. A source that only confirmed identity is labelled as such.
Record the version or release when available and the date Scholion last
verified the specific record against the claim. Group repeated references
without hiding distinct submissions, conflicts or differences in scope.
The backend supplies this provenance for every presentation.

### When to offer a refresh

Evaluate freshness for each source and claim from the most recent documented
verification of the exact record and wording. The threshold is **more than
three calendar months**. Add three months to the verification date, using the
last day of the destination month if needed, and offer a refresh starting the
following day. For example, a record checked on 4 November is due for a
refresh on 5 February. An absent or invalid verification date calls for
verification as well. Publication, export and import dates are separate
metadata.

When a check is due, the development agent proposes a refresh and the card
should surface the same recommendation in its source disclosure. Name the
source, exact entry, affected claim and date last checked. Keep the recorded
version and its evidence scope available during the review. The procedure is
to retrieve the current public record, compare it with the retained evidence
and wording, review differences and conflicts, update the affected catalogue
entries and rerun the registered checks on synthetic data. Record the reviewed
version and new verification date after a successful check, including when the
wording is still valid. An unreachable source leaves the review pending.
Opening a card or offering a refresh performs no download or write. Use an
existing importer where the inventory confirms it covers the source and
review the resulting differences before accepting them.

## Repeatable gallery

Build the offline synthetic gallery with
`PYTHONPATH=src:tests python3 tests/ui_gallery.py --out /tmp/scholion-gallery`.
Install development-only browser tooling using `npm ci --prefix tests/browser`,
then `tests/browser/node_modules/.bin/playwright install chromium`.
Run `node tests/browser/check-gallery.cjs /tmp/scholion-gallery/index.html
/tmp/scholion-gallery-check`. An optional third argument points at a previous
check directory for exact HTML/computed-style/geometry comparison. A browser
check fails if its browser cannot start. It does not silently count as accepted.

The gallery imports the actual component, actual CSS and translation catalogues.
Synthetic services isolate the component contract; surrounding page adapters and
clinical support helpers retain their separate tests. The generated HTML can be
opened for visual review. It is not a product route and never reads a profile.

## Curated positions before region summaries

When a thematic gene has curated positions, pass those positions to the shared
position-card component first, including their exact reading or explicit refusal.
Do not prepend a gene-region reference card that appears to have no personal
reading. Clinical and research group headings remain separate. Attach the region
details once, after the final position group. Genes without curated positions
retain a gene-level summary and the actual VCF records in details; never select
an arbitrary variant as a genotype for the whole gene.

A gene's known curated positions are retained across thematic topics, including
positions first curated for another panel. The original annotation panel tags,
condition, sources and explicit refusal of automatic interpretation remain
unchanged. Reusing a factual genotype is not a new clinical association with the
current topic. The region summary is used only when that gene has no curated
position anywhere in the catalogue.

## Genotype-specific research meaning

`personal_meaning` is supplied by the shared core (`personal_meaning.py`). It
separates a sourced genotype hypothesis from study context and from an action
assessment. Every explanation uses “What this may mean for you”. It starts
with the sourced summary, including direction and comparison when established.
Mechanism, relevant personal observations and limitations follow when
available. The text describes the scope of a study or reference when it has
no genotype-specific interpretation. Source URLs stay in the source
disclosure. The component does not count research alleles or infer effects.

Authored genotype comparisons retain the exact allele frame and source witnesses
in `research_interpretations.json`. Existing quantitative associations are reused
from `genetic_lab_links.json`; they are not copied into a second rule catalogue.
A missing studied allele does not imply protection or the reverse effect.
Uncertain reading, identity conflict, an unstudied genotype or changed source
identity keeps the study visible without applying its personal comparison.
No hypothesis changes clinical findings, scores, prescriptions or eligibility.
