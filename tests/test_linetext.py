"""Line-oriented system text files (NAMEDB, GAMEDB, MENU, …): extract, render, check."""
import glob
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import linetext  # noqa: E402

SAMPLE = ('# comment 日本語\r\n'
          '[OTO]\r\n'
          '\t桜田, 咲太郎\r\n'
          '\r\n'
          '[MOK]\r\n'
          '\t拓哉\t# 注釈\r\n'
          '\tabc\r\n').encode('cp932')


def test_extract_only_consumed_japanese_lines():
    rows = linetext.extract(SAMPLE, 'NAMEDB/namedb.txt')
    assert [(r['id'], r['src']) for r in rows] == [
        ('NAMEDB/namedb.txt:3', '桜田, 咲太郎'), ('NAMEDB/namedb.txt:6', '拓哉')]


def test_render_keeps_indent_comment_and_line_endings():
    out = linetext.render(SAMPLE, {'NAMEDB/namedb.txt:6': '타쿠야'}, 'NAMEDB/namedb.txt',
                          encode=lambda s: s.encode('utf-8'))
    assert out.split(b'\r\n')[5] == b'\t' + '타쿠야'.encode('utf-8') + b'\t# ' + '注釈'.encode('cp932')
    assert linetext.render(SAMPLE, {}, 'NAMEDB/namedb.txt') == SAMPLE


def test_render_rejects_unknown_id():
    with pytest.raises(KeyError):
        linetext.render(SAMPLE, {'NAMEDB/namedb.txt:99': 'x'}, 'NAMEDB/namedb.txt')


@pytest.mark.parametrize('src,ko,ok', [
    ('桜田, 咲太郎', '사쿠라다, 사쿠타로', True),
    ('桜田, 咲太郎', '사쿠라다 사쿠타로', False),          # field separator lost
    ('"@r115第%s話", -1', '"@r115제%s화", -1', True),
    ('"@r115第%s話", -1', '"@r115%s화", -1', True),
    ('"@r115第%s話", -1', '"제%s화", -1', False),           # colour code dropped
    ('名前', '이름#', False),
])
def test_check(src, ko, ok):
    assert (linetext.check(src, ko, encode=str.encode) == []) is ok


ALL = [p for p in glob.glob(os.path.join(ROOT, 'work', 'unpacked', '*', '*.txt'))]


@pytest.mark.skipif(not ALL, reason='work/unpacked not present')
def test_round_trip_all_txt_files():
    for p in ALL:
        data = open(p, 'rb').read()
        fid = '/'.join(p.split(os.sep)[-2:])
        rows = linetext.extract(data, fid)
        assert linetext.render(data, {r['id']: r['src'] for r in rows}, fid) == data, p
