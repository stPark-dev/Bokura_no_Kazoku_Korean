"""Apply translation entries (text/*_ko.jsonl) to extracted files, checking them against the baseline."""
import json

import linetext
import mes


def load_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def apply_event(files, src, ko, encode, body_max=mes.BODY_MAX):
    """files: {name: original .mes bytes}; src: baseline entries; ko: translation entries.
    encode: an encoder, or a list of encoders in order of preference (per block, the first one whose
    output passes mes.check is used; errors are reported for the last one).
    Returns {name: new bytes} for the files that received translations."""
    encoders = encode if isinstance(encode, list) else [encode]
    chosen = {}

    def check(s, text, _enc):
        for e in encoders:
            errs = mes.check(s, text, e, body_max)
            if not errs:
                chosen[(s, text)] = e
                return []
        return errs

    def render(data, texts, name):
        return mes.render(data, {k: (t, chosen[(srcs[name][k], t)]) for k, t in texts.items()}, encoders[-1])
    srcs = {}
    for e in src:
        srcs.setdefault(e['file'], {})[e['label']] = e['src']
    return _apply(files, src, ko, encoders[-1], check, lambda b: b['label'], render)


def apply_sys(files, src, ko, encode):
    """Line units of system text files; files keyed by path relative to work/unpacked.
    encode: an encoder or a preference-ordered list (first passing linetext.check per line)."""
    encoders = encode if isinstance(encode, list) else [encode]
    chosen = {}
    base = {e['id']: e['src'] for e in src}

    def check(s, text, _enc):
        for e in encoders:
            errs = linetext.check(s, text, e)
            if not errs:
                chosen[(s, text)] = e
                return []
        return errs

    def render(data, texts, name):
        current = {r['id']: r['src'] for r in linetext.extract(data, name)}
        bad = [i for i in texts if current.get(i) != base[i]]
        if bad:
            raise ValueError(f'{name}: source mismatch at {bad}')
        out = data
        for i, t in texts.items():
            out = linetext.render(out, {i: t}, name, chosen[(base[i], t)])
        return out
    return _apply(files, src, ko, encoders[-1], check, lambda b: b['id'], render)


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
