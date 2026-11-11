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


@pytest.mark.parametrize('src,ko,ok', [
    ('000\t@s22続@s14　@s22き@s14　@s22か@s14　@s22ら', '000\t@s22이@s14　@s22어@s14　@s22하@s14　@s22기', True),
    ('009\t@s18@r115@g108@b53ＮＥＷゲーム', '009\t@s18@r115@g108@b53새 게임', True),
    ('000\t@s22Ｎ@s1　@s22Ｅ@s1　@s22Ｗ', '000\t@s22새@s3　@s22게@d20임', True),   # spacing tokens are layout
    ('003\t@s22設@d20定', '003\t@s22설정', True),
    ('012\t@r119@g119@b96@s20は@s10　@s20い', '012\t@s20네', False),           # colour dropped
])
def test_spacing_tokens_are_movable(src, ko, ok):
    assert (linetext.check(src, ko, encode=str.encode) == []) is ok
