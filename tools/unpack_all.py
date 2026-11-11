"""Unpack every XAP under an ISO extraction dir; verify sizes. Usage: unpack_all.py SRC_DATA_DIR OUT_DIR"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from xap import read_entries, read_file

src, out = sys.argv[1], sys.argv[2]
total = 0
for fn in sorted(glob.glob(os.path.join(src, '**', '*.XAP'), recursive=True)):
    rel = os.path.relpath(fn, src)
    d = open(fn, 'rb').read()
    for e in read_entries(d):
        data = read_file(d, e)
        p = os.path.join(out, rel, e.name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(data)
        total += 1
print('files', total)
