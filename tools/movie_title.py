"""Replace the title text in PSS movies (D9): ending title cards (black background) and the opening title
(over a near-static shot). Only the GOPs that show the title are re-encoded; they are spliced back with zero
stuffing so the rest of the stream, the audio and all timestamps stay byte-identical."""
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import pss

FONT = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc', 1)


def _font(size):
    return ImageFont.truetype(FONT[0], size, index=FONT[1])


def draw_spaced(img, text, center_x, top, size, pitch, colour, max_width=None):
    """Draw text with a fixed per-character pitch (the source titles are letter-spaced), shrinking the
    pitch and then the size to stay within max_width."""
    d = ImageDraw.Draw(img)
    while True:
        f = _font(size)
        widths = [d.textlength(c, font=f) for c in text]
        total = sum(widths) + pitch * (len(text) - 1)
        if max_width is None or total <= max_width or size <= 10:
            break
        if pitch > 2:
            pitch -= 1
        else:
            size -= 1
    x = center_x - total / 2
    for c, w in zip(text, widths):
        d.text((x, top), c, font=f, fill=colour)
        x += w + pitch


def _bands(lum, thr=40):
    rows = (lum > thr).any(1)
    out, s = [], None
    for y, on in enumerate(list(rows) + [False]):
        if on and s is None:
            s = y
        if not on and s is not None:
            out.append((s, y))
            s = None
    return out


def _groups(cols, gap=8):
    xs = np.where(cols)[0]
    out = [[xs[0], xs[0]]]
    for x in xs[1:]:
        if x - out[-1][1] > gap:
            out.append([x, x])
        else:
            out[-1][1] = x
    return out


def ending_layout(ref):
    """From a full-brightness title frame: line bands, text spans to cover, flower positions, peak colour."""
    a = np.asarray(ref.convert('RGB')).astype(int)
    lum = a.max(2)
    b1, b2 = _bands(lum)[:2]
    g1 = _groups((lum[b1[0]:b1[1]] > 40).any(0))
    g2 = _groups((lum[b2[0]:b2[1]] > 40).any(0))
    peak = a[b1[0]:b2[1]].reshape(-1, 3)[lum[b1[0]:b2[1]].reshape(-1).argmax()]
    mask = np.zeros(lum.shape, bool)
    mask[b1[0]:b1[1], g1[0][0]:g1[-1][1] + 1] = lum[b1[0]:b1[1], g1[0][0]:g1[-1][1] + 1] > 60
    return {'line1': (b1, g1[0][0], g1[-1][1]), 'line2': (b2, g2[0][1] + 3, g2[-1][0] - 3),
            'mask': mask, 'ref_mean': float(lum[mask].mean()), 'colour': tuple(int(v) for v in peak)}


def ending_edit(frame, lay, line1, line2):
    """Returns (edited frame, fade). fade = brightness of the original title pixels relative to the reference."""
    a = np.asarray(frame.convert('RGB')).astype(float).max(2)
    m = lay['mask']
    fade = float(a[m].mean() / max(1.0, lay['ref_mean']))
    if fade < 0.03:
        return frame, 0.0
    (y0, y1), x0, x1 = lay['line1']
    (z0, z1), u0, u1 = lay['line2']
    out = frame.convert('RGB').copy()
    d = ImageDraw.Draw(out)
    d.rectangle((x0 - 2, y0 - 2, x1 + 2, y1 + 1), fill=(0, 0, 0))
    d.rectangle((u0, z0 - 2, u1, z1 + 1), fill=(0, 0, 0))
    col = tuple(int(c * min(1.0, fade)) for c in lay['colour'])
    draw_spaced(out, line1, (x0 + x1) / 2, y0 - 3, 15, 4, col)
    draw_spaced(out, line2, (u0 + u1) / 2, z0 - 3, 18, 8, col, max_width=u1 - u0 - 6)
    return out, fade


def _run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reencode(es, a, b, edit, tmp):
    """Re-encode GOPs [a, b) of `es` with the frame list passed through edit(list of PIL) -> list of PIL."""
    table = pss.gops(es)
    first, n = table[a]['base'], table[b]['base'] - table[a]['base']
    src = os.path.join(tmp, 'in.m2v')
    open(src, 'wb').write(es)
    fdir = os.path.join(tmp, 'f')
    os.makedirs(fdir, exist_ok=True)
    _run(['ffmpeg', '-y', '-i', src, '-vf', f"select='between(n,{first},{first + n - 1})'", '-vsync', '0',
          '-start_number', '0', os.path.join(fdir, '%05d.png')])
    paths = [os.path.join(fdir, f'{k:05d}.png') for k in range(n)]
    for p, img in zip(paths, edit([Image.open(p) for p in paths])):
        img.save(p)
    _, non_intra = pss.quant_matrices(es)
    budget = table[b]['offset'] - table[a]['offset']
    rate = int(budget * 8 / (n / 29.97) * 0.9)
    for _ in range(8):
        out = os.path.join(tmp, 'seg.m2v')
        _run(['ffmpeg', '-y', '-framerate', '30000/1001', '-start_number', '0', '-i', os.path.join(fdir, '%05d.png'),
              '-frames:v', str(n), '-c:v', 'mpeg2video', '-pix_fmt', 'yuv420p', '-g', '18', '-bf', '2',
              '-flags', '+cgop', '-sc_threshold', '1000000000', '-aspect', '10:7', '-b:v', str(rate), '-maxrate', '9000k', '-bufsize', '1835008',
              '-inter_matrix', ','.join(map(str, non_intra)), out])
        seg = pss.strip_sequence_headers(pss.gop_data(open(out, 'rb').read()))
        if len(seg) <= budget:
            break
        rate = int(rate * 0.8)
    else:
        raise ValueError('could not fit the re-encoded segment')
    return pss.replace_range(es, table[a]['offset'], table[b]['offset'], seg), n


