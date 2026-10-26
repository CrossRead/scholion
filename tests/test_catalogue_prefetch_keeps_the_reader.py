"""Batch prefetch is only an acceleration of the existing raw region cache."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, genome


class TestCataloguePrefetch(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.vcf = str(self.root/'synthetic.vcf.gz')
        Path(self.vcf).write_bytes(b'synthetic')
        Path(self.vcf+'.tbi').write_bytes(b'index')
        genome._REGION_CACHE.clear()
        self.addCleanup(genome._REGION_CACHE.clear)
        self.loci = {'rs1': {'chrom': '1', 'pos': 100, 'pos_grch37': 90, 'ref': 'A', 'alt': 'G'},
                     'rs2': {'chrom': 'X', 'pos': 200, 'pos_grch37': 190, 'ref': 'C', 'alt': 'T'}}
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name,value in [('vcf_path',Path(self.vcf)),('_sites_vcfs',[]),('_have_bcftools',True),
                           ('_index_usable',True),('engine_pin',None),('assembly_of','GRCh38')]:
            stack.enter_context(patch.object(genome,name,return_value=value))
        stack.enter_context(patch.object(genome,'contig_name',side_effect=lambda v,c:'chr'+c.removeprefix('chr')))
        stack.enter_context(patch.object(core,'loci',return_value={'loci':self.loci}))
        self.reader = stack.enter_context(patch.object(genome.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'')))

    def test_positive_negative_filtered_and_multiallelic_rows_keep_exact_bytes(self):
        line = 'chr1\t100\trs1\tA\tG,T\t60\tLowQual\t.\tGT:DP\t1/2:23'
        self.reader.return_value.stdout = line+'\n'
        genome._prefetch_catalogue_rows()
        self.assertEqual([line.split('\t')],genome._query_region(self.vcf,'1',100))
        self.assertEqual([],genome._query_region(self.vcf,'X',200))
        self.assertEqual(1,self.reader.call_count)
        rows = genome._query_region(self.vcf,'1',100)
        rows[0][3] = 'changed'
        self.assertEqual('A',genome._query_region(self.vcf,'1',100)[0][3])

    def test_each_file_uses_its_own_build_and_contig_spelling(self):
        site = str(self.root/'sites.vcf.gz')
        Path(site).write_bytes(b'synthetic sites');Path(site+'.tbi').write_bytes(b'index')
        with patch.object(genome,'_sites_vcfs',return_value=[site]), \
                patch.object(genome,'assembly_of',side_effect=lambda f:'GRCh37' if f==site else 'GRCh38'):
            genome._prefetch_catalogue_rows()
        self.assertEqual(2,self.reader.call_count)
        args = [call.args[0] for call in self.reader.call_args_list]
        self.assertEqual('chr1:100-100,chrX:200-200',args[0][-2])
        self.assertEqual('chr1:90-90,chrX:190-190',args[1][-2])
        self.assertEqual(site,args[1][-1])

    def test_complex_or_failed_batches_leave_every_position_to_the_original_reader(self):
        outputs = ['malformed', 'chr1\t95\t.\tAAAAAA\tA\t.\tPASS\t.',
                   'chr1\t100\t.\tA\t<NON_REF>\t.\tPASS\tEND=150',
                   'chr1\t100\t.\tA\tG\t.\tPASS\tEND=150',
                   'chr2\t100\t.\tA\tG\t.\tPASS\t.']
        cases = [(0,text,None) for text in outputs]+[(1,'',None),(0,'',subprocess.TimeoutExpired('bcftools',60))]
        for code,text,error in cases:
            with self.subTest(text=text,error=type(error).__name__):
                genome._REGION_CACHE.clear();self.reader.reset_mock()
                self.reader.side_effect = error
                self.reader.return_value = subprocess.CompletedProcess([],code,text)
                genome._prefetch_catalogue_rows()
                self.assertEqual({},genome._REGION_CACHE)
                self.reader.side_effect = None
                self.reader.return_value = subprocess.CompletedProcess([],0,'chr1\t100\t.\tA\tG\t.\tPASS\t.\n')
                self.assertEqual('G',genome._query_region(self.vcf,'1',100)[0][4])
                self.assertEqual(2,self.reader.call_count)

    def test_changed_index_during_query_does_not_install_stale_rows(self):
        def change_index(*args,**kwargs):
            Path(self.vcf+'.tbi').write_bytes(b'new different index')
            return subprocess.CompletedProcess([],0,'')
        self.reader.side_effect = change_index
        genome._prefetch_catalogue_rows()
        self.assertEqual({},genome._REGION_CACHE)

    def test_linear_unindexed_unknown_build_and_no_binary_skip_prefetch(self):
        for name,value in [('engine_pin','linear'),('_have_bcftools',False),
                           ('_index_usable',False),('assembly_of',None),('vcf_path',None)]:
            with self.subTest(name=name),patch.object(genome,name,return_value=value):
                genome._prefetch_catalogue_rows()
        self.reader.assert_not_called()

    def test_batches_are_bounded_and_already_cached_regions_are_not_requeried(self):
        self.loci.clear()
        self.loci.update({str(p):{'chrom':'1','pos':p,'ref':'A','alt':'G'} for p in range(1,258)})
        genome._prefetch_catalogue_rows()
        self.assertEqual(3,self.reader.call_count)
        self.assertTrue(all(len(call.args[0][-2].split(','))<=128 for call in self.reader.call_args_list))
        genome._prefetch_catalogue_rows()
        self.assertEqual(3,self.reader.call_count)
