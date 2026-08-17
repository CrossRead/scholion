#!/usr/bin/env bash
# Task #11: regular reanalysis — the world's new knowledge × an unchanged genome.
# The cadence is the owner's decision, MONTHLY by default (on the 1st, via a cloud
# reminder); the file name is historical.
#
# The genome does not change, but the knowledge bases do: ClinVar is updated weekly,
# CPIC and PharmCAT release new versions, and PGS models accumulate candidates in the
# registry. One run collects all of that into a single summary:
#   1) ClinVar: a fresh database → re-annotation of YOUR VCF → a diff (what is new/changed);
#   2) ACMG SF: a repeat scan of secondary findings against the fresh annotation;
#   3) PGS: a review of candidates for a model change (prs_model_review);
#   4) tool versions: whether new PharmCAT / PyPGx releases exist (it only reports,
#      it updates NOTHING itself — updating tools is a separate decision);
#   5) completeness of the PhenoAge panel + the checklist for the next draw
#      (draw_checklist.py): which markers are missing for biological age to be
#      computed and a series to be built;
#   6) the summary + a record in profile/reanalysis_history.json.
#
# Run: bash src/ingest/quarterly_reanalysis.sh   (minutes; needs the network)
# No data is sent anywhere — only public databases are downloaded.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="${SCHOLION_REPO_DIR:-$(cd "$HERE/../.." && pwd)}"
GEN="$PROJECT/genome"
PROFILE="$PROJECT/profile"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
TODAY="$(date +%Y-%m-%d)"

echo "══════════════════════════════════════════════════════"
echo " Regular reanalysis · $TODAY"
echo "══════════════════════════════════════════════════════"
command -v bcftools >/dev/null || { echo "❌ bcftools is missing"; exit 1; }
command -v curl >/dev/null || { echo "❌ curl is missing"; exit 1; }

echo
echo "── 1/5 · ClinVar: fresh database + diff ─────────────"
if bash "$HERE/update_check.sh"; then CLINVAR_OK=1; else CLINVAR_OK=0; echo "⚠ the ClinVar step did not finish — the summary will go without it"; fi

echo
echo "── 2/5 · ACMG SF: repeat scan ───────────────────────"
if python3 "$HERE/acmg_sf_scan.py"; then ACMG_OK=1; else ACMG_OK=0; echo "⚠ the ACMG scan did not finish"; fi

echo
echo "── 3/5 · PGS: review of model-change candidates ─────"
PGS_REVIEW="$(python3 "$HERE/prs_model_review.py" 2>&1)" && PGS_OK=1 || PGS_OK=0
echo "$PGS_REVIEW"

echo
echo "── 4/5 · tool versions (information only) ───────────"
PHARMCAT_LATEST="$(curl -fsL --max-time 20 https://api.github.com/repos/PharmGKB/PharmCAT/releases/latest 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin).get("tag_name",""))' 2>/dev/null || true)"
PHARMCAT_HAVE="$(ls "$HOME/genomic_work/pharmcat"/pharmcat-*-all.jar 2>/dev/null | sed 's/.*pharmcat-\(.*\)-all.jar/v\1/' | head -1)"
PYPGX_LATEST="$(curl -fsL --max-time 20 https://pypi.org/pypi/pypgx/json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["info"]["version"])' 2>/dev/null || true)"
PYPGX_HAVE="$(python3 -c 'import pypgx;print(pypgx.__version__)' 2>/dev/null || true)"
echo "  PharmCAT: installed ${PHARMCAT_HAVE:-?}, latest release ${PHARMCAT_LATEST:-could not check}"
echo "  PyPGx:    installed ${PYPGX_HAVE:-?}, latest release ${PYPGX_LATEST:-could not check}"
echo "  (updating the tools is a separate decision: a new version = a recomputation and a re-check of the conclusions)"

echo
echo "── 5/5 · PhenoAge and the checklist for the next draw ─"
CHECKLIST="$(python3 "$HERE/draw_checklist.py" 2>&1)" && DRAW_OK=1 || DRAW_OK=0
echo "$CHECKLIST"

echo
echo "── Summary ──────────────────────────────────────────"
python3 - "$PROJECT" "$TODAY" "$CLINVAR_OK" "$ACMG_OK" "$PGS_OK" \
  "${PHARMCAT_HAVE:-}" "${PHARMCAT_LATEST:-}" "${PYPGX_HAVE:-}" "${PYPGX_LATEST:-}" "$DRAW_OK" <<'PYEOF'
