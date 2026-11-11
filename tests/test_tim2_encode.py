"""TIM2 re-encoding: keep header and CLUT, write pixels (nearest palette colour)."""
import glob
import os
import sys

import pytest
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import tim2  # noqa: E402

FILES = sorted(glob.glob(os.path.join(ROOT, 'work', 'unpacked', '**', '*.tm2'), recursive=True))


@pytest.mark.skipif(not FILES, reason='work/unpacked not present')
def test_round_trip_all_images_byte_identical():
    for p in FILES:
        d = open(p, 'rb').read()
        assert tim2.encode(d, tim2.decode(d)) == d, p


@pytest.mark.skipif(not FILES, reason='work/unpacked not present')
def test_edit_changes_only_edited_pixels():
    p = next(f for f in FILES if f.endswith('sysicn08.tm2'))
    d = open(p, 'rb').read()
    im = tim2.decode(d)
    pal_colour = im.getpixel((0, 0))
    im2 = im.copy()
    im2.putpixel((5, 5), pal_colour)
    out = tim2.decode(tim2.encode(d, im2))
    assert out.getpixel((5, 5)) == pal_colour
    diff = [(x, y) for x in range(im.width) for y in range(im.height) if out.getpixel((x, y)) != im.getpixel((x, y))]
    assert diff in ([], [(5, 5)])


def test_size_mismatch_fails():
    p = FILES[0] if FILES else None
    if not p:
        pytest.skip('no data')
    d = open(p, 'rb').read()
    with pytest.raises(ValueError):
        tim2.encode(d, Image.new('RGBA', (3, 3)))
