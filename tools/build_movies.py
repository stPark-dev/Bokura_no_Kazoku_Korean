"""D9: Korean titles in the ending movies (title cards) and the opening. Heavy (ffmpeg), so outputs are
cached in work/movie_ko/; the ISO build picks them up.

usage: build_movies.py ORIG_ISO OUT_DIR
"""
import mmap
import os
import sys

import iso9660
import movie_title

ENDINGS = {1: '전신주', 2: '푸른 하늘', 3: '아름다운 자연', 4: '도쿄의 새', 5: '저녁노을', 6: '동물원', 7: '수족관',
           8: '낙엽', 9: '고층 건물', 10: '도쿄의 눈', 11: '야경', 12: '도쿄의 고양이', 13: 'V 사인', 14: '관계자 편',
           15: '봄의 벚꽃'}


def main(iso, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    f = open(iso, 'rb')
    m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    files = {name: (lba, size) for name, lba, size in iso9660.list_files(m)}
    for n, title in ENDINGS.items():
        lba, size = files[f'DATA/MOVIE/ENDING{n}.PSS']
        data = m[lba * 2048:lba * 2048 + size]
        new = movie_title.ending(data, n, title)
        assert len(new) == len(data)
        open(os.path.join(out_dir, f'ENDING{n}.PSS'), 'wb').write(new)
        print('ENDING', n, title)
    lba, size = files['DATA/MOVIE/OPENING.PSS']
    data = m[lba * 2048:lba * 2048 + size]
    open(os.path.join(out_dir, 'OPENING.PSS'), 'wb').write(movie_title.opening(data))
    print('OPENING')


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(__file__))
    main(*sys.argv[1:3])
