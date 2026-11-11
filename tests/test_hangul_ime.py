import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from hangul_ime import Ime  # noqa: E402


def typed(keys, slots=4):
    ime = Ime(slots)
    for k in keys:
        ime.press(k)
    return ime.text()


def test_basic_syllables():
    assert typed('ㄱㅣㅁ') == '김'
    assert typed('ㅎㅏㄴㄱㅡㄹ') == '한글'


def test_dokkaebi_moves_final_to_next_syllable():
    assert typed('ㄱㅏㄴㅏ') == '가나'
    assert typed('ㅇㅣㄹㄱㅇㅓ') == '읽어'  # compound final splits: ㄺ -> ㄹ + ㄱ


def test_compound_vowel_and_final():
    assert typed('ㄱㅗㅏ') == '과'
    assert typed('ㅇㅡㅣ') == '의'
    assert typed('ㄷㅏㄹㄱ') == '닭'
    assert typed('ㅇㅓㅂㅅ') == '없'


def test_standalone_jamo_and_vowel_first():
    assert typed('ㅏ') == 'ㅏ'
    assert typed('ㄱ') == 'ㄱ'
    assert typed('ㅗㅏ') == 'ㅘ'
    assert typed('ㄱㄱ') == 'ㄱㄱ'


def test_non_ksx1001_syllable_is_not_composed():
    # 똠 is not in KS X 1001: final ㅁ stays a separate jamo
    assert typed('ㄸㅗㅁ') == '또ㅁ'


def test_non_jamo_char_is_written_plainly():
    assert typed('ㄱA') == 'ㄱA'


def test_backspace_peels_one_jamo_at_a_time():
    ime = Ime(4)
    for k in 'ㄷㅏㄹㄱ':
        ime.press(k)
    seq = []
    for _ in range(5):
        ime.backspace()
        seq.append(ime.text())
    assert seq == ['달', '다', 'ㄷ', '', '']


def test_backspace_compound_vowel():
    ime = Ime(4)
    for k in 'ㄱㅗㅏ':
        ime.press(k)
    ime.backspace()
    assert ime.text() == '고'


def test_slot_limit_blocks_split_when_full():
    # 4 slots: '가나다라' then vowel would need a 5th slot -> plain behaviour (no change)
    ime = Ime(4)
    for k in 'ㄱㅏㄴㅏㄷㅏㄹㅏ':
        ime.press(k)
    assert ime.text() == '가나다라'
