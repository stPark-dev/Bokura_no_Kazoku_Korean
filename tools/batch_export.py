"""Export untranslated baseline entries whose file name matches a glob, for a translation batch.

usage: batch_export.py SRC_JSONL KO_JSONL GLOB OUT_JSON
OUT_JSON: [{"id", "head", "src"}] in baseline order (protected fields stay in the baseline file).
"""
import fnmatch
import json
import sys

from apply_text import load_jsonl


def export(src, ko, pattern):
    done = {e['id'] for e in ko}
    return [{'id': e['id'], 'head': e['head'], 'src': e['src']} for e in src
            if fnmatch.fnmatch(e['file'], pattern) and e['id'] not in done]


def main(src_path, ko_path, pattern, out_path):
    try:
        ko = load_jsonl(ko_path)
    except FileNotFoundError:
        ko = []
    rows = export(load_jsonl(src_path), ko, pattern)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=0)
    print(f'{len(rows)} entries')


if __name__ == '__main__':
    main(*sys.argv[1:5])
