"""Graphics-text replacement: spec -> edited RGBA image confined to declared rects."""
import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import gfx  # noqa: E402

FONT = gfx.FONTS['sans-bold']


def base():
    im = Image.new('RGBA', (64, 32), (0, 0, 0, 0))
    for x in range(64):
        im.putpixel((x, 31), (255, 0, 0, 255))   # art outside the edited rect must survive
    return im


def test_render_draws_only_inside_rect():
    item = {'rect': [4, 4, 40, 20], 'clear': True, 'text': '가계부', 'font': 'sans-bold',
            'fill': [[200, 220, 200], [120, 160, 120]], 'outline': [40, 40, 40], 'stroke': 1}
    out = gfx.render(base(), [item])
    inside = [out.getpixel((x, y)) for x in range(4, 44) for y in range(4, 24)]
    assert any(p[3] > 0 for p in inside)
    for x in range(64):
        for y in range(32):
            if not (4 <= x < 44 and 4 <= y < 24):
                assert out.getpixel((x, y)) == base().getpixel((x, y))


def test_text_is_fitted_to_rect():
    item = {'rect': [0, 0, 20, 10], 'clear': True, 'text': '아주 긴 글자열입니다', 'font': 'sans-bold',
            'fill': [[255, 255, 255]], 'outline': None, 'stroke': 0}
    out = gfx.render(base(), [item])
    assert out.getpixel((0, 31)) == (255, 0, 0, 255)


def test_spec_validation():
    with pytest.raises(ValueError, match='outside'):
        gfx.render(base(), [{'rect': [60, 0, 10, 10], 'clear': True, 'text': 'x', 'font': 'sans-bold',
                             'fill': [[0, 0, 0]], 'outline': None, 'stroke': 0}])
    with pytest.raises(KeyError):
        gfx.render(base(), [{'rect': [0, 0, 10, 10], 'clear': True, 'text': 'x', 'font': 'nope',
                             'fill': [[0, 0, 0]], 'outline': None, 'stroke': 0}])
