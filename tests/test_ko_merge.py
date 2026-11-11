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


def test_merge_rejects_entries_failing_check():
    def check(src, ko):
        return ['bad'] if 'x' in ko else []
    with pytest.raises(ValueError, match='A: bad'):
        ko_merge.merge(SRC, [], {'A': 'xx', 'B': 'ok'}, state='needs_review', check=check)
    assert len(ko_merge.merge(SRC, [], {'B': 'ok'}, state='needs_review', check=check)) == 1


def test_reuse_fills_identical_sources_only():
    src = [{'id': 'A', 'sha1': 's1', 'src': 'x'}, {'id': 'B', 'sha1': 's2', 'src': 'x'},
           {'id': 'C', 'sha1': 's3', 'src': 'y'}]
    cur = [{'id': 'A', 'sha1': 's1', 'ko': 'X', 'state': 'needs_review'}]
    assert ko_merge.reuse(src, cur) == {'B': 'X'}


def test_reuse_skips_conflicting_translations():
    src = [{'id': 'A', 'sha1': 's1', 'src': 'x'}, {'id': 'B', 'sha1': 's2', 'src': 'x'},
           {'id': 'C', 'sha1': 's3', 'src': 'x'}]
    cur = [{'id': 'A', 'sha1': 's1', 'ko': 'X', 'state': 'needs_review'},
           {'id': 'B', 'sha1': 's2', 'ko': 'Y', 'state': 'needs_review'}]
    assert ko_merge.reuse(src, cur) == {}
