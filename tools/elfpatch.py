"""SCPS_150.88 executable patches: extra PT_LOAD segment after .bss, heap start relocation, name-entry hooks."""
import struct

import keystone

import ime_asm

ORIG_END = 0x4254AC
HOOK_BASE = 0x425500

# Revision-specific facts (SCPS_150.88, SHA1 of the image in docs/survey.md)
END_LUI_LO = [(0x1001D0, 0x1001D8, 0x3C040042, 0x248454AC),   # crt0: SetupHeap(_end, -1)
              (0x22B768, 0x22B770, 0x3C020042, 0x244254AC)]   # helper returning _end
END_DATA_WORD = 0x2BDA94
COMMIT_SITE = 0x1A5DB0      # lw v1,0x88c(s1)  — start of "buf[pos] = key"
COMMIT_ORIG = (0x8E23088C, 0x8E220880)
BS_SITE = 0x1A5694          # lw a0,0x88c(s1); beqz a0,0x1a62f0 — start of "delete one char"
BS_ORIG = (0x8E24088C, 0x10800315)
GAME_CONTINUE = 0x1A55E8    # sw zero,0x78(s1) -> back to the left (index) panel, state -0x28a
SET_STATE = 0x1A62DC        # a0=1; [0x3a0(sp)]->state = v1; loop
FIELD_FULL = 0x1A62D0       # pos reached 4 or 8: v0=2 -> state -0x4d1 (original behaviour)
STATE_RIGHT_ACTIVE = -0x4CA  # right (candidate) panel, cursor kept
RIGHT_CANCEL_SITE = 0x1A54C0  # b 0x1a55e8; sw zero,0x70(s1) — × in the candidate panel (after its sound)
RIGHT_CANCEL_ORIG = (0x10000049, 0xAE200070)
BS_RESUME = 0x1A56A0
BS_EMPTY = 0x1A62F0


def _segments(d):
    phoff = struct.unpack_from('<I', d, 0x1C)[0]
    n = struct.unpack_from('<H', d, 0x2C)[0]
    return phoff, n, [struct.unpack_from('<8I', d, phoff + i * 32) for i in range(n)]


def _off(d, va):
    _, _, segs = _segments(d)
    for t, off, v, pa, fsz, msz, fl, al in segs:
        if t == 1 and v <= va < v + fsz:
            return va - v + off
    raise ValueError(f'{va:#x} not file-backed')


def patch_words(d, table):
    """table: {va: (expected_word, new_word)}; d: bytearray modified in place."""
    for va, (exp, new) in table.items():
        o = _off(d, va)
        cur = struct.unpack_from('<I', d, o)[0]
        if cur != exp:
            raise ValueError(f'{va:#x}: expected {exp:#010x}, found {cur:#010x}')
    for va, (exp, new) in table.items():
        struct.pack_into('<I', d, _off(d, va), new)


def add_segment(elf, vaddr, data):
    d = bytearray(elf)
    phoff, n, segs = _segments(d)
    first_data = min(s[1] for s in segs if s[0] == 1)
    if phoff + (n + 1) * 32 > first_data or any(d[phoff + n * 32:phoff + (n + 1) * 32]):
        raise ValueError('no room for another program header')
    for t, off, v, pa, fsz, msz, fl, al in segs:
        if t == 1 and v < vaddr + len(data) and vaddr < v + msz:
            raise ValueError('new segment overlaps an existing one')
    d += b'\0' * ((-len(d)) % 16)
    off = len(d)
    d += data
    struct.pack_into('<8I', d, phoff + n * 32, 1, off, vaddr, vaddr, len(data), len(data), 7, 16)
    struct.pack_into('<H', d, 0x2C, n + 1)
    return bytes(d)


def _hi_lo(v):
    lo = v & 0xFFFF
    return ((v + 0x8000) >> 16) & 0xFFFF, lo


