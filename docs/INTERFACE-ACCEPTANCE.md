# Executable interface acceptance

Level five compares the same affected capability through the CLI, the Web HTTP
API, MCP over a real stdio process and Ouroboros tool handlers. The optional
agent-plugin check starts its actual manifest launcher. The command inventory
comes from `contract.PARITY`, tools from `contract.PLUGIN`, and doors from
`contract.access()`. A changed route or an unknown requested capability fails;
the report lists commands it did not exercise. Add an executable scenario before
claiming that a new capability passed this level.

```sh
python3 src/tools/check_interfaces.py --commands metrics lifestyle --out /tmp/interfaces.json
```

With no `--commands`, all supported scenarios run in English and Russian:
measurements, lifestyle, overview, compact visit document, both system registers,
medications, labs, ClinVar, saved PGS, recomputation preview and dictated notes.
The tool copies only its bundled synthetic fixture into a temporary directory;
it clears inherited profile/workstation/genome settings before importing the
engine. No real genome is prepared. All child processes have bounded timeouts;
the local server and temporary profile are closed on exit.

Compare complete CLI/Web payloads and MCP structured content where supplied,
plus CLI/MCP/plugin text. Only the transport container envelope and MCP report
wrapper are handled separately; measurement dates, sources, qualifications and
available actions remain in the comparison. The system tool's appended retelling
rule is allowed, while the complete CLI report must remain present. Different
acknowledgements for dictated writes are compared by their persisted JSON.
Missing-date refusals and stale-screen writes must preserve every profile byte.

## Installed delivery

Build the sanitized repository, build and install its actual wheel into a fresh
environment. Copy this driver and `tests/fixtures/profile` from that build to an
external acceptance directory preserving their relative paths. Run from there,
with no source checkout in `PYTHONPATH`, using the installed interpreter:

```sh
env -u PYTHONPATH /tmp/scholion-installed/bin/python src/tools/check_interfaces.py --installed --agent-plugin /tmp/scholion-plugin --out /tmp/installed-interfaces.json
```

The plugin directory contains the delivered `.mcp.json` and launcher. The driver
reads the manifest and requires the console script beside this interpreter before
starting the launcher; it must not fall back to another local installation. Record
the wheel digest, driver/fixture/plugin digests and interpreter with
`candidate_evidence.py` or the release ledger. Evidence output is append-only.

This is not a browser rendering test, a model dialogue or a native host GUI test.
The Ouroboros registered adapter, its proxy/companion, browser rendering and OS
printing have separate acceptance records. `check_ouroboros_host.py` exercises a
real supported host without a model. The preview scenario does not prove a full
genome recalculation; use its existing synthetic worker/failure/cancellation
checks and matching real-data evidence where required. Never label these absent
checks passed just because the common handlers agreed. Mandatory full source and
sanitized-package gates remain unchanged.
