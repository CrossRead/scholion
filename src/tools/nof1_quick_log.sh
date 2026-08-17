#!/usr/bin/env bash
# Marking adherence to an n-of-1 protocol in a single action — for Apple Shortcuts,
# a hotkey or an icon in the Dock. It finds the running experiment itself, so the
# shortcut does not have to store its id.
#
# Usage:
#   bash src/tools/nof1_quick_log.sh ok               # protocol adhered to
#   bash src/tools/nof1_quick_log.sh violated "coffee at 16:00"
#   bash src/tools/nof1_quick_log.sh status           # which phase is on now
#
# Why NOT through an HTTP endpoint of the local server: the server listens on
# 127.0.0.1, but ANY page open in the browser can knock on that address — ordinary
# CSRF. For a request that changes experiment data this is extra attack surface
# with no gain at all: Shortcuts on macOS can run a shell command directly, and
# that is enough. If an endpoint is ever needed (for marking from a phone, say), it
# must require a local secret and accept POST only — otherwise it should not exist.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -d "$ROOT/src/scholion" ] || ROOT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT" || { echo "project root not found"; exit 1; }

ACTION="${1:-status}"
NOTE="${2:-}"

# The id of the experiment running today — from the schedule, with no manual entry
EXP_ID="$(python3 - <<'PY'
import json, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, "src")
try:
    from scholion import core
    p = Path(core.profile_dir()) / "experiments.json"
except Exception:
    p = Path("profile/experiments.json")
if not p.exists():
    sys.exit(0)
today = date.today()
for e in json.loads(p.read_text(encoding="utf-8")).get("experiments", []):
    for b in e.get("schedule", []):
        if date.fromisoformat(b["start"]) <= today <= date.fromisoformat(b["end"]):
            print(e["id"])
            sys.exit(0)
PY
)"

if [ -z "$EXP_ID" ]; then
  echo "No experiment block is running today — there is nothing to mark."
  exit 0
fi

case "$ACTION" in
  ok)        python3 src/ingest/nof1.py log "$EXP_ID" --ok ${NOTE:+--note "$NOTE"} ;;
  violated)  python3 src/ingest/nof1.py log "$EXP_ID" --violated ${NOTE:+--note "$NOTE"} ;;
  status)    python3 src/ingest/nof1.py status ;;
  *)         echo "usage: $(basename "$0") ok|violated|status [note]"; exit 2 ;;
esac
