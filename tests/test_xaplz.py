import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from xaplz import decompress  # noqa: E402
from xap import read_entries, read_file  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), '..', 'work', 'iso', 'DATA')


def test_literal_short_ref_and_end():
    # bits: 0 'a' | 0 'b' | 1 0 <0xfe> len(1,1,0 -> n=3 -> 4 bytes) | 1 0 <0x00> end
    assert decompress(bytes([0x2D, 0x61, 0x62, 0xFE, 0x00, 0x00])) == b'ababab'


def test_long_ref():
    # 'x' literal, then long ref: byte 0xff, 4 bits 1111 -> ((-1)<<4|15) - 255 = -256 ... use smaller: bits 0000
    # offset = ((0xff-256)*16 + 0) - 255 = -271 -> invalid with 1 byte history
    with pytest.raises(ValueError):
        # flag: 0 'x', 1 1 <0xff> 0000, len 0 -> 2 bytes
        decompress(bytes([0b01100000, 0x78, 0xFF, 0b00000000]))


def test_size_mismatch_raises():
    with pytest.raises(ValueError):
        decompress(bytes([0x2D, 0x61, 0x62, 0xFE, 0x00, 0x00]), expected_size=7)


@pytest.mark.skipif(not os.path.isdir(DATA), reason='original image not extracted')
def test_sysmes_decodes_from_original():
    d = open(os.path.join(DATA, 'SYSMES.XAP'), 'rb').read()
    (e,) = read_entries(d)
    assert e.name == 'sysmes.txt'
    text = read_file(d, e).decode('cp932')
    assert '浪人する' in text