def _trampolines(base, commit, backspace):
    """t_commit replaces the game's "write char, pos++, return to index panel" with:
    composition hook; pos++ only when a new slot was used; full field -> original confirm state;
    otherwise stay in the candidate panel (state -0x4ca) so jamo can be typed in a row."""
    src = f'''
.set noreorder
t_commit:
    jal   {commit:#x}
    addu  $a0, $s1, $zero
    beq   $v0, $zero, t_stay
    nop
    lw    $v1, 0x88c($s1)
    addiu $v1, $v1, 1
    sw    $v1, 0x88c($s1)
    addiu $v0, $zero, 4
    beq   $v1, $v0, t_full
    addiu $v0, $zero, 8
    beq   $v1, $v0, t_full
    nop
t_stay:
    addiu $v0, $zero, 1
    sw    $v0, 0x78($s1)
    j     {SET_STATE:#x}
    addiu $v1, $zero, {STATE_RIGHT_ACTIVE}
t_full:
    j     {FIELD_FULL:#x}
    nop
t_bs:
    jal   {backspace:#x}
    addu  $a0, $s1, $zero
    beq   $v0, $zero, t_b0
    nop
    j     {GAME_CONTINUE:#x}
    nop
t_b0:
    lw    $a0, 0x88c($s1)
    beq   $a0, $zero, t_bz
    addiu $v1, $a0, -1
    j     {BS_RESUME:#x}
    nop
t_bz:
    j     {BS_EMPTY:#x}
    nop
t_rbs:
    jal   {backspace:#x}
    addu  $a0, $s1, $zero
    bne   $v0, $zero, t_rstay
    nop
    lw    $v1, 0x88c($s1)
    beq   $v1, $zero, t_rleft
    addiu $v0, $zero, 4
    beq   $v1, $v0, t_rleft
    addiu $v1, $v1, -1
    sw    $v1, 0x88c($s1)
    lw    $v0, 0x880($s1)
    sll   $a0, $v1, 1
    addu  $v0, $v0, $a0
    addiu $a0, $zero, 0x81
    sb    $a0, 0($v0)
    addiu $a0, $zero, 0x40
    sb    $a0, 1($v0)
t_rstay:
    addiu $v0, $zero, 1
    sw    $v0, 0x78($s1)
    j     {SET_STATE:#x}
    addiu $v1, $zero, {STATE_RIGHT_ACTIVE}
t_rleft:
    j     {GAME_CONTINUE:#x}
    sw    $zero, 0x70($s1)
'''
    ks = keystone.Ks(keystone.KS_ARCH_MIPS, keystone.KS_MODE_MIPS32 + keystone.KS_MODE_LITTLE_ENDIAN)
    enc, _ = ks.asm(src, base)
    code = bytes(enc)
    head, _ = ks.asm(src.split('t_bs:')[0], base)
    head2, _ = ks.asm(src.split('t_rbs:')[0], base)
    return code, {'t_commit': base, 't_bs': base + len(head), 't_rbs': base + len(head2)}


def _j(target):
    return (2 << 26) | ((target >> 2) & 0x3FFFFFF)


def name_entry_patch(elf):
    """Return (patched_elf_bytes, info)."""
    tramp_base = HOOK_BASE
    tramp_len = len(_trampolines(tramp_base, 0x100000, 0x100000)[0])
    ime_base = (tramp_base + tramp_len + 15) & ~15
    ime_blob, ime_syms = ime_asm.build(ime_base)
    tramp, tsyms = _trampolines(tramp_base, ime_syms['commit'], ime_syms['backspace'])
    assert len(tramp) == tramp_len
    blob = tramp + b'\0' * (ime_base - tramp_base - len(tramp)) + ime_blob
    end = (HOOK_BASE + len(blob) + 15) & ~15

    d = bytearray(add_segment(elf, HOOK_BASE, blob))
    hi, lo = _hi_lo(end)
    table = {}
    for lui_va, lo_va, lui_w, lo_w in END_LUI_LO:
        table[lui_va] = (lui_w, (lui_w & 0xFFFF0000) | hi)
        table[lo_va] = (lo_w, (lo_w & 0xFFFF0000) | lo)
    table[END_DATA_WORD] = (ORIG_END, end)
    table[COMMIT_SITE] = (COMMIT_ORIG[0], _j(tsyms['t_commit']))
    table[COMMIT_SITE + 4] = (COMMIT_ORIG[1], 0)
    table[BS_SITE] = (BS_ORIG[0], _j(tsyms['t_bs']))
    table[BS_SITE + 4] = (BS_ORIG[1], 0)
    table[RIGHT_CANCEL_SITE] = (RIGHT_CANCEL_ORIG[0], _j(tsyms['t_rbs']))
    table[RIGHT_CANCEL_SITE + 4] = (RIGHT_CANCEL_ORIG[1], 0)
    patch_words(d, table)
    return bytes(d), {'base': HOOK_BASE, 'size': len(blob), 'end': end, **tsyms, **ime_syms}
