import glob
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from xaplz import compress, decompress  # noqa: E402

UNPACKED = os.path.join(os.path.dirname(__file__), '..', 'work', 'unpacked')


@pytest.mark.parametrize('data', [
    b'',
    b'a',
    b'ab',
    b'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    b'abcabcabcabcabcabcabc' * 50,
    bytes(range(256)) * 40,  # forces long distances (> 255)
])
def test_round_trip_synthetic(data):
    assert decompress(compress(data), len(data)) == data


def test_round_trip_random():
    rnd = random.Random(1234)
    for n in (1, 7, 300, 5000, 20000):
        alphabet = bytes(rnd.randrange(256) for _ in range(12))
        data = bytes(rnd.choice(alphabet) for _ in range(n))
        assert decompress(compress(data), n) == data


def test_long_distance_is_used_and_correct():
    block = bytes(random.Random(5).randrange(256) for _ in range(3000))
    data = block + b'\x00' * 100 + block
    c = compress(data)
    assert decompress(c, len(data)) == data
    assert len(c) < len(data) * 0.7


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='originals not unpacked')
def test_round_trip_real_files_and_ratio():
    files = sorted(glob.glob(os.path.join(UNPACKED, 'EVENT.XAP', '*.mes')))[:40]
    files += [os.path.join(UNPACKED, 'FONT.XAP', 'font20.moj')]
    for f in files:
        d = open(f, 'rb').read()
        c = compress(d)
        assert decompress(c, len(d)) == d, f
        assert len(c) < len(d), f
