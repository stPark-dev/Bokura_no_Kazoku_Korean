"""Apply translation entries (text/*_ko.jsonl) to extracted files, checking them against the baseline."""
import json

import mes


def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def apply_event(files, src, ko, encode):
    """files: {name: original .mes bytes}; src: baseline entries; ko: translation entries.
    Returns {name: new bytes} for the files that received translations."""
    base = {e['id']: e for e in src}
    seen, per_file, errors = set(), {}, []
    for k in ko:
        i = k['id']
        if i not in base:
            raise ValueError(f'unknown id {i}')
        if i in seen:
            raise ValueError(f'duplicate id {i}')
        seen.add(i)
        b = base[i]
        if k['sha1'] != b['sha1']:
            raise ValueError(f'{i}: translated against another baseline ({k["sha1"]} != {b["sha1"]})')
        errors += [f'{i}: {e}' for e in mes.check(b['src'], k['ko'], encode)]
        per_file.setdefault(b['file'], {})[b['label']] = k['ko']
    if errors:
        raise ValueError('\n'.join(errors))
    return {name: mes.render(files[name], texts, encode) for name, texts in per_file.items()}
