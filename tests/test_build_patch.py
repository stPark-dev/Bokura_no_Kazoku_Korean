"""Release-policy checks of the product build."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import build_patch  # noqa: E402

SRC = [{'id': 'A', 'src': 'x'}, {'id': 'B', 'src': 'y'}]


def test_policy_dev_allows_anything():
    assert build_patch.text_problems(SRC, [], 'dev') == []


def test_policy_beta_needs_every_entry_translated_and_reviewed():
    ko = [{'id': 'A', 'state': 'reviewed'}]
    assert any('untranslated' in p for p in build_patch.text_problems(SRC, ko, 'beta'))
    ko = [{'id': 'A', 'state': 'reviewed'}, {'id': 'B', 'state': 'needs_review'}]
    assert any('state' in p for p in build_patch.text_problems(SRC, ko, 'beta'))
    ko = [{'id': 'A', 'state': 'reviewed'}, {'id': 'B', 'state': 'distribution_eligible'}]
    assert build_patch.text_problems(SRC, ko, 'beta') == []


def test_policy_release_needs_distribution_eligible():
    ko = [{'id': 'A', 'state': 'reviewed'}, {'id': 'B', 'state': 'distribution_eligible'}]
    assert any('state' in p for p in build_patch.text_problems(SRC, ko, 'release'))


def test_exceptions_are_declared_with_decisions():
    for e in build_patch.EXCEPTIONS:
        assert e['what'] and e['basis']
