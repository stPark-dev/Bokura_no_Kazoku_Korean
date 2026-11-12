"""Apply text/gfx_ko.json to original tm2 files. Returns {archive_path: new_tm2_bytes}; optional preview PNGs.

usage: build_gfx.py work/unpacked PREVIEW_DIR
"""
import hashlib
import json
import os
import sys

from PIL import Image

import gfx
import tim2
import title_logo

GENERATORS = {'title_logo': title_logo.make}

SPEC = os.path.join(os.path.dirname(__file__), '..', 'text', 'gfx_ko.json')


IMPORTS = os.path.join(os.path.dirname(__file__), '..', 'work', 'gfx_import')


def imported(imports):
    """{'ARCHIVE/file.tm2': png path} for repainted images under `imports` (D13; kept out of the repository)."""
    out = {}
    for d, _, names in os.walk(imports):
        for n in names:
            if n.lower().endswith('.png'):
                rel = os.path.relpath(os.path.join(d, n), imports).replace(os.sep, '/')
                out[rel[:-4] + '.tm2'] = os.path.join(d, n)
    return out


def build(read, spec=None, preview=None, imports=None, used=None):
    """read(path) -> original tm2 bytes for 'ARCHIVE/file.tm2'. A PNG in `imports` replaces the whole image
    (new palette) and supersedes its spec entry; `used` collects {path: PNG sha1}."""
    spec = json.load(open(SPEC, encoding='utf-8')) if spec is None else spec
    pngs = imported(imports) if imports and os.path.isdir(imports) else {}
    out = {}
    for path, png in sorted(pngs.items()):
        data = open(png, 'rb').read()
        out[path] = tim2.encode_palette(read(path), Image.open(png))
        if used is not None:
            used[path] = hashlib.sha1(data).hexdigest()
    for path, items in spec.items():
        if path in pngs:
            continue
        if isinstance(items, dict):          # {"generator": name}: whole-image generator
            fn = GENERATORS[items['generator']]
            orig = read(path)
            img = fn(tim2.decode(orig))
        else:
            orig = read(path)
            img = gfx.render(tim2.decode(orig), items)
        out[path] = tim2.encode(orig, img)
        if preview:
            back = tim2.decode(out[path])
            bg = Image.new('RGBA', back.size, (255, 0, 255, 255))
            bg.alpha_composite(back)
            os.makedirs(preview, exist_ok=True)
            bg.resize((back.width * 3, back.height * 3), Image.NEAREST).save(
                os.path.join(preview, path.replace('/', '_') + '.png'))
    return out


if __name__ == '__main__':
    root = sys.argv[1]
    res = build(lambda p: open(os.path.join(root, p), 'rb').read(), preview=sys.argv[2])
    print(len(res), 'images')
