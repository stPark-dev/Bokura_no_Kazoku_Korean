"""Apply review results to a *_ko.jsonl: fixes propagate to every entry with the same source text and the same
previous wording; reviewed entries (and those duplicates) become state 'reviewed'.

usage: review_merge.py SRC_JSONL KO_JSONL REVIEW_IN_JSON REVIEW_OUT_JSON
  REVIEW_IN_JSON: the list given to the reviewer (ids reviewed); REVIEW_OUT_JSON: {"fixes": {id: ko}, ...}
"""
import json
import os
import sys

import hangul_map
import linetext
import mes
from apply_text import load_jsonl


def apply(src, current, fixes, reviewed, check=None):
    text_of = {e['id']: e['src'] for e in src}
    cur = {e['id']: dict(e) for e in current}
    for i in list(fixes) + list(reviewed):
        if i not in cur:
            raise ValueError(f'unknown id {i}')
    if check:
        errs = [f'{i}: {e}' for i, k in fixes.items() for e in check(text_of[i], k)]
        if errs:
            raise ValueError('\n'.join(errs))
    groups = {}
    for e in cur.values():
        groups.setdefault((text_of[e['id']], e['ko']), []).append(e['id'])
    for i in reviewed:
        for j in groups[(text_of[i], cur[i]['ko'])]:
            cur[j]['state'] = 'reviewed'
    for i, k in fixes.items():
        old = (text_of[i], [e for e in current if e['id'] == i][0]['ko'])
        for j in groups[old]:
            cur[j]['ko'] = k
            cur[j]['state'] = 'reviewed'
    return [cur[e['id']] for e in current]


def main(src_path, ko_path, rin, rout):
    src = load_jsonl(src_path)
    reviewed = [r['id'] for r in json.load(open(rin, encoding='utf-8')) if r['id'] in {e['id'] for e in src}]
    fixes = {i: k for i, k in json.load(open(rout, encoding='utf-8'))['fixes'].items() if i in {e['id'] for e in src}}
    cmap = hangul_map.build()
    checker = linetext.check if os.path.basename(src_path).startswith('sys') else mes.check
    out = apply(src, load_jsonl(ko_path), fixes, reviewed,
                check=lambda s, k: checker(s, k, lambda t: hangul_map.encode(t, cmap)))
    with open(ko_path, 'w', encoding='utf-8', newline='\n') as f:
        for e in out:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    print(f'{len(fixes)} fixes, {sum(e["state"] == "reviewed" for e in out)}/{len(out)} reviewed')


if __name__ == '__main__':
    main(*sys.argv[1:5])
