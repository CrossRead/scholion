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

Options include `register`, `fallback`, `referenceOnly`, `compound`,
`geneScreen` and `geneRegion`. Optional HTML slots are deliberate boundaries:

| Slot | Placement and caller responsibility |
| --- | --- |
| `geneHtml` | Identity link with a page-specific navigation context |
| `annotationHtml` | Additional annotation content inside the annotation disclosure |
| `detailHtml` | Override for composed reference/clinical details; normally supplied by the component |
| `extraHtml` | Additional reading/inheritance details inside that disclosure |
| `contextHtml` | Separate contextual section below the base card, e.g. a laboratory comparison |

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
