# Logging an experiment in one action (macOS Shortcuts)

The daily "protocol followed / violated" log entry is the only action in the project
the user performs **every day**, and whether the experiment's conclusion is honest
depends directly on it: a day without an entry counts as unknown, and once entry
coverage drops below 80 % the verdict is downgraded to descriptive. Requiring a
terminal to be opened for this is a reliable way to end up with an experiment that
has no entries.

Below is how to put it on a shortcut, a hotkey or your voice without adding a single
dependency to the project.

## What is already in place

`src/tools/nof1_quick_log.sh` — a wrapper that finds today's running block by itself
and does not require remembering the experiment id:

```bash
bash src/tools/nof1_quick_log.sh ok                      # followed
bash src/tools/nof1_quick_log.sh violated "coffee at 16:00" # violated, with a reason
bash src/tools/nof1_quick_log.sh status                  # which phase is running
```

If no block is running today, the script says so and writes nothing.

## A shortcut in Shortcuts (2 minutes)

1. Open **Shortcuts** → new shortcut.
2. Add the **Run Shell Script** action.
3. Shell `/bin/bash`, text (substitute your own path):

   ```bash
   cd "$HOME/path/to/Scholion-project-files" && bash src/tools/nof1_quick_log.sh ok
   ```

4. Give the shortcut a clear name — for example "Experiment: followed". Make a second
   copy with `violated` for a day with a violation.
5. In the shortcut's properties turn on **Pin in Menu Bar** — and the log entry is one
   click away from any application. The same place is where a **hotkey** is assigned,
   and the shortcut's name becomes the voice phrase for Siri.

From there it works like any other macOS action: a click in the menu bar, a key
combination, or "Hey Siri, experiment followed".

## Why not through the local server

The tempting option is "add an `/api/nof1/log?status=ok` endpoint to `server.py` and
call it from Shortcuts". It should not be done, and here is why.

The server listens on `127.0.0.1` — that protects against the neighbours on your Wi-Fi,
but **it does not protect against the browser**: any open tab can send a request to
localhost, and for a GET endpoint that takes a single image tag in HTML. The result is
classic CSRF — an unrelated site silently corrupts your experiment's data. For a
state-changing action that is extra attack surface with nothing gained: Shortcuts runs
a shell command directly perfectly well.

If the endpoint does turn out to be needed — to log from a phone, say — it must accept
POST only, require a local secret from a file with `600` permissions, and check the
`Origin` header. Without all three conditions it is better not built at all.

## Launching the application itself

The project needs no separate menu-bar app: the root already contains
`Scholion.command` and `Scholion.app` — a double click brings up the local
server and opens the interface in a browser. The page can be added to the Dock as a web
app through Safari ("Add to Dock"), and it will behave like an ordinary Mac
application. A native wrapper (`rumps`/PyObjC) would require another external dependency,
and a platform-specific one. The package declares exactly one — `pdfplumber`, for
reading laboratory PDFs — and every line of analysis runs on the standard library.
Keeping that list at one is worth more than a dock icon.
