# Measurement presentation

`src/scholion/web/measurements.js` owns measurement cards and annual summaries.
The page binds live translation/formatting and contextual presentation services
once. It supplies fresh core results on every call; the component keeps no profile
or reading cache. No calculation, source selection, annual aggregation or clinical
inference moves into the browser.

`create(services)` returns:

- `project(result, view)` normalizes the label, displayed value, qualifier and
  unit. One value renderer owns their markup across all three card variants.

- `render(result, view)` for `lab`, `metric`, or `lifestyle`. These are deliberate
  density/context variants of one component, preserving existing output.
- `current(result)` and `annual(result)` for the Today table. Annual results and
  comparison eligibility come from the backend. No new sampling or window rule.
- `sparkline`, `datasets`, `windowSeries`, `label`, `groups`, `isBodyMass` and
  `origin` for existing compact/chart consumers. Weight and BMI keep one line
  with observation provenance; other sources retain their existing distinction.

Services supply translated text, escaping, number/date formatting, badges, flags,
contextual notes, target presentation and live chart colours. The component owns
the card anatomy, source labels, annual comparison composition and graph output.
A page's delegates only insert the returned HTML or select the context variant.
The existing CSS cascade is unchanged in this extraction; general component style
ownership is a separate migration, not an excuse to change appearance here.

Missing, censored and unqualified comparisons stay distinct. Censored values are
not plotted as exact trend points. A normal isolated measurement does not create
a request for more testing. The renderer relays supplied results; it cannot alter
clinical meaning independently of CLI, MCP or plugins.

Use the synthetic gallery (`tests/ui_gallery.py`) and direct module tests.
`tests/browser/check-gallery.cjs` checks the actual rendered component in a real
browser, with optional old/new geometry comparison. Missing browser tooling is
an explicit failure of that check, not a passed/skipped browser acceptance.
