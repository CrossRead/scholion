# Shared resolver of the sample identifier for the pipeline scripts.
# To use it:  . "$(dirname "$0")/_sample.sh"
#
# Order: the SAMPLE environment variable → the .sample file in the project root → an
# error. The real number is never hard-coded: it is personal, whereas src/ is a
# portable layer that goes out to other people.
if [ -z "${SAMPLE:-}" ]; then
  _sch_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  if [ -f "$_sch_root/.sample" ]; then
    SAMPLE="$(tr -d ' \t\r\n' < "$_sch_root/.sample")"
  fi
fi
if [ -z "${SAMPLE:-}" ]; then
  echo "❌ the sample identifier (SAMPLE) is not set." >&2
  echo "   Once:        echo 'YOUR_ID' > \"$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.sample\"" >&2
  echo "   Or per run:  SAMPLE=YOUR_ID bash $0 ..." >&2
  exit 1
fi
export SAMPLE
