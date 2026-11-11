"""Extract line units of system text files (*.txt under work/unpacked) into text/sys_src.jsonl.

usage: extract_sys.py work/unpacked text/sys_src.jsonl
"""
import glob
import hashlib
import json
import os
import sys

import linetext

EXCLUDE = {
    'FONT.XAP/vcode.txt': 'vertical punctuation substitution table, not displayed text (kept per D5)',
    'MENU.XAP/kanji.txt': 'name-entry candidate list, replaced by the jamo grid (D6)',
}


def files(unpacked):
    paths = glob.glob(os.path.join(unpacked, '*', '*.txt')) + glob.glob(os.path.join(unpacked, '*', '*', '*.txt'))
    rel = sorted(os.path.relpath(p, unpacked).replace(os.sep, '/') for p in paths)
    return [r for r in rel if r not in EXCLUDE]


def extract(unpacked):
    out = []
    for rel in files(unpacked):
        with open(os.path.join(unpacked, rel), 'rb') as f:
            data = f.read()
        for r in linetext.extract(data, rel):
            out.append({'id': r['id'], 'file': rel, 'src': r['src'],
                        'sha1': hashlib.sha1(r['src'].encode('cp932')).hexdigest()})
    return out


def main(unpacked, dest):
    with open(dest, 'w', encoding='utf-8', newline='\n') as f:
        for e in extract(unpacked):
            f.write(json.dumps(e, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main(*sys.argv[1:])
