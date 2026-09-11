"""The screen that answers «is there a finding worth acting on» — runnable, and
refusing to match across assemblies.

Two facts met, and from inside the product neither was visible.

The screen reads a table it does not compute, and the pass that writes that table
lived in the data-preparation directory — which travels in the source archive and
NOT in the wheel. So after an ordinary `pip install`, the product could say «the
ACMG scan has not been run» and offer nothing that would run it. The sentence was
true and the situation it described was ours, and the screen it blocked is the one
whose 84 genes include 28 in which a finding is a hereditary-cancer finding.

And the pass matched by POSITION with no check that both files speak the same
coordinate system. ClinVar is published per assembly and the guide names the
GRCh38 file; a great many personal files are GRCh37. Crossed, the run does not
fail — it finds nothing at all, or it matches a position that in the other build
belongs to a different base. A silent zero from a screen for actionable findings
is the worst answer this software can produce, and nothing in it was looking.

The audit before 0.4.11 then read the pass itself and found the same shape four
more times, each a row that matched a position and was taken as a finding without
a further question: whose column is this (a trio's first column is somebody's
mother), which allele is this (a two-ALT row with `2/2` matched on the first ALT),
is there a call at all (`./.` is not a reference, and «not a reference» was the
only test), and — for the refusal itself — was the ClinVar build read from the
ClinVar file, or from the variable the person set about THEIR file. Each has a
class below, and each was proved by reverting the line it guards.
"""
from __future__ import annotations

import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import acmg_scan, genome

#: BRCA1 in both builds — the contig lengths are what the assembly is read from,
#: and they are properties of the reference rather than claims in a header.
CHR1_LEN = {"GRCh38": 248956422, "GRCh37": 249250621}
CHR17_LEN = {"GRCh38": 83257441, "GRCh37": 81195210}

#: The catalogue's own biallelic gene on chr1 — two heterozygotes there are a
#: question of phase, one is a carrier. Coordinates are synthetic and only have
#: to agree between the two files.
MUTYH = ("1", 45331000, 45332000)


def vcf(path: Path, build, rows, sample=True, clinvar=False, samples=("ME",), extra=()):
    """A gzip-compressed VCF. `build=None` writes no contig lines at all — the
    headerless shape a `bcftools view -G` or a hand-made file has."""
    head = ["##fileformat=VCFv4.2"]
    if build:
        head += [f"##contig=<ID=1,length={CHR1_LEN[build]}>",
                 f"##contig=<ID=17,length={CHR17_LEN[build]}>"]
    head += list(extra)
    cols = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"
    if sample:
        cols += "\tFORMAT\t" + "\t".join(samples)
    body = "\n".join("\t".join(r) for r in rows)
    path.write_bytes(gzip.compress(("\n".join(head + [cols]) + "\n" + body + "\n").encode()))
    return path


def clinvar_row(chrom, pos, ref, alt, gene, sig="Pathogenic", rs="80357906"):
    info = f"CLNSIG={sig};CLNREVSTAT=criteria_provided,_single_submitter;CLNDN=Breast_cancer;GENEINFO={gene}:672;RS={rs}"
    return [chrom, str(pos), ".", ref, alt, ".", ".", info]


def personal_row(chrom, pos, ref, alt, gt="0/1", filt="PASS", *more):
    """One row; `more` are the genotypes of further samples, in column order."""
    return [chrom, str(pos), ".", ref, alt, "60", filt, ".", "GT", gt, *more]


def brca1_clinvar(dir_, build="GRCh38"):
    pos = 43092919 if build == "GRCh38" else 41244936
    return vcf(dir_ / "clinvar.vcf.gz", build,
               [clinvar_row("17", pos, "G", "A", "BRCA1")], sample=False)


def table_rows(res):
    lines = Path(res["table"]).read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"))) for ln in lines[1:] if ln.strip()]


class _Files(unittest.TestCase):
    ENV = ("SCHOLION_CLINVAR_VCF", "SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE",
           "SCHOLION_GENOME_ASSEMBLY")

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self._env = {k: os.environ.get(k) for k in self.ENV}
        for k in self._env:
            os.environ.pop(k, None)
        # Both readers cache by path; a fresh directory per test keeps the paths
        # apart, and clearing keeps a test from inheriting what another one read.
        genome.assembly_of.cache_clear()
        genome.samples_of.cache_clear()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        genome.assembly_of.cache_clear()
        genome.samples_of.cache_clear()


