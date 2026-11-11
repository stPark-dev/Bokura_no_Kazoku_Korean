"""Apply translation entries (text/*_ko.jsonl) to extracted files, checking them against the baseline."""
import json

import linetext
import mes


def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def apply_event(files, src, ko, encode):
    """files: {name: original .mes bytes}; src: baseline entries; ko: translation entries.
    Returns {name: new bytes} for the files that received translations."""
    return _apply(files, src, ko, encode, mes.check,
                  lambda b: b['label'], lambda data, texts, name: mes.render(data, texts, encode))


def apply_sys(files, src, ko, encode):
    """Line units of system text files; files keyed by path relative to work/unpacked."""
    def render(data, texts, name):
        current = {r['id']: r['src'] for r in linetext.extract(data, name)}
        base = {e['id']: e['src'] for e in src}
        bad = [i for i in texts if current.get(i) != base[i]]
        if bad:
            raise ValueError(f'{name}: source mismatch at {bad}')
        return linetext.render(data, texts, name, encode)
    return _apply(files, src, ko, encode, linetext.check, lambda b: b['id'], render)


def _apply(files, src, ko, encode, check, key, render):
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
        errors += [f'{i}: {e}' for e in check(b['src'], k['ko'], encode)]
        per_file.setdefault(b['file'], {})[key(b)] = k['ko']
    if errors:
        raise ValueError('\n'.join(errors))
    return {name: render(files[name], texts, name) for name, texts in per_file.items()}
