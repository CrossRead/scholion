"""A compressed file position is not a BGZF virtual read boundary."""
from __future__ import annotations

import io
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import bamlite
from tests.test_a_file_without_an_index_is_still_a_file import block as bgzf


class TestBamChunkBoundaries(unittest.TestCase):
    def test_a_chunk_larger_than_the_gzip_read_buffer_reaches_its_real_end(self):
        payload=b'A'*60000
        blocks=[bgzf(payload) for _ in range(24)]
        encoded=b''.join(blocks)
        end=(sum(map(len,blocks[:-1]))<<16)+len(payload)
        actual=bamlite._read_chunk(io.BytesIO(encoded),0,end)
        self.assertEqual(actual,payload*24)

    def test_the_end_offset_inside_a_block_is_exclusive(self):
        encoded=bgzf(b'abcdef')+bgzf(b'later')
        self.assertEqual(bamlite._read_chunk(io.BytesIO(encoded),1,5),b'bcde')

    def test_a_boundary_at_the_next_block_does_not_read_that_block(self):
        first=bgzf(b'first')
        self.assertEqual(bamlite._read_chunk(io.BytesIO(first+b'not a BGZF block'),0,len(first)<<16),b'first')

    def test_a_truncated_chunk_is_an_error_not_partial_depth(self):
        block=bgzf(b'content')
        with self.assertRaises((ValueError,OSError,EOFError)):
            bamlite._read_chunk(io.BytesIO(block[:-4]),0,7)

    def test_a_truncated_bam_record_is_not_zero_coverage(self):
        with mock.patch.object(bamlite,'references',return_value={'1':0}), \
             mock.patch.object(bamlite,'BamIndex') as index, \
             mock.patch.object(bamlite,'_read_chunk',return_value=b'\x28\x00\x00\x00'+b'\x00'*10), \
             mock.patch('builtins.open',mock.mock_open()):
            index.return_value.chunks.return_value=[(0,10)]
            with self.assertRaises(ValueError):
                bamlite.depth('synthetic.bam','1',1,10)
