"""Merge a batch {id: translation} into a *_ko.jsonl file, binding each entry to the baseline sha1.

usage: ko_merge.py SRC_JSONL KO_JSONL BATCH_JSON [--state S] [--replace]
"""
import argparse
import json

from apply_text import load_jsonl


def merge(src, current, batch, state, replace=False):
    base = {e['id']: e for e in src}
    cur = {e['id']: e for e in current}
    for i, text in batch.items():
        if i not in base:
            raise ValueError(f'unknown id {i}')
        if i in cur and not replace:
            raise ValueError(f'{i} already translated (use replace)')
        cur[i] = {'id': i, 'sha1': base[i]['sha1'], 'ko': text, 'state': state}
    order = {e['id']: n for n, e in enumerate(src)}
    return sorted(cur.values(), key=lambda e: order[e['id']])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('ko')
    ap.add_argument('batch')
    ap.add_argument('--state', default='needs_review')
    ap.add_argument('--replace', action='store_true')
    a = ap.parse_args()
    try:
        current = load_jsonl(a.ko)
    except FileNotFoundError:
        current = []
    with open(a.batch, encoding='utf-8') as f:
        batch = json.load(f)
    out = merge(load_jsonl(a.src), current, batch, a.state, a.replace)
    with open(a.ko, 'w', encoding='utf-8', newline='\n') as f:
        for e in out:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    print(f'{len(batch)} merged, {len(out)} total')


if __name__ == '__main__':
    main()
