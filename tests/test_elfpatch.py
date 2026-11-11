import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import elfpatch  # noqa: E402
from elfdis import Elf  # noqa: E402

ELF = os.path.join(os.path.dirname(__file__), '..', 'work', 'iso', 'SCPS_150.88')
need = pytest.mark.skipif(not os.path.exists(ELF), reason='original executable not extracted')


def _orig():
    return open(ELF, 'rb').read()


@need
def test_patch_rejects_unexpected_original_bytes():
    d = bytearray(_orig())
    with pytest.raises(ValueError):
        elfpatch.patch_words(d, {0x1A5DB0: (0xDEADBEEF, 0)})


@need
def test_add_segment_is_loadable_and_keeps_existing_bytes():
    orig = _orig()
    out = elfpatch.add_segment(orig, 0x425500, b'\x11\x22\x33\x44' * 4)
    e = Elf.__new__(Elf)
    e.d = out
    phoff = struct.unpack_from('<I', out, 0x1C)[0]
    n = struct.unpack_from('<H', out, 0x2C)[0]
    assert n == 4
    segs = [struct.unpack_from('<8I', out, phoff + i * 32) for i in range(n)]
    t, off, va, pa, fsz, msz, fl, al = segs[3]
    assert t == 1 and va == 0x425500 and fsz == msz == 16 and out[off:off + 16] == b'\x11\x22\x33\x44' * 4
    assert out[:len(orig)][0x1000:] == orig[0x1000:]


@need
def test_name_entry_patch_installs_hooks_and_moves_heap():
    out, info = elfpatch.name_entry_patch(_orig())
    e = Elf.__new__(Elf)
    e.d = out
    import capstone  # noqa: F401
    from elfdis import Elf as E2
    p = os.path.join(os.path.dirname(ELF), '..', '..', 'build')
    os.makedirs(p, exist_ok=True)
    tmp = os.path.join(p, 'test_patched.elf')
    open(tmp, 'wb').write(out)
    ee = E2(tmp)
    end = info['end']
    assert end % 16 == 0 and end >= info['base'] + info['size']
    # heap start (SetupHeap arg), memory-size helper and data word all use the new _end
    assert ee.word(0x1001D0) >> 16 == 0x3C04 and ((ee.word(0x1001D0) & 0xFFFF) << 16) + struct.unpack('<h', struct.pack('<H', ee.word(0x1001D8) & 0xFFFF))[0] == end
    assert ((ee.word(0x22B768) & 0xFFFF) << 16) + struct.unpack('<h', struct.pack('<H', ee.word(0x22B770) & 0xFFFF))[0] == end
    assert ee.word(0x2BDA94) == end
    # hook sites jump into the new segment
    for site in (0x1A5DB0, 0x1A5694, 0x1A54C0):
        w = ee.word(site)
        assert w >> 26 == 2 and ((w & 0x3FFFFFF) << 2) >= info['base']
        assert ee.word(site + 4) == 0
    # bss clear range is untouched (still ends at the original _end)
    assert ee.word(0x100128) == 0x246354AC


@need
def test_particle_hook_replaces_strlen_call_and_updates_source_pointer():
    unicorn = pytest.importorskip('unicorn')
    from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_PC, UC_MIPS_REG_RA, UC_MIPS_REG_S0,
                                    UC_MIPS_REG_SP, UC_MIPS_REG_V0)
    import hangul_map
    out, info = elfpatch.name_entry_patch(_orig())
    w = struct.unpack_from('<I', out, elfpatch._off(bytearray(out), elfpatch.PARTICLE_SITE))[0]
    assert w >> 26 == 3 and (w & 0x3FFFFFF) << 2 == info['t_part']
    assert struct.unpack_from('<I', out, elfpatch._off(bytearray(out), elfpatch.PARTICLE_SITE + 4))[0] == 0x0220202D  # move a0,s1 kept

    off = elfpatch._off(bytearray(out), info['base'])
    uc = unicorn.Uc(unicorn.UC_ARCH_MIPS, unicorn.UC_MODE_MIPS32 + unicorn.UC_MODE_LITTLE_ENDIAN)
    uc.mem_map(0x400000, 0x300000)
    uc.mem_write(info['base'], out[off:off + info['size']])
    cmap = hangul_map.build()
    uc.mem_write(0x500000, hangul_map.encode('치코', cmap) + b'\0')
    src = hangul_map.encode('은（는）「', cmap)
    uc.mem_write(0x501000, src + b'\0')
    uc.reg_write(UC_MIPS_REG_A0, 0x500000)
    uc.reg_write(UC_MIPS_REG_S0, 0x501000)
    uc.reg_write(UC_MIPS_REG_SP, 0x5F0000)
    uc.reg_write(UC_MIPS_REG_RA, 0x600000)
    uc.emu_start(info['t_part'], 0x600000, count=5000)
    assert uc.reg_read(UC_MIPS_REG_PC) == 0x600000 and uc.reg_read(UC_MIPS_REG_SP) == 0x5F0000
    assert uc.reg_read(UC_MIPS_REG_V0) == 6
    assert bytes(uc.mem_read(0x500000, 7)) == hangul_map.encode('치코는', cmap) + b'\0'
    assert uc.reg_read(UC_MIPS_REG_S0) == 0x501000 + len(src) - 2
