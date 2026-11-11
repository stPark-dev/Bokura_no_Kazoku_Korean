"""MIPS (R5900-safe subset) implementation of the name-entry Hangul composition hooks.

build(base) -> (blob, symbols). Entry points (C-like, a0 = CMenuInputKanji object):
  commit(obj)    -> v0=1: caller advances pos (char written at buf[pos]); v0=0: merged into buf[pos-1]
  backspace(obj) -> v0=1: last char reduced in place (caller must not delete); v0=0: let the game delete
Object fields (SCPS_150.88): +0x880 u8* name buffer (8 x SJIS), +0x884/+0x885 key code bytes,
+0x88C s32 cursor position. Composition never crosses slot 0 or slot 4 (family/given name boundary).

Register discipline: entry points keep their state in a0, t0-t7; helpers may clobber v0, v1, a1-a3,
t8, t9 (and ra, which every non-leaf saves on the stack). No mul (EE): shifts/adds; loops > 6 insns.
"""
import keystone

import hangul_ime
import hangul_map

N_SYL = 2350
N_JAMO = 51
LIN0 = 1410  # linear index of SJIS 0x889F
NONE = 0xFF


def _lin(code):
    lead, trail = code >> 8, code & 0xFF
    li = lead - 0x81 if lead < 0xE0 else lead - 0xC1
    ti = trail - 0x40 if trail < 0x80 else trail - 0x41
    return li * 188 + ti


assert _lin(0x889F) == LIN0


def _tables():
    t = hangul_ime.T
    syl, _ = hangul_map.ksx1001_hangul()
    uni = [ord(c) - 0xAC00 for c in syl]
    assert uni == sorted(uni)
    pairs = [b for p in t['pairs'] for b in p]
    return {
        'UNI': b''.join(v.to_bytes(2, 'little') for v in uni),
        'CHO_OF': bytes(t['cho_of']),
        'JUNG_OF': bytes(t['jung_of']),
        'JONG_OF': bytes(t['jong_of']),
        'JAMO_OF_CHO': bytes(t['jamo_of_cho']),
        'JAMO_OF_JUNG': bytes(t['jamo_of_jung']),
        'JAMO_OF_JONG': bytes(t['jamo_of_jong']),
        'PAIRS': bytes(pairs),
    }, len(t['pairs'])