class TestTheBuildsAreComparedBeforeThePositions(_Files):

    def test_a_crossed_run_is_refused_and_says_which_file_to_fetch(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh37", [personal_row("17", 41244936, "G", "A")])
        cv = brca1_clinvar(self.dir, "GRCh38")
        res = acmg_scan.scan(str(me), str(cv))
        self.assertEqual(res["status"], "assembly_mismatch")
        self.assertEqual(res["assembly"], "GRCh37")
        self.assertEqual(res["clinvar_assembly"], "GRCh38")
        self.assertIn("GRCh37", res["url"], "the download offered is the one for THEIR build")
        self.assertNotIn("⟦", res["message"])

    def test_a_clinvar_file_that_will_not_say_its_build_is_not_used(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh37", [personal_row("17", 41244936, "G", "A")])
        cv = self.dir / "mystery.vcf.gz"
        cv.write_bytes(gzip.compress(b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"))
        res = acmg_scan.scan(str(me), str(cv))
        self.assertEqual(res["status"], "clinvar_assembly_unknown")

    def test_the_assembly_is_read_out_of_the_clinvar_file(self):
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh37", [], sample=False)
        self.assertEqual(acmg_scan.clinvar_assembly(str(cv)), "GRCh37")

    def test_a_reference_line_answers_where_no_contig_length_does(self):
        cv = self.dir / "byline.vcf.gz"
        cv.write_bytes(gzip.compress(b"##fileformat=VCFv4.2\n##reference=GRCh38.p14\n"
                                     b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"))
        self.assertEqual(acmg_scan.clinvar_assembly(str(cv)), "GRCh38")

    def test_a_contig_length_outranks_the_reference_line(self):
        """The line is what somebody wrote; the length is what the reference is."""
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh37", [], sample=False,
                 extra=["##reference=GRCh38"])
        self.assertEqual(acmg_scan.clinvar_assembly(str(cv)), "GRCh37")


class TestTheClinvarBuildIsReadFromTheClinvarFile(_Files):
    """A4. `SCHOLION_GENOME_ASSEMBLY` is the documented way of naming the build of
    a personal file whose header will not say. The ClinVar build went through the
    same reader, which honours that variable first — so the person it was written
    for, declaring GRCh37 for a headerless file and holding the GRCh38 ClinVar,
    saw «GRCh37 against GRCh37» and a scan that ran across builds. The refusal
    was disarmed by the one variable that should have armed it."""

    def test_the_declared_build_of_the_personal_file_does_not_become_clinvars(self):
        os.environ["SCHOLION_GENOME_ASSEMBLY"] = "GRCh37"
        cv = brca1_clinvar(self.dir, "GRCh38")
        self.assertEqual(acmg_scan.clinvar_assembly(str(cv)), "GRCh38")

    def test_a_declared_grch37_against_the_grch38_clinvar_is_still_refused(self):
        os.environ["SCHOLION_GENOME_ASSEMBLY"] = "GRCh37"
        me = vcf(self.dir / "me.vcf.gz", None, [personal_row("17", 41244936, "G", "A")])
        cv = brca1_clinvar(self.dir, "GRCh38")
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "assembly_mismatch", res.get("message"))
        self.assertEqual(res["assembly"], "GRCh37", "the declaration still holds for THEIR file")
        self.assertEqual(res["clinvar_assembly"], "GRCh38")
        self.assertFalse((self.dir / acmg_scan.OUT_NAME).exists(), "nothing was written")

    def test_a_declaration_that_matches_the_clinvar_file_lets_the_scan_run(self):
        os.environ["SCHOLION_GENOME_ASSEMBLY"] = "GRCh38"
        me = vcf(self.dir / "me.vcf.gz", None, [personal_row("17", 43092919, "G", "A")])
        cv = brca1_clinvar(self.dir, "GRCh38")
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(res["found"], 1)


class TestAPersonalFileOfUnknownBuildIsRefused(_Files):
    """A5. The ClinVar side already refused when its build could not be told; the
    personal side did not, so a headerless file with no index for the probe went
    into the scan with `assembly=None` — the crossed-build run with one side
    blank, and a clean `ok` on top of it."""

    def test_no_contigs_no_declaration_no_index_means_no_scan(self):
        me = vcf(self.dir / "me.vcf.gz", None, [personal_row("17", 43092919, "G", "A")])
        cv = brca1_clinvar(self.dir, "GRCh38")
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "personal_assembly_unknown", res.get("message"))
        self.assertIn("SCHOLION_GENOME_ASSEMBLY", res["message"],
                      "the refusal names the one way of closing it")
        self.assertNotIn("⟦", res["message"])
        self.assertFalse((self.dir / acmg_scan.OUT_NAME).exists(), "nothing was written")

    def test_the_refusal_comes_before_the_clinvar_file_is_asked_for(self):
        """Which ClinVar to fetch depends on the build; without the build, «fetch
        the GRCh38 one» is a guess dressed as an instruction."""
        me = vcf(self.dir / "me.vcf.gz", None, [personal_row("17", 43092919, "G", "A")])
        res = acmg_scan.scan(str(me), None, out_dir=str(self.dir))
        self.assertEqual(res["status"], "personal_assembly_unknown")


class TestTheColumnReadIsThePersons(_Files):
    """A2. Column ten was read unconditionally. In a trio `MOTHER, ME` with
    `0/1, 0/0`, that reported the mother's BRCA1 heterozygote as the person's —
    with `SCHOLION_GENOME_SAMPLE=ME` set or not, because nothing asked."""

    def _trio(self, gts=("0/1", "0/0")):
        me = vcf(self.dir / "trio.vcf.gz", "GRCh38",
                 [personal_row("17", 43092919, "G", "A", gts[0], "PASS", gts[1])],
                 samples=("MOTHER", "ME"))
        return me, brca1_clinvar(self.dir)

    def test_a_file_with_several_samples_and_no_choice_is_refused(self):
        me, cv = self._trio()
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "several_samples", res.get("message"))
        self.assertEqual(res["samples"], ["MOTHER", "ME"])
        self.assertIn("SCHOLION_GENOME_SAMPLE=", res["message"])
        self.assertNotIn("⟦", res["message"])
        self.assertFalse((self.dir / acmg_scan.OUT_NAME).exists(), "nothing was written")

    def test_the_chosen_sample_is_the_one_read(self):
        me, cv = self._trio()
        os.environ["SCHOLION_GENOME_SAMPLE"] = "ME"
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(res["found"], 0, "ME is 0/0; the heterozygote is MOTHER's")
        self.assertEqual(res["sample"], "ME")

    def test_the_other_column_reads_the_other_person(self):
        me, cv = self._trio()
        os.environ["SCHOLION_GENOME_SAMPLE"] = "MOTHER"
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["found"], 1)
        self.assertEqual(res["sample"], "MOTHER")

    def test_a_named_sample_that_is_not_there_is_refused_by_name(self):
        me, cv = self._trio()
        os.environ["SCHOLION_GENOME_SAMPLE"] = "NOBODY"
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "sample_not_found")
        self.assertIn("NOBODY", res["message"])
        self.assertIn("MOTHER", res["message"])

    def test_a_sites_only_file_holds_nobodys_genotype(self):
        me = vcf(self.dir / "sites.vcf.gz", "GRCh38",
                 [clinvar_row("17", 43092919, "G", "A", "BRCA1")], sample=False)
        res = acmg_scan.scan(str(me), str(brca1_clinvar(self.dir)), out_dir=str(self.dir))
        self.assertEqual(res["status"], "no_sample_column")
        self.assertNotIn("⟦", res["message"])

    def test_one_sample_needs_no_choice(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        res = acmg_scan.scan(str(me), str(brca1_clinvar(self.dir)), out_dir=str(self.dir))
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["sample"], "ME")


