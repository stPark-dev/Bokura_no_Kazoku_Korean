"""Product build: original ISO -> Korean ISO + manifest, in one pass.

usage: build_patch.py ORIG_ISO OUT_ISO [--policy dev|beta|release]
  dev     : any translation state (development / PoC policy; never distributed)
  beta    : every unit translated and at least 'reviewed' (pre-release review candidate)
  release : every unit 'distribution_eligible'
Movies come from work/movie_ko (tools/build_movies.py) and are checked against its manifest.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import apply_text  # noqa: E402
import build_gfx  # noqa: E402
import build_poc2  # noqa: E402
import elfpatch  # noqa: E402
import font20  # noqa: E402
import hangul_map  # noqa: E402
import iso9660  # noqa: E402
import mes  # noqa: E402
from xap import read_entries, read_file, rebuild  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), '..')
TEXT = os.path.join(ROOT, 'text')
SOURCE_SHA1 = 'f2a8187457148a66fbbb3841032fe430cb5572d4'   # SCPS-15088 (docs/survey.md)
OK_STATES = {'dev': None, 'beta': {'reviewed', 'distribution_eligible'}, 'release': {'distribution_eligible'}}
EXCEPTIONS = [
    {'what': 'staff credits in OPENING.PSS / ENDING1-15.PSS (only the titles are Korean)', 'basis': 'D9'},
    {'what': 'shop signs and other scenery text in MENU.XAP/inf*.tm2 (64 photos)', 'basis': 'D10'},
    {'what': 'small author/publisher print on book covers', 'basis': 'docs/graphics_text.md G4'},
    {'what': 'FONT.XAP/vcode.txt, MENU.XAP/kanji.txt, GAMEDB.XAP/readme.txt (not displayed text)',
     'basis': 'tools/extract_sys.py EXCLUDE'},
    {'what': 'memory-card save name ぼくらのかぞく shown by the PS2 browser (BIOS has no Hangul)',
     'basis': 'docs/survey.md'},
]
TEXT_SETS = [('event', 'EVENT'), ('gamemes', 'GAMEMES'), ('sys', 'SYS')]


def text_problems(src, ko, policy):
    ok = OK_STATES[policy]
    if ok is None:
        return []
    have = {k['id']: k for k in ko}
    out = [f'untranslated {e["id"]}' for e in src if e['id'] not in have]
    out += [f'state {k["state"]} {k["id"]}' for k in ko if k['state'] not in ok]
    return out


# Strings passed to formats by the executable (same byte length). 0x2DD758: season argument of the album
# caption '%s年目の%s%s' (window.txt [album], code 0x1960A4); its cp932 bytes are a Hangul code in our font.
ELF_STRINGS = [(0x2DD758, '春', '봄')]


def patch_elf_strings(elf, table, encode, off=elfpatch._off):
    out = bytearray(elf)
    for va, orig, new in table:
        o, a, b = off(out, va), orig.encode('cp932'), encode(new)
        if bytes(out[o:o + len(a) + 1]) != a + b'\0':
            raise ValueError(f'{va:#x}: original {orig!r} not found')
        if len(b) != len(a):
            raise ValueError(f'{va:#x}: length {len(b)} != {len(a)}')
        out[o:o + len(b)] = b
    return bytes(out)


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def build(orig, policy):
    problems = []
    if sha1(orig) != SOURCE_SHA1:
        problems.append('source ISO is not SCPS-15088 ' + SOURCE_SHA1)
    loaded = {}
    for name, _ in TEXT_SETS:
        src = apply_text.load_jsonl(os.path.join(TEXT, f'{name}_src.jsonl'))
        ko = apply_text.load_jsonl(os.path.join(TEXT, f'{name}_ko.jsonl'))
        loaded[name] = (src, ko)
        problems += text_problems(src, ko, policy)
    movies = os.path.join(ROOT, 'work', 'movie_ko')
    mman = os.path.join(movies, 'manifest.json')
    if policy != 'dev':
        if not os.path.exists(mman):
            problems.append('work/movie_ko/manifest.json missing (run tools/build_movies.py)')
        elif json.load(open(mman))['source_sha1'] != SOURCE_SHA1:
            problems.append('movies were built from another source ISO')
    if problems:
        raise SystemExit('policy %s failed:\n  ' % policy + '\n  '.join(problems[:40]) +
                         (f'\n  ... {len(problems)} problems' if len(problems) > 40 else ''))

    cmap = hangul_map.build()

    def plain(t):
        return hangul_map.encode(t, cmap)

    def archive(path):
        _, lba, size = iso9660.find(orig, path)
        return orig[lba * 2048:lba * 2048 + size]

    def file_of(x, name):
        return read_file(x, next(e for e in read_entries(x) if e.name == name))
    files = {}                                   # 'ARCHIVE/name' -> bytes, applied per archive at the end

    # font: KS X 1001 Hangul in the kanji code range
    fx = archive('DATA/FONT.XAP')
    f = font20.Font.parse(file_of(fx, 'font20.moj'), file_of(fx, 'font20.xim'))
    moj, xim = font20.build_korean(f, cmap, font20.default_ttf()).serialize()
    files['FONT.XAP/font20.moj'], files['FONT.XAP/font20.xim'] = moj, xim

    # executable: name entry (jamo composition), particle hook, kana index labels
    elf, _ = elfpatch.name_entry_patch(archive('SCPS_150.88'))
    elf = bytearray(elf)
    off = elfpatch._off(elf, build_poc2.KANA_LABELS_VA)
    expect = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもや  ゆ  よらりるれろわ        '
    assert bytes(elf[off:off + build_poc2.KANA_LABELS_LEN]) == expect.encode('cp932')[:build_poc2.KANA_LABELS_LEN]
    elf[off:off + build_poc2.KANA_LABELS_LEN] = build_poc2.labels(cmap)
    replaced = {'SCPS_150.88': patch_elf_strings(elf, ELF_STRINGS, plain)}
    files['MENU.XAP/kanji.txt'] = hangul_map.encode(
        build_poc2.kanji_txt(file_of(archive('DATA/MENU.XAP'), 'kanji.txt').decode('cp932')), cmap)

    # dialogue and system messages
    ev = archive('DATA/EVENT.XAP')
    src, ko = loaded['event']
    new = apply_text.apply_event({e.name: read_file(ev, e) for e in read_entries(ev) if e.name.endswith('.mes')},
                                 src, ko, [mes.vertical_encoder(plain), plain])
    files.update({f'EVENT.XAP/{n}': b for n, b in new.items()})
    gx = archive('DATA/GAMEMES.XAP')
    src, ko = loaded['gamemes']
    new = apply_text.apply_event({e.name: read_file(gx, e) for e in read_entries(gx)}, src, ko, plain)
    files.update({f'GAMEMES.XAP/{n}': b for n, b in new.items()})

    # system text (line units) and graphics
    src, ko = loaded['sys']
    arcs = {k['id'].rsplit(':', 1)[0].rsplit('/', 1)[0] for k in ko}
    for arc in sorted(arcs):
        x = archive('DATA/' + arc)
        out = apply_text.apply_sys({f'{arc}/{e.name}': read_file(x, e) for e in read_entries(x)}, src,
                                   [k for k in ko if k['id'].startswith(arc + '/')],
                                   plain)   # spaces: half-cell advance hook in the ELF (elfpatch SPACE_SITE)
        files.update(out)
    gfx_used = {}                     # D13: repainted PNGs in work/gfx_import (not in the repository)
    files.update(build_gfx.build(lambda p: file_of(archive('DATA/' + p.rsplit('/', 1)[0]), p.rsplit('/', 1)[1]),
                                 imports=build_gfx.IMPORTS, used=gfx_used))

    by_arc = {}
    for path, data in files.items():
        arc, name = path.rsplit('/', 1)
        by_arc.setdefault(arc, {})[name] = data
    for arc, fs in by_arc.items():
        replaced['DATA/' + arc] = rebuild(archive('DATA/' + arc), files=fs)
    if os.path.isdir(movies):
        man = json.load(open(mman)) if os.path.exists(mman) else {'files': {}}
        for name, digest in man['files'].items():
            data = open(os.path.join(movies, name), 'rb').read()
            if sha1(data) != digest:
                raise SystemExit(f'work/movie_ko/{name} does not match its manifest')
            replaced['DATA/MOVIE/' + name] = data
    img = bytearray(orig)
    iso9660.replace_all(img, replaced)
    out = bytes(img)
    try:
        commit = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ''
    manifest = {'policy': policy, 'source_sha1': SOURCE_SHA1, 'out_sha1': sha1(out), 'commit': commit,
                'replaced': sorted(replaced), 'exceptions': EXCEPTIONS,
                'units': {n: len(loaded[n][1]) for n, _ in TEXT_SETS}, 'gfx_import': gfx_used}
    return out, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--policy', default='dev', choices=sorted(OK_STATES))
    a = ap.parse_args()
    out, manifest = build(open(a.src, 'rb').read(), a.policy)
    open(a.dst, 'wb').write(out)
    json.dump(manifest, open(a.dst + '.manifest.json', 'w'), ensure_ascii=False, indent=1)
    print(a.policy, manifest['out_sha1'], len(manifest['replaced']), 'files replaced')


if __name__ == '__main__':
    main()