ASM = r'''
.set noreorder
    j     commit
    nop
    j     backspace
    nop
    j     particle
    nop

# ---------------- helpers ----------------
# h_lin: a1 = SJIS code -> v0 = linear index - LIN0
h_lin:
    srl   $t8, $a1, 8
    andi  $t9, $a1, 0xff
    sltiu $v0, $t8, 0xe0
    beq   $v0, $zero, L1
    addiu $t8, $t8, -0xc1
    addiu $t8, $t8, 0x40
L1:  sltiu $v0, $t9, 0x80
    beq   $v0, $zero, L2
    addiu $t9, $t9, -0x41
    addiu $t9, $t9, 1
L2:  sll   $v0, $t8, 7
    sll   $v1, $t8, 5
    addu  $v0, $v0, $v1
    sll   $v1, $t8, 4
    addu  $v0, $v0, $v1
    sll   $v1, $t8, 3
    addu  $v0, $v0, $v1
    sll   $v1, $t8, 2
    addu  $v0, $v0, $v1
    addu  $v0, $v0, $t9
    jr    $ra
    addiu $v0, $v0, -{LIN0}

# h_code: a1 = index (relative to LIN0) -> v0 = SJIS code
h_code:
    addiu $t8, $a1, {LIN0}
    addiu $t9, $zero, 188
    div   $zero, $t8, $t9
    mflo  $t8
    mfhi  $t9
    sltiu $v0, $t8, 31
    bne   $v0, $zero, LC1
    addiu $t8, $t8, 0x81
    addiu $t8, $t8, 0x40
LC1:  sltiu $v0, $t9, 63
    bne   $v0, $zero, LC2
    addiu $t9, $t9, 0x40
    addiu $t9, $t9, 1
LC2:  sll   $v0, $t8, 8
    jr    $ra
    or    $v0, $v0, $t9

# h_ks: a1 = syllable offset (0..11171) -> v0 = KS index or -1   (binary search over UNI)
h_ks:
    addiu $t8, $zero, 0
    addiu $t9, $zero, {N_SYL}
    lui   $a3, %hi(UNI)
    addiu $a3, $a3, %lo(UNI)
L3:  slt   $v0, $t8, $t9
    beq   $v0, $zero, L5
    addu  $a2, $t8, $t9
    srl   $a2, $a2, 1
    sll   $v1, $a2, 1
    addu  $v1, $v1, $a3
    lhu   $v1, 0($v1)
    beq   $v1, $a1, L4
    sltu  $v0, $v1, $a1
    beq   $v0, $zero, L6
    nop
    b     L3
    addiu $t8, $a2, 1
L6:  b     L3
    addu  $t9, $a2, $zero
L4:  jr    $ra
    addu  $v0, $a2, $zero
L5:  jr    $ra
    addiu $v0, $zero, -1

# h_syl: a1 = cho, a2 = jung, a3 = jong -> v0 = SJIS code or -1
h_syl:
    addiu $sp, $sp, -16
    sw    $ra, 0($sp)
    sll   $v0, $a1, 4
    sll   $v1, $a1, 2
    addu  $v0, $v0, $v1
    addu  $v0, $v0, $a1
    addu  $v0, $v0, $a2
    sll   $v1, $v0, 5
    sll   $v0, $v0, 2
    subu  $v0, $v1, $v0
    bal   h_ks
    addu  $a1, $v0, $a3
    bltz  $v0, L7
    nop
    bal   h_code
    addu  $a1, $v0, $zero
L7:  lw    $ra, 0($sp)
    jr    $ra
    addiu $sp, $sp, 16

# h_pair: a1 = x, a2 = y -> v0 = r or -1
h_pair:
    lui   $a3, %hi(PAIRS)
    addiu $a3, $a3, %lo(PAIRS)
    addiu $t9, $zero, {N_PAIRS}
L8:  beq   $t9, $zero, L9
    lbu   $v0, 0($a3)
    lbu   $v1, 1($a3)
    bne   $v0, $a1, L10
    addiu $t9, $t9, -1
    beq   $v1, $a2, L11
    nop
L10: b     L8
    addiu $a3, $a3, 3
L11: jr    $ra
    lbu   $v0, 2($a3)
L9:  jr    $ra
    addiu $v0, $zero, -1

# h_unpair: a1 = r -> v0 = x, v1 = y   or v0 = -1
h_unpair:
    lui   $a3, %hi(PAIRS)
    addiu $a3, $a3, %lo(PAIRS)
    addiu $t9, $zero, {N_PAIRS}
L12: beq   $t9, $zero, L13
    lbu   $v0, 2($a3)
    addiu $t9, $t9, -1
    nop
    nop
    nop
    bne   $v0, $a1, L12
    addiu $a3, $a3, 3
    lbu   $v0, -3($a3)
    jr    $ra
    lbu   $v1, -2($a3)
L13: jr    $ra
    addiu $v0, $zero, -1

# h_tab: a1 = table base, a2 = index -> v0 = byte
h_tab:
    addu  $v0, $a1, $a2
    jr    $ra
    lbu   $v0, 0($v0)

# ---------------- commit ----------------
commit:
    addiu $sp, $sp, -16
    sw    $ra, 0($sp)
    lw    $t0, 0x88c($a0)
    lw    $t1, 0x880($a0)
    lbu   $t2, 0x884($a0)
    lbu   $v0, 0x885($a0)
    sll   $t2, $t2, 8
    or    $t2, $t2, $v0
    beq   $t0, $zero, c_plain
    addiu $v0, $zero, 4
    beq   $t0, $v0, c_plain
    nop
    bal   h_lin
    addu  $a1, $t2, $zero
    addiu $t4, $v0, -{N_SYL}
    sltiu $v0, $t4, {N_JAMO}
    beq   $v0, $zero, c_plain
    sll   $t3, $t0, 1
    addu  $t3, $t3, $t1
    lbu   $t5, -2($t3)
    lbu   $v0, -1($t3)
    sll   $t5, $t5, 8
    or    $t5, $t5, $v0
    bal   h_lin
    addu  $a1, $t5, $zero
    addu  $t6, $v0, $zero
    addiu $t7, $t6, -{N_SYL}
    sltiu $v0, $t7, {N_JAMO}
    bne   $v0, $zero, c_prev_jamo
    sltiu $v0, $t6, {N_SYL}
    beq   $v0, $zero, c_plain
    nop
    # prev syllable: t5 = cho, t6 = jung, t7 = jong
    lui   $v1, %hi(UNI)
    addiu $v1, $v1, %lo(UNI)
    sll   $v0, $t6, 1
    addu  $v1, $v1, $v0
    lhu   $v1, 0($v1)
    addiu $v0, $zero, 588
    div   $zero, $v1, $v0
    mflo  $t5
    mfhi  $v1
    addiu $v0, $zero, 28
    div   $zero, $v1, $v0
    mflo  $t6
    mfhi  $t7
    lui   $a1, %hi(JUNG_OF)
    addiu $a1, $a1, %lo(JUNG_OF)
    bal   h_tab
    addu  $a2, $t4, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, c_syl_cons
    nop
    # ---- vowel after syllable
    bne   $t7, $zero, c_split
    nop
    lui   $a1, %hi(JAMO_OF_JUNG)
    addiu $a1, $a1, %lo(JAMO_OF_JUNG)
    bal   h_tab
    addu  $a2, $t6, $zero
    addu  $a1, $v0, $zero
    bal   h_pair
    addu  $a2, $t4, $zero
    bltz  $v0, c_plain
    lui   $a1, %hi(JUNG_OF)
    addiu $a1, $a1, %lo(JUNG_OF)
    bal   h_tab
    addu  $a2, $v0, $zero
    addu  $a1, $t5, $zero
    addu  $a2, $v0, $zero
    bal   h_syl
    addu  $a3, $zero, $zero
    b     c_merge
    nop
c_split:
    lui   $a1, %hi(JAMO_OF_JONG)
    addiu $a1, $a1, %lo(JAMO_OF_JONG)
    bal   h_tab
    addu  $a2, $t7, $zero
    addu  $t3, $v0, $zero          # t3 = moving consonant (jj) unless compound
    bal   h_unpair
    addu  $a1, $t3, $zero
    bltz  $v0, L_split_simple
    addu  $t7, $zero, $zero        # (delay) kept jong = 0
    addu  $t3, $v1, $zero          # compound: move the second part
    lui   $a1, %hi(JONG_OF)
    addiu $a1, $a1, %lo(JONG_OF)
    bal   h_tab
    addu  $a2, $v0, $zero
    addu  $t7, $v0, $zero          # keep the first part
L_split_simple:
    lui   $a1, %hi(CHO_OF)
    addiu $a1, $a1, %lo(CHO_OF)
    bal   h_tab
    addu  $a2, $t3, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, c_plain
    addu  $t3, $v0, $zero          # t3 = cho of new syllable
    addu  $a1, $t5, $zero
    addu  $a2, $t6, $zero
    bal   h_syl
    addu  $a3, $t7, $zero
    bltz  $v0, c_plain
    addu  $t5, $v0, $zero          # t5 = new prev code
    lui   $a1, %hi(JUNG_OF)
    addiu $a1, $a1, %lo(JUNG_OF)
    bal   h_tab
    addu  $a2, $t4, $zero
    addu  $a1, $t3, $zero
    addu  $a2, $v0, $zero
    bal   h_syl
    addu  $a3, $zero, $zero
    bltz  $v0, c_plain
    sll   $v1, $t0, 1
    addu  $v1, $v1, $t1
    srl   $a1, $t5, 8
    sb    $a1, -2($v1)
    sb    $t5, -1($v1)
    srl   $a1, $v0, 8
    sb    $a1, 0($v1)
    sb    $v0, 1($v1)
    b     c_ret
    addiu $v0, $zero, 1
    # ---- consonant after syllable
c_syl_cons:
    bne   $t7, $zero, L16
    lui   $a1, %hi(JONG_OF)
    addiu $a1, $a1, %lo(JONG_OF)
    bal   h_tab
    addu  $a2, $t4, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, c_plain
    addu  $a3, $v0, $zero
    addu  $a1, $t5, $zero
    bal   h_syl
    addu  $a2, $t6, $zero
    b     c_merge
    nop
L16: lui   $a1, %hi(JAMO_OF_JONG)
    addiu $a1, $a1, %lo(JAMO_OF_JONG)
    bal   h_tab
    addu  $a2, $t7, $zero
    addu  $a1, $v0, $zero
    bal   h_pair
    addu  $a2, $t4, $zero
    bltz  $v0, c_plain
    lui   $a1, %hi(JONG_OF)
    addiu $a1, $a1, %lo(JONG_OF)
    bal   h_tab
    addu  $a2, $v0, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, c_plain
    addu  $a3, $v0, $zero
    addu  $a1, $t5, $zero
    bal   h_syl
    addu  $a2, $t6, $zero
    b     c_merge
    nop
    # ---- previous char is a jamo (t7 = its index, t4 = key jamo)
c_prev_jamo:
    lui   $a1, %hi(JUNG_OF)
    addiu $a1, $a1, %lo(JUNG_OF)
    bal   h_tab
    addu  $a2, $t4, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, c_plain
    addu  $t6, $v0, $zero          # t6 = jung of key
    lui   $a1, %hi(CHO_OF)
    addiu $a1, $a1, %lo(CHO_OF)
    bal   h_tab
    addu  $a2, $t7, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, L17
    addu  $a1, $v0, $zero
    addu  $a2, $t6, $zero
    bal   h_syl
    addu  $a3, $zero, $zero
    b     c_merge
    nop
L17: addu  $a1, $t7, $zero
    bal   h_pair
    addu  $a2, $t4, $zero
    bltz  $v0, c_plain
    nop
    bal   h_code
    addiu $a1, $v0, {N_SYL}
    # ---- write v0 (or fall back to plain when v0 < 0) into buf[pos-1]
c_merge:
    bltz  $v0, c_plain
    sll   $v1, $t0, 1
    addu  $v1, $v1, $t1
    srl   $a1, $v0, 8
    sb    $a1, -2($v1)
    sb    $v0, -1($v1)
    b     c_ret
    addu  $v0, $zero, $zero
c_plain:
    sll   $v1, $t0, 1
    addu  $v1, $v1, $t1
    srl   $a1, $t2, 8
    sb    $a1, 0($v1)
    sb    $t2, 1($v1)
    addiu $v0, $zero, 1
c_ret:
    lw    $ra, 0($sp)
    jr    $ra
    addiu $sp, $sp, 16

# ---------------- backspace ----------------
backspace:
    addiu $sp, $sp, -16
    sw    $ra, 0($sp)
    lw    $t0, 0x88c($a0)
    lw    $t1, 0x880($a0)
    beq   $t0, $zero, b_no
    addiu $v0, $zero, 4
    beq   $t0, $v0, b_no
    sll   $t3, $t0, 1
    addu  $t3, $t3, $t1
    lbu   $t5, -2($t3)
    lbu   $v0, -1($t3)
    sll   $t5, $t5, 8
    or    $t5, $t5, $v0
    bal   h_lin
    addu  $a1, $t5, $zero
    addu  $t6, $v0, $zero
    addiu $t7, $t6, -{N_SYL}
    sltiu $v0, $t7, {N_JAMO}
    bne   $v0, $zero, b_jamo
    sltiu $v0, $t6, {N_SYL}
    beq   $v0, $zero, b_no
    nop
    lui   $v1, %hi(UNI)
    addiu $v1, $v1, %lo(UNI)
    sll   $v0, $t6, 1
    addu  $v1, $v1, $v0
    lhu   $v1, 0($v1)
    addiu $v0, $zero, 588
    div   $zero, $v1, $v0
    mflo  $t5
    mfhi  $v1
    addiu $v0, $zero, 28
    div   $zero, $v1, $v0
    mflo  $t6
    mfhi  $t7
    beq   $t7, $zero, L18
    lui   $a1, %hi(JAMO_OF_JONG)
    addiu $a1, $a1, %lo(JAMO_OF_JONG)
    bal   h_tab
    addu  $a2, $t7, $zero
    bal   h_unpair
    addu  $a1, $v0, $zero
    bltz  $v0, L19
    addu  $a3, $zero, $zero
    lui   $a1, %hi(JONG_OF)
    addiu $a1, $a1, %lo(JONG_OF)
    bal   h_tab
    addu  $a2, $v0, $zero
    addu  $a3, $v0, $zero
L19: addu  $a1, $t5, $zero
    bal   h_syl
    addu  $a2, $t6, $zero
    b     b_write
    nop
L18: lui   $a1, %hi(JAMO_OF_JUNG)
    addiu $a1, $a1, %lo(JAMO_OF_JUNG)
    bal   h_tab
    addu  $a2, $t6, $zero
    bal   h_unpair
    addu  $a1, $v0, $zero
    bltz  $v0, L20
    lui   $a1, %hi(JUNG_OF)
    addiu $a1, $a1, %lo(JUNG_OF)
    bal   h_tab
    addu  $a2, $v0, $zero
    addu  $a1, $t5, $zero
    addu  $a2, $v0, $zero
    bal   h_syl
    addu  $a3, $zero, $zero
    b     b_write
    nop
L20: lui   $a1, %hi(JAMO_OF_CHO)
    addiu $a1, $a1, %lo(JAMO_OF_CHO)
    bal   h_tab
    addu  $a2, $t5, $zero
    bal   h_code
    addiu $a1, $v0, {N_SYL}
    b     b_write
    nop
b_jamo:
    bal   h_unpair
    addu  $a1, $t7, $zero
    bltz  $v0, b_no
    addu  $t6, $v0, $zero
    lui   $a1, %hi(JUNG_OF)
    addiu $a1, $a1, %lo(JUNG_OF)
    bal   h_tab
    addu  $a2, $t6, $zero
    addiu $v1, $zero, {NONE}
    beq   $v0, $v1, b_no
    nop
    bal   h_code
    addiu $a1, $t6, {N_SYL}
b_write:
    bltz  $v0, b_no
    srl   $a1, $v0, 8
    sb    $a1, -2($t3)
    sb    $v0, -1($t3)
    b     b_ret
    addiu $v0, $zero, 1
b_no:
    addu  $v0, $zero, $zero
b_ret:
    lw    $ra, 0($sp)
    jr    $ra
    addiu $sp, $sp, 16

# ---------------- particle(out=a0, src=a1) -> v0 = strlen(out) after append, v1 = new src ----------
# out holds the expanded name (NUL-terminated). If src starts with X(Y) in full-width parens (0x8169/0x816A,
# 1-3 / 0-3 double-byte chars) and the last double-byte char of out (ASCII colour codes may follow the
# name) is a KS X 1001 syllable: append X (final consonant) or
# Y (no final, or final rieul and X == EU + Y, as in euro/ro). State: t0 out, t1 src/X start, t2 out end,
# t3 open paren, t4 len(X), t5 Y start, t6 close paren, t7 len(Y).
particle:
    addiu $sp, $sp, -16
    sw    $ra, 0($sp)
    addu  $t0, $a0, $zero
    addu  $t1, $a1, $zero
    addu  $t2, $a0, $zero
P_len:
    lb    $v0, 0($t2)
    beq   $v0, $zero, P_lend
    nop
    nop
    nop
    nop
    b     P_len
    addiu $t2, $t2, 1
P_lend:
    addu  $t3, $t1, $zero
    addu  $t4, $zero, $zero
P_x:
    bal   P_char
    addu  $a1, $t3, $zero
    bltz  $v0, P_fail
    addiu $v1, $zero, 0x69
    beq   $v0, $v1, P_xend
    addiu $v1, $zero, 0x6a
    beq   $v0, $v1, P_fail
    addiu $t3, $t3, 2
    addiu $t4, $t4, 1
    sltiu $a2, $t4, 4
    beq   $a2, $zero, P_fail
    nop
    b     P_x
    nop
P_xend:
    beq   $t4, $zero, P_fail
    addiu $t5, $t3, 2
    addu  $t6, $t5, $zero
    addu  $t7, $zero, $zero
P_y:
    bal   P_char
    addu  $a1, $t6, $zero
    bltz  $v0, P_fail
    addiu $v1, $zero, 0x6a
    beq   $v0, $v1, P_yend
    addiu $v1, $zero, 0x69
    beq   $v0, $v1, P_fail
    addiu $t6, $t6, 2
    addiu $t7, $t7, 1
    sltiu $a2, $t7, 4
    beq   $a2, $zero, P_fail
    nop
    b     P_y
    nop
P_yend:
    addu  $a1, $t0, $zero
    addiu $a3, $zero, -1
P_scan:
    beq   $a1, $t2, P_sdone
    lbu   $v0, 0($a1)
    sltiu $a2, $v0, 0x81
    bne   $a2, $zero, P_s1
    addiu $a2, $v0, -0xa0
    sltiu $a2, $a2, 0x40
    bne   $a2, $zero, P_s1
    lbu   $v1, 1($a1)
    sll   $v0, $v0, 8
    or    $a3, $v0, $v1
    b     P_scan
    addiu $a1, $a1, 2
P_s1:
    nop
    b     P_scan
    addiu $a1, $a1, 1
P_sdone:
    bltz  $a3, P_fail
    nop
    bal   h_lin
    addu  $a1, $a3, $zero
    sltiu $a2, $v0, {N_SYL}
    beq   $a2, $zero, P_fail
    sll   $v0, $v0, 1
    lui   $v1, %hi(UNI)
    addiu $v1, $v1, %lo(UNI)
    addu  $v1, $v1, $v0
    lhu   $v0, 0($v1)
    addiu $v1, $zero, 28
    divu  $zero, $v0, $v1
    mfhi  $v0
    beq   $v0, $zero, P_pickY
    addiu $v1, $zero, 8
    bne   $v0, $v1, P_pickX
    addiu $v1, $t7, 1
    bne   $v1, $t4, P_pickX
    lbu   $v0, 0($t1)
    xori  $v0, $v0, {EU_HI}
    bne   $v0, $zero, P_pickX
    lbu   $v0, 1($t1)
    xori  $v0, $v0, {EU_LO}
    bne   $v0, $zero, P_pickX
    addiu $a1, $t1, 2
    addu  $a2, $t5, $zero
P_cmp:
    beq   $a2, $t6, P_pickY
    lbu   $v0, 0($a1)
    lbu   $v1, 0($a2)
    addiu $a1, $a1, 1
    addiu $a2, $a2, 1
    nop
    beq   $v0, $v1, P_cmp
    nop
P_pickX:
    addu  $a1, $t1, $zero
    b     P_copy
    addu  $a2, $t3, $zero
P_pickY:
    addu  $a1, $t5, $zero
    addu  $a2, $t6, $zero
P_copy:
    beq   $a1, $a2, P_done
    lbu   $v0, 0($a1)
    sb    $v0, 0($t2)
    addiu $a1, $a1, 1
    addiu $t2, $t2, 1
    nop
    b     P_copy
    nop
P_done:
    sb    $zero, 0($t2)
    subu  $v0, $t2, $t0
    b     P_ret
    addiu $v1, $t6, 2
P_fail:
    subu  $v0, $t2, $t0
    addu  $v1, $t1, $zero
P_ret:
    lw    $ra, 0($sp)
    jr    $ra
    addiu $sp, $sp, 16

# P_char: a1 -> v0 = -1 if not a double-byte char, the trail byte when the lead is 0x81, else 0 (leaf)
P_char:
    lbu   $v0, 0($a1)
    lbu   $v1, 1($a1)
    sltiu $a2, $v0, 0x81
    bne   $a2, $zero, P_cbad
    addiu $a2, $v0, -0xa0
    sltiu $a2, $a2, 0x40
    bne   $a2, $zero, P_cbad
    addiu $a2, $v0, -0x81
    bne   $a2, $zero, P_cok
    nop
    jr    $ra
    addu  $v0, $v1, $zero
P_cok:
    jr    $ra
    addu  $v0, $zero, $zero
P_cbad:
    jr    $ra
    addiu $v0, $zero, -1
'''


