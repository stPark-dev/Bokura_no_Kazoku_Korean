"""Line-oriented text files read through the line reader at SCPS_150.88 0x24AC50 (leading ' \\t\\r\\x1a'
skipped, '#' starts a comment, trailing blanks trimmed). A unit is the consumed part of one line that
contains non-ASCII text; everything else on the line (indent, trailing blanks, comment) is preserved.

Ids are '<archive>/<file>:<1-based line number>'.
"""
import re

TRIM = ' \t\r\x1a'


def _cp932(s):
    return s.encode('cp932')


def _split(raw):
    """raw line bytes (no '\\n') -> (prefix, consumed, suffix)."""
    body = raw.split(b'#')[0]
    consumed = body.strip(TRIM.encode())
    if not consumed:
        return raw, b'', b''
    start = body.index(consumed)
    return raw[:start], consumed, raw[start + len(consumed):]


def extract(data, file_id, decode=lambda b: b.decode('cp932')):
    rows = []
    for n, raw in enumerate(data.split(b'\n'), 1):
        _, consumed, _ = _split(raw)
        if consumed and any(c >= 0x80 for c in consumed):
            rows.append({'id': f'{file_id}:{n}', 'src': decode(consumed)})
    return rows


def render(data, texts, file_id, encode=_cp932):
    lines = data.split(b'\n')
    out = list(lines)
    for i, text in texts.items():
        f, _, n = i.rpartition(':')
        if f != file_id or not n.isdigit() or not 1 <= int(n) <= len(lines):
            raise KeyError(i)
        prefix, consumed, suffix = _split(lines[int(n) - 1])
        if not consumed:
            raise KeyError(i)
        out[int(n) - 1] = prefix + encode(text) + suffix
    return b'\n'.join(out)


LAYOUT = re.compile(r'@[sd]\d+')  # pitch/offset codes: movable-layout policy, re-tuned per screen


def _skeleton(s):
    return re.sub(r'[^\x21-\x7e]', '', LAYOUT.sub('', s))


def check(src, text, encode=_cp932):
    errs = []
    if _skeleton(text) != _skeleton(src):
        errs.append(f'ASCII skeleton differs: {_skeleton(src)!r} -> {_skeleton(text)!r}')
    if '#' in text and '#' not in src:
        errs.append('"#" starts a comment')
    if text != text.strip(TRIM):
        errs.append('leading/trailing blank is trimmed by the reader')
    try:
        b = encode(text)
        if len(b) > 255:
            errs.append(f'line bytes {len(b)} > 255')
    except (UnicodeError, ValueError, KeyError) as e:
        errs.append(f'encode: {e}')
    return errs
