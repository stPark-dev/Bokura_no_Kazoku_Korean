"""Distribution package for a beta/release build: xdelta patch + Windows/Linux appliers + guide + notices.

    python3 tools/build_patch.py work/build/beta.iso --policy beta
    python3 tools/package_release.py work/build/beta.iso 0.9.0-beta.1 \\
        --decoder <xdelta3-3.2.2-windows-x86_64/xdelta3decode.exe> --decoder-license <xdelta LICENSE>

writes work/dist/<NAME>/ and work/dist/<NAME>.zip (+ .sha256). No game data goes in: the patch is a
VCDIFF delta from the source ISO, encoded without secondary compression so any xdelta3 decoder reads it.
The patch is decoded again and must reproduce the build's out_sha1 before anything is packaged.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'release'
PATCH_FILE = 'Kazoku-ko.xdelta'
FONT_LICENSE = ROOT.parent / 'fonts' / 'LICENSE'  # SIL OFL 1.1 text
URLS = {}
# file -> (encoding, line ending); .bat stays BOM-less (cmd would print the BOM), .txt gets a BOM for Notepad
TEXT_FILES = {'한글패치_적용.bat': ('utf-8', '\r\n'), 'apply.sh': ('utf-8', '\n'), '읽어주세요.txt': ('utf-8-sig', '\r\n'),
              'DISTRIBUTION_NOTICE.txt': ('utf-8-sig', '\r\n'), 'THIRD_PARTY_NOTICES.txt': ('utf-8-sig', '\r\n')}


def render(text, values):
    out = re.sub(r'\{\{(\w+)\}\}', lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)
    left = re.findall(r'\{\{(\w+)\}\}', out)
    if left: raise ValueError('unfilled placeholders: ' + ', '.join(sorted(set(left))))
    return out


def file_sha(path, algo='sha1'):
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def _delta(src, target, out):
    subprocess.run(['xdelta3', '-e', '-9', '-S', 'none', '-f', '-s', src, target, str(out)], check=True)
    with tempfile.TemporaryDirectory() as d:
        check = os.path.join(d, 'check.iso')
        subprocess.run(['xdelta3', '-d', '-f', '-s', src, str(out), check], check=True)
        return file_sha(check)


def make_package(pkg, src_iso, built_iso, manifest, version, decoder, licenses, urls=URLS):
    pkg = Path(pkg)
    if manifest.get('policy') not in ('beta', 'release'):
        raise SystemExit('only beta/release builds are packaged (manifest policy: %s)' % manifest.get('policy'))
    if file_sha(src_iso) != manifest['source_sha1']: raise SystemExit('source ISO does not match manifest source_sha1')
    if file_sha(built_iso) != manifest['out_sha1']: raise SystemExit('built ISO does not match manifest out_sha1')
    if pkg.exists(): shutil.rmtree(pkg)
    (pkg / 'patch').mkdir(parents=True); (pkg / 'tools').mkdir(); (pkg / 'licenses').mkdir()
    if _delta(src_iso, built_iso, pkg / 'patch' / PATCH_FILE) != manifest['out_sha1']:
        raise SystemExit('decoded patch does not reproduce out_sha1')
    values = dict(urls, VERSION=version, SRC_SHA1=manifest['source_sha1'], OUT_SHA1=manifest['out_sha1'],
                  PATCH_FILE=PATCH_FILE, OUT_NAME='BokuraNoKazoku_KR_v%s.iso' % version)
    for name, (enc, eol) in TEXT_FILES.items():
        text = render((TEMPLATES / name).read_text('utf-8'), values).replace('\n', eol)
        (pkg / name).write_bytes(text.encode(enc))
    (pkg / 'apply.sh').chmod(0o755)
    (pkg / 'VERSION.txt').write_text('%s\nsource_commit=%s\n' % (version, manifest.get('commit', '')), 'utf-8')
    shutil.copy(decoder, pkg / 'tools' / 'xdelta3decode.exe')
    for name, path in licenses.items(): shutil.copy(path, pkg / 'licenses' / name)
    files = sorted(p for p in pkg.rglob('*') if p.is_file())
    (pkg / 'CHECKSUMS.sha256').write_text(
        ''.join('%s  %s\n' % (file_sha(p, 'sha256'), p.relative_to(pkg).as_posix()) for p in files), 'utf-8')
    return pkg


def zip_package(pkg, archive):
    pkg, archive = Path(pkg), Path(archive)
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(pkg.rglob('*')):
            if not p.is_file(): continue
            info = zipfile.ZipInfo.from_file(p, '%s/%s' % (pkg.name, p.relative_to(pkg).as_posix()))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, p.read_bytes())
    return archive


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('built'); ap.add_argument('version')
    ap.add_argument('--source', default=str(ROOT / 'work' / 'orig.iso'))
    ap.add_argument('--decoder', required=True); ap.add_argument('--decoder-license', required=True)
    ap.add_argument('--out-dir', default=str(ROOT / 'work' / 'dist'))
    a = ap.parse_args(argv)
    manifest = json.load(open(a.built + '.manifest.json', encoding='utf-8'))
    name = 'BokuraNoKazoku-Korean-Patch-v' + a.version
    pkg = make_package(Path(a.out_dir) / name, a.source, a.built, manifest, a.version, a.decoder,
                       {'xdelta3-Apache-2.0.txt': a.decoder_license, 'Noto-CJK-OFL-1.1.txt': str(FONT_LICENSE)})
    archive = zip_package(pkg, Path(a.out_dir) / (name + '.zip'))
    digest = file_sha(archive, 'sha256')
    Path(str(archive) + '.sha256').write_text('%s  %s\n' % (digest, archive.name), 'utf-8')
    print('%s (%d bytes)\nsha256 %s' % (archive, archive.stat().st_size, digest))


if __name__ == '__main__':
    main()
