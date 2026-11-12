"""PS2 PSS movies (MPEG-2 program stream: 16 KiB packs, video 0xE0, SPU2 audio 0xBD, padding 0xBE).
Only the video elementary stream is replaced, at the same total length, so every pack, packet, audio
payload and timestamp keeps its position."""
import struct


def _video_packets(d):
    """Yield (payload_start, payload_end) of each video PES packet, in stream order."""
    i = 0
    while i < len(d) - 4:
        if d[i:i + 4] == b'\x00\x00\x01\xba':
            i += 14 + (d[i + 13] & 7)
            continue
        if d[i:i + 3] != b'\x00\x00\x01':
            raise ValueError(f'lost sync at {i:#x}')
        sid = d[i + 3]
        if sid == 0xb9:
            return
        ln = struct.unpack_from('>H', d, i + 4)[0]
        if sid == 0xe0:
            yield i + 9 + d[i + 8], i + 6 + ln
        i += 6 + ln


def video_es(d):
    return b''.join(d[a:b] for a, b in _video_packets(d))


def splice(d, es):
    slots = list(_video_packets(d))
    if sum(b - a for a, b in slots) != len(es):
        raise ValueError('new video ES must have exactly the original length')
    out = bytearray(d)
    k = 0
    for a, b in slots:
        out[a:b] = es[k:k + b - a]
        k += b - a
    return bytes(out)


def replace_prefix(es, cut, new):
    """Replace es[:cut] (which must end at a start code boundary) by `new` followed by zero stuffing
    (MPEG-2 allows any number of zero bytes before a start code)."""
    return replace_range(es, 0, cut, new)


def gops(es):
    """GOP table: offset of each GOP header, display index of its first frame (base) and picture count."""
    out = []
    i = es.find(b'\x00\x00\x01\xb8')
    while i >= 0:
        nxt = es.find(b'\x00\x00\x01\xb8', i + 4)
        end = nxt if nxt >= 0 else len(es)
        n = 0
        j = es.find(b'\x00\x00\x01\x00', i, end)
        while j >= 0:
            n += 1
            j = es.find(b'\x00\x00\x01\x00', j + 4, end)
        out.append({'offset': i, 'base': (out[-1]['base'] + out[-1]['count']) if out else 0, 'count': n})
        i = nxt
    return out


def replace_range(es, start, end, new):
    """Replace es[start:end] by `new` + zero stuffing (same length)."""
    if len(new) > end - start:
        raise ValueError(f'new segment {len(new)} bytes > {end - start} available')
    return es[:start] + new + b'\0' * (end - start - len(new)) + es[end:]


ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7,
          14, 21, 28, 35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31, 39,
          46, 53, 60, 61, 54, 47, 55, 62, 63]


def quant_matrices(es):
    """(intra, non_intra) in raster order from the first sequence header; None when not loaded (default)."""
    i = es.find(b'\x00\x00\x01\xb3') + 4
    bits = int.from_bytes(es[i:i + 140], 'big')
    total = 140 * 8
    pos = 12 + 12 + 4 + 4 + 18 + 1 + 10 + 1          # size, aspect, frame rate, bit rate, marker, vbv, constrained

    def take(n):
        nonlocal pos
        v = (bits >> (total - pos - n)) & ((1 << n) - 1)
        pos += n
        return v

    def matrix():
        m = [0] * 64
        for k in range(64):
            m[ZIGZAG[k]] = take(8)
        return m
    intra = matrix() if take(1) else None
    non_intra = matrix() if take(1) else None
    return intra, non_intra


def gop_data(es):
    """Bytes from the first GOP header on, without a trailing sequence end code."""
    out = es[es.find(b'\x00\x00\x01\xb8'):]
    return out[:-4] if out.endswith(b'\x00\x00\x01\xb7') else out


def strip_sequence_headers(seg):
    """Drop sequence headers and their sequence / sequence-display extensions (ext ids 1, 2), so the
    stream's original sequence header (matrices, progressive_sequence) stays in effect."""
    pos = []
    j = seg.find(b'\x00\x00\x01')
    while j >= 0:
        pos.append(j)
        j = seg.find(b'\x00\x00\x01', j + 3)
    out = bytearray(seg[:pos[0]] if pos else seg)
    skipping = False
    for k, a in enumerate(pos):
        b = pos[k + 1] if k + 1 < len(pos) else len(seg)
        code = seg[a + 3]
        if code == 0xb3:
            skipping = True
        elif not (code == 0xb5 and skipping and (seg[a + 4] >> 4) in (1, 2)):
            skipping = False
        if not skipping:
            out += seg[a:b]
    return bytes(out)


_UNIT_END = (0x00, 0xb3, 0xb7, 0xb8)          # picture, sequence header, sequence end, GOP


def picture_units(es, start, end):
    """Pictures in es[start:end] in coded order: offset/end (picture header up to the next picture, GOP,
    sequence header or sequence end code), temporal reference and coding type."""
    out = []
    j = es.find(b'\x00\x00\x01', start, end)
    while 0 <= j:
        code = es[j + 3]
        if out and out[-1]['end'] is None and code in _UNIT_END:
            out[-1]['end'] = j
        if code == 0x00:
            out.append({'offset': j, 'end': None, 'tr': (es[j + 4] << 2) | (es[j + 5] >> 6),
                        'type': 'xIPB'[(es[j + 5] >> 3) & 7]})
        j = es.find(b'\x00\x00\x01', j + 3, end)
    if out and out[-1]['end'] is None:
        out[-1]['end'] = end
    return out


def place_pictures(es, start, end, new):
    """Put the pictures of `new` (same coded order, types and temporal references) into the slots of the
    pictures in es[start:end], each at its original offset followed by zero stuffing. Everything else,
    GOP headers included, stays. The PES timestamps of the pack that carries each picture start therefore
    keep pointing at the same picture."""
    old_units, new_units = picture_units(es, start, end), picture_units(new, 0, len(new))
    if [(u['tr'], u['type']) for u in old_units] != [(u['tr'], u['type']) for u in new_units]:
        raise ValueError('new pictures differ in coded order, type or temporal reference')
    out = bytearray(es)
    for o, n in zip(old_units, new_units):
        data = new[n['offset']:n['end']]
        room = o['end'] - o['offset']
        if len(data) > room:
            raise ValueError(f'picture at {o["offset"]:#x}: {len(data)} bytes > {room}')
        out[o['offset']:o['end']] = data + b'\0' * (room - len(data))
    return bytes(out)
