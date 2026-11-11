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