class TestAMultiallelicRowIsReadByAlleleIndex(_Files):
    """A3. `REF G, ALT A,T, GT 2/2` matched ClinVar's `G>A` by position and by
    the first ALT, and the genotype was judged «not reference, all alleles the
    same» — homozygous, for an allele the person does not carry."""

    def _pair(self, gt, clinvar_alt="A"):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38",
                 [personal_row("17", 43092919, "G", "A,T", gt)])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row("17", 43092919, "G", clinvar_alt, "BRCA1")], sample=False)
        return acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))

    def test_two_copies_of_the_other_allele_are_not_a_finding(self):
        res = self._pair("2/2")
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(res["found"], 0)

    def test_one_copy_of_the_matched_allele_is_heterozygous(self):
        res = self._pair("1/2")
        self.assertEqual(res["found"], 1)
        self.assertEqual(table_rows(res)[0]["zygosity"], "het")

    def test_two_copies_of_the_matched_allele_are_homozygous(self):
        res = self._pair("1/1")
        self.assertEqual(table_rows(res)[0]["zygosity"], "hom")

    def test_the_second_alt_is_matched_by_its_own_index(self):
        res = self._pair("2/2", clinvar_alt="T")
        self.assertEqual(res["found"], 1)
        row = table_rows(res)[0]
        self.assertEqual((row["alt"], row["zygosity"]), ("T", "hom"))

    def test_a_partial_call_is_one_copy_seen(self):
        """`./1` is one allele read and one not — a heterozygote at most, never a
        homozygote, which is what «all the digits agree» made of it."""
        res = self._pair("./1")
        self.assertEqual(res["found"], 1)
        self.assertEqual(table_rows(res)[0]["zygosity"], "het")


