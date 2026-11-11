import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import review_merge  # noqa: E402

SRC = [{'id': 'A', 'sha1': '1', 'src': 'x'}, {'id': 'B', 'sha1': '2', 'src': 'x'},
       {'id': 'C', 'sha1': '3', 'src': 'x'}, {'id': 'D', 'sha1': '4', 'src': 'y'}]
CUR = [{'id': 'A', 'sha1': '1', 'ko': 'X1', 'state': 'needs_review'},
       {'id': 'B', 'sha1': '2', 'ko': 'X1', 'state': 'needs_review'},
       {'id': 'C', 'sha1': '3', 'ko': 'X2', 'state': 'needs_review'},
       {'id': 'D', 'sha1': '4', 'ko': 'Y', 'state': 'needs_review'}]


def test_fix_propagates_to_same_source_and_same_wording_and_marks_reviewed():
    out = {e['id']: e for e in review_merge.apply(SRC, CUR, {'A': 'X9'}, ['A', 'D'])}
    assert out['A']['ko'] == out['B']['ko'] == 'X9'
    assert out['C']['ko'] == 'X2' and out['C']['state'] == 'needs_review'   # different wording: untouched
    assert out['A']['state'] == out['B']['state'] == out['D']['state'] == 'reviewed'


def test_check_errors_abort():
    with pytest.raises(ValueError, match='A: bad'):
        review_merge.apply(SRC, CUR, {'A': 'bad'}, ['A'], check=lambda s, k: ['bad'] if k == 'bad' else [])


def test_unknown_id():
    with pytest.raises(ValueError, match='unknown'):
        review_merge.apply(SRC, CUR, {'Z': 'q'}, [])
