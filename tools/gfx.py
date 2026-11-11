"""Graphics-text replacement. A spec item edits one rectangle of an image:
  {"rect": [x, y, w, h], "clear": bool, "text": str, "font": key of FONTS, "fill": [[r,g,b], ...] (1 colour or a
   top->bottom gradient), "outline": [r,g,b] | null, "stroke": px, optional "size" (max px), "align": "center"|"left",
   "bg": [r,g,b,a] (colour used when clearing; default transparent)}
Text is shrunk to fit the rect; nothing outside the rect changes.
"""
from PIL import Image, ImageDraw, ImageFont

FONTS = {
    'sans-bold': ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 1),
    'sans-black': ('/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc', 1),
    'sans-medium': ('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc', 1),
}


def _font(key, size):
    path, index = FONTS[key]
    return ImageFont.truetype(path, size, index=index)


def _text_layer(item, w, h):
    stroke = item.get('stroke', 0)
    size = item.get('size', h)
    while True:
        f = _font(item['font'], size)
        box = f.getbbox(item['text'], stroke_width=stroke)
        tw, th = box[2] - box[0], box[3] - box[1]
        if (tw <= w and th <= h) or size <= 6:
            break
        size -= 1
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    x = (w - tw) // 2 - box[0] if item.get('align', 'center') == 'center' else -box[0]
    y = (h - th) // 2 - box[1]
    mask = Image.new('L', (w, h), 0)
    ImageDraw.Draw(mask).text((x, y), item['text'], font=f, fill=255)
    if item.get('outline') is not None and stroke:
        ImageDraw.Draw(layer).text((x, y), item['text'], font=f, fill=tuple(item['outline']) + (255,),
                                   stroke_width=stroke, stroke_fill=tuple(item['outline']) + (255,))
    fill = item['fill']
    grad = Image.new('RGBA', (w, h))
    for yy in range(h):
        t = 0 if len(fill) == 1 else min(1, max(0, (yy - y - box[1]) / max(1, th)))
        a, b = fill[0], fill[-1]
        grad.paste(tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,), (0, yy, w, yy + 1))
    layer.paste(grad, (0, 0), mask)
    return layer


def render(img, items):
    out = img.convert('RGBA').copy()
    for it in items:
        x, y, w, h = it['rect']
        if x < 0 or y < 0 or x + w > out.width or y + h > out.height:
            raise ValueError(f'rect {it["rect"]} outside image {out.size}')
        if it.get('clear'):
            out.paste(tuple(it.get('bg', (0, 0, 0, 0))), (x, y, x + w, y + h))
        region = out.crop((x, y, x + w, y + h))
        region.alpha_composite(_text_layer(it, w, h))
        out.paste(region, (x, y))
    return out
