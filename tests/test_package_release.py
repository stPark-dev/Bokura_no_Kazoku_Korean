import hashlib
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import package_release  # noqa: E402

pytestmark = pytest.mark.skipif(not shutil.which('xdelta3'), reason='xdelta3 missing')


def _files(tmp_path):
    src = tmp_path / 'src.iso'
    out = tmp_path / 'out.iso'
    src.write_bytes(bytes(range(256)) * 64)
    out.write_bytes(bytes(range(256)) * 60 + b'Korean' * 100)
    dec = tmp_path / 'xdelta3decode.exe'
    dec.write_bytes(b'MZ')
    lic = tmp_path / 'LICENSE'
    lic.write_text('license')
    return src, out, dec, lic


def test_package_contains_patch_scripts_and_notices(tmp_path):
    src, out, dec, lic = _files(tmp_path)
    man = {'policy': 'beta', 'source_sha1': hashlib.sha1(src.read_bytes()).hexdigest(),
           'out_sha1': hashlib.sha1(out.read_bytes()).hexdigest(), 'commit': 'abc'}
    pkg = package_release.make_package(tmp_path / 'pkg', src, out, man, '0.9.0-beta.1', dec,
                                       {'xdelta3-Apache-2.0.txt': lic, 'Noto-CJK-OFL-1.1.txt': lic})
    names = {p.relative_to(pkg).as_posix() for p in pkg.rglob('*') if p.is_file()}
    assert {'patch/Kazoku-ko.xdelta', 'apply.sh', '한글패치_적용.bat', '읽어주세요.txt', 'CHECKSUMS.sha256',
            'DISTRIBUTION_NOTICE.txt', 'THIRD_PARTY_NOTICES.txt', 'tools/xdelta3decode.exe'} <= names
    readme = (pkg / '읽어주세요.txt').read_text('utf-8-sig')
    assert '{{' not in readme and man['out_sha1'] in readme


def test_dev_build_is_not_packaged(tmp_path):
    src, out, dec, lic = _files(tmp_path)
    man = {'policy': 'dev', 'source_sha1': '', 'out_sha1': ''}
    with pytest.raises(SystemExit):
        package_release.make_package(tmp_path / 'pkg', src, out, man, '0', dec, {})
