"""Horizontal text width check (D12). Widths are in full-width cells: a double-byte character or Hangul
syllable is 1, an ASCII character (space included, once spaces are drawn half width) is 0.5, and layout
codes (@sNN @dNN @rNN @gNN @bNN @0 @n) and %s are 0. Per display line (@n), the translation must not be
wider than the widest source line, and must not have more lines."""
import os
import re

CODES = re.compile(r'@[sdrgb]\d+|@[0-9a-z]|%s')


def cells(s):
    s = CODES.sub('', s)
    return sum(0.5 if ord(c) < 0x80 else 1 for c in s)


def lines(s):
    return [cells(p) for p in s.split('@n')]


def text_part(src, ko):
    i = len(os.path.commonprefix([src, ko]))
    j = len(os.path.commonprefix([src[i:][::-1], ko[i:][::-1]]))
    # keep codes whole: back up to the last ASCII-only boundary before the first difference
    while i and src[i - 1] not in ' \t,"':
        i -= 1
    return src[i:len(src) - j], ko[i:len(ko) - j]


def check(src, ko):
    s, k = text_part(src, ko)
    sl, kl = lines(s), lines(k)
    errs = []
    if len(kl) > len(sl):
        errs.append(f'{len(kl)} lines > {len(sl)}')
    if max(kl) > max(sl):
        errs.append(f'width {max(kl):g} > {max(sl):g}')
    return errs
