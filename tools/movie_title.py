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


def _closed(es, gop):
    return bool(es[gop['offset'] + 7] & 0x40)


def _encode_chunk(es, table, a, b, fdir, start_number, lead, tmp):
    """Encode frames for GOPs [a, b) (closed GOPs only at a) and return the pictures from GOP a on."""
    first = table[a]['base']
    keys = [table[k]['base'] - first + lead + next(u['tr'] for u in pss.picture_units(
        es, table[k]['offset'], table[k + 1]['offset']) if u['type'] == 'I') for k in range(a, b)]
    frames = lead + table[b]['base'] - first
    _, non_intra = pss.quant_matrices(es)
    out = os.path.join(tmp, 'seg.m2v')
    for q in range(2, 32):
        _run(['ffmpeg', '-y', '-framerate', '30000/1001', '-start_number', str(start_number),
              '-i', os.path.join(fdir, '%05d.png'), '-frames:v', str(frames), '-c:v', 'mpeg2video',
              '-pix_fmt', 'yuv420p', '-g', '1000', '-bf', '2', '-b_strategy', '0', '-sc_threshold', '1000000000',
              '-aspect', '10:7', '-qscale:v', str(q),
              '-force_key_frames', ','.join(f'{max(0.0, k - 0.5) * 1001 / 30000:.6f}' for k in sorted({0, *keys})),
              '-inter_matrix', ','.join(map(str, non_intra)), out])
        seg = open(out, 'rb').read()
        if lead:
            seg = seg[pss.gops(seg)[1]['offset']:]
        try:
            return pss.place_pictures(es, table[a]['offset'], table[b]['offset'], seg)
        except ValueError as e:
            if 'bytes >' not in str(e):
                raise
            es_fit = e
    raise ValueError(f'could not fit the re-encoded pictures: {es_fit}')


def reencode(es, a, b, edit, tmp):
    """Re-encode GOPs [a, b) of `es` with the frame list passed through edit(list of PIL) -> list of PIL.
    The encoder is driven to the same GOP layout (I frames at the same display positions, two B frames,
    open GOPs; a closed GOP starts a separate encode) and every picture is put back at its original offset,
    so the per-picture PES timestamps stay valid. An open first GOP gets four lead-in frames so its leading
    B frames have a P frame to refer to."""
    table = pss.gops(es)
    first, n = table[a]['base'], table[b]['base'] - table[a]['base']
    lead = 0 if a == 0 or _closed(es, table[a]) else 4
    src = os.path.join(tmp, 'in.m2v')
    open(src, 'wb').write(es)
    fdir = os.path.join(tmp, 'f')
    os.makedirs(fdir, exist_ok=True)
    _run(['ffmpeg', '-y', '-i', src, '-vf', f"select='between(n,{first - lead},{first + n - 1})'", '-vsync', '0',
          '-start_number', '0', os.path.join(fdir, '%05d.png')])
    paths = [os.path.join(fdir, f'{k:05d}.png') for k in range(lead, lead + n)]
    for p, img in zip(paths, edit([Image.open(p) for p in paths])):
        img.save(p)
    cuts = [a] + [k for k in range(a + 1, b) if _closed(es, table[k])] + [b]
    for c0, c1 in zip(cuts, cuts[1:]):
        lead_c = lead if c0 == a else 0
        es = _encode_chunk(es, table, c0, c1, fdir, table[c0]['base'] - first + lead - lead_c, lead_c, tmp)
    return es, n


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
           'last': 1905, 'text': '우리들의가족', 'shot_diff': 25}


def opening_edit(frames, first_index, cfg=OPENING):
    import cv2
    from PIL import ImageFilter
    plate = np.asarray(frames[cfg['plate'] - first_index].convert('L')).astype(float)
    y0, y1 = cfg['rows']
    boxes = [(c - 18, y0 - 6, c + 16, y1 + 9) for c in cfg['centers']]

    def strength(f, box):
        x0, b0, x1, b1 = box
        g = np.asarray(f.convert('L')).astype(float)[b0:b1, x0:x1]
        return max(0.0, np.percentile(g, 98) - np.percentile(plate[b0:b1, x0:x1], 98))
    raw = [[strength(f, b) for b in boxes] for f in frames]
    peak = [max(1.0, max(r[i] for r in raw)) for i in range(len(boxes))]
    n = len(cfg['text'])
    span = (cfg['centers'][0], cfg['centers'][-1])
    xs = [span[0] + (span[1] - span[0]) * j / (n - 1) for j in range(n)]
    f_ = _font(20)
    out, started = [], False
    for f, r in zip(frames, raw):
        # Inside the sky shot, every box is erased from the first trace of the title on (the source letters
        # fade out at different rates, and cloud drift leaves small residues), and the Korean title is drawn
        # with the mean fade. A cut to another shot ends the edit: there every box looks "bright".
        ratios = [v / p for v, p in zip(r, peak)]
        shot = np.abs(np.asarray(f.convert('L')).astype(float) - plate).mean() < cfg['shot_diff']
        started = started or max(ratios) > 0.03
        if not shot or not started:
            out.append(f)
            continue
        a = min(1.0, float(np.mean(ratios)))
        bgr = cv2.cvtColor(np.asarray(f.convert('RGB')), cv2.COLOR_RGB2BGR)
        mask = np.zeros(bgr.shape[:2], np.uint8)
        for x0, b0, x1, b1 in boxes:
            mask[b0:b1, x0:x1] = 255
        clean = Image.fromarray(cv2.cvtColor(cv2.inpaint(bgr, mask, 5, cv2.INPAINT_TELEA), cv2.COLOR_BGR2RGB)).convert('RGBA')
        for ch, x in zip(cfg['text'], xs):
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