class TestANoCallIsNotAFinding(_Files):
    """A1. `./.` at a P/LP position — the ordinary shape of a joint-called family
    file and of a gVCF — was written into the table with zygosity `?` and, under
    the gene's rule `any`, `reportable=yes`. The file said «not read here» and
    the screen said «finding»."""

    def _run(self, gt):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A", gt)])
        return acmg_scan.scan(str(me), str(brca1_clinvar(self.dir)), out_dir=str(self.dir))

    def test_a_no_call_row_is_not_written(self):
        res = self._run("./.")
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(res["found"], 0)
        self.assertEqual(res["to_discuss"], 0)
        self.assertEqual(table_rows(res), [])

    def test_a_phased_no_call_is_the_same_silence(self):
        self.assertEqual(self._run(".|.")["found"], 0)

    def test_the_no_call_is_counted_and_said_rather_than_dropped(self):
        """«None found» over an unread P/LP position is a weaker sentence than
        «none found», and the count is what makes the difference visible."""
        res = self._run("./.")
        self.assertEqual(res["no_calls"], 1)
        self.assertIn("not called", res["message"])
        self.assertNotIn("⟦", res["message"])
        self.assertEqual(acmg_scan.read_meta(self.dir)["no_calls"], 1)

    def test_a_called_row_is_not_counted_as_a_no_call(self):
        res = self._run("0/1")
        self.assertEqual((res["found"], res["no_calls"]), (1, 0))
        self.assertNotIn("not called", res["message"])


class TestACallTheCallerDidNotStandBehindIsNotDecided(_Files):
    """B.21. The personal FILTER column was not read: a `LowQual` heterozygote in
    BRCA1 was a finding «yes», on the same footing as a PASS one."""

    def test_a_filtered_row_is_written_as_filtered_and_not_as_a_finding(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38",
                 [personal_row("17", 43092919, "G", "A", "0/1", "LowQual")])
        res = acmg_scan.scan(str(me), str(brca1_clinvar(self.dir)), out_dir=str(self.dir))
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(res["to_discuss"], 0)
        self.assertEqual(res["filtered"], 1)
        row = table_rows(res)[0]
        self.assertEqual((row["filter"], row["reportable"]), ("LowQual", "filtered"))
        self.assertIn("FILTER", res["message"])

    def test_a_pass_row_and_an_unfiltered_row_are_decided(self):
        for filt in ("PASS", "."):
            with self.subTest(filter=filt):
                me = vcf(self.dir / f"me-{filt}.vcf.gz", "GRCh38",
                         [personal_row("17", 43092919, "G", "A", "0/1", filt)])
                res = acmg_scan.scan(str(me), str(brca1_clinvar(self.dir)), out_dir=str(self.dir))
                self.assertEqual(res["to_discuss"], 1)
                self.assertEqual(table_rows(res)[0]["filter"], filt)

    def test_a_filtered_heterozygote_does_not_make_a_clean_one_need_phase(self):
        """Two hets in a biallelic gene are «needs phase». One of them LowQual is
        one clean carrier and one call to look at again — not a pair."""
        chrom, p1, p2 = MUTYH
        me = vcf(self.dir / "me.vcf.gz", "GRCh38",
                 [personal_row(chrom, p1, "C", "T", "0/1", "PASS"),
                  personal_row(chrom, p2, "G", "A", "0/1", "LowQual")])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row(chrom, p1, "C", "T", "MUTYH", rs="1"),
                  clinvar_row(chrom, p2, "G", "A", "MUTYH", rs="2")], sample=False)
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        verdicts = {r["pos"]: r["reportable"] for r in table_rows(res)}
        self.assertEqual(verdicts, {str(p1): "carrier_only", str(p2): "filtered"})


