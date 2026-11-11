"""font20.moj (glyph table) + font20.xim (4bpp alpha atlas) codec and Korean font builder."""
import os
import struct
from dataclasses import dataclass, replace

MOJ_HDR = 0x60
XIM_HDR = 0x70
TTF_DEFAULT = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc', 1)  # Noto Sans CJK KR Medium


@dataclass(frozen=True)
class Glyph:
    code: int
    xoff: int
    yoff: int
    x: int
    y: int
    w: int
    h: int


class Font:
    def __init__(self, moj_hdr, xim_hdr, glyphs, width, height, pix):
        self.moj_hdr = moj_hdr
        self.xim_hdr = xim_hdr
        self.glyphs = glyphs
        self.width = width
        self.height = height
        self.pix = pix  # bytearray of 4-bit indices, row-major

    @classmethod
    def parse(cls, moj, xim):
        if moj[:4] != b'MOJI':
            raise ValueError('not MOJI')
        n = struct.unpack_from('<I', moj, MOJ_HDR)[0]
        glyphs = []
        for i in range(n):
            code, xo, yo, pos, w, h, pad = struct.unpack_from('<HbbIBBH', moj, MOJ_HDR + 4 + i * 12)
            if pad:
                raise ValueError(f'glyph {code:#x}: nonzero pad')
            glyphs.append(Glyph(code, xo, yo, pos & 0xFFFF, pos >> 16, w, h))
        if MOJ_HDR + 4 + n * 12 != len(moj):
            raise ValueError('moj size mismatch')
        dsz, _z, height, width = struct.unpack_from('<IIII', xim, 0x60)
        if dsz != width * height // 2 + 0x10 or len(xim) != XIM_HDR + width * height // 2:
            raise ValueError('xim size mismatch')
        raw = xim[XIM_HDR:]
        pix = bytearray(width * height)
        for i, b in enumerate(raw):
            pix[2 * i] = b & 15
            pix[2 * i + 1] = b >> 4
        return cls(moj[:MOJ_HDR], xim[:XIM_HDR], glyphs, width, height, pix)

    def pixel(self, x, y):
        return self.pix[y * self.width + x]

    def _moj(self):
        body = struct.pack('<I', len(self.glyphs))
        for g in self.glyphs:
            body += struct.pack('<HbbIBBH', g.code, g.xoff, g.yoff, g.y << 16 | g.x, g.w, g.h, 0)
        hdr = bytearray(self.moj_hdr)
        struct.pack_into('<I', hdr, 4, MOJ_HDR + len(body) - 8)
        return bytes(hdr) + body

    def _xim(self):
        hdr = bytearray(self.xim_hdr)
        struct.pack_into('<IIII', hdr, 0x60, self.width * self.height // 2 + 0x10, 0, self.height, self.width)
        raw = bytearray(len(self.pix) // 2)
        for i in range(len(raw)):
            raw[i] = self.pix[2 * i] | self.pix[2 * i + 1] << 4
        return bytes(hdr) + bytes(raw)

    def serialize_original_layout(self):
        return self._moj(), self._xim()

    serialize = serialize_original_layout


def default_ttf():
    return TTF_DEFAULT


def _render_hangul(ch, ttf, size=19):
    from PIL import Image, ImageDraw, ImageFont
    path, index = ttf
    font = ImageFont.truetype(path, size, index=index)
    w, h = 22, 21
    im = Image.new('L', (w, h), 0)
    dr = ImageDraw.Draw(im)
    # center the ink box inside a 20x20 cell placed at x=1 (glyph uses xoff=-1 like kanji)
    l, t, r, b = dr.textbbox((0, 0), ch, font=font)
    ox = 1 + (20 - (r - l)) // 2 - l
    oy = (20 - (b - t)) // 2 - t
    dr.text((ox, oy), ch, font=font, fill=255)
    return [[(im.getpixel((x, y)) * 15 + 127) // 255 for x in range(w)] for y in range(h)]


def _pack(items, width):
    """items: list of (glyph_without_pos, bitmap rows). Shelf-pack in order. Returns glyphs, height, pix."""
    placed = []
    x = y = row_h = 0
    for g, bm in items:
        if x + g.w > width:
            y += row_h
            x = row_h = 0
        placed.append((replace(g, x=x, y=y), bm))
        x += g.w
        row_h = max(row_h, g.h)
    height = y + row_h
    pix = bytearray(width * height)
    for g, bm in placed:
        for dy in range(g.h):
            pix[(g.y + dy) * width + g.x:(g.y + dy) * width + g.x + g.w] = bytes(bm[dy])
    return [g for g, _ in placed], height, pix


def build_korean(orig, cmap, ttf):
    items = []
    for g in orig.glyphs:
        if g.code < 0x889F:
            bm = [[orig.pixel(g.x + dx, g.y + dy) for dx in range(g.w)] for dy in range(g.h)]
            items.append((g, bm))
    for ch, code in cmap.items():
        bm = _render_hangul(ch, ttf)
        items.append((Glyph(code, -1, 0, 0, 0, len(bm[0]), len(bm)), bm))
    items.sort(key=lambda it: it[0].code)
    glyphs, height, pix = _pack(items, orig.width)
    if height > orig.height:
        raise ValueError(f'atlas height {height} exceeds original {orig.height}')
    return Font(orig.moj_hdr, orig.xim_hdr, glyphs, orig.width, height, pix)
