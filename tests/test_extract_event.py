"""The committed extraction baseline text/event_src.jsonl must match a fresh extraction."""
import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import extract_event  # noqa: E402

UNPACKED = os.path.join(ROOT, 'work', 'unpacked')
BASELINE = os.path.join(ROOT, 'text', 'event_src.jsonl')


def test_entry_shape(tmp_path):
    d = tmp_path / 'EVENT.XAP'
    d.mkdir()
    (d / 'a.mes').write_bytes('x_01, 1.0\r\n\t「あ@n\r\n\t,\r\n\t　い」@n\r\n'.encode('cp932'))
    (d / 'a.scb').write_bytes(b'\0')
    [e] = extract_event.extract(str(tmp_path))
    assert e['id'] == 'EVENT/a.mes/x_01'
    assert e['file'] == 'a.mes' and e['label'] == 'x_01' and e['head'] == 'x_01, 1.0'
    assert e['src'] == '「あ@n\n,\n　い」@n'
    assert e['segments'] == 2
    assert len(e['sha1']) == 40


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='work/unpacked not present')
def test_baseline_matches_fresh_extraction():
    fresh = extract_event.extract(UNPACKED)
    with open(BASELINE, encoding='utf-8') as f:
        committed = [json.loads(line) for line in f]
    assert committed == fresh


def test_other_archive_prefix(tmp_path):
    d = tmp_path / 'GAMEMES.XAP'
    d.mkdir()
    (d / 'gamemes.mes').write_bytes('reso_1_01\r\n\t『$MAIN$と@n\r\n'.encode('cp932'))
    [e] = extract_event.extract(str(tmp_path), archive='GAMEMES.XAP', prefix='GAMEMES')
    assert e['id'] == 'GAMEMES/gamemes.mes/reso_1_01'


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='work/unpacked not present')
def test_gamemes_baseline_matches_fresh_extraction():
    with open(os.path.join(ROOT, 'text', 'gamemes_src.jsonl'), encoding='utf-8') as f:
        assert [json.loads(line) for line in f] == extract_event.extract(UNPACKED, 'GAMEMES.XAP', 'GAMEMES')
