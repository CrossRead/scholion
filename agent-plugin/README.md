# Scholion — plugin

Scholion supports individuals and clinicians reading one person's medical data
at a time: the genome (VCF), years of
laboratory forms, current prescriptions and wearable exports. It answers questions
such as «does this drug fit my genotype», «which of my results moved, and what
is acting on them» and «what can this data not tell me». Every finding carries its
evidence level and says what it rests on: whether a genotype was read or assumed,
and how much of a gene was covered.

It is **not a medical device**. It does not diagnose, does not start or stop
therapy and does not change doses. What it produces is material for a
conversation with a physician.

## One person per conversation

An individual can use one local container; a clinician can register several on
the same machine. Each contains one person's data. Tool answers carry the active
container's technical ID, never its optional human label. The mapping from ID
to person stays outside Scholion. The local web interface has Personal and Visit
display modes; changing the mode does not change the patient.

The tool server pins its conversation to the active container. If a person
switches containers, subsequent calls refuse with `container.changed`; start a
new conversation rather than combining two people's answers. The skill requires
the assistant to disclose that it is preparing answers from that container's
data and that the treating clinician makes the decisions.

No model tool lists, switches, exports or erases patients. A human performs
those operations in the local CLI or web controls. An assistant with shell
access has a different permission boundary: the instruction forbids browsing or
switching people on its own; terminal access is not a technical sandbox.

This folder is one package with two manifests: `plugin.json` and `mcp.json` for
clients that read Agent Plugins, and `.claude-plugin/plugin.json` and `.mcp.json`
for Claude. It holds the skill (`skills/scholion/`), the safety rules
(`skills/scholion/reference/assistant-rules.md`) and a launcher for the local tool
server (`scripts/scholion-mcp`).
These manifests do not mean the plugin has been accepted into a public catalogue.

## Before you install it

The plugin does not install the engine, and the launcher installs nothing. Install
it once:

```
pipx install scholion
```

(or `python3 -m pip install --user scholion`). Python 3.10 or newer, standard
library only. If the engine is missing, the server refuses to start and prints
this command.

The server runs on the machine that holds the data. An app that cannot start a
local process cannot use this plugin.

## Where the data goes

- **Source files stay on the disk.** The engine reads them locally and does not
  upload medical files for analysis. Lookups and host-provided models have the
  separate boundaries below.
- **What reaches the model.** A tool's answer is handed to the client. If it uses
  a remote model, that answer can reach the model's provider under the client's
  policies. A tool answers only what it was asked, but
  the answer is about the person. Findings below the strong evidence levels reach
  the model labelled as hypotheses, together with the rule for how they may be
  retold.
- **Tools that ask the network.** Each is marked `openWorldHint` and sends only the
  name it was given:

  | Tool | Hosts | What leaves |
  |---|---|---|
  | `sch_check_drug_gene`, `sch_check_prescription` | rxnav.nlm.nih.gov, mor.nlm.nih.gov, api.cpicpgx.org, api.mymemory.translated.net | the drug name, when the local base does not know it |
  | `sch_genome_lookup` | rest.ensembl.org | the rsID or gene symbol |
  | `sch_version` | pypi.org | nothing about the person |
  | `sch_update` | pypi.org | nothing about the person; only after the person says yes |

- **The update question.** Once a day, whichever tool is called first also asks
  pypi.org whether a newer build exists, so the assistant can say so. Nothing about
  the person is sent. `SCHOLION_OFFLINE=1` turns every request off, this one
  included.

The technical ID is not anonymisation: an answer can contain genotypes,
measurements, dates, medications and file provenance. Review the host's data
handling before using real records. Offline mode blocks Scholion's own network
requests, not a host's requests to a model provider. The full policy is
[PRIVACY.md](PRIVACY.md), copied from the project's canonical policy.

## What it writes

Six tools write, and each says so (`readOnlyHint: false`):

- `sch_ingest_labs` — transcribes a folder of laboratory forms the person pointed at;
- `sch_focus_log` — records what the person dictates;
- `sch_lab_draw` — records why one day has two blood draws;
- `sch_marker_propose` — records a proposed name for a marker nobody recognised;
- `sch_recompute` — rebuilds derived files, and only with confirmation;
- `sch_update` — installs a newer build, and only with the person's own yes.

No tool records a value the model settled on itself.

## Try it on the demo

Use `scholion init --demo` only in an empty, deliberately selected test container.
It creates the synthetic profile that the following tool calls read; it is not
permission to overwrite an existing person's records. Then ask:

1. «Call `sch_rules`, then give me the second opinion before my visit.»
2. «I've been prescribed omeprazole — check it against my genome and my current medicines.»
3. «What can't my data tell me about my thyroid?»

## Rules the assistant follows

`sch_rules` returns the safety rules in full. Among Scholion's own documents they
come first. They do not ask the model to set aside the app it runs in or the person
it works for.

Licence: Apache-2.0 (`LICENSE`). Source: https://github.com/CrossRead/scholion
