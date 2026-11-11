# Screen context and resource ownership

`web/view-lifecycle.js` owns the active screen. The page calls `beginView` for
navigation, system/panel subviews and the visit report. Renderers keep their
existing markup and receive a fresh root; an old asynchronous response can only
write into a detached root. Presentation components do not fetch data.

The context records profile identity, data revision, language, display mode and
answer-cache generation. `snapshot`/`matches` protect shared reference caches;
`recontext` binds a newly opened screen after the profile refresh. The latest
language request wins even when replies arrive in the opposite order.

Register screen timers and other disposable resources with `interval`, `timeout`
and `own`. Leaving a screen releases them exactly once. Chart instances are
released by the page's disposal adapter. A callback must check that its root is
current before touching global UI. Background user jobs belong to the application,
not a screen: navigation stops screen polling, not an import or recalculation.

Writes initiated by a screen use `viewPost(root)`. Its captured profile and root
must still be current before a write and before its result is acted on. The HTTP
client sends `X-Scholion-View-Profile`; the server checks the opaque identity
inside the existing pinned-container context. A mismatch returns HTTP 409 before
reading or writing the other profile. Clients without the optional header retain
the existing contract. Profile selection and explicit container export/erase keep
their own guards. Ouroboros forwards this header independently of its host binding
and bridge token. No path or medical data is added to the header.

The CLI never changes process-wide SIGPIPE handling. A closed terminal consumer
is handled at stdout; a disconnected HTTP client ends only that response. A
completed write is not rolled back merely because the client closed its tab.
Calculation errors still use the normal error-reporting path.

## Focused checks

- `test_view_lifecycle`: ownership, cleanup, timers, language and shared-cache races.
- `test_a_late_tab_cannot_replace_the_current_screen`: real page adapters with
  deliberately reordered responses, including cache invalidation after a write.
- `test_http_client_disconnect`: CLI-launched server, reset GET/POST connections,
  persistence, profile refusal and terminal pipe behavior.
- Browser acceptance: real navigation, chart disposal, mode/language switching,
  delayed replies, profile isolation and unchanged screen/print presentation.

Run the targeted tests through `src/tools/run_tests.py --suite-only` so the
synthetic profile and offline environment are retained. Full source and sanitized
package gates apply to a stable candidate, not every presentation edit.
