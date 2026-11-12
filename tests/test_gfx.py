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


def test_title_logo_only_changes_logo_band():
    import os
    p = os.path.join(os.path.dirname(__file__), '..', 'work', 'png', 'TITLE.XAP', 'title.png')
    if not os.path.exists(p):
        pytest.skip('no data')
    import title_logo
    im = Image.open(p).convert('RGBA')
    out = title_logo.make(im)
    assert out.size == im.size
    x0, y0, x1, y1 = title_logo.BOX
    assert out.crop((0, y1, im.width, im.height)).tobytes() == im.crop((0, y1, im.width, im.height)).tobytes()
    assert out.crop((x0, y0, x1, y1)).tobytes() != im.crop((x0, y0, x1, y1)).tobytes()


def test_generator_entry_in_build():
    import build_gfx

    def read(path):
        raise AssertionError('not called for an unknown generator')
    with pytest.raises(KeyError):
        build_gfx.build(read, spec={'X.XAP/a.tm2': {'generator': 'nope'}})


UNPACKED = os.path.join(os.path.dirname(__file__), '..', 'work', 'unpacked')
ICON = 'MENURES.XAP/sysicn06.tm2'


def _read(path):
    return open(os.path.join(UNPACKED, path), 'rb').read()


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='work/unpacked not present')
def test_import_png_replaces_spec_and_gets_new_palette(tmp_path):
    import build_gfx
    import tim2
    w, h = tim2.decode(_read(ICON)).size
    painted = Image.new('RGBA', (w, h), (12, 200, 90, 255))
    (tmp_path / 'MENURES.XAP').mkdir()
    painted.save(tmp_path / 'MENURES.XAP' / 'sysicn06.png')
    used = {}
    out = build_gfx.build(_read, spec={ICON: [{'rect': [0, 0, 4, 4], 'clear': True}]}, imports=str(tmp_path),
                          used=used)
    assert tim2.decode(out[ICON]).getpixel((w // 2, h // 2))[:3] == (12, 200, 90)
    assert list(used) == [ICON] and len(used[ICON]) == 40


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='work/unpacked not present')
def test_import_png_with_wrong_size_fails(tmp_path):
    import build_gfx
    (tmp_path / 'MENURES.XAP').mkdir()
    Image.new('RGBA', (3, 3)).save(tmp_path / 'MENURES.XAP' / 'sysicn06.png')
    with pytest.raises(ValueError):
        build_gfx.build(_read, spec={}, imports=str(tmp_path))


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='work/unpacked not present')
def test_export_writes_original_and_current_korean(tmp_path):
    import gfx_export
    import tim2
    rows = gfx_export.export(_read, {ICON: [{'src': '家計簿', 'text': '가계부', 'rect': [160, 0, 78, 41],
                                             'clear': True, 'font': 'sans-black', 'fill': [[160, 195, 195]]}]},
                             str(tmp_path))
    orig = Image.open(tmp_path / '원본' / 'MENURES.XAP' / 'sysicn06.png')
    assert orig.size == tim2.decode(_read(ICON)).size
    assert (tmp_path / '현재한글' / 'MENURES.XAP' / 'sysicn06.png').exists()
    assert rows[0]['path'] == ICON and rows[0]['texts'] == '家計簿→가계부'
