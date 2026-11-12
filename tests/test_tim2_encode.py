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


def _clut_files(itype):
    out = []
    for p in FILES:
        d = open(p, 'rb').read()
        if tim2._layout(d)[5] == itype:
            out.append(d)
    return out


@pytest.mark.skipif(not FILES, reason='work/unpacked not present')
@pytest.mark.parametrize('itype', [4, 5])
def test_encode_new_palette_reproduces_new_colours(itype):
    d = _clut_files(itype)[0]
    w, h = tim2.decode(d).size
    n = 16 if itype == 4 else 256
    cols = [(255, 0, 0, 255), (0, 200, 40, 255), (10, 20, 250, 128), (0, 0, 0, 0)]
    im = Image.new('RGBA', (w, h))
    for y in range(h):
        for x in range(w):
            im.putpixel((x, y), cols[(x // 3 + y) % len(cols)])
    out = tim2.encode_palette(d, im)
    assert len(out) == len(d) and out[:0x40] == d[:0x40]
    back = tim2.decode(out)
    for x, y in [(0, 0), (3 % w, 0), (6 % w, 1 % h), (w - 1, h - 1)]:
        want, got = im.getpixel((x, y)), back.getpixel((x, y))
        assert all(abs(a - b) <= 8 for a, b in zip(want, got)), (want, got)
    assert len(set(back.get_flattened_data())) <= n


@pytest.mark.skipif(not FILES, reason='work/unpacked not present')
def test_encode_palette_of_unchanged_image_is_close():
    d = _clut_files(5)[0]
    im = tim2.decode(d)
    back = tim2.decode(tim2.encode_palette(d, im))
    worst = max(0 if p[3] == q[3] == 0 else max(abs(a - b) for a, b in zip(p, q))
                for p, q in zip(im.get_flattened_data(), back.get_flattened_data()))
    assert worst <= 2          # <= 256 colours: exact palette (alpha keeps its 7-bit precision)


@pytest.mark.skipif(not FILES, reason='work/unpacked not present')
def test_encode_palette_many_colours_is_quantized():
    d = next(x for x in _clut_files(5) if min(tim2.decode(x).size) >= 32)
    w, h = tim2.decode(d).size
    im = Image.new('RGBA', (w, h))
    im.putdata([(x * 255 // w, y * 255 // h, (x + y) % 256, 255) for y in range(h) for x in range(w)])
    back = tim2.decode(tim2.encode_palette(d, im))
    err = [max(abs(a - b) for a, b in zip(p, q)) for p, q in zip(im.get_flattened_data(), back.get_flattened_data())]
    assert sum(err) / len(err) < 24
