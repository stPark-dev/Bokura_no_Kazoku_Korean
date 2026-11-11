"""EVENT/GAMEMES .mes files, modelled on the loader in SCPS_150.88.

Consumer facts (disassembly):
- 0x24AC50 reads one line: skips leading ' \\t\\r\\x1a', stops at '\\n' or '#' (byte-wise, so '#'
  starts a comment), keeps at most 255 bytes, trims the same set at the end. Empty lines are skipped.
- 0x13DA10: a line whose first byte is [0-9A-Za-z] is a block label; any other line is appended with
  strcat (no separator) to a 0x400-byte stack buffer (sp+0x500, unchecked; overflow hits saved registers).
- 0x13DBF8: the label line is split on ',' (trimming ' \\t') into label + voice times; the body is split
  on ',' into the same number of segments (0x24A570, Shift-JIS aware). Display breaks are '@n'.
"""
import re
from dataclasses import dataclass, field

TRIM = ' \t\r\x1a'
LINE_MAX = 255
BODY_MAX = 0x400 - 1
NAME_VAR = re.compile(r'\$[A-Z]+\$')
NAME_WITH_PARTICLE = re.compile(r'\$[A-Z]+\$(?:([^（）]{1,3})（([^（）]{0,3})）)?')  # hook keeps one form
LINE_CELLS_MAX = 19   # source maximum (names as 4 cells); 20+ cells left the screen in PoC3
NAME_CELLS = 4        # name entry field holds 4 characters
SEG_LINES_MAX = 3     # source maximum display lines per voice segment


def _cp932(s):
    return s.encode('cp932')


def _is_label(content):
    c = content[0]
    return c < 0x80 and chr(c).isalnum()


@dataclass
class Block:
    label: str
    head: str
    head_index: int
    body_indices: list = field(default_factory=list)
    body: list = field(default_factory=list)

    @property
    def src(self):
        return '\n'.join(self.body)

    @property
    def segments(self):
        return self.src.count(',') + 1


def _content(raw):
    return raw.split(b'#')[0].strip(TRIM.encode())


def parse(data, decode=lambda b: b.decode('cp932')):
    blocks = []
    for i, raw in enumerate(data.split(b'\n')):
        c = _content(raw)
        if not c:
            continue
        if _is_label(c):
            head = decode(c)
            blocks.append(Block(head.split(',')[0].strip(), head, i))
        elif not blocks:
            raise ValueError(f'line {i}: body text before the first label')
        else:
            blocks[-1].body_indices.append(i)
            blocks[-1].body.append(decode(c))
    return blocks


def render(data, texts, encode=_cp932):
    """texts: {label: text}; each text line becomes '\\t' + line + CRLF in place of the block's body."""
    if not texts:
        return data
    lines = data.split(b'\n')
    blocks = {b.label: b for b in parse(data)}
    unknown = set(texts) - set(blocks)
    if unknown:
        raise KeyError(sorted(unknown))
    replace, drop = {}, set()
    for label, text in texts.items():
        b = blocks[label]
        enc = encode
        if isinstance(text, tuple):  # (text, encoder) chosen per block
            text, enc = text
        new = [b'\t' + enc(line) + b'\r' for line in text.split('\n')]
        if b.body_indices:
            replace[b.body_indices[0]] = new
            drop.update(b.body_indices[1:])
        else:
            replace[b.head_index] = [lines[b.head_index]] + new
    out = []
    for i, raw in enumerate(lines):
        if i in replace:
            out.extend(replace[i])
        elif i not in drop:
            out.append(raw)
    return b'\n'.join(out)


def check(src, text, encode=_cp932, body_max=BODY_MAX):
    """Mechanical checks of a translated block body against its source; returns error strings."""
    errs = []
    if text.count(',') != src.count(','):
        errs.append(f'segments: {text.count(",") + 1} != {src.count(",") + 1}')
    if sorted(NAME_VAR.findall(text)) != sorted(NAME_VAR.findall(src)):
        errs.append(f'name variables: {NAME_VAR.findall(text)} != {NAME_VAR.findall(src)}')
    total = 0
    for n, line in enumerate(text.split('\n')):
        if '#' in line:
            errs.append(f'line {n}: "#" starts a comment')
            line = line.split('#')[0]
        if line != line.strip(TRIM):
            errs.append(f'line {n}: leading/trailing blank is trimmed by the reader')
        line = line.strip(TRIM)
        if not line:
            continue
        try:
            b = encode(line)
        except (UnicodeError, ValueError, KeyError) as e:
            errs.append(f'line {n}: encode: {e}')
            continue
        if _is_label(b):
            errs.append(f'line {n}: starts with [0-9A-Za-z], read as a label')
        if len(b) > LINE_MAX:
            errs.append(f'line {n}: line bytes {len(b)} > {LINE_MAX}')
        total += len(b)
    if total > body_max:
        errs.append(f'body bytes {total} > {body_max}')
    return errs + _layout(text) + _particles(text)


# After a name variable, a particle whose form depends on the final consonant must be a pair X（Y） so the
# hook at 0x13E4C8 can choose (it only looks right after the name, not across a line break).
UNPAIRED = re.compile(r'\$[A-Z]+\$((?:@n\n　)?)(은|는|이|가|을|를|과|와|으로|로|아|야|랑|라|란|였|랍)(?![^（\n]{0,3}（)')


def _particles(text):
    return [f'unpaired particle after name: {m.group(0)!r} (use X（Y） right after the name)'
            for m in UNPAIRED.finditer(text)]


def _layout(text):
    """Vertical event window (PoC3): a 20-cell column runs off the screen. Limits = source maxima."""
    errs = []
    for s, seg in enumerate(text.replace('\n', '').split(',')):
        lines = [x for x in seg.split('@n') if x]
        if len(lines) > SEG_LINES_MAX:
            errs.append(f'segment {s}: {len(lines)} display lines > {SEG_LINES_MAX}')
        for line in lines:
            n = len(NAME_WITH_PARTICLE.sub(
                lambda m: '＊' * (NAME_CELLS + max(len(m[1] or ''), len(m[2] or ''))), line))
            if n > LINE_CELLS_MAX:
                errs.append(f'segment {s}: {n} cells > {LINE_CELLS_MAX}: {line}')
    return errs


VERTICAL_SPACE = '@s10 @s20'  # vertical event text: pitch 10 for the space, back to the default 20 (PoC3 pixels)


def vertical_encoder(encode):
    """Wrap an encoder so ASCII spaces take half a cell in the vertical event window."""
    return lambda s: encode(s.replace(' ', VERTICAL_SPACE))
