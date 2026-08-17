"""No genomic coordinate is written down twice.

`src/ingest/extract_pgx_loci.sh` is the documented next step after building a VCF:
`fastq_to_vcf.sh`, `README_track2.md` and `PREPARING-THE-GENOME.md` all send the
reader to it. It carried its own table of seventeen rsID→position pairs, parallel
to `src/scholion/knowledge/loci.json`, and by the time anybody compared them eight
of the seventeen disagreed:

* both CYP2C19 markers on chromosome **19** — the gene is on **10**;
* both TPMT markers and `rs67376798` (DPYD) at their **GRCh37** positions, under a
  heading that says GRCh38 — TPMT off by 231 bases, DPYD by almost a million;
* the two CYP2D6 markers swapped with each other;
* `rs55886062` present in the script and absent from the catalogue.

None of that surfaces as an error. `bcftools` finds no row at a wrong position and
the marker is written out as `./. (ref/not covered)` — the same output a position
the sequencing genuinely missed produces. A person following the documented route
is told nothing was found where their genotype was.

The repair is not "correct the eight": it is that the script reads the catalogue,
so there is no second table to drift. What is checked here is that property, not
those eight numbers — the numbers would be right for exactly as long as nobody
edits either side.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

import support

INGEST = support.ROOT / "src" / "ingest"
SCRIPT = INGEST / "extract_pgx_loci.sh"
CATALOGUE = support.ROOT / "src" / "scholion" / "knowledge" / "loci.json"

#: An rsID and a `chrom:pos` within a few characters of each other — the shape of a
#: coordinate table wherever it is written. Deliberately loose: it costs a comment
#: to work around and the point is that working around it is a decision.
COORD_TABLE = re.compile(r"rs\d+\D{0,40}\b\d{1,2}:\d{6,}")


class TestNoScriptCarriesItsOwnCoordinates(unittest.TestCase):

    def setUp(self):
        if not INGEST.is_dir():
            self.skipTest("the ingest scripts are not part of this build")

    def test_no_ingest_script_holds_an_rsid_beside_a_position(self):
        offenders = []
        for f in sorted(INGEST.iterdir()):
            if f.suffix not in (".sh", ".py") or not f.is_file():
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue          # the prose above may quote what went wrong
                if COORD_TABLE.search(line):
                    offenders.append(f"{f.name}:{n}")
        self.assertEqual(offenders, [],
                         "a coordinate table has come back into a processing script: "
                         + ", ".join(offenders) + " — the catalogue is the only place a "
                         "position is written down")


class TestTheScriptTakesItsLociFromTheCatalogue(unittest.TestCase):

    def setUp(self):
        if not (SCRIPT.exists() and CATALOGUE.exists()):
            self.skipTest("the script or the catalogue is not part of this build")
        self.text = SCRIPT.read_text(encoding="utf-8")
        self.loci = json.loads(CATALOGUE.read_text(encoding="utf-8"))["loci"]

    def _genes(self):
        m = re.search(r'GENES="\$\{PGX_GENES:-([^}]*)\}"', self.text)
        self.assertIsNotNone(m, "the script no longer declares the genes it scans")
        return m.group(1).split()

    def test_it_reads_the_catalogue_file(self):
        self.assertIn("loci.json", self.text)

    def test_every_gene_it_names_exists_in_the_catalogue(self):
        """A gene with no loci scans nothing, silently — the same failure one level up."""
        have = {(e.get("gene") or "").upper() for e in self.loci.values()}
        missing = sorted(g for g in self._genes() if g.upper() not in have)
        self.assertEqual(missing, [], "the script scans genes the catalogue knows no locus for: "
                                      + ", ".join(missing))

    def test_the_markers_the_interpretation_model_needs_are_within_its_reach(self):
        """The pharmacogenetic model computes phenotypes from named rsIDs.

        If the extraction pass does not reach them, the documented route ends with a
        profile the model cannot use — and, again, without an error.
        """
        kb = json.loads((support.ROOT / "src" / "scholion" / "knowledge"
                         / "cpic_drug_gene.json").read_text(encoding="utf-8"))
        genes = {g.upper() for g in self._genes()}
        need = {m["rsid"] for gname, g in kb["genes"].items() if gname.upper() in genes
                for m in g.get("markers", []) if m.get("rsid")}
        reach = {rs for rs, e in self.loci.items() if (e.get("gene") or "").upper() in genes}
        self.assertEqual(sorted(need - reach), [],
                         "the interpretation model needs positions the extraction pass does not "
                         "scan")

    def test_the_extraction_emits_the_catalogue_positions_unchanged(self):
        """Run the script's own selection step and compare it with the catalogue.

        This is the check the eight wrong numbers would have failed. It runs the
        embedded Python rather than the whole script, because the rest of it needs
        bcftools and a VCF.
        """
        body = self.text.split("<<'LOCI_PY'", 1)
        self.assertEqual(len(body), 2, "the selection step is no longer a LOCI_PY block")
        code = body[1].split("LOCI_PY", 1)[0]
        p = subprocess.run([sys.executable, "-c", code, str(CATALOGUE), *self._genes()],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr[-600:])
        rows = [l.split("\t") for l in p.stdout.splitlines() if l.strip()]
        self.assertTrue(rows, "the selection step emitted nothing")
        for rs, coord, gene, *_ in rows:
            with self.subTest(rsid=rs):
                e = self.loci[rs]
                self.assertEqual(coord, f"{e['chrom']}:{e['pos']}")
                self.assertEqual(gene, e["gene"])

    def test_the_locus_the_repair_dropped_is_named_rather_than_forgotten(self):
        """`rs55886062` (DPYD *13) existed only in the script's own table.

        Reading the catalogue means it is no longer scanned. That is a real loss of
        coverage on an actionable allele, and the rule of this project is that a
        loss is written down where the decision lives, not left to be rediscovered.
        """
        meta = json.loads(CATALOGUE.read_text(encoding="utf-8"))["_meta"]
        self.assertIn("rs55886062", json.dumps(meta, ensure_ascii=False),
                      "the dropped locus is not named anywhere in the catalogue's own notes")


if __name__ == "__main__":
    unittest.main()
