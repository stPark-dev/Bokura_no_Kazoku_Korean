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


def test_elf_strings_replaces_same_length_and_checks_original():
    enc = lambda s: s.encode('cp932') if s == '春' else b'\x8d\xbb'
    elf = b'xx' + '春'.encode('cp932') + b'\x00yy'
    out = build_patch.patch_elf_strings(elf, [(2, '春', '봄')], enc, off=lambda d, va: va)
    assert out == b'xx\x8d\xbb\x00yy'
    with pytest.raises(ValueError, match='original'):
        build_patch.patch_elf_strings(b'xxAB\x00', [(2, '春', '봄')], enc, off=lambda d, va: va)
    with pytest.raises(ValueError, match='length'):
        build_patch.patch_elf_strings(elf, [(2, '春', '봄봄')], lambda s: b'\x8d\xbb' * len(s) if s != '春' else s.encode('cp932'),
                                      off=lambda d, va: va)


def test_album_season_is_korean():
    assert (0x2DD758, '春', '봄') in build_patch.ELF_STRINGS
