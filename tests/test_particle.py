"""Particle selection after an expanded name variable: `$OKA$은（는）` -> 은 or 는."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import particle  # noqa: E402


@pytest.mark.parametrize('name,rest,out,left', [
    ('지민', '은（는）보았다', '은', '보았다'),
    ('치코', '은（는）보았다', '는', '보았다'),
    ('치코', '이（가）', '가', ''),
    ('지민', '을（를）', '을', ''),
    ('치코', '과（와）', '와', ''),
    ('지민', '아（야）', '아', ''),
    ('지민', '으로（로）', '으로', ''),
    ('치코', '으로（로）', '로', ''),
    ('하늘', '으로（로）', '로', ''),      # ㄹ final takes 로
    ('하늘', '은（는）', '은', ''),
    ('지민', '이에요（예요）', '이에요', ''),
    ('치코', '이에요（예요）', '예요', ''),
])
def test_select(name, rest, out, left):
    assert particle.select(name, rest) == (out, left)


@pytest.mark.parametrize('name,rest', [
    ('ＡＢ', '은（는）'),         # not Hangul: keep both forms
    ('ㄱ', '은（는）'),           # lone jamo: keep both
    ('', '은（는）'),
    ('지민', '「안녕」'),          # no particle pattern
    ('지민', '은（는'),           # unterminated
    ('지민', '가나다라（는）'),    # first form longer than 3
    ('지민', '은（가나다라）'),    # second form longer than 3
    ('지민', '（는）'),           # empty first form
])
def test_untouched(name, rest):
    assert particle.select(name, rest) == ('', rest)


@pytest.mark.parametrize('out,rest,pick', [
    ('@r80@g80@b255지민@r255@g255@b255', '은（는）', '은'),   # coloured name: trailing ASCII codes skipped
    ('@r80@g80@b255치코@r255@g255@b255', '으로（로）', '로'),
    ('@r80@g80@b255ＡＢ@r255@g255@b255', '은（는）', ''),
])
def test_trailing_codes_are_skipped(out, rest, pick):
    assert particle.select(out, rest)[0] == pick
