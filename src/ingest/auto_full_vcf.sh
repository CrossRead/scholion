#!/bin/bash
# =============================================================================
# auto_full_vcf.sh — wait for the alignment (fastq_to_vcf.sh) to finish and then AUTO-start
# the full VCF computation (call_full_vcf.sh). Smarter than a «schedule»: it watches for
# actual completion (no bwa/samtools processes + a stable markdup.bam), not for the clock.
#
# Run it in the background (it survives closing the Terminal and sleeping in between):
#   nohup bash '<path>/auto_full_vcf.sh' >/dev/null 2>&1 &
# Progress/log:
#   tail -f ~/genomic_work/$SAMPLE/auto_full_vcf.log
# Stop waiting (if you change your mind):
#   pkill -f auto_full_vcf.sh
# -----------------------------------------------------------------------------
set -u
. "$(dirname "$0")/_sample.sh"

WORKDIR="${WORKDIR:-$HOME/genomic_work/$SAMPLE}"
MARKED="$WORKDIR/${SAMPLE}.markdup.bam"
HERE="$(cd "$(dirname "$0")" && pwd)"
CALL="$HERE/call_full_vcf.sh"
LOG="$WORKDIR/auto_full_vcf.log"

mkdir -p "$WORKDIR"
say(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }
notify(){ osascript -e "display notification \"$1\" with title \"Scholion\"" >/dev/null 2>&1 || true; }

[ -f "$CALL" ] || { say "❌ call_full_vcf.sh was not found next to it ($CALL). Stopping."; exit 1; }

say "Waiting for the alignment to finish. Readiness = no bwa/samtools processes AND a stable $MARKED."
STABLE=0
while true; do
  RUN="$(pgrep -x bwa 2>/dev/null; pgrep -x bwa-mem2 2>/dev/null; pgrep -x samtools 2>/dev/null)"
  if [ -z "$RUN" ] && [ -f "$MARKED" ]; then
    S1=$(stat -f%z "$MARKED" 2>/dev/null || echo 0)
    sleep 90
    S2=$(stat -f%z "$MARKED" 2>/dev/null || echo 0)
    if [ "$S1" = "$S2" ] && [ "${S1:-0}" -gt 1000000 ]; then
      STABLE=$((STABLE + 1))
      say "markdup.bam is stable (~$((S1 / 1024 / 1024)) MB), confirmation $STABLE/2…"
      [ "$STABLE" -ge 2 ] && break
    else
      STABLE=0
    fi
  else
    STABLE=0
    sleep 120
  fi
done

say "✅ The alignment is finished. Starting call_full_vcf.sh…"
notify "Alignment done — computing the full VCF"
bash "$CALL" >>"$LOG" 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then
  say "⚠️ call_full_vcf.sh exited with code $RC. Details in the log: $LOG"
  notify "Error while computing the VCF — see the log"
  exit "$RC"
fi

say "🎉 The full genomic database has been computed (the genome/ folder). Starting the ClinVar annotation…"
notify "The full VCF is ready — computing the clinically significant findings (ClinVar)"
ANN="$HERE/annotate_clinvar.sh"
if [ -f "$ANN" ]; then
  bash "$ANN" >>"$LOG" 2>&1
  RC2=$?
  if [ "$RC2" -eq 0 ]; then
    say "✅ Everything is ready: the full VCF + the ClinVar findings (genome/clinvar_hits.tsv)."
    notify "Done: the full VCF + the clinically significant findings"
  else
    say "⚠️ annotate_clinvar.sh code $RC2 — the VCF is ready, the annotation can be repeated by hand. Log: $LOG"
    notify "The VCF is ready; the ClinVar annotation failed — see the log"
  fi
else
  say "ℹ️ annotate_clinvar.sh was not found next to it — skipping the annotation (the VCF is ready)."
fi
