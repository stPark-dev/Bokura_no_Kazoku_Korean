"""The committed baseline text/sys_src.jsonl must match a fresh extraction of the declared files."""
import json
import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import extract_sys  # noqa: E402

UNPACKED = os.path.join(ROOT, 'work', 'unpacked')


def test_entry_shape(tmp_path):
    d = tmp_path / 'NAMEDB.XAP'
    d.mkdir()
    (d / 'namedb.txt').write_bytes('[OKA]\r\n\t智子\r\n'.encode('cp932'))
    [e] = extract_sys.extract(str(tmp_path))
    assert e == {'id': 'NAMEDB.XAP/namedb.txt:2', 'file': 'NAMEDB.XAP/namedb.txt', 'src': '智子',
                 'sha1': e['sha1']} and len(e['sha1']) == 40


def test_excluded_files_are_declared_with_reasons():
    assert all(reason for reason in extract_sys.EXCLUDE.values())


@pytest.mark.skipif(not os.path.isdir(UNPACKED), reason='work/unpacked not present')
def test_baseline_matches_fresh_extraction():
    with open(os.path.join(ROOT, 'text', 'sys_src.jsonl'), encoding='utf-8') as f:
        assert [json.loads(line) for line in f] == extract_sys.extract(UNPACKED)
