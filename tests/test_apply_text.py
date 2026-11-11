"""Applying text/event_ko.jsonl entries to EVENT.XAP."""
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import apply_text  # noqa: E402
import hangul_map  # noqa: E402
import mes  # noqa: E402

CMAP = hangul_map.build()
SRC = [{'id': 'EVENT/a.mes/x_01', 'file': 'a.mes', 'label': 'x_01', 'src': '「あ@n\n,\n　い」@n', 'sha1': 'S1'},
       {'id': 'EVENT/a.mes/x_02', 'file': 'a.mes', 'label': 'x_02', 'src': '$OTO$「う」@n', 'sha1': 'S2'}]
DATA = 'x_01, 1.0\r\n\t「あ@n\r\n\t,\r\n\t　い」@n\r\n\r\nx_02\r\n\t$OTO$「う」@n\r\n'.encode('cp932')


def enc(s):
    return hangul_map.encode(s, CMAP)


def test_apply_replaces_block():
    ko = [{'id': 'EVENT/a.mes/x_01', 'sha1': 'S1', 'ko': '「아@n\n,\n　이」@n', 'state': 'needs_review'}]
    out = apply_text.apply_event({'a.mes': DATA}, SRC, ko, enc)
    blocks = mes.parse(out['a.mes'], decode=lambda b: hangul_map.decode(b, CMAP))
    assert blocks[0].src == '「아@n\n,\n　이」@n'
    assert out['a.mes'].endswith('x_02\r\n\t$OTO$「う」@n\r\n'.encode('cp932'))


def test_stale_baseline_fails():
    ko = [{'id': 'EVENT/a.mes/x_01', 'sha1': 'OLD', 'ko': '「아@n\n,\n　이」@n', 'state': 'needs_review'}]
    with pytest.raises(ValueError, match='baseline'):
        apply_text.apply_event({'a.mes': DATA}, SRC, ko, enc)


def test_check_failure_fails():
    ko = [{'id': 'EVENT/a.mes/x_02', 'sha1': 'S2', 'ko': '「우」@n', 'state': 'needs_review'}]
    with pytest.raises(ValueError, match='name variables'):
        apply_text.apply_event({'a.mes': DATA}, SRC, ko, enc)


def test_unknown_and_duplicate_ids_fail():
    with pytest.raises(ValueError, match='unknown'):
        apply_text.apply_event({'a.mes': DATA}, SRC, [{'id': 'EVENT/a.mes/zz', 'sha1': '', 'ko': ''}], enc)
    e = {'id': 'EVENT/a.mes/x_01', 'sha1': 'S1', 'ko': '「아@n\n,\n　이」@n'}
    with pytest.raises(ValueError, match='duplicate'):
        apply_text.apply_event({'a.mes': DATA}, SRC, [e, e], enc)


def test_untranslated_files_untouched():
    assert apply_text.apply_event({'a.mes': DATA}, SRC, [], enc) == {}
