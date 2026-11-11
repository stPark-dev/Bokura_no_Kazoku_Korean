"""Extract EVENT.XAP/*.mes blocks into the translation baseline text/event_src.jsonl.

usage: extract_event.py work/unpacked text/event_src.jsonl [ARCHIVE PREFIX]   (e.g. GAMEMES.XAP GAMEMES)
"""
import glob
import hashlib
import json
import os
import sys

import mes


def extract(unpacked, archive='EVENT.XAP', prefix='EVENT'):
    out = []
    for path in sorted(glob.glob(os.path.join(unpacked, archive, '*.mes'))):
        name = os.path.basename(path)
        for b in mes.parse(open(path, 'rb').read()):
            out.append({
                'id': f'{prefix}/{name}/{b.label}',
                'file': name,
                'label': b.label,
                'head': b.head,
                'src': b.src,
                'segments': b.segments,
                'sha1': hashlib.sha1(b.src.encode('cp932')).hexdigest(),
            })
    return out


def main(unpacked, dest, archive='EVENT.XAP', prefix='EVENT'):
    with open(dest, 'w', encoding='utf-8', newline='\n') as f:
        for e in extract(unpacked, archive, prefix):
            f.write(json.dumps(e, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:])
