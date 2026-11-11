import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import ko_merge  # noqa: E402

SRC = [{'id': 'A', 'sha1': 's1', 'src': 'x'}, {'id': 'B', 'sha1': 's2', 'src': 'y'}]


def test_merge_adds_sorted_by_baseline_order_with_baseline_sha1():
    out = ko_merge.merge(SRC, [], {'B': 'yy', 'A': 'xx'}, state='needs_review')
    assert [(e['id'], e['sha1'], e['ko'], e['state']) for e in out] == [
        ('A', 's1', 'xx', 'needs_review'), ('B', 's2', 'yy', 'needs_review')]


def test_merge_refuses_silent_overwrite():
    cur = [{'id': 'A', 'sha1': 's1', 'ko': 'old', 'state': 'needs_review'}]
    with pytest.raises(ValueError, match='already'):
        ko_merge.merge(SRC, cur, {'A': 'new'}, state='needs_review')
    out = ko_merge.merge(SRC, cur, {'A': 'new'}, state='in_progress', replace=True)
    assert out == [{'id': 'A', 'sha1': 's1', 'ko': 'new', 'state': 'in_progress'}]


def test_merge_unknown_id():
    with pytest.raises(ValueError, match='unknown'):
        ko_merge.merge(SRC, [], {'Z': 'z'}, state='needs_review')
