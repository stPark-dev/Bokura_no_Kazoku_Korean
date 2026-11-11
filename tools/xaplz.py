"""XAP LZ decompressor, transcribed from SCPS_150.88 @ 0x249958.

Bitstream: flag bytes MSB-first, interleaved with data bytes.
  0            -> literal byte
  1 0 <b>      -> offset = b - 256 (b == 0 terminates)
  1 1 <b> 4bit -> offset = ((b - 256) << 4 | bits) - 255
  then length: n=1; while getbit(): n = n*2 + getbit(); copy n+1 bytes.
"""


class _Bits:
    def __init__(self, src):
        self.src = src
        self.i = 0
        self.flag = 0
        self.mask = 0

    def byte(self):
        b = self.src[self.i]
        self.i += 1
        return b

    def bit(self):
        if self.mask == 0:
            self.flag = self.byte()
            self.mask = 0x80
        r = 1 if self.flag & self.mask else 0
        self.mask >>= 1
        return r


def decompress(src, expected_size=None):
    s = _Bits(src)
    out = bytearray()
    while True:
        if not s.bit():
            out.append(s.byte())
            continue
        if s.bit():
            off = s.byte() - 256
            for _ in range(4):
                off = off * 2 + s.bit()
            off -= 0xFF
        else:
            b = s.byte()
            if b == 0:
                break
            off = b - 256
        n = 1
        while s.bit():
            n = n * 2 + s.bit()
        start = len(out) + off
        if start < 0:
            raise ValueError(f"back-reference before start (pos={len(out)}, off={off})")
        for k in range(n + 1):
            out.append(out[start + k])
    if expected_size is not None and len(out) != expected_size:
        raise ValueError(f"size mismatch {len(out)} != {expected_size}")
    return bytes(out)


SHORT_MAX = 255           # distance 1..255  -> "1 0 <256-d>"
LONG_MAX = 4096 + 255     # distance 256..4351 -> "1 1 <b> 4bit"
MIN_LEN = 2
CHAIN = 48


class _Writer:
    def __init__(self):
        self.out = bytearray()
        self.flag_pos = -1
        self.nbits = 8

    def bit(self, b):
        if self.nbits == 8:
            self.flag_pos = len(self.out)
            self.out.append(0)
            self.nbits = 0
        if b:
            self.out[self.flag_pos] |= 0x80 >> self.nbits
        self.nbits += 1

    def byte(self, v):
        self.out.append(v)


def _put_length(w, length):
    n = length - 1
    bits = bin(n)[3:]  # binary digits after the leading 1
    for c in bits:
        w.bit(1)
        w.bit(c == '1')
    w.bit(0)


def compress(data):
    """Greedy LZ encoder producing streams accepted by decompress() / the game routine."""
    data = bytes(data)
    n = len(data)
    w = _Writer()
    heads = {}
    i = 0

    def insert(p):
        if p + 1 < n:
            heads.setdefault(data[p:p + 2], []).append(p)

    while i < n:
        best_len, best_dist = 0, 0
        if i + 1 < n:
            cands = heads.get(data[i:i + 2], ())
            for p in reversed(cands[-CHAIN:]):
                d = i - p
                if d > LONG_MAX:
                    break
                ln = 2
                while i + ln < n and data[p + ln] == data[i + ln]:
                    ln += 1
                if ln > best_len:
                    best_len, best_dist = ln, d
        if best_len >= MIN_LEN:
            w.bit(1)
            if best_dist <= SHORT_MAX:
                w.bit(0)
                w.byte(256 - best_dist)
            else:
                v = 255 - best_dist  # (b-256)*16 + low4, in [-4096, -1]
                w.bit(1)
                w.byte((v >> 4) + 256)
                for k in range(3, -1, -1):
                    w.bit((v >> k) & 1)
            _put_length(w, best_len)
            for p in range(i, i + best_len):
                insert(p)
            i += best_len
        else:
            w.bit(0)
            w.byte(data[i])
            insert(i)
            i += 1
    w.bit(1)
    w.bit(0)
    w.byte(0)
    return bytes(w.out)
