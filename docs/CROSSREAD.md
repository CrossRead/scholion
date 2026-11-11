# Crossread integration

Scholion consumes the owner's independent Crossread design system. The vendored
CSS is `src/scholion/web/crossread.css`; its version, SHA-256, licence and component
inventory are recorded beside it in `crossread.manifest.json`.

The independent Crossread project owns the source CSS, generic component
catalogue and design rules. Scholion owns its own layout, chart behavior,
application text and medical rules. Do not put product data in the design system.

The initial vendor snapshot is Crossread 1.0.0, byte-for-byte identical to the
Crossread 1.0 stylesheet already used in this application. No styling changes
are implied by extracting the independent project.

To update, review the independent source change, verify that the current vendor
file still matches its recorded hash, copy the new CSS and manifest, and run the
Scholion tests and browser checks in both themes. A modified vendor file requires
reconciliation, not a forced overwrite. No automatic network update is used.

All application surfaces use Crossread controls, cards, tables and typography.
The former scoped Pico layer is removed. Local layout rules do not modify the
independent vendor stylesheet.
Product color names map to `--cr-*` tokens in one block. Charts read tokens when
they draw. Printing explicitly uses the light palette and retains sources,
container identity and engine version.

Crossread is Apache-2.0. See ATTRIBUTION.md and LICENSE. The reconstructed design
references are not evidence that an application feature or release check passed.
