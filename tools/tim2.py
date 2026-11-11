"""Minimal TIM2 (.tm2) -> PIL image decoder (first picture). Supports 4/8bpp CLUT (CSM1, swizzled 8bpp CLUT) and 16/24/32bpp."""
import struct
from PIL import Image


def _a(v):
    return min(255, v * 2)


def _clut(raw, n, ctype):
    cols = []
    bpp = {1: 2, 2: 3, 3: 4}[ctype & 0x3f]
    for i in range(n):
        c = raw[i * bpp:(i + 1) * bpp]
        if bpp == 2:
            v = c[0] | c[1] << 8
            cols.append(((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3, 255 if v & 0x8000 else 0))
        elif bpp == 3:
            cols.append((c[0], c[1], c[2], 255))
        else:
            cols.append((c[0], c[1], c[2], _a(c[3])))
    if n == 256 and not (ctype & 0x80):
        out = list(cols)
        for i in range(256):
            j = (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)
            out[i] = cols[j]
        cols = out
    return cols


def decode(data):
    if data[:4] != b'TIM2':
        raise ValueError('not TIM2')
    off = 0x10 if data[5] == 0 else 0x80
    total, clut_sz, img_sz, hdr_sz, clut_cols, fmt, mip, ctype, itype, w, h = struct.unpack_from('<IIIHHBBBBHH', data, off)
    p = off + hdr_sz
    pix = data[p:p + img_sz]
    craw = data[p + img_sz:p + img_sz + clut_sz]
    im = Image.new('RGBA', (w, h))
    px = im.load()
    if itype in (4, 5):
        cols = _clut(craw, clut_cols, ctype)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                v = (pix[i >> 1] >> (4 * (i & 1))) & 15 if itype == 4 else pix[i]
                px[x, y] = cols[v] if v < len(cols) else (255, 0, 255, 255)
    elif itype == 3:
        for i in range(w * h):
            c = pix[i * 4:i * 4 + 4]
            px[i % w, i // w] = (c[0], c[1], c[2], _a(c[3]))
    elif itype == 2:
        for i in range(w * h):
            c = pix[i * 3:i * 3 + 3]
            px[i % w, i // w] = (c[0], c[1], c[2], 255)
    elif itype == 1:
        for i in range(w * h):
            v = pix[i * 2] | pix[i * 2 + 1] << 8
            px[i % w, i // w] = ((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3, 255)
    else:
        raise ValueError(f'image type {itype}')
    return im