class TestTheTableLandsWhereTheScreenLooks(_Files):
    """A6. The table was written beside the variant file, and `scholion acmg`
    reads it out of the genome folder. With the file anywhere else — `--vcf`, or
    `SCHOLION_GENOME_VCF` pointing at external storage — the command said «ok,
    the table is written» and the screen said «the scan has not been run»."""

    def setUp(self):
        super().setUp()
        self._genome_dir = os.environ.get("SCHOLION_GENOME_DIR")
        self.genome_dir = self.dir / "genome"
        os.environ["SCHOLION_GENOME_DIR"] = str(self.genome_dir)
        self.elsewhere = self.dir / "elsewhere"
        self.elsewhere.mkdir()

    def tearDown(self):
        if self._genome_dir is None:
            os.environ.pop("SCHOLION_GENOME_DIR", None)
        else:
            os.environ["SCHOLION_GENOME_DIR"] = self._genome_dir
        super().tearDown()

    def test_by_default_the_table_goes_to_the_genome_folder_not_beside_the_file(self):
        me = vcf(self.elsewhere / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        cv = brca1_clinvar(self.elsewhere)
        res = acmg_scan.scan(str(me), str(cv))
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(Path(res["table"]), self.genome_dir / acmg_scan.OUT_NAME)
        self.assertFalse((self.elsewhere / acmg_scan.OUT_NAME).exists())

    def test_the_screen_then_finds_what_the_scan_wrote(self):
        me = vcf(self.elsewhere / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        acmg_scan.scan(str(me), str(brca1_clinvar(self.elsewhere)))
        found = genome.acmg_sf_findings()
        self.assertEqual(found["status"], "ok", found.get("message"))
        self.assertEqual([r["gene"] for r in found["reportable"]], ["BRCA1"])

    def test_out_dir_still_overrides(self):
        me = vcf(self.elsewhere / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        res = acmg_scan.scan(str(me), str(brca1_clinvar(self.elsewhere)), out_dir=str(self.elsewhere))
        self.assertEqual(Path(res["table"]).parent, self.elsewhere)


class TestTheTableCarriesItsProvenance(_Files):
    """A7. The table said nothing about which builds it was matched in, which
    ClinVar release, or when — so a reader could not tell a stale or crossed
    table from a current one. A sidecar says so; JSON rather than `#` lines,
    because the table's reader takes its first line as the header."""

    def _scan(self, **kw):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row("17", 43092919, "G", "A", "BRCA1")], sample=False,
                 extra=["##fileDate=2026-09-01"])
        return acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir), **kw)

    def test_the_sidecar_is_written_beside_the_table_and_says_what_matters(self):
        res = self._scan()
        meta = acmg_scan.read_meta(self.dir)
        self.assertIsNotNone(meta)
        self.assertEqual(Path(res["meta"]), self.dir / acmg_scan.META_NAME)
        self.assertEqual(meta["assembly"], "GRCh38")
        self.assertEqual(meta["clinvar_assembly"], "GRCh38")
        self.assertEqual(Path(meta["clinvar_path"]).name, "clinvar.vcf.gz")
        self.assertEqual(meta["clinvar_file_date"], "2026-09-01")
        self.assertEqual(res["clinvar_file_date"], "2026-09-01")
        self.assertRegex(meta["scanned"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(meta["sample"], "ME")
        for key in ("no_calls", "filtered", "found", "catalogue_version"):
            self.assertIn(key, meta)

    def test_the_sidecar_is_found_from_the_table_path_as_well(self):
        res = self._scan()
        self.assertEqual(acmg_scan.read_meta(res["table"]), acmg_scan.read_meta(self.dir))

    def test_no_sidecar_is_none_and_so_is_a_broken_one(self):
        self.assertIsNone(acmg_scan.read_meta(self.dir))
        (self.dir / acmg_scan.META_NAME).write_text("{not json", encoding="utf-8")
        self.assertIsNone(acmg_scan.read_meta(self.dir))
        (self.dir / acmg_scan.META_NAME).write_text("[1, 2]", encoding="utf-8")
        self.assertIsNone(acmg_scan.read_meta(self.dir), "a list is not a record")

    def test_the_sidecar_is_utf8_json_a_person_can_read(self):
        self._scan()
        raw = (self.dir / acmg_scan.META_NAME).read_text(encoding="utf-8")
        self.assertEqual(json.loads(raw)["assembly"], "GRCh38")
        self.assertIn("\n", raw.strip(), "indented, not one line")


class TestTheScreenRuns(_Files):

    def test_a_matching_pair_produces_the_table_the_screen_reads(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row("17", 43092919, "G", "A", "BRCA1")], sample=False)
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "ok", res.get("message"))
        self.assertEqual(res["found"], 1)
        self.assertEqual(res["to_discuss"], 1)
        table = Path(res["table"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(table[0].split("\t")[0], "gene")
        self.assertIn("filter", table[0].split("\t"))
        self.assertIn("BRCA1", table[1])
        self.assertIn("het", table[1])

    def test_a_homozygous_reference_row_is_not_a_finding(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38",
                 [personal_row("17", 43092919, "G", "A", gt="0/0")])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row("17", 43092919, "G", "A", "BRCA1")], sample=False)
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["found"], 0)
        self.assertEqual(res["no_calls"], 0, "a reference call is a call")

    def test_a_conflicting_interpretation_is_not_a_finding(self):
        """A conflict is uncertainty. Counting it would put a person in front of a
        geneticist over a variant the submitters do not agree about."""
        me = vcf(self.dir / "me.vcf.gz", "GRCh38", [personal_row("17", 43092919, "G", "A")])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row("17", 43092919, "G", "A", "BRCA1",
                              sig="Conflicting_interpretations_of_pathogenicity")], sample=False)
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "clinvar_empty",
                         "nothing P/LP in the list is a property of the FILE, and says so")

    def test_a_gene_outside_the_list_is_not_reported(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh38", [personal_row("1", 100000, "G", "A")])
        cv = vcf(self.dir / "clinvar.vcf.gz", "GRCh38",
                 [clinvar_row("1", 100000, "G", "A", "NOTAGENE")], sample=False)
        res = acmg_scan.scan(str(me), str(cv), out_dir=str(self.dir))
        self.assertEqual(res["status"], "clinvar_empty")


class TestWhatItSaysWhenItCannotRun(_Files):

    def test_without_a_clinvar_file_it_names_the_one_download(self):
        me = vcf(self.dir / "me.vcf.gz", "GRCh37", [personal_row("17", 41244936, "G", "A")])
        res = acmg_scan.scan(str(me), None, out_dir=str(self.dir))
        self.assertEqual(res["status"], "no_clinvar")
        self.assertIn("vcf_GRCh37", res["url"])
        self.assertIn("curl", res["message"])

    def test_the_two_published_files_are_named_per_build(self):
        self.assertIn("GRCh37", acmg_scan.CLINVAR_URL)
        self.assertIn("GRCh38", acmg_scan.CLINVAR_URL)
        self.assertNotEqual(acmg_scan.CLINVAR_URL["GRCh37"], acmg_scan.CLINVAR_URL["GRCh38"])

    def test_every_refusal_has_a_sentence_in_both_languages(self):
        from scholion.i18n import plural as _plural
        from scholion.i18n import t as _t
        keys = ("acmg_scan.no_genome", "acmg_scan.no_clinvar", "acmg_scan.assembly_mismatch",
                "acmg_scan.clinvar_assembly_unknown", "acmg_scan.clinvar_empty",
                "acmg_scan.done", "acmg_scan.no_sample_column", "acmg_scan.sample_not_found",
                "acmg_scan.several_samples", "acmg_scan.personal_assembly_unknown")
        families = ("acmg_scan.no_calls", "acmg_scan.filtered")
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for k in keys:
                    with self.subTest(lang=lang, key=k):
                        self.assertNotIn("⟦", _t(k, assembly="GRCh37", url="U", personal="GRCh37",
                                                 clinvar="GRCh38", found=0, yes=0, path="p",
                                                 name="X", names="X, Y", cmd="C"))
                for fam in families:
                    for n in (1, 2, 5):
                        with self.subTest(lang=lang, family=fam, n=n):
                            self.assertNotIn("⟦", _plural(n, fam))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


if __name__ == "__main__":
    unittest.main()
