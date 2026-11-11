"""Hangul -> Shift-JIS code assignment.

The game font replaces every kanji glyph (codes >= 0x889F). KS X 1001 Hangul syllables (2,350, in
KS order) followed by compatibility jamo (51) are assigned to consecutive valid SJIS double-byte
codes starting at 0x889F. Every other character is encoded as cp932 and must stay below 0x889F.
"""
KANJI_START = 0x889F


def _sjis_codes(start=KANJI_START):
    lead, trail = start >> 8, start & 0xFF
    while True:
        yield lead << 8 | trail
        trail += 1
        if trail == 0x7F:
            trail = 0x80
        if trail > 0xFC:
            trail = 0x40
            lead += 1
            if lead == 0xA0:
                lead = 0xE0


def ksx1001_hangul():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.append(bytes([hi, lo]).decode('euc-kr'))
    jamo = [bytes([0xA4, lo]).decode('euc-kr') for lo in range(0xA1, 0xD4)]
    return out, jamo


def build():
    syll, jamo = ksx1001_hangul()
    gen = _sjis_codes()
    return {ch: next(gen) for ch in syll + jamo}


def _is_hangul(ch):
    o = ord(ch)
    return 0xAC00 <= o <= 0xD7A3 or 0x3131 <= o <= 0x318E or 0x1100 <= o <= 0x11FF


def encode(text, cmap, allow_kanji=False):
    """allow_kanji=True is the development/PoC policy only: kanji bytes pass through (render as wrong glyphs)."""
    out = bytearray()
    for i, ch in enumerate(text):
        if ch in cmap:
            out += cmap[ch].to_bytes(2, 'big')
            continue
        if _is_hangul(ch):
            raise ValueError(f'unmapped Hangul {ch!r} at {i}')
        try:
            b = ch.encode('cp932')
        except UnicodeEncodeError:
            raise ValueError(f'unencodable {ch!r} at {i}') from None
        if len(b) == 2 and int.from_bytes(b, 'big') >= KANJI_START and not allow_kanji:
            raise ValueError(f'kanji-range glyph {ch!r} at {i} (replaced by Hangul in the font)')
        out += b
    return bytes(out)


def decode(data, cmap):
    rev = {v: k for k, v in cmap.items()}
    out = []
    i = 0
    while i < len(data):
        b = data[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            code = b << 8 | data[i + 1]
            out.append(rev[code] if code in rev else data[i:i + 2].decode('cp932'))
            i += 2
        else:
            out.append(data[i:i + 1].decode('cp932'))
            i += 1
    return ''.join(out)
