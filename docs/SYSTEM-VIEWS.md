# Shared system presentation

`web/system-views.js` owns the HTML composition for system layers, attention
insights, visit topics/charts and prescriptions. `web/system-views.css` owns their
component rules, including context-specific density. Crossread tokens and the
page's layout remain unchanged. Screens retain navigation, event binding, data
selection and requests; their former function names are thin delegates.

Create one instance with `ScholionSystemViews.create(services)`. Translation,
escaping, date/number formatting, badges and measurement labels are presentation
services. Gene, laboratory, correction-route and testing-proposal renderers are
explicit composition slots. They keep their existing shared owners. `selected`
is a live callback: the component must not retain a patient's selection, language
or data between renders. Methods return HTML, never fetch or modify data.

`systemCardHtml`, `attentionItemHTML`/`attentionHTML`, `visitInsightHTML`,
`visitReportSystem`/`visitReportChart`, `systemMedicationsHtml`, `medItem`,
`controlsHtml` and `treatmentHtml` are the composition entry points. Supporting
fact, comparison, context and provenance methods are shared by these views.
Current/historical prescriptions and clinical conclusions remain server verdicts.
No inference, new source merging or clinical ranking belongs in this component.

Change composition here first. Do not put a second copy in a screen or expand a
thin delegate. Context differences use services or explicit method arguments.
New slots need a documented owner and a behavioral check. Component rules must
not reappear in page CSS; overall screen grids and print-page layout stay there.

`tests/browser/gallery-system-cases.js` supplies synthetic states for both direct
module checks and the browser gallery. Gallery services intentionally omit the
specialized slot content; real-page comparison and existing clinical/genetic
checks cover those integrations. Tests import the factory; source-text extraction
is reserved for a one-time migration comparison against the previous version.

Run `tests.test_system_view_component` and affected semantic regressions during
implementation. The gallery runs EN/RU, patient/clinician, both themes and narrow
and wide layouts, including real disclosures and navigation targets. On a stable
candidate also verify the actual page and the sanitized installed wheel. This is
presentation reuse, not a replacement for CLI, MCP, plugin and Web parity.
