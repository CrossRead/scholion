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

#: An rsID and a `chrom:pos` within a few characters of each other — one shape of
#: a coordinate table. Deliberately loose: it costs a comment to work around and
#: the point is that working around it is a decision.
COORD_TABLE = re.compile(r"rs\d+\D{0,40}\b\d{1,2}:\d{6,}")

#: The OTHER shape, and the one that mattered. `fastq_to_vcf.sh` carried its
#: table as BED: tab-separated, `chrN <tab> start <tab> end`, the position BEFORE
#: the name and no colon anywhere. The rule above was written from the specimen
#: that had just been found — an rsID followed by `chr:pos` — and read straight
#: past all fourteen BED lines while five of them pointed at the wrong place.
#: A guard shaped like one example is green next to the next example.
#:
#: So the property is stated instead of the specimen: a genomic coordinate,
#: written down, in a script. Whether an rsID stands next to it is irrelevant —
#: a bare interval is a coordinate too, and `TPMT_region` had no rsID at all.
BED_TABLE = re.compile(r"^\s*chr[0-9XYMxym]+\s+\d{4,}\s+\d{4,}")


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
                if COORD_TABLE.search(line) or BED_TABLE.match(line):
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

    def test_the_note_about_a_withheld_locus_matches_the_catalogue(self):
        """A locus named as NOT scanned must actually not be there — and back.

        This started as a test that `rs55886062` (DPYD *13) be named in `_meta`:
        the repair that moved the script onto the catalogue dropped it, and the
        rule of this project is that a loss is written down where the decision
        lives rather than left to be rediscovered. That was right, and it aged in
        a day. Task 59 verified the coordinate against dbSNP and entered the
        locus; the note went on describing a loss that no longer existed, and
        nothing complained, because the test only asked whether the rsID appeared
        in the text.

        So the property is stated instead: whatever the note declares withheld is
        absent from `loci`, and whatever it declares closed is present. A note
        checked against the thing it describes cannot drift away from it in
        silence — which is the same demand this project makes of its own output.
        """
        cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        pending = cat["_meta"].get("pending")
        text = pending if isinstance(pending, str) else json.dumps(pending, ensure_ascii=False)
        loci = cat["loci"]

        # Sentences, so that "closed" applies to the locus in its own sentence
        # and not to every rsID in the paragraph.
        for sentence in re.split(r"(?<=[.;])\s+", text):
            for rs in re.findall(r"rs\d+", sentence):
                closed = "CLOSED" in sentence.upper()
                with self.subTest(rsid=rs, closed=closed):
                    # `assertTrue` and not `assertIn`: the failure message of the
                    # latter prints the whole catalogue, and a fifty-entry dump
                    # buries the one sentence that says what went wrong.
                    if closed:
                        self.assertTrue(rs in loci,
                                        f"{rs} is written up as CLOSED and is not in the catalogue")
                    else:
                        self.assertTrue(rs not in loci,
                                        f"{rs} is written up as withheld and IS in the "
                                        f"catalogue — the note outlived the decision")

    def test_the_note_is_not_empty(self):
        """A vacuously green check is the failure this test class exists about."""
        cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        pending = cat["_meta"].get("pending")
        text = pending if isinstance(pending, str) else json.dumps(pending, ensure_ascii=False)
        self.assertTrue(re.findall(r"rs\d+", text),
                        "the note names no locus at all, so it asserts nothing")


