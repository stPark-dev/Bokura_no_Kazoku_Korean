"""Reference model of the in-game Hangul composition (name entry), and the tables the MIPS hook uses.

Characters are handled in compatibility-jamo index space (U+3131.. -> 0..50) and syllable index
space (U+AC00.. -> 0..11171). Only KS X 1001 syllables can be produced.
"""
import hangul_map

JAMO0 = 0x3131
CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ'
JONG = ' ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'
VOWEL_PAIRS = ['ㅗㅏㅘ', 'ㅗㅐㅙ', 'ㅗㅣㅚ', 'ㅜㅓㅝ', 'ㅜㅔㅞ', 'ㅜㅣㅟ', 'ㅡㅣㅢ']
FINAL_PAIRS = ['ㄱㅅㄳ', 'ㄴㅈㄵ', 'ㄴㅎㄶ', 'ㄹㄱㄺ', 'ㄹㅁㄻ', 'ㄹㅂㄼ', 'ㄹㅅㄽ', 'ㄹㅌㄾ', 'ㄹㅍㄿ', 'ㄹㅎㅀ', 'ㅂㅅㅄ']
NONE = 0xFF


def jamo_index(ch):
    return ord(ch) - JAMO0


def tables():
    """Byte tables indexed by jamo index (0..50) plus inverse tables, all as lists of ints."""
    cho_of = [NONE] * 51
    jung_of = [NONE] * 51
    jong_of = [NONE] * 51
    for i, c in enumerate(CHO):
        cho_of[jamo_index(c)] = i
    for i, c in enumerate(JUNG):
        jung_of[jamo_index(c)] = i
    for i, c in enumerate(JONG):
        if i:
            jong_of[jamo_index(c)] = i
    jamo_of_cho = [jamo_index(c) for c in CHO]
    jamo_of_jung = [jamo_index(c) for c in JUNG]
    jamo_of_jong = [0] + [jamo_index(c) for c in JONG[1:]]
    pairs = [tuple(jamo_index(c) for c in p) for p in VOWEL_PAIRS + FINAL_PAIRS]
    return dict(cho_of=cho_of, jung_of=jung_of, jong_of=jong_of, jamo_of_cho=jamo_of_cho,
                jamo_of_jung=jamo_of_jung, jamo_of_jong=jamo_of_jong, pairs=pairs)


T = tables()
KS = set(hangul_map.ksx1001_hangul()[0])


def _pair(a, b):
    for x, y, r in T['pairs']:
        if x == a and y == b:
            return r
    return None


def _unpair(r):
    for x, y, rr in T['pairs']:
        if rr == r:
            return x, y
    return None


def _syl(cho, jung, jong):
    ch = chr(0xAC00 + (cho * 21 + jung) * 28 + jong)
    return ch if ch in KS else None


def _split(ch):
    s = ord(ch) - 0xAC00
    return s // 588, (s % 588) // 28, s % 28


def _is_syl(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3


def _is_jamo(ch):
    return 0x3131 <= ord(ch) <= 0x3163


def compose(prev, key):
    """Return (replacement_for_prev, new_char_or_None) or None when no composition applies."""
    if not _is_jamo(key) or prev is None:
        return None
    j = jamo_index(key)
    if _is_jamo(prev):
        p = jamo_index(prev)
        if T['cho_of'][p] != NONE and T['jung_of'][j] != NONE:
            s = _syl(T['cho_of'][p], T['jung_of'][j], 0)
            return (s, None) if s else None
        if T['jung_of'][p] != NONE and T['jung_of'][j] != NONE:
            r = _pair(p, j)
            return (chr(JAMO0 + r), None) if r is not None else None
        return None
    if not _is_syl(prev):
        return None
    cho, jung, jong = _split(prev)
    if T['jung_of'][j] != NONE:  # vowel
        if jong == 0:
            r = _pair(T['jamo_of_jung'][jung], j)
            if r is None:
                return None
            s = _syl(cho, T['jung_of'][r], 0)
            return (s, None) if s else None
        jj = T['jamo_of_jong'][jong]
        parts = _unpair(jj)
        if parts:
            keep, move = T['jong_of'][parts[0]], parts[1]
        else:
            keep, move = 0, jj
        if T['cho_of'][move] == NONE:
            return None
        a = _syl(cho, jung, keep)
        b = _syl(T['cho_of'][move], T['jung_of'][j], 0)
        return (a, b) if a and b else None
    # consonant
    if jong == 0:
        if T['jong_of'][j] == NONE:
            return None
        s = _syl(cho, jung, T['jong_of'][j])
        return (s, None) if s else None
    r = _pair(T['jamo_of_jong'][jong], j)
    if r is None or T['jong_of'][r] == NONE:
        return None
    s = _syl(cho, jung, T['jong_of'][r])
    return (s, None) if s else None


def peel(ch):
    """Backspace on one character: reduced character, or None to delete it entirely."""
    if _is_jamo(ch):
        parts = _unpair(jamo_index(ch))
        return chr(JAMO0 + parts[0]) if parts and T['jung_of'][parts[0]] != NONE else None
    if not _is_syl(ch):
        return None
    cho, jung, jong = _split(ch)
    if jong:
        parts = _unpair(T['jamo_of_jong'][jong])
        return _syl(cho, jung, T['jong_of'][parts[0]] if parts else 0)
    parts = _unpair(T['jamo_of_jung'][jung])
    if parts:
        return _syl(cho, T['jung_of'][parts[0]], 0)
    return chr(JAMO0 + T['jamo_of_cho'][cho])


class Ime:
    def __init__(self, slots):
        self.slots = slots
        self.buf = []

    def press(self, key):
        prev = self.buf[-1] if self.buf else None
        r = compose(prev, key)
        if r:
            a, b = r
            if b is None:
                self.buf[-1] = a
                return
            if len(self.buf) < self.slots:
                self.buf[-1] = a
                self.buf.append(b)
            return
        if len(self.buf) < self.slots:
            self.buf.append(key)

    def backspace(self):
        if not self.buf:
            return
        r = peel(self.buf[-1])
        if r:
            self.buf[-1] = r
        else:
            self.buf.pop()

    def text(self):
        return ''.join(self.buf)
