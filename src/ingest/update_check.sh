#!/usr/bin/env bash
# A monthly check: update ClinVar, re-check the genome and show what is new.
# A snapshot of the current findings → a fresh annotation → a diff → genome/whats_new.json.
# Started by a button in the application, or by hand / on a schedule (launchd/cron).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${PROJECT_DIR:-$(cd "$HERE/../.." && pwd)}"
GEN="$PROJECT/genome"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

command -v bcftools >/dev/null 2>&1 || { echo "❌ bcftools is not in PATH. Install it (brew install bcftools) or run this from a terminal."; exit 3; }
mkdir -p "$GEN"

PREV="$GEN/clinvar_hits.prev.tsv"
if [ -f "$GEN/clinvar_hits.tsv" ]; then cp "$GEN/clinvar_hits.tsv" "$PREV"; else : > "$PREV"; fi

echo "→ updating the ClinVar database and annotating your genome (this takes a few minutes)…"
if ! PROJECT_DIR="$PROJECT" bash "$HERE/annotate_clinvar.sh"; then
  echo "❌ annotate_clinvar.sh exited with an error"; exit 4
fi

REL="$(python3 - "$GEN/clinvar_meta.json" <<'PY' 2>/dev/null || true
import json,sys
try:
    m=json.load(open(sys.argv[1]))
    print(m.get("release") or m.get("date") or m.get("clinvar_release") or "")
except Exception:
    print("")
PY
)"
TODAY="$(date +%F)"
echo "→ comparing against the snapshot taken before the update…"
python3 "$HERE/clinvar_diff.py" "$PREV" "$GEN/clinvar_hits.tsv" "$GEN/whats_new.json" "$REL" "$TODAY"
echo "✓ the check is complete ($TODAY, ClinVar ${REL:-?})"
