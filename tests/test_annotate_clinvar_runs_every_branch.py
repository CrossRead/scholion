"""annotate_clinvar.sh runs every branch to the end under `set -u` — executed, not read.

Task 121. The first quarterly reanalysis (01.09.2026) stopped on «GEN: unbound
variable» in the branch that renames ClinVar's contigs for a `chr`-prefixed
genome. The name had leaked from the orchestrator, and the same name stood in
three places, the second and third invisible until the first was fixed.
`shellcheck` does not report an unbound ALL-CAPS name, so the only guard this
class of defect has is running the branch.

The external programs are replaced by stubs on PATH: `curl` writes the file it
is told to, `bcftools` answers `view -h` with a header — `chr` contigs or not,
as the case needs — and writes whatever `-o` names; `tabix` does nothing. The
genome is a sparse file above the script's size floor. Nothing is downloaded,
nothing large is written, and each case takes a fraction of a second.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import support

SCRIPT = support.ROOT / "src" / "ingest" / "annotate_clinvar.sh"

_BCFTOOLS = r'''#!/bin/sh
# view -h FILE: a header. The personal VCF carries chr contigs when CHR_PREFIX=1.
if [ "$1" = "view" ] && [ "$2" = "-h" ]; then
  case "$3" in
    *clinvar*) echo '##fileformat=VCFv4.2'; echo '##fileDate=2026-08-29'; echo '##contig=<ID=1>' ;;
    *) echo '##fileformat=VCFv4.2'
       if [ "${CHR_PREFIX:-0}" = "1" ]; then echo '##contig=<ID=chr1>'; else echo '##contig=<ID=1>'; fi ;;
  esac
  exit 0
fi
# view -i ... FILE (the extraction) and query: one significant row
if [ "$1" = "view" ]; then echo 'row'; exit 0; fi
if [ "$1" = "query" ]; then cat >/dev/null; printf 'chr1\t100\tA\tG\t0/1\trs1\tPathogenic\tx\ty\n'; exit 0; fi
# anything with -o OUT: write OUT
out=""; prev=""
for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done
[ -n "$out" ] && : > "$out"
echo "$*" >> "${CALLS:-/dev/null}"
exit 0
'''
_CURL = r'''#!/bin/sh
out=""; prev=""
for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done
[ -n "$out" ] && : > "$out"
exit 0
'''
_TABIX = "#!/bin/sh\nexit 0\n"


@unittest.skipUnless(SCRIPT.exists() and shutil.which("sh") and shutil.which("bash"),
                     "the script and a POSIX shell are needed")
class TestEveryBranchRunsToTheEnd(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="acv_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name, body in (("bcftools", _BCFTOOLS), ("curl", _CURL), ("tabix", _TABIX)):
            p = self.bin / name
            p.write_text(body, encoding="utf-8")
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self.genome = self.root / "genome"
        self.genome.mkdir()
        self.vcf = self.genome / "SAMPLE.full.vcf.gz"
        with open(self.vcf, "wb") as f:          # sparse: above the 10 MB floor, nothing written
            f.truncate(11_000_000)
        self.calls = self.root / "calls.txt"

    def run_it(self, chr_prefix: bool, reference: bool):
        if reference:
            (self.genome / "GRCh38.fa").write_text(">chr1\nACGT\n", encoding="utf-8")
        env = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin", "HOME": str(self.root),
               "SCHOLION_REPO_DIR": str(self.root), "SCHOLION_GENOME_DIR": str(self.genome),
               "SCHOLION_CLINVAR_CACHE": str(self.root / "cache"), "CALLS": str(self.calls),
               "CHR_PREFIX": "1" if chr_prefix else "0", "LC_ALL": "C"}
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, encoding="utf-8",
                              timeout=60, stdin=subprocess.DEVNULL)

    def assert_finished(self, p):
        self.assertNotIn("unbound variable", p.stderr)
        self.assertEqual(0, p.returncode, p.stderr[-800:])
        self.assertIn("Done", p.stdout)
        meta = json.loads((self.genome / "clinvar_meta.json").read_text(encoding="utf-8"))
        self.assertEqual(("2026-08-29", 1), (meta["clinvar_date"], meta["hits"]))

    def test_the_chr_branch_with_a_reference(self):
        p = self.run_it(chr_prefix=True, reference=True)
        self.assert_finished(p)
        self.assertIn("--rename-chrs", self.calls.read_text(encoding="utf-8"))
        self.assertTrue(json.loads((self.genome / "clinvar_norm.json").read_text(encoding="utf-8"))["left_aligned"])

    def test_the_chr_branch_without_a_reference(self):
        """The case of 01.09.2026: chr contigs, and the FASTA search finds nothing."""
        p = self.run_it(chr_prefix=True, reference=False)
        self.assert_finished(p)
        self.assertFalse(json.loads((self.genome / "clinvar_norm.json").read_text(encoding="utf-8"))["left_aligned"])

    def test_the_plain_branch(self):
        p = self.run_it(chr_prefix=False, reference=False)
        self.assert_finished(p)
        self.assertNotIn("--rename-chrs", self.calls.read_text(encoding="utf-8") if self.calls.exists() else "")

    def test_the_guard_would_have_caught_the_leak(self):
        """The same run with the leaked name put back fails exactly as 01.09 did —
        proof that these cases execute the branch rather than walk past it."""
        broken = self.root / "broken.sh"
        text = SCRIPT.read_text(encoding="utf-8").replace('for cand in "$GENOME_DIR"/*.fa', 'for cand in "$GEN"/*.fa', 1)
        self.assertNotEqual(text, SCRIPT.read_text(encoding="utf-8"), "the line the leak was on has moved")
        broken.write_text(text, encoding="utf-8")
        env = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin", "HOME": str(self.root),
               "SCHOLION_REPO_DIR": str(self.root), "SCHOLION_GENOME_DIR": str(self.genome),
               "SCHOLION_CLINVAR_CACHE": str(self.root / "cache"), "CHR_PREFIX": "1", "LC_ALL": "C"}
        p = subprocess.run(["bash", str(broken)], env=env, capture_output=True, text=True, encoding="utf-8",
                           timeout=60, stdin=subprocess.DEVNULL)
        self.assertNotEqual(0, p.returncode)
        self.assertIn("GEN: unbound variable", p.stderr)


if __name__ == "__main__":
    unittest.main()
