import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import font20  # noqa: E402
import hangul_map  # noqa: E402

FONT = os.path.join(os.path.dirname(__file__), '..', 'work', 'unpacked', 'FONT.XAP')
need = pytest.mark.skipif(not os.path.isdir(FONT), reason='originals not unpacked')


def _orig():
    return open(os.path.join(FONT, 'font20.moj'), 'rb').read(), open(os.path.join(FONT, 'font20.xim'), 'rb').read()


@need
def test_moj_xim_round_trip_byte_identical():
    moj, xim = _orig()
    f = font20.Font.parse(moj, xim)
    assert len(f.glyphs) == 3681
    m2, x2 = f.serialize_original_layout()
    assert m2 == moj and x2 == xim


def test_hangul_map_is_valid_sjis_kanji_space_and_unique():
    cmap = hangul_map.build()
    assert len(cmap) == 2350 + 51
    codes = list(cmap.values())
    assert len(set(codes)) == len(codes)
    for ch, code in cmap.items():
        lead, trail = code >> 8, code & 0xFF
        assert 0x88 <= lead <= 0x9F or 0xE0 <= lead <= 0xEA
        assert 0x40 <= trail <= 0xFC and trail != 0x7F
        assert code >= 0x889F
    assert '가' in cmap and '힝' in cmap and 'ㄱ' in cmap and 'ㅣ' in cmap


def test_encode_mixes_hangul_and_cp932():
    cmap = hangul_map.build()
    b = hangul_map.encode('가@n「A」', cmap)
    assert b[:2] == cmap['가'].to_bytes(2, 'big')
    assert b[2:] == '@n「A」'.encode('cp932')
    assert hangul_map.decode(b, cmap) == '가@n「A」'


def test_encode_rejects_unmapped_hangul():
    cmap = hangul_map.build()
    with pytest.raises(ValueError):
        hangul_map.encode('똠', cmap)  # not in KS X 1001


def test_encode_rejects_kanji_after_font_replacement():
    cmap = hangul_map.build()
    with pytest.raises(ValueError):
        hangul_map.encode('家', cmap)


@need
def test_build_korean_font_keeps_non_kanji_and_adds_hangul():
    moj, xim = _orig()
    f = font20.Font.parse(moj, xim)
    cmap = hangul_map.build()
    k = font20.build_korean(f, cmap, font20.default_ttf())
    codes = [g.code for g in k.glyphs]
    assert codes == sorted(codes)
    orig_non_kanji = {g.code: g for g in f.glyphs if g.code < 0x889F}
    for c in orig_non_kanji:
        assert c in codes
    for code in cmap.values():
        assert code in codes
    assert len(k.glyphs) <= len(f.glyphs)
    assert k.height <= f.height and k.width == f.width
    m2, x2 = k.serialize()
    k2 = font20.Font.parse(m2, x2)
    assert [(g.code, g.w, g.h) for g in k2.glyphs] == [(g.code, g.w, g.h) for g in k.glyphs]
    ga = next(g for g in k2.glyphs if g.code == cmap['가'])
    assert any(k2.pixel(ga.x + dx, ga.y + dy) for dx in range(ga.w) for dy in range(ga.h))
    # non-kanji glyph pixels are preserved exactly
    a_code = int.from_bytes('あ'.encode('cp932'), 'big')
    go = orig_non_kanji[a_code]
    gk = next(g for g in k2.glyphs if g.code == a_code)
    for dy in range(go.h):
        for dx in range(go.w):
            assert f.pixel(go.x + dx, go.y + dy) == k2.pixel(gk.x + dx, gk.y + dy)


def test_dev_policy_passes_kanji_through_as_cp932():
    cmap = hangul_map.build()
    assert hangul_map.encode('家가', cmap, allow_kanji=True) == '家'.encode('cp932') + cmap['가'].to_bytes(2, 'big')
