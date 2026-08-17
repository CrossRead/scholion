# Scholion — an Ouroboros plugin

The implementation lives inside the package as `scholion/ouroboros_tools.py`,
so `pip install scholion` delivers it too. This folder holds a thin re-export
for the case where the project is unpacked as a folder and never installed:
one implementation, two ways to reach it.

Ouroboros discovers tools by scanning its own tools package, so the module is
copied there once. The contract is `get_tools() -> list[ToolEntry]`.

## Install

```bash
pip install scholion
cp "$(python3 -c 'import scholion.ouroboros_tools as m; print(m.__file__)')" \
   <ouroboros>/ouroboros/tools/
export SCHOLION_REPO_DIR=~/.local/share/scholion   # where your data lives
```

Without an install, copy `scholion_tools.py` from this folder instead and put
the project's `src` on `PYTHONPATH`.

Self-check outside Ouroboros: `python3 -m scholion.ouroboros_tools` prints the
tool list.

## Tools

14 tools with the `sch_` prefix: a second opinion on a drug, drug-gene check,
lab analysis, suggested tests, locus lookup, ClinVar findings, health metrics,
lifestyle, polygenic scores, longevity, goals, biological age, provenance and
lab ingest.

User data (`profile/`, `genome/`) stays local and is not part of the plugin.
