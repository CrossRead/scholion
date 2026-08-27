# Connecting an assistant to Scholion

Scholion runs on the machine that holds the data. There is **no account, no key,
no token and no credential of any kind**, and no service to authenticate
against — there is nothing to authenticate to. If a program asks you for a
«Scholion credential», see [When something asks for a key](#when-something-asks-you-for-a-key)
below: it is not Scholion, and this page says what it is instead.

The product answers this question itself, so nothing here has to be taken on
trust:

```bash
scholion capabilities --json | python3 -m json.tool | head -40
```

The `access` block lists every door, what each one costs, which environment
variables the build reads, and — derived from the source rather than promised —
that none of them holds a secret.

---

## Several doors, one engine

The heading used to count them, and the count went stale twice: a fifth door
arrived with the tool server and a sixth with the skill folder, while the word
stayed «four». `scholion capabilities --json` answers with the list, derived from
the build — this table is the readable copy of it.

| Door | Reach it with | Use it when |
|---|---|---|
| **Command line** | `scholion <command>` | the assistant can run shell commands |
| **MCP server** | `scholion mcp` | the assistant speaks the Model Context Protocol |
| **Skill folder** | copy the skill folder to ~/.agents/skills/scholion/ | the host reads skills from that shared path and has no plugin mechanism of its own |
| **Ouroboros tools module** | `import scholion.ouroboros_tools` | a classic Ouroboros checkout |
| **Ouroboros Hub skill** | the `scholion` skill | Ouroboros Hub — plus a **Scholion** tab on the Widgets page, which is where the owner is told what to load and where |

There is also `scholion serve` — a local web page for a person, bound to
`127.0.0.1`. It is not an assistant surface and has no API.

All of them run the same engine, so an answer does not depend on which door it
came through. Pick by what the host can do, not by what you want to ask.

### The skill folder

The cheapest door there is: a directory with an entry file in it. Nothing is
registered, nobody moderates it, and no plugin mechanism is involved — which is
exactly why it is worth carrying, because a host that has none of those can still
be reached.

`~/.agents/skills/` is the shared path and Codex, Gemini CLI and OpenClaw read it
as they are; Claude Code and Hermes each keep their own folder and take the same
single file. OpenClaw is also served through its own registry — that is the
supported route there, and the `git:` form of its installer is not, because it
expects a repository whose root is the skill. The README carries the table, with the date it was checked.
The directory has to be named `scholion` — the format requires the folder name
and the `name` field to match.

```bash
pip install scholion
mkdir -p ~/.agents/skills/scholion
cp "$(scholion skill --path)" ~/.agents/skills/scholion/SKILL.md
```

That one file is the whole of it. It is deliberately small and deliberately
self-describing: it tells the host what this is, what to run for the usual
requests, the safety rules that come before any answer, and — because a host
reading only this file would otherwise never learn — that a tool server and an
in-process module exist for it. The long instruction and the canon of rules are
NOT copied there; they are printed out of the installed package on demand, so
there is one copy of each and it is the one that ships.

---

## The MCP server

**New in 0.4.0.** A host that speaks the Model Context Protocol can call the same
tools the Ouroboros plugin registers, without a plugin and without a shell.

### What it is

A **local process**, spoken to over **standard input and output**. It opens no
port, contacts no host, and has no authentication step, because there is nobody
on the other end of the pipe but the program that started it. Protocol version
`2024-11-05`; the tool list is derived from the plugin's rather than written a
second time, so the two cannot disagree.

### Configure it

Most hosts take a JSON block naming a command to run. The shape differs by host;
the content does not:

```json
{
  "mcpServers": {
    "scholion": {
      "command": "scholion",
      "args": ["mcp"]
    }
  }
}
```

If `scholion` is not on the host's `PATH` — common when the host runs outside
your shell — give the absolute path (`which scholion` prints it), or start it
through the interpreter that has it:

```json
{
  "mcpServers": {
    "scholion": {
      "command": "/usr/local/bin/python3",
      "args": ["-m", "scholion", "mcp"]
    }
  }
}
```

To point the server at a profile or a genome that is not in the default place,
add the environment block the host provides:

```json
{
  "mcpServers": {
    "scholion": {
      "command": "scholion",
      "args": ["mcp"],
      "env": {
        "SCHOLION_PROFILE_DIR": "/path/to/profile",
        "SCHOLION_GENOME_VCF": "/path/to/genome.vcf.gz",
        "SCHOLION_OFFLINE": "1"
      }
    }
  }
}
```

Those are paths and switches. None of them is a secret, and none of them is
required to start.

### Check it without a host

The server is a program that reads JSON-RPC from stdin. You can talk to it by
hand, which is the quickest way to tell «not configured» from «broken»:

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | scholion mcp | head -2
```

The first line answers with the protocol version and the server's name; the
second lists the tools. If both arrive, the server works and anything still
wrong is on the host's side of the pipe.

---

## When something asks you for a key

**It is not Scholion.** There is no key to give it. Three things it usually is:

**A host that assumes every tool server is remote.** Many MCP clients were built
for servers reached over the network, where a token is the norm, and present the
same connection dialogue for a local one. Leave the credential fields empty — the
server ignores them — or use the host's «local»/«stdio» server type if it offers
one.

**An assistant that has no Scholion tools in front of it.** This is the common
case and the confusing one, because the request sounds specific. Asked to send
something to Scholion with no way to reach it, an assistant may reach for a
plausible cause — a missing credential — rather than say it cannot get there
from where it is. The tell is that it cannot name what it is asking for. Ask it
to list the tools it actually has; if none of them is a Scholion tool, no key
would have helped.

**A different program with a similar name.** Check what is actually being run.

Whatever the source, one command settles it:

```bash
scholion capabilities --json | python3 -c "import json,sys; print(json.load(sys.stdin)['access']['auth'])"
```

---

## What an assistant should know before it starts

- **Not a medical device.** Every answer is material for a conversation with a
  physician. The safety rules travel with the product: `scholion skill --rules`.
- **The data does not move.** The profile, the genome and the laboratory history
  stay on the machine. Two lookups leave it when used — a drug the local
  knowledge base does not carry, and an rsID the catalogue does not carry — and
  `SCHOLION_OFFLINE=1` disables both. `scholion assistant` prints every address
  the build can reach, scanned from its own source.
- **An answer says what it rests on.** «No findings» is qualified by how much was
  read; a genotype says whether it was called or assumed. An assistant relaying
  an answer should relay that qualification with it.
- **What to run, in order, when something is not answering:**

  ```bash
  scholion --version          # is it installed, and which build
  scholion capabilities       # what this build can do, and how to reach it
  scholion genome-status      # what it can see of the genome, and why not
  scholion limits             # what it cannot say, and what would change that
  ```
