"""PoC1: Korean font + a few Korean lines (title menu, first event). Usage: build_poc1.py ORIG_ISO OUT_ISO"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import font20  # noqa: E402
import hangul_map  # noqa: E402
import iso9660  # noqa: E402
from xap import read_entries, read_file, rebuild  # noqa: E402

MENU = {
    '000': '@s22새@s1　@s22게@s1　@s22임',
    '001': '@s22이@s14　@s22어@s14　@s22하@s14　@s22기',
    '002': '@s22가@s5　@s22족@s5　@s22의@s5　@s22기@s5　@s22록',
    '003': '@s22설@d20정',
}
EVENT = {
    '「ねえ私たち@n': '「있잖아, 우리@n',
    '　出会ってから何年経つのかな？」@n': '　만난 지 몇 년이나 됐을까?」@n',
    '「え？　…最初は幼稚園だろ、で…　」@n': '「응?　…처음엔 유치원이었지, 그리고…　」@n',
}


def patch_lines(text, table):
    out = []
    for line in text.split('\r\n'):
        body = line.lstrip('\t')
        if body in table:
            line = line[:len(line) - len(body)] + table[body]
        out.append(line)
    return '\r\n'.join(out)


def patch_menu(text):
    out = []
    for line in text.split('\r\n'):
        key = line.split('\t', 1)[0]
        if key in MENU and '\t' in line:
            line = key + '\t' + MENU[key]
        out.append(line)
    return '\r\n'.join(out)


def get(xap_bytes, name):
    e = next(e for e in read_entries(xap_bytes) if e.name == name)
    return read_file(xap_bytes, e)


def main(src, dst):
    img = bytearray(open(src, 'rb').read())
    cmap = hangul_map.build()

    def rd(path):
        _, lba, size = iso9660.find(img, path)
        return bytes(img[lba * 2048:lba * 2048 + size])

    font_xap = rd('DATA/FONT.XAP')
    f = font20.Font.parse(get(font_xap, 'font20.moj'), get(font_xap, 'font20.xim'))
    moj, xim = font20.build_korean(f, cmap, font20.default_ttf()).serialize()
    new_font = rebuild(font_xap, files={'font20.moj': moj, 'font20.xim': xim})

    mr = rd('DATA/MENURES.XAP')
    menumes = patch_menu(get(mr, 'menumes.txt').decode('cp932'))
    new_mr = rebuild(mr, files={'menumes.txt': hangul_map.encode(menumes, cmap, allow_kanji=True)})

    ev = rd('DATA/EVENT.XAP')
    mes = patch_lines(get(ev, '000h0a.mes').decode('cp932'), EVENT)
    new_ev = rebuild(ev, files={'000h0a.mes': hangul_map.encode(mes, cmap, allow_kanji=True)})

    iso9660.replace_all(img, {'DATA/FONT.XAP': new_font, 'DATA/MENURES.XAP': new_mr, 'DATA/EVENT.XAP': new_ev})
    open(dst, 'wb').write(img)
    print('font', len(font_xap), '->', len(new_font), '| menures', len(mr), '->', len(new_mr),
          '| event', len(ev), '->', len(new_ev))


if __name__ == '__main__':
    main(*sys.argv[1:3])
