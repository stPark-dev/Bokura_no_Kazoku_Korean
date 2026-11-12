"""D13: repaint text images with GPT (MENURES/INTERF icons and MENU book covers; album photo labels and
MINIG keep the automatic Korean version).

  gfx_gpt.py prep work/unpacked work/gfx_gpt   -> 입력/ (4x, transparency on magenta), 안내/ (text areas
                                                 outlined), 요청문.txt, empty 결과/
  (GPT results go to work/gfx_gpt/결과/ under the same file names)
  gfx_gpt.py take work/unpacked work/gfx_gpt   -> only the text areas of each result are pasted onto the
                                                 original (magenta -> transparent) into work/gfx_import/,
                                                 comparison sheets in 비교/
"""
import json
import os
import re
import sys

from PIL import Image, ImageDraw

import build_gfx
import gfx
import tim2

SCALE = 4
KEY = (255, 0, 255)
ALBUM = re.compile(r'^(gen|kok|jij|kyo|mok|niy|pan|poo)\d')
TEXT = os.path.join(os.path.dirname(__file__), '..', 'text')


def targets(spec):
    out = []
    for path, items in spec.items():
        arc, name = path.split('/', 1)
        if not isinstance(items, list):
            continue
        if arc in ('MENURES.XAP', 'INTERF.XAP') or (arc == 'MENU.XAP' and not ALBUM.match(name)):
            out.append(path)
    return sorted(out)


def flat(path):
    return path[:-4].replace('/', '__') + '.png'


def unflat(name):
    return name[:-4].replace('__', '/') + '.tm2'


def enlarge(im):
    bg = Image.new('RGBA', im.size, KEY + (255,))
    bg.alpha_composite(im.convert('RGBA'))
    return bg.convert('RGB').resize((im.width * SCALE, im.height * SCALE), Image.NEAREST)


def rects(path, items):
    """Text areas to take from the GPT result: each rect for icon sheets (other icons share the sheet), the
    bounding box for a book cover (the new title may be laid out differently)."""
    rs = [list(i['rect']) for i in items]
    if not path.startswith('MENU.XAP/'):
        return rs
    x0, y0 = min(r[0] for r in rs), min(r[1] for r in rs)
    x1, y1 = max(r[0] + r[2] for r in rs), max(r[1] + r[3] for r in rs)
    return [[x0, y0, x1 - x0, y1 - y0]]


def _alpha(c):
    """Coverage of a resampled pixel over the magenta key: magenta-ness min(R, B) - G (grey, white and
    black are not magenta), snapped at both ends."""
    m = min(c[0], c[2]) - c[1]
    return 255 if m <= 40 else 0 if m >= 215 else 255 - m


def _unkey(c, a):
    """Remove the magenta share from a partly keyed pixel (c = a*F + (1-a)*KEY)."""
    if a in (0, 255):
        return tuple(c)
    f = a / 255
    return tuple(max(0, min(255, round((v - (1 - f) * k) / f))) for v, k in zip(c, KEY))


def merge(orig, result, areas, pad=2, keep_alpha=False):
    """Paste the text areas of `result` (any size, same aspect ratio) onto `orig`. keep_alpha (book covers):
    the original transparency is kept and magenta never shows; otherwise magenta becomes transparent."""
    orig = orig.convert('RGBA')
    if abs(result.width / result.height - orig.width / orig.height) > 0.02 * orig.width / orig.height:
        raise ValueError(f'aspect ratio {result.size} differs from {orig.size}')
    small = result.convert('RGB').resize(orig.size, Image.LANCZOS)
    out = orig.copy()
    for x, y, w, h in areas:
        for yy in range(max(0, y - pad), min(orig.height, y + h + pad)):
            for xx in range(max(0, x - pad), min(orig.width, x + w + pad)):
                c = small.getpixel((xx, yy))
                a = _alpha(c)
                if keep_alpha:
                    oa = orig.getpixel((xx, yy))[3]
                    if oa and a:
                        out.putpixel((xx, yy), _unkey(c, a) + (oa,))
                else:
                    out.putpixel((xx, yy), (_unkey(c, a) + (a,)) if a else (0, 0, 0, 0))
    return out


