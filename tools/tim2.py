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


def _layout(data):
    off = 0x10 if data[5] == 0 else 0x80
    total, clut_sz, img_sz, hdr_sz, clut_cols, fmt, mip, ctype, itype, w, h = struct.unpack_from('<IIIHHBBBBHH', data, off)
    return off + hdr_sz, img_sz, clut_sz, clut_cols, ctype, itype, w, h


def encode(orig, img):
    """Return `orig` with its pixel data replaced by `img` (same size). Header and CLUT are kept; CLUT images
    use the nearest palette colour (an unchanged pixel keeps its original index, so round trips are exact)."""
    p, img_sz, clut_sz, clut_cols, ctype, itype, w, h = _layout(orig)
    img = img.convert('RGBA')
    if img.size != (w, h):
        raise ValueError(f'size {img.size} != {(w, h)}')
    out = bytearray(orig)
    pix = orig[p:p + img_sz]
    src = img.load()
    if itype in (4, 5):
        cols = _clut(orig[p + img_sz:p + img_sz + clut_sz], clut_cols, ctype)
        cache = {}

        def nearest(c):
            if c not in cache:
                cache[c] = min(range(len(cols)), key=lambda k: sum((a - b) ** 2 for a, b in zip(cols[k], c)))
            return cache[c]
        idx = []
        for y in range(h):
            for x in range(w):
                i = y * w + x
                old = (pix[i >> 1] >> (4 * (i & 1))) & 15 if itype == 4 else pix[i]
                c = src[x, y]
                idx.append(old if old < len(cols) and cols[old] == c else nearest(c))
        if itype == 4:
            for i in range(0, w * h, 2):
                out[p + (i >> 1)] = idx[i] | (idx[i + 1] << 4 if i + 1 < w * h else 0)
        else:
            out[p:p + w * h] = bytes(idx)
    elif itype == 3:
        for i in range(w * h):
            r, g, b, a = src[i % w, i // w]
            oa = orig[p + i * 4 + 3]
            out[p + i * 4:p + i * 4 + 4] = bytes((r, g, b, oa if _a(oa) == a else (a + 1) // 2))
    else:
        raise ValueError(f'encoding image type {itype} not supported')
    return bytes(out)


def _clut_raw(cols, ctype):
    """Inverse of _clut for 32-bit CLUT entries (all CLUT images in SCPS-15088 use them)."""
    if ctype & 0x3f != 3:
        raise ValueError(f'CLUT type {ctype:#x} not supported')
    raw = list(cols)
    if len(cols) == 256 and not (ctype & 0x80):
        for i in range(256):
            raw[(i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1)] = cols[i]
    return b''.join(bytes((r, g, b, (a + 1) // 2)) for r, g, b, a in raw)


def encode_palette(orig, img):
    """Like encode, but for CLUT images builds a new palette from `img` (for repainted images whose colours
    are not in the original palette). Header, sizes and CLUT format are kept."""
    p, img_sz, clut_sz, clut_cols, ctype, itype, w, h = _layout(orig)
    if itype not in (4, 5):
        return encode(orig, img)
    img = img.convert('RGBA')
    if img.size != (w, h):
        raise ValueError(f'size {img.size} != {(w, h)}')
    n = min(clut_cols, 16 if itype == 4 else 256)
    px = list(img.get_flattened_data())
    exact = img.getcolors(n)
    if exact:                                   # few colours: exact palette
        cols = [c for _, c in exact]
        where = {c: k for k, c in enumerate(cols)}
        idx = [where[c] for c in px]
    else:
        q = img.quantize(colors=n, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
        pal = q.getpalette(rawmode='RGBA')
        cols = [tuple(pal[4 * i:4 * i + 4]) for i in range(min(n, len(pal) // 4))]
        idx = list(q.get_flattened_data())
    cols += [(0, 0, 0, 0)] * (clut_cols - len(cols))
    out = bytearray(orig)
    if itype == 4:
        for i in range(0, w * h, 2):
            out[p + (i >> 1)] = idx[i] | (idx[i + 1] << 4 if i + 1 < w * h else 0)
    else:
        out[p:p + w * h] = bytes(idx)
    out[p + img_sz:p + img_sz + clut_cols * 4] = _clut_raw(cols, ctype)
    return bytes(out)
