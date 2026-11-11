"""Run the MIPS particle hook in Unicorn and compare with tools/particle.py."""
import os
import random
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import hangul_map  # noqa: E402
import ime_asm  # noqa: E402
import particle  # noqa: E402

unicorn = pytest.importorskip('unicorn')
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN  # noqa: E402
from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_PC, UC_MIPS_REG_RA,  # noqa: E402
                                UC_MIPS_REG_SP, UC_MIPS_REG_V0, UC_MIPS_REG_V1)

BASE, OUT, SRC, STACK, STOP = 0x425500, 0x500000, 0x501000, 0x5F0000, 0x600000
CMAP = hangul_map.build()


def enc(s):
    return hangul_map.encode(s, CMAP)


@pytest.fixture(scope='module')
def uc():
    blob, sym = ime_asm.build(BASE)
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 + UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0x400000, 0x300000)
    u.mem_write(BASE, blob)
    u.sym = sym
    return u


def run(uc, name, rest):
    nb, rb = enc(name), enc(rest)
    uc.mem_write(OUT, nb + b'\0' + b'\xEE' * 32)
    uc.mem_write(SRC, rb + b'\0')
    uc.reg_write(UC_MIPS_REG_A0, OUT)
    uc.reg_write(UC_MIPS_REG_A1, SRC)
    uc.reg_write(UC_MIPS_REG_SP, STACK)
    uc.reg_write(UC_MIPS_REG_RA, STOP)
    uc.emu_start(uc.sym['particle'], STOP, count=5000)
    assert uc.reg_read(UC_MIPS_REG_PC) == STOP and uc.reg_read(UC_MIPS_REG_SP) == STACK
    n = uc.reg_read(UC_MIPS_REG_V0)
    out = bytes(uc.mem_read(OUT, n + 1))
    assert out[-1] == 0, 'output not NUL-terminated'
    return out[:-1], uc.reg_read(UC_MIPS_REG_V1) - SRC


def expect(name, rest):
    pick, left = particle.select(name, rest)
    return enc(name + pick), len(enc(rest)) - len(enc(left))


def test_entry_points_unchanged():
    _, sym = ime_asm.build(BASE)
    assert (sym['commit'], sym['backspace'], sym['particle']) == (BASE, BASE + 8, BASE + 16)


@pytest.mark.parametrize('name,rest', [
    ('지민', '은（는）보았다'), ('치코', '은（는）보았다'), ('하늘', '으로（로）'), ('지민', '으로（로）'),
    ('치코', '으로（로）'), ('하늘', '은（는）'), ('치코', '이에요（예요）'), ('지민', '이랑（랑）'),
    ('ＡＢ', '은（는）'), ('ㄱ', '은（는）'), ('', '은（는）'), ('지민', '「안녕」'), ('지민', '은（는'),
    ('지민', '가나다라（는）'), ('지민', '은（가나다라）'), ('지민', '（는）'), ('지민', ''), ('김', '이（）'),
    ('@r80@g80@b255지민@r255@g255@b255', '은（는）'), ('@r80@g80@b255치코@r255@g255@b255', '으로（로）'),
    ('@r80@g80@b255ＡＢ@r255@g255@b255', '은（는）'), ('@b1', '은（는）'),
])
def test_cases(uc, name, rest):
    assert run(uc, name, rest) == expect(name, rest)


def test_random(uc):
    rnd = random.Random(11)
    syl = [chr(c) for c in range(0xAC00, 0xD7A4) if chr(c) in CMAP]
    forms = ['은（는）', '이（가）', '을（를）', '과（와）', '으로（로）', '아（야）', '이랑（랑）', '이（）', '으（）',
             '은（는', '（는）', '은는）', '「', '']
    for _ in range(3000):
        name = ''.join(rnd.choice(syl) for _ in range(rnd.randrange(0, 5)))
        if rnd.random() < 0.5:
            name = '@r80@g80@b255' + name + rnd.choice(['', '@r255@g255@b255', '@n'])
        rest = rnd.choice(forms) + rnd.choice(['', '보았다', '…'])
        assert run(uc, name, rest) == expect(name, rest), (name, rest)
