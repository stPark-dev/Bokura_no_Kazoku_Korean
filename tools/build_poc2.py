"""PoC2: PoC1 + Hangul jamo composition in name entry. Usage: build_poc2.py ORIG_ISO OUT_ISO"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_poc1  # noqa: E402
import elfpatch  # noqa: E402
import hangul_map  # noqa: E402
import iso9660  # noqa: E402
from xap import rebuild  # noqa: E402

KANA_LABELS_VA = 0x2DEEB8
KANA_LABELS_LEN = 100  # 50 cells x 2 bytes
JAMO_GRID = ('ㄱㄲㄴㄷㄸㄹ\r\nㅁㅂㅃㅅㅆㅇ\r\nㅈㅉㅊㅋㅌㅍ\r\nㅎ　　　　　\r\n'
             'ㅏㅐㅑㅒㅓㅔ\r\nㅕㅖㅗㅘㅙㅚ\r\nㅛㅜㅝㅞㅟㅠ\r\nㅡㅢㅣ\r\n')


def kanji_txt(orig_text):
    """Section [a] -> jamo grid; other kana sections emptied; [eisu]/[kigou] kept."""
    out = ['[a]\r\n' + JAMO_GRID]
    for part in orig_text.split('\r\n['):
        key = part.split(']', 1)[0].lstrip('[')
        if key in ('eisu', 'kigou'):
            out.append('[' + part.lstrip('[').rstrip('\r\n') + '\r\n')
    return '\r\n'.join(out)


def labels(cmap):
    b = hangul_map.encode('한', cmap) + b'  ' * 49
    assert len(b) == KANA_LABELS_LEN
    return b


def main(src, dst):
    build_poc1.main(src, dst)
    img = bytearray(open(dst, 'rb').read())
    cmap = hangul_map.build()

    def rd(path):
        _, lba, size = iso9660.find(img, path)
        return bytes(img[lba * 2048:lba * 2048 + size])

    elf, info = elfpatch.name_entry_patch(rd('SCPS_150.88'))
    elf = bytearray(elf)
    off = elfpatch._off(elf, KANA_LABELS_VA)
    expect = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもや  ゆ  よらりるれろわ        '.encode('cp932')
    assert bytes(elf[off:off + KANA_LABELS_LEN]) == expect[:KANA_LABELS_LEN], 'kana label table mismatch'
    elf[off:off + KANA_LABELS_LEN] = labels(cmap)

    menu = rd('DATA/MENU.XAP')
    k = build_poc1.get(menu, 'kanji.txt').decode('cp932')
    new_menu = rebuild(menu, files={'kanji.txt': hangul_map.encode(kanji_txt(k), cmap)})

    iso9660.replace_all(img, {'SCPS_150.88': bytes(elf), 'DATA/MENU.XAP': new_menu})
    open(dst, 'wb').write(img)
    print('hook segment', {k: hex(v) for k, v in info.items()})


if __name__ == '__main__':
    main(*sys.argv[1:3])
