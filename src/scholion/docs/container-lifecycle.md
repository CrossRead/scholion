# Exporting and erasing a container

These are human-only operations in the CLI and local web interface. No model
tool can export or erase a container. A registered technical ID is mandatory;
explicit data-directory environment overrides are refused for these operations.

## Export

```sh
scholion export --patient demo-001 --to /absolute/local/path/demo-001.tar.gz --json
```

Choose a new destination outside all registered containers and their sources.
The destination must not already exist. The archive contains the five data
slots, their owned external storage, remaining local caches, `container.json`,
the local journal and an export manifest. Workstation settings and the clinic
journal do not travel. The archive is personal data; it is not the public
Scholion package and must not be uploaded as a bug report.

The archive is written to a private temporary file and installed at its final
name only when the inventory still matches. A failed attempt leaves no partial
archive at that name. This is a local backup/export, not an automated import or
cross-machine synchronization service. External absolute paths in `sources.json`
remain the original declarations and must be reviewed when restoring elsewhere.

## External ownership is explicit

A source declaration alone is not permission to delete every file in a folder.
After checking that a directory is exclusively owned by one container, its
administrator may place `.scholion-owner.json` inside that directory:

```json
{"container": "demo-001", "scope": "."}
```

For an external per-domain file (for example `labs.json`), the declaration's
`scope` is that exact file name, not `.`. Only the known domain file and its
ownership declaration are included, not neighboring files. Unknown external
source kinds outside owned slots refuse rather than guess their scope. A selected
BAM, VCF or reference outside those slots also refuses; review its ownership
and storage layout first. A shared reference is not made private by renaming it.

The software never creates ownership declarations automatically. A declaration
does not override another registered container's reference to the same or an
overlapping path. Symlinks, hardlinked files, special files, unavailable sources,
malformed settings and overlapping roots also refuse. Disconnecting an external
drive must not turn an incomplete export into a reported success.

## Erase: inspect, then confirm

The active container cannot be erased. First deliberately select another
container, then inspect the target's complete inventory:

```sh
scholion erase --patient demo-001 --json
```

The preview lists files, byte count and a digest, and removes nothing. After
reviewing it, repeat the exact ID and replace `DIGEST_FROM_PREVIEW` below:

```sh
scholion erase --patient demo-001 --confirm demo-001 --digest DIGEST_FROM_PREVIEW --json
```

An intervening change invalidates the confirmation. Erasure includes raw
originals, external owned files, local profile data and caches. Preserve any
originals required by your retention policy separately **before** confirming.
Scholion cannot undo erasure. This removes files, not operating-system snapshots,
backups, exported copies or recoverable storage sectors; it is not forensic
secure erasure and does not by itself establish legal compliance.

A failed deletion returns `ok: false` and the inventory actually removed. An
`erasing` marker prevents new operations on an incompletely erased container;
inspect the local files and restore from a separately retained backup before
repairing the registry/marker. Do not simply clear the marker to silence the
refusal. Workstation state and code outside the five slots are not deleted.

## Journals

On a registered workstation, data access attempts are recorded locally and in
`clinic-journal.jsonl` beside `workstation.json`. Records contain only technical
ID, UTC time, action and surface: `cli-tty`, `cli-script`, `web`, `mcp` or
`ouroboros`. They contain no label, clinical content or command arguments.
Read/write entries describe an access attempt, not proof that it succeeded.
Export is recorded as an attempt; erasure additionally records its completion
or failure. The clinic journal survives erasure; the container journal travels
with export and is removed with its container.

These are local audit records, not tamper-proof legal evidence. A local user
with filesystem access can alter them. Explicit environment overrides and the
legacy unregistered single-profile mode are not a clinic audit boundary.

## Local web interface

On a registered workstation, use **Export / erase** beside the patient selector.
Export names a local destination on the machine running Scholion. Erasure first
shows the inventory, then requires typing the ID. Browser requests do not
upload or download the medical archive; it stays at the explicit local path.
