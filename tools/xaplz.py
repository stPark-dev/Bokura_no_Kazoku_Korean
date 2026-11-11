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