def _book_titles():
    """tm2 name -> (Japanese title, Korean title) from bookinfo.txt numbers and the GAMEDB book list."""
    def rows(name):
        return {json.loads(l)['id']: json.loads(l) for l in open(os.path.join(TEXT, name), encoding='utf-8')}
    src, ko = rows('sys_src.jsonl'), rows('sys_ko.jsonl')
    num_tm2 = {}
    for i, e in src.items():
        m = re.match(r'(\d+),\s*(\w+\.tm2),', e['src'])
        if i.startswith('MENU.XAP/bookinfo.txt') and m:
            num_tm2[m.group(1)] = m.group(2)
    out = {}
    for i, e in src.items():
        m = re.match(r'(\d+),\s*([^,]+?)\s*,', e['src'])
        if i.startswith('GAMEDB.XAP/book.txt') and m and m.group(1) in num_tm2 and num_tm2[m.group(1)] not in out:
            k = re.match(r'\d+,\s*([^,]+?)\s*,', ko[i]['ko'])
            out[num_tm2[m.group(1)]] = (m.group(2), k.group(1))
    return out


def pairs(path, items, titles=None):
    name = path.split('/', 1)[1]
    if path.startswith('MENU.XAP/'):
        titles = _book_titles() if titles is None else titles
        return [titles[name]] if name in titles else []
    return [(i['src'], i['text']) for i in items if i.get('src')]


def prompt(path, repl):
    lines = '\n'.join(f'  {a} → {b}' for a, b in repl)
    cover = path.startswith('MENU.XAP/')
    kind = '책 표지' if cover else '메뉴 아이콘 묶음'
    extra = '- 제목만 바꾸고, 작은 저자·출판사 글자는 그대로 둡니다.\n' if cover else ''
    return (f'[{flat(path)}]\n'
            f'첨부한 그림은 PS2 게임의 {kind}입니다. 그림 속 일본어 글자를 한국어로 바꿔 주세요.\n{lines}\n{extra}'
            '- 바꾸는 글자는 원래 글자와 같은 자리·크기·색·글씨체 느낌(테두리·그림자 포함)으로 그립니다.\n'
            '- 글자 말고는 그림을 하나도 바꾸지 마세요(구도·색·다른 아이콘 그대로).\n'
            '- 자홍색(#FF00FF) 배경은 투명 자리이니 그대로 두세요.\n'
            '- 가로세로 비율을 그대로 유지합니다.\n')


BUNDLE = 6                      # book covers per GPT request (3 x 2)
POS = ['위 왼쪽', '위 가운데', '위 오른쪽', '아래 왼쪽', '아래 가운데', '아래 오른쪽']
GAP = 24
GAP_COLOUR = (60, 60, 60)


