"""D13: export the images with Japanese text (every entry of text/gfx_ko.json) for repainting outside the
build. Writes <out>/원본/<ARCHIVE>/<name>.png (original), <out>/현재한글/... (current automatic Korean
version) and <out>/목록.tsv. Repainted PNGs go to work/gfx_import/<ARCHIVE>/<name>.png (same size).

usage: gfx_export.py work/unpacked work/gfx_export
"""
import json
import os
import sys

import build_gfx
import tim2


def _texts(items):
    if isinstance(items, dict):
        return f'(생성기 {items["generator"]})'
    return ', '.join(f'{i["src"]}→{i["text"]}' for i in items if i.get('src'))


def export(read, spec, out_dir):
    korean = build_gfx.build(read, spec=spec)
    rows = []
    for path, items in spec.items():
        orig = read(path)
        name = path[:-4] + '.png'
        for sub, data in (('원본', orig), ('현재한글', korean[path])):
            dest = os.path.join(out_dir, sub, *name.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tim2.decode(data).save(dest)
        _, _, _, clut_cols, _, itype, w, h = tim2._layout(orig)
        rows.append({'path': path, 'size': f'{w}x{h}', 'colours': {4: 16, 5: 256}.get(itype, 'full'),
                     'texts': _texts(items)})
    return rows


GUIDE = """이미지 교체 안내 (D13)

- 원본/      게임 원본 그림 (일본어 글자 포함)
- 현재한글/  지금 빌드가 자동으로 그린 한글판 (참고용)
- 목록.tsv   파일별 크기·색 수·바꿀 글자(원문→번역)

고친 그림은 work/gfx_import/ 아래에 원본/과 같은 경로·같은 이름·같은 크기(픽셀)의 PNG로 넣는다.
  예) work/gfx_export/원본/MENURES.XAP/sysicn06.png → work/gfx_import/MENURES.XAP/sysicn06.png
- 투명 영역(알파)은 그대로 살린다. 크기가 다르면 빌드가 멈춘다.
- 색 수가 16/256인 그림은 빌드가 팔레트를 새로 만든다(색이 많으면 가까운 색으로 줄어듦).
- 여러 아이콘이 한 장에 모인 그림은 다른 칸을 건드리지 않는다.
- gfx_import/에 넣은 그림은 그 파일의 자동 한글 처리(text/gfx_ko.json)보다 우선한다.
- 게임 그림의 2차 저작물이므로 저장소에 커밋하지 않는다(work/는 .gitignore).
"""


def main(root, out_dir):
    spec = json.load(open(build_gfx.SPEC, encoding='utf-8'))
    rows = export(lambda p: open(os.path.join(root, p), 'rb').read(), spec, out_dir)
    with open(os.path.join(out_dir, '목록.tsv'), 'w', encoding='utf-8') as f:
        f.write('경로\t크기\t색수\t글자(원문→번역)\n')
        for r in rows:
            f.write(f'{r["path"]}\t{r["size"]}\t{r["colours"]}\t{r["texts"]}\n')
    open(os.path.join(out_dir, '안내.txt'), 'w', encoding='utf-8').write(GUIDE)
    print(len(rows), 'images ->', out_dir)


if __name__ == '__main__':
    main(*sys.argv[1:3])