def ending(pss_bytes, number, title, gops=11):
    es = pss.video_es(pss_bytes)

    def edit(frames):
        lum = [np.asarray(f.convert('L'))[150:260].max() for f in frames[:120]]
        lay = ending_layout(frames[int(np.argmax(lum))])
        out, done = [], False
        for k, f in enumerate(frames):
            if done:
                out.append(f)
                continue
            g, fade = ending_edit(f, lay, f'엔딩 {number}', title)
            if fade == 0.0 and k > int(np.argmax(lum)):
                done = True                       # the title has gone; later frames stay untouched
            out.append(g)
        return out
    with tempfile.TemporaryDirectory() as tmp:
        new, _ = reencode(es, 0, gops, edit, tmp)
    return pss.splice(pss_bytes, new)


# Opening: 「ぼくらのかぞく」 letter-spaced over a near-static city shot (measured on SCPS-15088 OPENING.PSS).
OPENING = {'centers': [87, 163, 240, 319, 400, 482, 558], 'rows': (192, 209), 'plate': 1680, 'first': 1690,
           'last': 1905, 'text': '우리들의가족'}


def opening_edit(frames, first_index, cfg=OPENING):
    import cv2
    from PIL import ImageFilter
    plate = np.asarray(frames[cfg['plate'] - first_index].convert('L')).astype(float)
    y0, y1 = cfg['rows']
    boxes = [(c - 14, y0 - 6, c + 15, y1 + 6) for c in cfg['centers']]

    def strength(f, box):
        x0, b0, x1, b1 = box
        g = np.asarray(f.convert('L')).astype(float)[b0:b1, x0:x1]
        return max(0.0, np.percentile(g, 98) - np.percentile(plate[b0:b1, x0:x1], 98))
    raw = [[strength(f, b) for b in boxes] for f in frames]
    peak = [max(1.0, max(r[i] for r in raw)) for i in range(len(boxes))]
    n = len(cfg['text'])
    span = (cfg['centers'][0], cfg['centers'][-1])
    xs = [span[0] + (span[1] - span[0]) * j / (n - 1) for j in range(n)]
    near = [min(range(len(boxes)), key=lambda i: abs(cfg['centers'][i] - x)) for x in xs]
    f_ = _font(20)
    out = []
    for f, r in zip(frames, raw):
        alpha = [min(1.0, v / p) if v / p > 0.08 else 0.0 for v, p in zip(r, peak)]
        if not any(alpha):
            out.append(f)
            continue
        bgr = cv2.cvtColor(np.asarray(f.convert('RGB')), cv2.COLOR_RGB2BGR)
        mask = np.zeros(bgr.shape[:2], np.uint8)
        for (x0, b0, x1, b1), a in zip(boxes, alpha):
            if a:
                mask[b0:b1, x0:x1] = 255
        clean = Image.fromarray(cv2.cvtColor(cv2.inpaint(bgr, mask, 5, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)).convert('RGBA')
        for ch, x, i in zip(cfg['text'], xs, near):
            a = alpha[i]
            if not a:
                continue
            shadow = Image.new('RGBA', clean.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).text((x + 2, (y0 + y1) / 2 + 2), ch, font=f_, fill=(40, 50, 70, int(150 * a)),
                                        anchor='mm')
            clean.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(1.5)))
            layer = Image.new('RGBA', clean.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((x, (y0 + y1) / 2), ch, font=f_, fill=(255, 255, 255, int(255 * a)), anchor='mm')
            clean.alpha_composite(layer)
        out.append(clean.convert('RGB'))
    return out


def opening(pss_bytes, cfg=OPENING):
    es = pss.video_es(pss_bytes)
    table = pss.gops(es)
    a = max(k for k, g in enumerate(table) if g['base'] <= cfg['plate'])
    b = min(k for k, g in enumerate(table) if g['base'] >= cfg['last'])
    first = table[a]['base']
    with tempfile.TemporaryDirectory() as tmp:
        new, _ = reencode(es, a, b, lambda frames: opening_edit(frames, first, cfg), tmp)
    return pss.splice(pss_bytes, new)
