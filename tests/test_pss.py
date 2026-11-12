"""PSS (PS2 MPEG program stream): video ES demux and same-length splice."""
import glob
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import pss  # noqa: E402

MOVIES = sorted(glob.glob(os.path.join(ROOT, 'work', 'movie', '*.PSS')))


@pytest.mark.skipif(not MOVIES, reason='work/movie not present')
def test_splice_identity_and_edit():
    d = open(MOVIES[0], 'rb').read()
    es = pss.video_es(d)
    assert pss.splice(d, es) == d
    edited = bytearray(es)
    edited[100:104] = b'\x00\x00\x00\x00'
    out = pss.splice(d, bytes(edited))
    assert len(out) == len(d) and pss.video_es(out) == bytes(edited)


@pytest.mark.skipif(not MOVIES, reason='work/movie not present')
def test_splice_rejects_length_change():
    d = open(MOVIES[0], 'rb').read()
    with pytest.raises(ValueError):
        pss.splice(d, pss.video_es(d) + b'\0')


def test_replace_prefix_pads_with_zero_stuffing():
    es = b'\x00\x00\x01\xb3' + b'A' * 20 + b'\x00\x00\x01\xb8' + b'B' * 10
    cut = es.index(b'\x00\x00\x01\xb8')
    new = pss.replace_prefix(es, cut, b'\x00\x00\x01\xb3XYZ')
    assert len(new) == len(es) and new.endswith(es[cut:]) and new.startswith(b'\x00\x00\x01\xb3XYZ')
    assert set(new[7:cut]) == {0}
    with pytest.raises(ValueError):
        pss.replace_prefix(es, cut, b'Q' * (cut + 1))


def test_gop_table_counts_pictures():
    gop = b'\x00\x00\x01\xb8\x00\x08\x00\x00'
    pic = lambda tr, t: b'\x00\x00\x01\x00' + bytes([tr >> 2, ((tr & 3) << 6) | (t << 3), 0, 0])
    es = b'\x00\x00\x01\xb3' + b'S' * 8 + gop + pic(0, 1) + b'x' * 5 + pic(1, 2) + gop + pic(2, 1) + pic(0, 3) + pic(1, 3)
    t = pss.gops(es)
    assert [(g['base'], g['count']) for g in t] == [(0, 2), (2, 3)]
    assert t[1]['offset'] == es.index(gop, t[0]['offset'] + 4)


def test_replace_range_keeps_tail_and_head():
    es = b'H' * 10 + b'\x00\x00\x01\xb8' + b'M' * 20 + b'\x00\x00\x01\xb8' + b'T' * 5
    a = es.index(b'\x00\x00\x01\xb8'); b = es.index(b'\x00\x00\x01\xb8', a + 1)
    out = pss.replace_range(es, a, b, b'\x00\x00\x01\xb8NEW')
    assert len(out) == len(es) and out[:a] == es[:a] and out[b:] == es[b:]
    with pytest.raises(ValueError):
        pss.replace_range(es, a, b, b'x' * (b - a + 1))


@pytest.mark.skipif(not MOVIES, reason='work/movie not present')
def test_quant_matrices_from_sequence_header():
    es = pss.video_es(open(MOVIES[0], 'rb').read())
    intra, non_intra = pss.quant_matrices(es)
    assert intra is None                                # default intra matrix
    assert len(non_intra) == 64 and non_intra[0] == 16  # custom non-intra matrix, raster order


def test_strip_headers_keeps_from_first_gop():
    es = b'\x00\x00\x01\xb3' + b'S' * 8 + b'\x00\x00\x01\xb5XX' + b'\x00\x00\x01\xb8GOP' + b'\x00\x00\x01\xb7'
    assert pss.gop_data(es) == b'\x00\x00\x01\xb8GOP'


def test_strip_sequence_headers_keeps_picture_extensions():
    seq = b'\x00\x00\x01\xb3' + b'S' * 8 + b'\x00\x00\x01\xb5\x14XX' + b'\x00\x00\x01\xb5\x23YY'
    gop = b'\x00\x00\x01\xb8G'
    pic = b'\x00\x00\x01\x00P' + b'\x00\x00\x01\xb5\x8fZZ' + b'\x00\x00\x01\x01D'
    out = pss.strip_sequence_headers(gop + pic + seq + gop + pic)
    assert out == gop + pic + gop + pic


def _pic(tr, t, body):
    return b'\x00\x00\x01\x00' + bytes([tr >> 2, ((tr & 3) << 6) | (t << 3), 0, 0]) + body


GOP = b'\x00\x00\x01\xb8\x00\x08\x00\x00'


def test_picture_units_split_at_picture_gop_and_sequence_codes():
    es = GOP + _pic(2, 1, b'aaaa') + _pic(0, 3, b'b') + GOP + _pic(0, 1, b'cc') + b'\x00\x00\x01\xb7'
    units = pss.picture_units(es, 0, len(es))
    assert [(u['tr'], u['type']) for u in units] == [(2, 'I'), (0, 'B'), (0, 'I')]
    assert es[units[0]['offset']:units[0]['end']] == _pic(2, 1, b'aaaa')
    assert units[2]['end'] == len(es) - 4


def test_place_pictures_keeps_each_picture_at_its_original_offset():
    head, tail = b'H' * 7, GOP + _pic(0, 1, b'tail')
    old = GOP + _pic(2, 1, b'I' * 20) + _pic(0, 3, b'B' * 10) + _pic(5, 2, b'P' * 15)
    es = head + old + tail
    new = GOP + _pic(2, 1, b'i' * 5) + _pic(0, 3, b'b' * 10) + _pic(5, 2, b'p')
    out = pss.place_pictures(es, len(head), len(head) + len(old), new)
    assert len(out) == len(es) and out.startswith(head + GOP) and out.endswith(tail)
    for o, n in zip(pss.picture_units(es, 0, len(es)), pss.picture_units(out, 0, len(out))):
        assert o['offset'] == n['offset']
    body = out[len(head):len(head) + len(old)]
    assert _pic(2, 1, b'i' * 5) + b'\0' * 15 + _pic(0, 3, b'b' * 10) + _pic(5, 2, b'p') + b'\0' * 14 in body


def test_place_pictures_rejects_mismatch_and_overflow():
    old = GOP + _pic(2, 1, b'I' * 4) + _pic(0, 3, b'B' * 4)
    with pytest.raises(ValueError):           # picture order differs
        pss.place_pictures(old, 0, len(old), GOP + _pic(0, 1, b'I') + _pic(1, 3, b'B'))
    with pytest.raises(ValueError):           # a picture larger than its slot
        pss.place_pictures(old, 0, len(old), GOP + _pic(2, 1, b'I' * 5) + _pic(0, 3, b'B'))


KO_MOVIES = sorted(glob.glob(os.path.join(ROOT, 'work', 'movie_ko', '*.PSS')))


@pytest.mark.skipif(not (KO_MOVIES and MOVIES), reason='work/movie_ko or work/movie not present')
@pytest.mark.parametrize('path', KO_MOVIES, ids=os.path.basename)
def test_korean_movies_keep_every_picture_at_its_original_offset(path):
    """The players take each picture's timestamp from the PES packet where it starts (opening froze when
    re-encoded pictures were packed to the front of the replaced range)."""
    orig = pss.video_es(open(os.path.join(ROOT, 'work', 'movie', os.path.basename(path)), 'rb').read())
    new = pss.video_es(open(path, 'rb').read())
    units = lambda es: [(u['offset'], u['tr'], u['type']) for u in pss.picture_units(es, 0, len(es))]
    assert units(new) == units(orig)
