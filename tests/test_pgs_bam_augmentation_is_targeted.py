"""Actual all-site calling replaces failed calls and touches only missing sites."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import prs_recompute, sites
from scholion.pgs_scoring import ScoringVCF, dosage


class TargetedBAM(unittest.TestCase):
    @unittest.skipUnless(shutil.which('bcftools') and shutil.which('samtools'), 'optional native genome tools absent')
    def test_real_bam_fills_only_missing_sites_and_keeps_reference_homozygotes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            reference = root / 'reference.fa'
            reference.write_text('>1\n' + 'A' * 100 + '\n', encoding='utf-8')
            sam = root / 'synthetic.sam'
            sam.write_text('@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:1\tLN:100\n@RG\tID:SYNTHETIC\tSM:SYNTHETIC\n' + ''.join(
                f'read{i}\t0\t1\t1\t60\t50M\t*\t0\t0\t' + 'A' * 50 + '\t' + 'I' * 50 + '\tRG:Z:SYNTHETIC\n'
                for i in range(30)), encoding='utf-8')
            bam = root / 'synthetic.bam'
            for command in (['samtools', 'faidx', str(reference)],
                            ['samtools', 'view', '-b', '-o', str(bam), str(sam)],
                            ['samtools', 'index', str(bam)]):
                subprocess.run(command, check=True, capture_output=True, stdin=subprocess.DEVNULL)
            vcf = root / 'calls.vcf'
            vcf.write_text('##fileformat=VCFv4.2\n##reference=GRCh38\n##contig=<ID=1,length=100>\n'
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
                '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Depth">\n'
                '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n'
                '1\t1\t.\tA\tG\t50\tPASS\t.\tGT:DP\t0/1:30\n'
                '1\t2\t.\tA\tG\t.\tPASS\t.\tGT:DP\t./.:0\n', encoding='utf-8')
            beds = []
            def run(commands):
                for argv in commands:
                    if '-R' in argv:
                        beds.append(Path(argv[argv.index('-R') + 1]).read_text(encoding='utf-8'))
                return prs_recompute._run_cancellable(commands, None)
            with mock.patch('scholion.gene_region.bam_path', return_value=bam), \
                 mock.patch('scholion.gene_region.reference_path', return_value=reference), \
                 mock.patch.dict(sites._CHR1, {100: 'GRCh38'}):
                output, preparation = prs_recompute._augment(vcf, {('1', 2)}, 'GRCh38', None, None, run=run)
            self.assertEqual(['1\t1\t2\n'], beds)
            self.assertEqual('targeted_bam', preparation)
            self.assertTrue(Path(str(output) + '.tbi').is_file())
            source = ScoringVCF(output)
            try:
                self.assertEqual(1, dosage('G', 'A', source.get('1', '1'))[0])
                self.assertEqual(0, dosage('G', 'A', source.get('1', '2'))[0])
                self.assertIsNone(dosage('G', 'A', source.get('1', '3'))[0])
            finally:
                source.close()

    def test_cancel_terminates_running_local_child(self):
        stopped = threading.Event()
        timer = threading.Timer(0.2, stopped.set)
        start = time.monotonic()
        timer.start()
        try:
            with self.assertRaises(prs_recompute.Stopped):
                prs_recompute._run_cancellable([[sys.executable, '-c', 'import time; time.sleep(20)']], stopped.is_set)
        finally:
            timer.cancel()
        self.assertLess(time.monotonic() - start, 3)


if __name__ == '__main__':
    unittest.main()
