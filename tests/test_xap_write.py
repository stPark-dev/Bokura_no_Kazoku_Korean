import glob
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from xap import read_entries, read_file, rebuild  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), '..', 'work', 'iso', 'DATA')
SMALL = ['SYSMES.XAP', 'GAMEMES.XAP', 'RESNAME.XAP', 'FONT.XAP', 'GAMEDB.XAP', 'EVENT.XAP', 'MINIG/MINIG5.XAP']

need = pytest.mark.skipif(not os.path.isdir(DATA), reason='original image not extracted')


@need
@pytest.mark.parametrize('name', SMALL)
def test_rebuild_with_original_payloads_is_byte_identical(name):
    d = open(os.path.join(DATA, name), 'rb').read()
    ents = read_entries(d)
    raw = {e.name: d[e.data_off:e.data_off + e.csize] for e in ents}
    assert rebuild(d, raw_payloads=raw) == d


@need
def test_rebuild_with_replaced_file_round_trips():
    d = open(os.path.join(DATA, 'RESNAME.XAP'), 'rb').read()
    new = {'school.txt': 'テスト 한글없음'.encode('cp932', 'replace') * 30}
    out = rebuild(d, files=new)
    ents = read_entries(out)
    assert [e.name for e in ents] == [e.name for e in read_entries(d)]
    for e in ents:
        got = read_file(out, e)
        if e.name in new:
            assert got == new[e.name]
        else:
            assert got == read_file(d, next(x for x in read_entries(d) if x.name == e.name))