class TestTheVersionOfClinVarSurvivesTheHandover(unittest.TestCase):
    """The key one script writes is the key the next one reads.

    `annotate_clinvar.sh` records the version of the base it downloaded;
    `update_check.sh` reads it back and hands it to `clinvar_diff.py`, which
    stamps it on the reanalysis report — the report whose whole claim is «against
    THIS version of ClinVar your genome now looks like this».

    The reader asked for `release`, then `date`, then `clinvar_release`. The
    writer has always written `clinvar_date`. Three guesses, none of them right,
    and a fallback chain is precisely what hides that: no exception, no empty
    result to notice, just a field that is blank in every report ever produced.
    Verified on the owner's real `clinvar_meta.json`, whose keys are
    `clinvar_date, synced, hits, url, restored, note`.

    Checked as a property rather than as a constant: whichever key the writer
    moves to, the reader has to move with it.
    """

    WRITER = INGEST / "annotate_clinvar.sh"
    READER = INGEST / "update_check.sh"

    def _written_keys(self):
        text = self.WRITER.read_text(encoding="utf-8")
        line = [l for l in text.splitlines() if "clinvar_meta" in l or '\\"synced\\"' in l]
        return set(re.findall(r'\\\\"([a-z_]+)\\\\":', text)) | set(re.findall(r'"([a-z_]+)":', text))

    def _read_keys(self):
        text = self.READER.read_text(encoding="utf-8")
        block = text[text.find("clinvar_meta.json"):]
        block = block[:block.find("TODAY=")] if "TODAY=" in block else block
        return set(re.findall(r'\.get\("([a-z_]+)"\)', block))

    def test_the_reader_asks_for_a_key_the_writer_writes(self):
        read, written = self._read_keys(), self._written_keys()
        self.assertTrue(read, "no key is read from clinvar_meta.json at all")
        unknown = sorted(read - written)
        self.assertEqual(
            unknown, [],
            f"update_check.sh reads {unknown} from clinvar_meta.json, which "
            f"annotate_clinvar.sh never writes (it writes {sorted(written & {'clinvar_date','synced','hits','url'})})")

    def test_the_version_is_read_by_one_name_and_not_guessed(self):
        """A chain of fallbacks is not robustness here, it is an unanswered question."""
        self.assertEqual(
            len(self._read_keys()), 1,
            "more than one spelling is tried for the version of ClinVar — "
            "one of them is right and nobody found out which")


class TestTheExtractionTargetReachesEveryMarker(unittest.TestCase):
    """Every marker the interpretation model may read has to be inside the
    alignment target, and not by a hair.

    `rs1142345` — TPMT *3C, the commonest deficient allele in Europeans — sat
    **31 bases** outside the left edge of `TPMT_region`. That is not a wrong
    coordinate anybody would spot by reading: the interval looks right, the gene
    is right, the number is nearly right. It is caught only by asking whether the
    locus is inside, and inside with room.

    Hence a MARGIN rather than mere containment. An interval that begins exactly
    at the locus is one rounding, one off-by-one, one BED half-open convention
    away from beginning after it.
    """

    MARGIN = 50
    SCRIPT = INGEST / "fastq_to_vcf.sh"

    def setUp(self):
        if not (self.SCRIPT.exists() and CATALOGUE.exists()):
            self.skipTest("the script or the catalogue is not part of this build")
        self.cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))

    def _bed(self):
        """Run the generator the script runs, on the catalogue the script reads."""
        src = self.SCRIPT.read_text(encoding="utf-8")
        i, j = src.find("BED_PY'\n") , src.find("\nBED_PY")
        self.assertGreater(i, 0, "the script no longer generates its target regions")
        code = src[i + len("BED_PY'\n"):j]
        p = subprocess.run([sys.executable, "-c", code, str(CATALOGUE), "200"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = []
        for line in p.stdout.splitlines():
            if not line.strip():
                continue
            chrom, start, end, name = line.split("\t")
            out.append((chrom[3:], int(start), int(end), name))
        self.assertTrue(out, "the generator emitted no regions")
        return out

    def test_every_catalogue_marker_is_inside_a_target_with_room(self):
        bed = self._bed()
        short = []
        for rs, e in self.cat["loci"].items():
            best = max((min(e["pos"] - s, end - e["pos"])
                        for c, s, end, _ in bed
                        if c == str(e["chrom"]) and s <= e["pos"] <= end), default=None)
            if best is None:
                short.append(f"{rs} ({e.get('gene')}) — outside every target region")
            elif best < self.MARGIN:
                short.append(f"{rs} ({e.get('gene')}) — {best} bp from the edge")
        self.assertEqual(short, [], "; ".join(short))

    def test_a_gene_that_needs_a_whole_window_declares_it_in_the_catalogue(self):
        """A whole-gene window is a coordinate too and lives in one place."""
        regions = self.cat.get("regions") or {}
        self.assertIn("CYP2D6", regions,
                      "CYP2D6 is called from structural variation and needs the gene, "
                      "not a point — the window has to be declared, not improvised")
        for gene, r in regions.items():
            self.assertLess(r["start"], r["end"], f"{gene}: an empty window")

    def test_the_script_writes_down_no_coordinate_of_its_own(self):
        text = self.SCRIPT.read_text(encoding="utf-8")
        offenders = [f"{n}: {l.strip()[:60]}"
                     for n, l in enumerate(text.splitlines(), 1)
                     if not l.lstrip().startswith("#") and BED_TABLE.match(l)]
        self.assertEqual(offenders, [], "; ".join(offenders))


if __name__ == "__main__":
    unittest.main()
