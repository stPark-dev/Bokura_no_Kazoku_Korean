"""Run the MIPS name-entry hooks in Unicorn and compare with the Python reference model."""
import os
import random
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import hangul_map  # noqa: E402
import ime_asm  # noqa: E402
from hangul_ime import Ime  # noqa: E402

unicorn = pytest.importorskip('unicorn')
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN  # noqa: E402
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_RA, UC_MIPS_REG_SP, UC_MIPS_REG_V0, UC_MIPS_REG_PC  # noqa: E402

BASE = 0x425500
OBJ = 0x500000
BUF = 0x501000
STACK = 0x5F0000
STOP = 0x600000
CMAP = hangul_map.build()
REV = {v: k for k, v in CMAP.items()}
SPACE = 0x8140


class Machine:
    def __init__(self):
        self.blob, self.sym = ime_asm.build(BASE)
        self.uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 + UC_MODE_LITTLE_ENDIAN)
        self.uc.mem_map(0x400000, 0x300000)
        self.uc.mem_write(BASE, self.blob)
        self.uc.mem_write(STOP, struct.pack('<I', 0))
        self.reset()

    def reset(self):
        self.uc.mem_write(OBJ, b'\0' * 0x900)
        self.uc.mem_write(OBJ + 0x880, struct.pack('<I', BUF))
        self.uc.mem_write(BUF, b'\x81\x40' * 8)
        self.pos = 0

    def _call(self, fn):
        self.uc.mem_write(OBJ + 0x88C, struct.pack('<i', self.pos))
        self.uc.reg_write(UC_MIPS_REG_A0, OBJ)
        self.uc.reg_write(UC_MIPS_REG_SP, STACK)
        self.uc.reg_write(UC_MIPS_REG_RA, STOP)
        self.uc.emu_start(self.sym[fn], STOP, count=20000)
        assert self.uc.reg_read(UC_MIPS_REG_PC) == STOP, 'did not return'
        assert self.uc.reg_read(UC_MIPS_REG_SP) == STACK, 'stack not balanced'
        return self.uc.reg_read(UC_MIPS_REG_V0)

    def commit(self, ch):
        code = CMAP[ch] if ch in CMAP else int.from_bytes(ch.encode('cp932'), 'big')
        self.uc.mem_write(OBJ + 0x884, bytes([code >> 8, code & 0xFF]))
        if self._call('commit'):
            self.pos += 1

    def backspace(self):
        if self._call('backspace'):
            return
        if self.pos:  # the game's own deletion
            self.pos -= 1
            self.uc.mem_write(BUF + 2 * self.pos, b'\x81\x40')

    def text(self):
        raw = self.uc.mem_read(BUF, 2 * self.pos)
        out = ''
        for i in range(0, len(raw), 2):
            c = raw[i] << 8 | raw[i + 1]
            out += REV[c] if c in REV else bytes(raw[i:i + 2]).decode('cp932')
        return out


@pytest.fixture(scope='module')
def m():
    return Machine()


def run_both(m, actions, slots=4):
    m.reset()
    ref = Ime(slots)
    for a in actions:
        if a == '<':
            m.backspace()
            if len(ref.buf) == 4:
                ref.buf.pop()  # pos 4 is the family/given boundary: the game's own whole-char delete
            else:
                ref.backspace()
        else:
            if m.pos >= slots:
                break  # the game leaves the field when it is full
            m.commit(a)
            ref.press(a)
        assert m.text() == ref.text(), (actions, a)
    return m.text()


@pytest.mark.parametrize('keys,expect', [
    ('ㄱㅣㅁ', '김'), ('ㅎㅏㄴㄱㅡㄹ', '한글'), ('ㄱㅏㄴㅏ', '가나'), ('ㅇㅣㄹㄱㅇㅓ', '읽어'),
    ('ㄱㅗㅏ', '과'), ('ㄷㅏㄹㄱ', '닭'), ('ㅗㅏ', 'ㅘ'), ('ㄸㅗㅁ', '또ㅁ'), ('ㄱＡ', 'ㄱＡ'),
])
def test_examples(m, keys, expect):
    assert run_both(m, keys) == expect


def test_backspace_sequence(m):
    assert run_both(m, 'ㄷㅏㄹㄱ<<<<<') == ''


def test_no_composition_across_given_name_boundary(m):
    m.reset()
    m.pos = 4
    m.uc.mem_write(BUF + 6, CMAP['가'].to_bytes(2, 'big'))
    m.commit('ㄴ')
    assert m.pos == 5 and bytes(m.uc.mem_read(BUF + 6, 2)) == CMAP['가'].to_bytes(2, 'big')


def test_random_sequences_match_reference(m):
    rnd = random.Random(7)
    jamo = [chr(0x3131 + i) for i in range(51)]
    pool = jamo * 3 + ['<'] * 20 + ['Ａ', '　']
    for _ in range(1500):
        acts = [rnd.choice(pool) for _ in range(rnd.randrange(1, 14))]
        acts = [a for a in acts if a != '　']
        run_both(m, acts)
