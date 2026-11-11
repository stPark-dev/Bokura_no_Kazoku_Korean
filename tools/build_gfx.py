"""Apply text/gfx_ko.json to original tm2 files. Returns {archive_path: new_tm2_bytes}; optional preview PNGs.

usage: build_gfx.py work/unpacked PREVIEW_DIR
"""
import json
import os
import sys

from PIL import Image

import gfx
import tim2

SPEC = os.path.join(os.path.dirname(__file__), '..', 'text', 'gfx_ko.json')


def build(read, spec=None, preview=None):
    """read(path) -> original tm2 bytes for 'ARCHIVE/file.tm2'."""
    spec = spec or json.load(open(SPEC, encoding='utf-8'))
    out = {}
    for path, items in spec.items():
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
