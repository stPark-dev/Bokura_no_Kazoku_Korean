"""PoC3: PoC2 + EVENT.XAP translations from text/event_ko.jsonl (development policy, not a release build).
Usage: build_poc3.py ORIG_ISO OUT_ISO"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import apply_text  # noqa: E402
import build_poc2  # noqa: E402
import hangul_map  # noqa: E402
import iso9660  # noqa: E402
import mes  # noqa: E402
from xap import read_entries, read_file, rebuild  # noqa: E402

TEXT = os.path.join(os.path.dirname(__file__), '..', 'text')


def main(src, dst):
    build_poc2.main(src, dst)
    orig = open(src, 'rb').read()
    _, lba, size = iso9660.find(orig, 'DATA/EVENT.XAP')
    ev = orig[lba * 2048:lba * 2048 + size]
    files = {e.name: read_file(ev, e) for e in read_entries(ev) if e.name.endswith('.mes')}
    cmap = hangul_map.build()

    def plain(t):
        return hangul_map.encode(t, cmap)
    new = apply_text.apply_event(files, apply_text.load_jsonl(os.path.join(TEXT, 'event_src.jsonl')),
                                 apply_text.load_jsonl(os.path.join(TEXT, 'event_ko.jsonl')),
                                 [mes.vertical_encoder(plain), plain])
    img = bytearray(open(dst, 'rb').read())
    replaced = {'DATA/EVENT.XAP': rebuild(ev, files=new)}
    print('event files translated:', len(new))

    _, glba, gsize = iso9660.find(orig, 'DATA/GAMEMES.XAP')
    gx = orig[glba * 2048:glba * 2048 + gsize]
    gfiles = {e.name: read_file(gx, e) for e in read_entries(gx)}
    gnew = apply_text.apply_event(gfiles, apply_text.load_jsonl(os.path.join(TEXT, 'gamemes_src.jsonl')),
                                  apply_text.load_jsonl(os.path.join(TEXT, 'gamemes_ko.jsonl')),
                                  lambda s: hangul_map.encode(s, cmap))
    replaced['DATA/GAMEMES.XAP'] = rebuild(gx, files=gnew)
    print('gamemes translated:', sorted(gnew))

    # system text: line units, applied to the archive as it is in the image built so far
    sys_src = apply_text.load_jsonl(os.path.join(TEXT, 'sys_src.jsonl'))
    sys_ko = apply_text.load_jsonl(os.path.join(TEXT, 'sys_ko.jsonl'))
    archives = sorted({k['id'].rsplit(':', 1)[0].rsplit('/', 1)[0] for k in sys_ko})  # e.g. MINIG/MINIG5.XAP
    for arc in archives:
        _, lba, size = iso9660.find(img, 'DATA/' + arc)
        x = bytes(img[lba * 2048:lba * 2048 + size])
        _, olba, osize = iso9660.find(orig, 'DATA/' + arc)
        ox = orig[olba * 2048:olba * 2048 + osize]
        # a file with system-text translations is rebuilt from its original bytes (supersedes PoC1 edits)
        files = {f'{arc}/{e.name}': read_file(ox, e) for e in read_entries(ox)}
        ko = [k for k in sys_ko if k['id'].startswith(arc + '/')]
        out = apply_text.apply_sys(files, sys_src, ko, lambda s: hangul_map.encode(s, cmap))
        replaced['DATA/' + arc] = rebuild(x, files={n.rsplit('/', 1)[1]: b for n, b in out.items()})
        print('system text translated:', sorted(out))
    iso9660.replace_all(img, replaced)
    open(dst, 'wb').write(img)


if __name__ == '__main__':
    main(*sys.argv[1:3])
