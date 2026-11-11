"""XAPF archive reader (SCPS_150.88).

Layout (little endian):
  0x00 'XAPF', u32 total_size, u32 body_chunk_off, u32 body_size
  0x10 'FILE', u32 chunk_size, u32 version(=1), u32 count
  0x20 count * 32-byte entries:
       u32 name_off (rel. 0x18), u32 flags, u32 data_off (abs),
       u32 size, u32 csize, u32 date, u32 time, u32 pad
  names (NUL-terminated), then 'BODY' chunk with data.
"""
import struct
from dataclasses import dataclass

from xaplz import decompress


@dataclass(frozen=True)
class Entry:
    name: str
    flags: int
    data_off: int
    size: int
    csize: int
    date: int
    time: int


def read_entries(d):
    if d[:4] != b'XAPF' or d[0x10:0x14] != b'FILE':
        raise ValueError('not an XAPF archive')
    count = struct.unpack_from('<I', d, 0x1C)[0]
    ents = []
    for i in range(count):
        no, fl, off, usz, csz, dt, tm, _ = struct.unpack_from('<8I', d, 0x20 + i * 32)
        start = 0x18 + no
        end = d.index(b'\0', start)
        ents.append(Entry(d[start:end].decode('cp932'), fl, off, usz, csz, dt, tm))
    return ents


def read_file(d, e):
    raw = d[e.data_off:e.data_off + e.csize]
    if e.flags == 1:
        return decompress(raw, e.size)
    if e.flags == 0 and e.csize == e.size:
        return raw
    raise ValueError(f'{e.name}: unknown flags {e.flags}')


def _pad16(n):
    return (n + 15) & ~15


def rebuild(orig, files=None, raw_payloads=None):
    """Rebuild an XAPF archive keeping entry order, names, flags and timestamps.

    files: {name: uncompressed bytes} to (re)compress; raw_payloads: {name: stored bytes} used verbatim.
    Entries in neither map keep their original stored bytes.
    """
    from xaplz import compress
    files = files or {}
    raw_payloads = raw_payloads or {}
    ents = read_entries(orig)
    unknown = (set(files) | set(raw_payloads)) - {e.name for e in ents}
    if unknown:
        raise KeyError(f'not in archive: {sorted(unknown)}')
    file_chunk_len = struct.unpack_from('<I', orig, 8)[0]
    file_chunk = bytearray(orig[0x10:0x10 + file_chunk_len])
    body = bytearray()
    body_start = 0x10 + file_chunk_len + 0x10
    for i, e in enumerate(ents):
        if e.name in files:
            if e.flags != 1:
                raise ValueError(f'{e.name}: unsupported flags {e.flags}')
            size, stored = len(files[e.name]), compress(files[e.name])
        elif e.name in raw_payloads:
            size, stored = e.size, raw_payloads[e.name]
        else:
            size, stored = e.size, orig[e.data_off:e.data_off + e.csize]
        off = body_start + len(body)
        struct.pack_into('<III', file_chunk, 0x10 + i * 32 + 8, off, size, len(stored))
        body += stored + b'\0' * (_pad16(len(stored)) - len(stored))
    body_chunk = b'BODY' + struct.pack('<I', len(body) + 8) + b'\0' * 8 + bytes(body)
    total = len(file_chunk) + len(body_chunk)
    head = b'XAPF' + struct.pack('<III', total, len(file_chunk), len(body_chunk))
    return head + bytes(file_chunk) + body_chunk
