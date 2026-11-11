"""PoC3: PoC2 + EVENT.XAP translations from text/event_ko.jsonl (development policy, not a release build).
Usage: build_poc3.py ORIG_ISO OUT_ISO"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import apply_text  # noqa: E402
import build_poc2  # noqa: E402
import hangul_map  # noqa: E402
import iso9660  # noqa: E402
from xap import read_entries, read_file, rebuild  # noqa: E402

TEXT = os.path.join(os.path.dirname(__file__), '..', 'text')


def main(src, dst):
    build_poc2.main(src, dst)
    orig = open(src, 'rb').read()
    _, lba, size = iso9660.find(orig, 'DATA/EVENT.XAP')
    ev = orig[lba * 2048:lba * 2048 + size]
    files = {e.name: read_file(ev, e) for e in read_entries(ev) if e.name.endswith('.mes')}
    cmap = hangul_map.build()
    new = apply_text.apply_event(files, apply_text.load_jsonl(os.path.join(TEXT, 'event_src.jsonl')),
                                 apply_text.load_jsonl(os.path.join(TEXT, 'event_ko.jsonl')),
                                 lambda s: hangul_map.encode(s, cmap))
    img = bytearray(open(dst, 'rb').read())
    iso9660.replace_all(img, {'DATA/EVENT.XAP': rebuild(ev, files=new)})
    open(dst, 'wb').write(img)
    print('event files translated:', sorted(new))


if __name__ == '__main__':
    main(*sys.argv[1:3])
