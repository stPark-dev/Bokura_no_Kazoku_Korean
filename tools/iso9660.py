"""Minimal ISO9660 file replace.

replace(): in place if it fits its sectors, else append at the image end and repoint.
replace_all(): keep the original file order; files after a grown file are shifted by the growth,
so on-disc distances (seek times while the game streams) stay close to the original layout."""
import struct
SEC = 2048

def _dir_records(img, lba, size):
    pos = lba * SEC; end = pos + size
    while pos < end:
        ln = img[pos]
        if ln == 0:
            pos = (pos // SEC + 1) * SEC; continue
        yield pos, img[pos:pos + ln]; pos += ln

def find(img, path):
    root = img[16 * SEC + 156:16 * SEC + 156 + 34]
    lba, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    parts = path.upper().strip('/').split('/')
    for i, p in enumerate(parts):
        for pos, rec in _dir_records(img, lba, size):
            nl = rec[32]; name = rec[33:33 + nl].decode('ascii', 'replace').split(';')[0]
            if name == p:
                lba = struct.unpack_from('<I', rec, 2)[0]; size = struct.unpack_from('<I', rec, 10)[0]
                if i == len(parts) - 1:
                    return pos, lba, size
                break
        else:
            raise FileNotFoundError(path)

def replace(img, path, data):
    """img: bytearray (modified in place, may grow). Returns (lba, mode)."""
    pos, lba, size = find(img, path)
    cap = (size + SEC - 1) // SEC * SEC
    if len(data) <= cap:
        img[lba * SEC:lba * SEC + cap] = data + b'\0' * (cap - len(data)); mode = 'inplace'
    else:
        if len(img) % SEC: raise ValueError('image not sector aligned')
        lba = len(img) // SEC
        img += data + b'\0' * ((-len(data)) % SEC); mode = 'append'
        total = len(img) // SEC
        struct.pack_into('<I', img, 16 * SEC + 80, total); struct.pack_into('>I', img, 16 * SEC + 84, total)
    struct.pack_into('<I', img, pos + 2, lba); struct.pack_into('>I', img, pos + 6, lba)
    struct.pack_into('<I', img, pos + 10, len(data)); struct.pack_into('>I', img, pos + 14, len(data))
    return lba, mode

def finalize(img, pad_sectors=2048):
    """Pad image tail (game reads ahead past file ends) and update volume size."""
    img += b'\0' * (pad_sectors * SEC)
    total = len(img) // SEC
    struct.pack_into('<I', img, 16 * SEC + 80, total); struct.pack_into('>I', img, 16 * SEC + 84, total)

def list_files(img):
    """[(path, lba, size)] for every file, depth-first, '/'-separated, without ';1'."""
    root = img[16 * SEC + 156:16 * SEC + 156 + 34]
    out = []
    def walk(lba, size, prefix):
        for pos, rec in _dir_records(img, lba, size):
            nl = rec[32]; raw = rec[33:33 + nl]
            if raw in (b'\0', b'\1'): continue
            name = raw.decode('ascii', 'replace').split(';')[0]
            clba, csize = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
            if rec[25] & 2: walk(clba, csize, prefix + name + '/')
            else: out.append((prefix + name, clba, csize))
    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')
    return out


def _records(img):
    """[(record pos, lba, size, is_dir)] for every file and subdirectory record (not '.'/'..')."""
    root = img[16 * SEC + 156:16 * SEC + 156 + 34]
    out = []
    def walk(lba, size):
        for pos, rec in _dir_records(img, lba, size):
            if rec[33:33 + rec[32]] in (b'\0', b'\1'): continue
            clba, csize, is_dir = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0], bool(rec[25] & 2)
            out.append((pos, clba, csize, is_dir))
            if is_dir: walk(clba, csize)
    walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0])
    return out


def _move_up(img, src, dst, n, chunk=1 << 24):
    """Copy img[src:src+n] to img[dst:...] with dst >= src (overlap safe: copies from the end)."""
    end = n
    while end > 0:
        beg = max(0, end - chunk)
        img[dst + beg:dst + end] = bytes(img[src + beg:src + end]); end = beg


def replace_all(img, new):
    """Replace files {path: data} keeping file order; later files shift only by the sectors that don't fit.
    img: bytearray modified in place (may grow). Directories must all lie before the first shifted file."""
    pos_of = {}
    for path, lba, size in list_files(img):
        pos_of[path] = find(img, path)[0]
    missing = set(new) - set(pos_of)
    if missing: raise FileNotFoundError(sorted(missing))
    recs = _records(img)
    files = sorted((lba, pos, size) for pos, lba, size, d in recs if not d)
    dirs = [lba for pos, lba, size, d in recs if d] + [struct.unpack_from('<I', img, 16 * SEC + 156 + 2)[0]]
    by_pos = {pos_of[p]: p for p in pos_of}
    total = len(img) // SEC
    plan, shift = [], 0  # (old lba, new lba, segment sectors, pos, path)
    for i, (lba, pos, size) in enumerate(files):
        seg = (files[i + 1][0] if i + 1 < len(files) else total) - lba
        plan.append((lba, lba + shift, seg, pos, by_pos[pos]))
        if by_pos[pos] in new:
            shift += max(0, (len(new[by_pos[pos]]) + SEC - 1) // SEC - seg)
    first_moved = min((o for o, n, _, _, _ in plan if n != o), default=None)
    if first_moved is not None and any(d >= first_moved for d in dirs):
        raise ValueError('a directory lies after a file that must move')
    img += b'\0' * (shift * SEC)
    for old, nl, seg, pos, path in reversed(plan):
        if nl != old: _move_up(img, old * SEC, nl * SEC, seg * SEC)
    for old, nl, seg, pos, path in plan:
        size = struct.unpack_from('<I', img, pos + 10)[0]
        if path in new:
            data = new[path]; cap = max(seg, (len(data) + SEC - 1) // SEC) * SEC
            img[nl * SEC:nl * SEC + cap] = data + b'\0' * (cap - len(data)); size = len(data)
        struct.pack_into('<I', img, pos + 2, nl); struct.pack_into('>I', img, pos + 6, nl)
        struct.pack_into('<I', img, pos + 10, size); struct.pack_into('>I', img, pos + 14, size)
    total = len(img) // SEC
    struct.pack_into('<I', img, 16 * SEC + 80, total); struct.pack_into('>I', img, 16 * SEC + 84, total)