import json, sys
from pathlib import Path

proj = Path(sys.argv[1]); today = sys.argv[2]
clinvar_ok, acmg_ok, pgs_ok = (sys.argv[3] == "1"), (sys.argv[4] == "1"), (sys.argv[5] == "1")
pc_have, pc_latest, px_have, px_latest = sys.argv[6:10]
draw_ok = (len(sys.argv) > 10 and sys.argv[10] == "1")

entry = {"date": today, "steps": {}}

# ClinVar / whats_new
wn = proj / "genome" / "whats_new.json"
if clinvar_ok and wn.exists():
    d = json.loads(wn.read_text())
    cv = d.get("clinvar", {})
    new, chg = cv.get("new", []), cv.get("changed", [])
    entry["steps"]["clinvar"] = {"release": cv.get("release"), "new": len(new), "changed": len(chg)}
    print(f"  ClinVar {cv.get('release','?')}: new significant findings {len(new)}, findings that changed status {len(chg)}")
    for x in (new + chg)[:8]:
        print(f"    · {x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)[:100]}")
    if new or chg:
        print("    → review every finding by the reading rules (zygosity/inheritance/penetrance), not as a diagnosis")
else:
    entry["steps"]["clinvar"] = {"ok": False}

# ACMG
ah = proj / "genome" / "acmg_sf_hits.tsv"
if acmg_ok and ah.exists():
    rows = [l for l in ah.read_text().splitlines()[1:] if l.strip()]
    actionable = [l for l in rows if "actionable" in l.lower() or "\tyes" in l.lower()]
    entry["steps"]["acmg"] = {"rows": len(rows)}
    print(f"  ACMG SF: rows in the report {len(rows)} (see the scan output above — the gating is there)")
else:
    entry["steps"]["acmg"] = {"ok": False}

entry["steps"]["pgs_review"] = {"ok": pgs_ok, "note": "decisions on candidates are taken by hand only (--accept-model)"}
entry["steps"]["tools"] = {"pharmcat": {"have": pc_have, "latest": pc_latest},
                           "pypgx": {"have": px_have, "latest": px_latest}}
if pc_latest and pc_have and pc_latest != pc_have:
    print(f"  ⚠ PharmCAT: {pc_latest} is available ({pc_have} installed) — after updating, rerun pharmcat_run.sh and re-check the report")
if px_latest and px_have and px_latest != px_have:
    print(f"  ⚠ PyPGx: {px_latest} is available ({px_have} installed) — after updating, rerun pgx_star_alleles.sh")

# PhenoAge and the draw checklist
chk = proj / "profile" / "next_draw_checklist.json"
if draw_ok and chk.exists():
    c = json.loads(chk.read_text())
    ph = c.get("phenoage", {})
    need = c.get("need_now", [])
    cp = ph.get("complete_panels", []) or []
    entry["steps"]["draw_checklist"] = {
        "need_now": len(need),
        "phenoage_complete_panels": len(cp),
        "phenoage_trend_possible": bool(ph.get("trend_possible")),
        "phenoage_missing": ph.get("union_missing_ru", []),
    }
    print(f"  Draw checklist: {len(need)} items without a fresh value "
          f"(profile/next_draw_checklist.md)")
    if not ph.get("trend_possible"):
        miss = ", ".join(ph.get("union_missing_ru", [])) or "—"
        print(f"  PhenoAge: complete panels {len(cp)} — a series cannot be built yet. "
              f"Add to the next draw: {miss}")
    else:
        print(f"  PhenoAge: complete panels {len(cp)} — the series is computed, look at the slope")
else:
    entry["steps"]["draw_checklist"] = {"ok": False}

hist = proj / "profile" / "reanalysis_history.json"
data = json.loads(hist.read_text()) if hist.exists() else {"runs": []}
data["runs"].append(entry)
hist.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n✓ record written to {hist} (runs in the history: {len(data['runs'])})")
print("\nManual reminders (deliberately not automated):")
print("  · if the PGS models changed — run prs_top_audit.py over the new tails;")
print("  · update IPD-IMGT/HLA and LongevityMap on demand, not on a schedule;")
print("  · show the results to the assistant — it will compare them against the profile and decide what to change in the docs.")
PYEOF