def build(base):
    """Assemble code + tables at `base`. Returns (bytes, {symbol: address})."""
    tabs, n_pairs = _tables()
    # lay out tables after the code; assemble twice (first pass to learn code size)
    eu = hangul_map.build()['으']
    src = ASM.format(LIN0=LIN0, N_SYL=N_SYL, N_JAMO=N_JAMO, NONE=NONE, N_PAIRS=n_pairs,
                     EU_HI=eu >> 8, EU_LO=eu & 0xFF)
    ks = keystone.Ks(keystone.KS_ARCH_MIPS, keystone.KS_MODE_MIPS32 + keystone.KS_MODE_LITTLE_ENDIAN)

    # keystone lacks %hi/%lo on symbols, so resolve them textually.
    code_size = None
    tab_addr = {}
    for _ in range(2):
        addr = base + (code_size or 0)
        addr = (addr + 15) & ~15
        tab_addr = {}
        for k, v in tabs.items():
            tab_addr[k] = addr
            addr += (len(v) + 3) & ~3
        text = src
        for k, a in tab_addr.items():
            hi = ((a + 0x8000) >> 16) & 0xFFFF
            lo = a & 0xFFFF
            lo_s = lo - 0x10000 if lo & 0x8000 else lo
            text = text.replace(f'%hi({k})', str(hi)).replace(f'%lo({k})', str(lo_s))
        enc, _ = ks.asm(text, base)
        code = bytes(enc)
        if code_size == len(code):
            break
        code_size = len(code)
    blob = bytearray(code)
    start = (base + len(blob) + 15) & ~15
    blob += b'\0' * (start - base - len(blob))
    for k, v in tabs.items():
        assert base + len(blob) == tab_addr[k], k
        blob += v + b'\0' * (((len(v) + 3) & ~3) - len(v))
    syms = dict(tab_addr)
    syms['commit'] = base
    syms['backspace'] = base + 8
    syms['particle'] = base + 16
    return bytes(blob), syms
