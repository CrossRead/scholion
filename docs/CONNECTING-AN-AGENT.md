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
| **Agent Plugins package** | import the folder agent-plugin/ into a client that reads Agent Plugins | ChatGPT desktop, Codex, Cursor, VS Code, GitHub Copilot, Kiro — one import brings the tools and the instruction that governs them together |

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

### The Agent Plugins package

`agent-plugin/` is this product packaged in the portable format five
vendors agreed on in August 2026 — AWS, Cursor, Microsoft, OpenAI and Vercel —
which is not a protocol but a folder shape: `plugin.json`, a `skills/` directory
holding Agent Skills, and `mcp.json` describing MCP servers. Nothing in it is new
here. It is the skill folder and the tool server, in one directory a client can
import in a single step.

That single step is the whole point, and the half that matters is the second one:
through the tool interface a model is handed a list of functions and **no
instruction with it**, which is why `sch_rules` has to be a tool at all. In this
package the instruction sits in the same folder as the functions and cannot be
installed without them.

**The launcher installs nothing.** The format has no install step, so
`mcp.json` points at `./bin/scholion-mcp`. The launcher looks for an installed
engine in this order:

1. A virtual environment the client keeps for this plugin, under `PLUGIN_DATA`.
2. `scholion` on the search path.
3. `scholion` in `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and
   `~/Library/Python/3.*/bin`.
4. A Python that can import the package.

The third step exists because a desktop application started from the Dock on
macOS gets only the system search path, where neither pipx nor Homebrew puts
anything. If no engine is found, the launcher refuses and prints the command
that installs one. This product does not put software on a machine at the
moment a model first reaches for a tool.

**Installing it in ChatGPT desktop.** These steps follow OpenAI's guide to
packaging plugins.

1. Install the engine once: `pipx install scholion`.
2. In ChatGPT, open Settings → Security and login and turn on Developer mode.
3. Create `~/.agents/plugins/marketplace.json`. The `path` is counted from your
   home folder, so replace `./path/to/scholion` with the location of your copy
   of the repository:

   ```json
   {
     "name": "local-scholion",
     "interface": { "displayName": "Scholion (local)" },
     "plugins": [
       {
         "name": "scholion",
         "source": { "source": "local", "path": "./path/to/scholion/agent-plugin" },
         "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
         "category": "Productivity"
       }
     ]
   }
   ```

4. Restart ChatGPT and install Scholion from the plugin directory.
5. Ask the assistant to call `sch_version`. The answer names the build that
   runs.

Codex reads the same file. For a marketplace kept inside a repository, the
file goes in `.agents/plugins/` at the repository's root, and `path` is counted
from there.

**It runs where the data is, and only there.** A client that declares MCP servers
in a plugin runs them locally; ChatGPT labels such a plugin *Desktop only* and
will not run it on the web. That is the correct label rather than a limitation:
this product reads one person's genome and laboratory forms off their own disk,
and in a cloud sandbox there is nothing for it to read.

---

## The MCP server

**New in 0.4.0.** A host that speaks the Model Context Protocol can call the same
tools the Ouroboros plugin registers, without a plugin and without a shell.

### What it is

A **local process**, spoken to over **standard input and output**. It opens no
port, contacts no host, and has no authentication step, because there is nobody
on the other end of the pipe but the program that started it. The tool list is
derived from the plugin's rather than written a second time, so the two cannot
disagree.

### Protocol revisions

**Since 0.5.3** the server speaks both eras of the protocol:

- **`2026-07-28`, without a handshake.** Each request names its revision in
  `_meta` (`io.modelcontextprotocol/protocolVersion`). `server/discover` lists
  the revisions, capabilities and instructions. Every result carries
  `resultType`, and `tools/list` carries `ttlMs` and `cacheScope`. A revision
  the server does not know is answered with error `-32022` and the list it does
  know.
- **`2025-11-25`, `2025-06-18`, `2025-03-26` and `2024-11-05`, through
  `initialize`.** The server agrees on the revision the client asks for. A
  revision it does not know is answered with `2025-11-25`, never echoed back.
  Only `2025-03-26` receives JSON-RPC batches, because only that revision has
  them.

**Structured output.** From `2025-06-18` on, thirteen tools declare an
`outputSchema` and answer with `structuredContent`: the structure their report
was rendered from, with the same top-level fields as the matching command's
`--json`, plus a `report` field. The text block holds the rendered report
rather than the serialised JSON, and `report` repeats the same text inside the
structure. The report carries the qualifications a model must pass on, and some
clients show a model only the structure.

`scholion capabilities --json` lists them under `access.doors.mcp.protocols`.

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
