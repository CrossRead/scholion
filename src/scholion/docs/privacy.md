# Privacy and local data

Scholion is a local analysis engine for individuals and clinicians. It has no
Scholion account, hosted medical-record service or analytics endpoint. The core
computes without a language model and does not upload source medical files for
analysis. This is not a promise that every integration keeps every answer local.

## Containers and identity

One container holds one person's profile, genome, raw documents, working data
and archives, including explicitly declared external storage. A workstation can
register several containers. The local CLI and web interface may display an
optional human label; model tools receive the technical container ID instead,
not that label. Keep the ID-to-person mapping outside Scholion.

A technical ID is not anonymisation. Genotypes, laboratory values and dates,
prescriptions, wearable readings and source-file provenance in an answer can be
personal data even without a name. Protect data directories and workstation
settings with the machine's access controls and your retention policy.

## What an assistant host receives

MCP and plugin tools send their requested answers to the host that called them.
Those answers identify the active container and may contain medical data. If the
host uses a remote model, the answer can reach its provider and may be retained
under that host's policies. A local model has a different boundary; Scholion
cannot enforce the host's logging, training, retention or onward disclosure.
Review those policies before connecting real records. Do not upload personal
files, exports or unredacted tool output to a public issue tracker.

The server pins an agent conversation to one container. After a human switches
containers, it refuses subsequent calls with `container.changed` rather than
returning the new person's data in the old conversation. Start a new conversation.
No model tool lists, switches, exports or erases containers. An assistant with
terminal access can run CLI commands or read files; the skill's permission rules
are not an operating-system sandbox.

Lower-evidence genetic positions reach a model with their level and hypothesis
passport. They are not conclusions. Level E has no conclusion. The safety canon
requires the assistant to disclose its role and the container at the start, and
to leave decisions to the treating clinician.

## Network requests made by Scholion

Local analysis does not require a network. Optional name lookups send minimal
query terms, not a profile or a source document:

| Operation | Destination | What is sent |
|---|---|---|
| Drug-name and class lookup | NLM RxNorm/RxClass, CPIC; a translation service for a Russian name | The drug name and identifiers needed for the lookup; the name can itself be personal information |
| Locus lookup | Ensembl | The requested rsID or gene query |
| Version check | PyPI | The Scholion package name, not medical data |
| Confirmed update | PyPI/package download infrastructure | The package request; installation needs the person's permission |

The first tool call can also check the public package version at most once a
day so the assistant can report an available update. Optional preparation and
reference-refresh commands download data from their declared public sources;
they are not background uploads of a person's medical files. The Assistant
screen and `scholion assistant` list the build's network hosts. Network requests
also disclose ordinary connection metadata to the service and network operator.

`SCHOLION_OFFLINE=1` blocks Scholion's outbound requests. It does not block an
assistant host from sending a prompt or tool answer to its model provider.

## Local server and journals

The web server binds to `127.0.0.1`, not the LAN. This is a local interface,
not a multi-user network service with authentication or role-based access.
Protect the machine and do not expose it through a proxy or port forwarding.

On a registered workstation, access attempts are journalled inside the container
and in the clinic journal beside workstation settings. Entries contain technical
ID, UTC time, action and surface, not the human label, clinical contents or
command arguments. An access-attempt entry is not proof of a successful action.
The clinic journal survives container erasure. These are local records, not
tamper-proof evidence; a person with filesystem access can change them.

## Export, erasure and backups

Export and erasure are deliberate human-only operations. Export writes a local
archive containing the complete owned container, including raw originals and
its journal. Workstation settings and the clinic journal do not travel. The
archive is medical data, not the public software package; store it accordingly.

Erasure requires preview and confirmation and includes raw originals and owned
external storage. Shared, unavailable or ambiguously owned storage refuses
rather than guessing. Keep originals required by your retention policy elsewhere
before confirming. Erasure does not remove previously exported copies, backups,
filesystem snapshots, recovery sectors or copies retained by an assistant host.
It is not forensic secure erasure or a claim of legal compliance.

See `scholion doc container-lifecycle` for the exact ownership, preview and
failure behaviour. This policy is also available with `scholion doc privacy`.
