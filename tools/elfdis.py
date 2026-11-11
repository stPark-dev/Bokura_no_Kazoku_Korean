"""Minimal PS2 ELF helper: VA<->file offset, string xrefs, disassembly (capstone MIPS)."""
import struct, sys
import capstone

class Elf:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        phoff = struct.unpack_from('<I', self.d, 0x1c)[0]
        n = struct.unpack_from('<H', self.d, 0x2c)[0]
        self.segs = []
        for i in range(n):
            t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', self.d, phoff + i * 32)
            if t == 1:
                self.segs.append((va, off, fsz))
        self.md = capstone.Cs(capstone.CS_ARCH_MIPS, capstone.CS_MODE_MIPS64 | capstone.CS_MODE_LITTLE_ENDIAN)

    def off(self, va):
        for v, o, s in self.segs:
            if v <= va < v + s:
                return va - v + o
        raise ValueError(hex(va))

    def va(self, off):
        for v, o, s in self.segs:
            if o <= off < o + s:
                return off - o + v
        raise ValueError(hex(off))

    def word(self, va):
        return struct.unpack_from('<I', self.d, self.off(va))[0]

    def dis(self, va, n):
        o = self.off(va)
        out = []
        for i in range(n):
            w = self.d[o + i * 4:o + i * 4 + 4]
            ins = list(self.md.disasm(w, va + i * 4))
            out.append(f"{va+i*4:08x}: {w.hex()}  " + (f"{ins[0].mnemonic} {ins[0].op_str}" if ins else ".word"))
        return out

    def xrefs(self, target):
        """Find lui/addiu(or ori/ld/lw) pairs forming target address in text segment."""
        hi = (target + 0x8000) >> 16
        lo = target & 0xffff
        res = []
        v, o, s = self.segs[0]
        lui = {}
        for i in range(0, s, 4):
            w = struct.unpack_from('<I', self.d, o + i)[0]
            op = w >> 26
            rt = (w >> 16) & 31
            rs = (w >> 21) & 31
            imm = w & 0xffff
            if op == 0x0f:
                lui[rt] = (v + i, imm)
            elif rs in lui and imm == lo and lui[rs][1] == hi and v + i - lui[rs][0] < 0x100:
                res.append(v + i)
        return res
