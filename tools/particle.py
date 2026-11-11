"""Reference model of the particle hook: after a name variable, `X（Y）` becomes X when the name ends
in a final consonant, Y otherwise; with a ㄹ final, X == '으' + Y also takes Y (으로/로).
The deciding character is the last double-byte character of the expanded output: the game appends
ASCII colour codes (`@r255@g255@b255`) after a coloured name. If it is not a precomposed syllable,
`X（Y）` stays unchanged."""
import re

MAX_FORM = 3
_CH = r'[^（）\x00-\x7f\uff61-\uff9f]'  # double-byte Shift-JIS characters only
_PAT = re.compile(r'(%s{1,%d})（(%s{0,%d})）' % (_CH, MAX_FORM, _CH, MAX_FORM))
RIEUL = 8


def select(out, rest):
    """out: expanded name as written so far. Return (text to append, remaining source)."""
    m = _PAT.match(rest)
    wide = [c for c in out if re.fullmatch(_CH, c)]
    if not m or not wide or not '가' <= wide[-1] <= '힣':
        return '', rest
    x, y = m.groups()
    jong = (ord(wide[-1]) - 0xAC00) % 28
    pick = y if jong == 0 or (jong == RIEUL and x == '으' + y) else x
    return pick, rest[m.end():]
