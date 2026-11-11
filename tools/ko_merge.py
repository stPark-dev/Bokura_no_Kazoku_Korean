"""Merge a batch {id: translation} into a *_ko.jsonl file, binding each entry to the baseline sha1.

usage: ko_merge.py SRC_JSONL KO_JSONL BATCH_JSON [--state S] [--replace]
       ko_merge.py SRC_JSONL KO_JSONL --reuse   (fill entries whose source equals a translated one)
"""
import argparse
import json

import hangul_map
import mes
from apply_text import load_jsonl


def merge(src, current, batch, state, replace=False, check=None):
    base = {e['id']: e for e in src}
    cur = {e['id']: e for e in current}
    if check:
        errs = [f'{i}: {e}' for i, text in batch.items() if i in base for e in check(base[i]['src'], text)]
        if errs:
            raise ValueError('\n'.join(errs))
    for i, text in batch.items():
        if i not in base:
            raise ValueError(f'unknown id {i}')
        if i in cur and not replace:
            raise ValueError(f'{i} already translated (use replace)')
        cur[i] = {'id': i, 'sha1': base[i]['sha1'], 'ko': text, 'state': state}
    order = {e['id']: n for n, e in enumerate(src)}
    return sorted(cur.values(), key=lambda e: order[e['id']])


def reuse(src, current):
    """{id: ko} for untranslated entries whose source text equals a translated one (single wording only)."""
    text_of = {e['id']: e['src'] for e in src}
    by_src = {}
    for k in current:
        by_src.setdefault(text_of[k['id']], set()).add(k['ko'])
    done = {k['id'] for k in current}
    return {e['id']: next(iter(by_src[e['src']])) for e in src
            if e['id'] not in done and len(by_src.get(e['src'], ())) == 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('ko')
    ap.add_argument('batch', nargs='?')
    ap.add_argument('--reuse', action='store_true')
    ap.add_argument('--state', default='needs_review')
    ap.add_argument('--replace', action='store_true')
    a = ap.parse_args()
    try:
        current = load_jsonl(a.ko)
    except FileNotFoundError:
        current = []
    if a.reuse:
        batch = reuse(load_jsonl(a.src), current)
    else:
        with open(a.batch, encoding='utf-8') as f:
            batch = json.load(f)
    cmap = hangul_map.build()
    out = merge(load_jsonl(a.src), current, batch, a.state, a.replace,
                check=lambda s, k: mes.check(s, k, lambda t: hangul_map.encode(t, cmap)))
    with open(a.ko, 'w', encoding='utf-8', newline='\n') as f:
        for e in out:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    print(f'{len(batch)} merged, {len(out)} total')


if __name__ == '__main__':
    main()
