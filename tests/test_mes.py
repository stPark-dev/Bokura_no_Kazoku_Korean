"""EVENT .mes parser/renderer: consumer rules of the loader at SCPS_150.88 0x13DA10."""
import glob
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import hangul_map  # noqa: E402
import mes  # noqa: E402

CMAP = hangul_map.build()

SAMPLE = ('# 000h1a\r\n\r\n'
          '000h1a_01, 1.982\r\n'
          '\t「僕の人生…@n\r\n'
          '\t,\r\n'
          '\t　僕は二十代@n\r\n'
          '#comment inside\r\n'
          '\t　結婚した」@n\r\n'
          '\r\n'
          '000h1a_02\r\n'
          '\t$OTO$「日記？@n\r\n'
          '\r\n').encode('cp932')


def test_parse_blocks():
    blocks = mes.parse(SAMPLE)
    assert [b.label for b in blocks] == ['000h1a_01', '000h1a_02']
    assert blocks[0].head == '000h1a_01, 1.982'
    assert blocks[0].src == '「僕の人生…@n\n,\n　僕は二十代@n\n　結婚した」@n'
    assert blocks[0].segments == 2
    assert blocks[1].src == '$OTO$「日記？@n'


def test_render_identity_and_replacement():
    assert mes.render(SAMPLE, {}) == SAMPLE
    out = mes.render(SAMPLE, {'000h1a_02': '$OTO$「일기？@n\n　두 줄」@n'},
                     encode=lambda s: hangul_map.encode(s, CMAP, allow_kanji=True))
    blocks = mes.parse(out, decode=lambda b: hangul_map.decode(b, CMAP))
    assert blocks[1].src == '$OTO$「일기？@n\n　두 줄」@n'
    assert out.startswith(SAMPLE[:SAMPLE.index(b'000h1a_02')])


def test_render_unknown_label_fails():
    with pytest.raises(KeyError):
        mes.render(SAMPLE, {'nope': 'x'})


@pytest.mark.parametrize('ko,err', [
    ('「a@n\n　b」@n', 'segments'),                     # comma line dropped
    ('「x@n\n,\n　y,z」@n', 'segments'),                 # stray ASCII comma splits a segment
    ('「x@n\n,\n　y」@n#', '#'),
    ('「x@n\n,\n3살」@n', 'label'),                      # line would be read as a new label
    ('「x@n\n,\n　' + '가' * 130 + '@n', 'line bytes'),
    ('「x@n\n,\n' + ('　' + '가' * 100 + '@n\n') * 6, 'body bytes'),
])
def test_check_rejects(ko, err):
    src = mes.parse(SAMPLE)[0].src
    errs = mes.check(src, ko, encode=lambda s: s.encode('utf-8').replace('가'.encode(), b'\x88\x9f'))
    assert any(err in e for e in errs), errs


@pytest.mark.parametrize('ko,err', [
    ('「x@n\n,\n　' + '가' * 19 + '@n', 'cells'),                 # 20 cells on one display line
    ('$OKA$「' + '가' * 15 + '@n\n,\n　y」@n', 'cells'),          # a name variable counts as 4 cells
    ('「x@n\n,\n　a@n\n　b@n\n　c@n\n　d」@n', 'display lines'),  # 4 lines in one voice segment
])
def test_check_layout(ko, err):
    src = mes.parse(SAMPLE)[0].src if '$' not in ko else '$OKA$「x@n\n,\n　y」@n'
    errs = mes.check(src, ko, encode=str.encode)
    assert any(err in e for e in errs), errs


def test_check_layout_limits_inclusive():
    assert mes.check('「x@n\n,\n　y」@n', '「' + '가' * 18 + '@n\n,\n　a@n\n　b@n\n　c」@n', encode=str.encode) == []


def test_check_name_variables():
    src = mes.parse(SAMPLE)[1].src
    assert mes.check(src, '「일기？@n', encode=str.encode)
    assert not mes.check(src, '$OTO$「일기？@n', encode=str.encode)


def test_check_accepts_translation():
    src = mes.parse(SAMPLE)[0].src
    assert mes.check(src, '「내 인생…@n\n,\n　나는 이십 대@n\n　결혼했다」@n', encode=str.encode) == []


EVENT = sorted(glob.glob(os.path.join(ROOT, 'work', 'unpacked', 'EVENT.XAP', '*.mes')))


@pytest.mark.skipif(not EVENT, reason='work/unpacked not present')
def test_corpus_round_trip_and_rules():
    n = over = 0
    for p in EVENT:
        data = open(p, 'rb').read()
        blocks = mes.parse(data)
        labels = [b.label for b in blocks]
        assert len(labels) == len(set(labels)), p
        assert mes.render(data, {b.label: b.src for b in blocks}) == data, p
        for b in blocks:
            errs = mes.check(b.src, b.src)
            if '欠番' in b.src:  # unused-type placeholders ("missing number"), 20 cells
                assert all('cells' in e for e in errs), (p, b.label, errs)
                over += bool(errs)
            else:
                assert errs == [], (p, b.label)
        n += len(blocks)
    assert len(EVENT) == 1517 and n == 4478 and over == 22


def test_layout_counts_particle_pair_as_its_longer_form():
    src = '$OKA$「x$OKA$@n'
    assert mes.check(src, '$OKA$「' + '가' * 9 + '$OKA$은（는）@n', encode=str.encode) == []  # 4+1+9+4+1 = 19
    assert mes.check(src, '$OKA$「' + '가' * 12 + '$OKA$으로（로）@n', encode=str.encode)          # 4+1+12+4+2 = 23


def test_vertical_encoder_halves_spaces_and_limits_count_expanded_bytes():
    enc = mes.vertical_encoder(lambda s: s.encode('cp932'))
    assert enc('a b') == b'a@s10 @s20b'
    src = '「x@n'
    long = '「' + ' '.join(['ab'] * 40) + '@n'          # 39 spaces -> +312 bytes after expansion
    assert any('line bytes' in e for e in mes.check(src, long, enc))
    assert not any('line bytes' in e for e in mes.check(src, long, lambda s: s.encode('cp932')))