def bundle(covers, scale=2):
    """Up to six covers on one 3:2 canvas (the shape GPT answers in): returns (canvas, cells [x, y, w, h])."""
    w, h = covers[0].width * scale, covers[0].height * scale
    gw, gh = 3 * w + 4 * GAP, 2 * h + 3 * GAP
    cw, ch = max(gw, round(gh * 1.5)), max(gh, round(gw / 1.5))
    x0, y0 = (cw - gw) // 2, (ch - gh) // 2
    canvas = Image.new('RGB', (cw, ch), GAP_COLOUR)
    cells = []
    for k, cover in enumerate(covers):
        x, y = x0 + GAP + (k % 3) * (w + GAP), y0 + GAP + (k // 3) * (h + GAP)
        canvas.paste(enlarge(cover).resize((w, h), Image.NEAREST), (x, y))
        cells.append([x, y, w, h])
    return canvas, cells


MATCH_MIN = 0.5      # below this the cover was redrawn too much to locate; keep its grid cell


def _locate(big, ref, cell):
    """GPT may move or resize a cover inside the bundle: find it again by matching the lower part of the
    original cover's opaque area (the title is at the top and was changed) at scales 0.8..1.2 around its cell.
    Falls back to the grid cell when nothing matches well."""
    import cv2
    import numpy as np
    x, y, w, h = cell
    rgb = np.asarray(ref.convert('RGB').crop((x, y, x + w, y + h))).astype(int)
    keyed = (rgb[..., 0] > 200) & (rgb[..., 2] > 200) & (rgb[..., 1] < 60)
    ys, xs = np.where(~keyed)
    if not len(xs):
        return tuple(cell)
    bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    top = by0 + int((by1 - by0) * 0.45)
    tmpl = np.asarray(ref.convert('L').crop((x + bx0, y + top, x + bx1, y + by1)), dtype=np.uint8)
    rx0, ry0 = max(0, x - w // 3), max(0, y - h // 3)
    region = np.asarray(big.convert('L').crop((rx0, ry0, min(big.width, x + w + w // 3),
                                               min(big.height, y + h + h // 3))), dtype=np.uint8)
    best = (MATCH_MIN, tuple(cell))
    for k in range(-10, 11):
        sc = 1 + k * 0.02
        t = cv2.resize(tmpl, (max(1, round(tmpl.shape[1] * sc)), max(1, round(tmpl.shape[0] * sc))),
                       interpolation=cv2.INTER_AREA)
        if t.shape[0] > region.shape[0] or t.shape[1] > region.shape[1]:
            continue
        _, score, _, (mx, my) = cv2.minMaxLoc(cv2.matchTemplate(region, t, cv2.TM_CCOEFF_NORMED))
        if score > best[0]:
            best = (score, (rx0 + mx - round(bx0 * sc), ry0 + my - round(top * sc), round(w * sc), round(h * sc)))
    return best[1]


def unbundle(result, size, cells, ref=None):
    if abs(result.width / result.height - size[0] / size[1]) > 0.02 * size[0] / size[1]:
        raise ValueError(f'bundle result {result.size}: aspect ratio differs from {size} (ask GPT for 3:2)')
    big = result.convert('RGB').resize(size, Image.LANCZOS)
    if ref is not None:
        cells = [_locate(big, ref, c) for c in cells]
    return [big.crop((x, y, x + w, y + h)) for x, y, w, h in cells]


def bundle_prompt(name, repl):
    lines = '\n'.join(f'  {k + 1}번({POS[k]}): {a} → {b}' for k, (a, b) in enumerate(repl))
    return (f'[{name}]\n'
            f'첨부한 그림에는 PS2 게임의 책 표지 {len(repl)}권이 격자로 놓여 있습니다. 각 표지의 일본어 제목을 한국어로 바꿔 주세요.\n'
            f'{lines}\n'
            '- 결과는 이 그림 한 장으로, 같은 격자 배치·가로세로 3:2 비율 그대로 주세요(표지를 따로 나누지 마세요).\n'
            '- 제목만 바꾸고, 작은 저자·출판사 글자와 그림·색·구도는 그대로 둡니다.\n'
            '- 바꾸는 글자는 원래 제목과 같은 자리·크기·색·글씨체 느낌(테두리·그림자 포함)으로 그립니다.\n'
            '- 표지 사이 회색 띠와 바깥 여백은 그대로 둡니다.\n')


def _guide(im, areas):
    g = enlarge(im)
    d = ImageDraw.Draw(g)
    for x, y, w, h in areas:
        d.rectangle((x * SCALE, y * SCALE, (x + w) * SCALE - 1, (y + h) * SCALE - 1), outline=(255, 0, 0), width=2)
    return g


def prep(read, spec, out_dir):
    titles = _book_titles()
    for sub in ('입력', '안내', '결과'):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
    texts = []
    for path in targets(spec):
        im = tim2.decode(read(path))
        enlarge(im).save(os.path.join(out_dir, '입력', flat(path)))
        _guide(im, rects(path, spec[path])).save(os.path.join(out_dir, '안내', flat(path)))
        texts.append(prompt(path, pairs(path, spec[path], titles)))
    open(os.path.join(out_dir, '요청문.txt'), 'w', encoding='utf-8').write('\n'.join(texts))
    covers = [p for p in targets(spec) if p.startswith('MENU.XAP/')]
    os.makedirs(os.path.join(out_dir, '묶음입력'), exist_ok=True)
    os.makedirs(os.path.join(out_dir, '묶음'), exist_ok=True)
    btexts = []
    for b in range(0, len(covers), BUNDLE):
        group = covers[b:b + BUNDLE]
        name = f'책묶음{b // BUNDLE + 1:02d}.png'
        canvas, cells = bundle([tim2.decode(read(p)) for p in group])
        canvas.save(os.path.join(out_dir, '묶음입력', name))
        json.dump({'size': canvas.size, 'cells': cells, 'paths': group},
                  open(os.path.join(out_dir, '묶음', name[:-4] + '.json'), 'w'), ensure_ascii=False)
        btexts.append(bundle_prompt(name, [pairs(p, spec[p], titles)[0] for p in group]))
    open(os.path.join(out_dir, '묶음요청문.txt'), 'w', encoding='utf-8').write('\n'.join(btexts))
    return len(texts)


def _sheet(images, label):
    w = sum(i.width for i in images) * 3 + 8 * (len(images) - 1)
    h = max(i.height for i in images) * 3
    sheet = Image.new('RGB', (w, h + 28), (40, 40, 40))
    x = 0
    for im in images:
        bg = Image.new('RGBA', im.size, (128, 128, 128, 255))
        bg.alpha_composite(im.convert('RGBA'))
        sheet.paste(bg.convert('RGB').resize((im.width * 3, im.height * 3), Image.NEAREST), (x, 0))
        x += im.width * 3 + 8
    ImageDraw.Draw(sheet).text((4, h + 4), label, font=gfx._font('sans-bold', 16), fill=(255, 255, 255))
    return sheet


def has_guide_box(result, size, areas):
    """True when the result carries the red rectangles of 안내/ (GPT was given the guide image, not 입력/):
    most of the pixels on the rect outlines are pure red."""
    sx, sy = result.width / size[0], result.height / size[1]
    px = result.convert('RGB').load()
    pts = []
    for x, y, w, h in areas:
        x0, y0, x1, y1 = x * sx, y * sy, (x + w) * sx - 1, (y + h) * sy - 1
        for k in range(20):
            t = k / 19
            pts += [(x0 + (x1 - x0) * t, y0), (x0 + (x1 - x0) * t, y1), (x0, y0 + (y1 - y0) * t), (x1, y0 + (y1 - y0) * t)]

    def red(p):
        return any(r > 200 and g < 60 and b < 60 for r, g, b in
                   (px[min(result.width - 1, max(0, round(p[0]) + dx)), min(result.height - 1, max(0, round(p[1]) + dy))]
                    for dx in (-2, 0, 2) for dy in (-2, 0, 2)))
    if sum(map(red, pts)) > 0.6 * len(pts):
        return True
    import numpy as np                          # GPT may redraw the box elsewhere: any long pure-red line
    a = np.asarray(result.convert('RGB')).astype(int)
    m = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] < 60)
    return bool(m.mean(axis=1).max() > 0.5 or m.mean(axis=0).max() > 0.5)


def take_areas(path, items, size):
    """GPT often draws a cover title larger than the original one, so covers take the whole repainted cover
    (cutting at the old title box leaves seams); icon sheets take only their text rects."""
    if path.startswith('MENU.XAP/'):
        return [[0, 0, size[0], size[1]]]
    return rects(path, items)


def _take_one(read, spec, path, result, titles, imports, compare_dir):
    orig = tim2.decode(read(path))
    if not path.startswith('MENU.XAP/') and has_guide_box(result, orig.size, rects(path, spec[path])):
        raise ValueError('빨간 안내 테두리가 그려져 있음 - 안내/ 가 아니라 입력/ 그림으로 다시 요청')
    new = merge(orig, result, take_areas(path, spec[path], orig.size), keep_alpha=path.startswith('MENU.XAP/'))
    dest = os.path.join(imports, *path[:-4].split('/')) + '.png'
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    new.save(dest)
    auto = tim2.decode(build_gfx.build(read, spec={path: spec[path]})[path])
    label = '원본 | 자동 한글 | GPT  —  ' + ', '.join(f'{a}→{b}' for a, b in pairs(path, spec[path], titles))
    _sheet([orig, auto, new], label).save(os.path.join(compare_dir, flat(path)))


def take(read, spec, gpt_dir, imports, compare_dir):
    """Single results are named like 입력/; bundle results like 묶음입력/ (책묶음NN.png)."""
    titles = _book_titles()
    done, failed = [], []
    os.makedirs(compare_dir, exist_ok=True)
    for name in sorted(os.listdir(os.path.join(gpt_dir, '결과'))):
        try:
            result = Image.open(os.path.join(gpt_dir, '결과', name))
            if name.startswith('책묶음'):
                lay = json.load(open(os.path.join(gpt_dir, '묶음', os.path.splitext(name)[0] + '.json')))
                ref, _ = bundle([tim2.decode(read(p)) for p in lay['paths']])
                jobs = list(zip(lay['paths'], unbundle(result, tuple(lay['size']), lay['cells'], ref=ref)))
            else:
                if unflat(name) not in targets(spec):
                    raise ValueError(f'{name}: not a GPT target')
                jobs = [(unflat(name), result)]
            for path, img in jobs:
                _take_one(read, spec, path, img, titles, imports, compare_dir)
                done.append(path)
        except ValueError as e:                 # one bad result (e.g. GPT changed the aspect ratio) skips only itself
            failed.append((name, str(e)))
    return done, failed


def main(cmd, root, work):
    spec = json.load(open(build_gfx.SPEC, encoding='utf-8'))

    def read(p):
        return open(os.path.join(root, p), 'rb').read()
    if cmd == 'prep':
        print(prep(read, spec, work), 'images ->', work)
    else:
        done, failed = take(read, spec, work, build_gfx.IMPORTS, os.path.join(work, '비교'))
        print(len(done), 'images -> work/gfx_import, comparison sheets ->', os.path.join(work, '비교'))
        for name, why in failed:
            print('건너뜀:', name, '-', why)


if __name__ == '__main__':
    main(*sys.argv[1:4])
