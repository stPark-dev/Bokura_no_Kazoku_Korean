"""Minimal PCSX2 PINE client (read memory, status, save state)."""
import socket, struct, glob, os, time

def sock_path():
    cands = glob.glob('/run/user/%d/.flatpak/net.pcsx2.PCSX2/xdg-run/pcsx2.sock' % os.getuid()) + \
            glob.glob('/run/user/%d/pcsx2.sock' % os.getuid())
    return cands[0] if cands else None

class Pine:
    def __init__(self, path=None):
        self.s = socket.socket(socket.AF_UNIX); self.s.connect(path or sock_path())
    def _cmd(self, payload):
        self.s.sendall(struct.pack('<I', len(payload) + 4) + payload)
        hdr = self._recv(4); n = struct.unpack('<I', hdr)[0]
        body = self._recv(n - 4)
        if body[0] != 0: raise RuntimeError('PINE fail')
        return body[1:]
    def _recv(self, n):
        b = b''
        while len(b) < n:
            c = self.s.recv(n - len(b))
            if not c: raise EOFError
            b += c
        return b
    def read32(self, a): return struct.unpack('<I', self._cmd(bytes([2]) + struct.pack('<I', a)))[0]
    def read8(self, a): return self._cmd(bytes([0]) + struct.pack('<I', a))[0]
    def write8(self, a, v): self._cmd(bytes([4]) + struct.pack('<IB', a, v))
    def write32(self, a, v): self._cmd(bytes([6]) + struct.pack('<II', a, v))
    def read(self, a, n):
        out = bytearray()
        for x in range(a, a + n, 4): out += struct.pack('<I', self.read32(x))
        return bytes(out[:n])
    def status(self): return struct.unpack('<I', self._cmd(bytes([0xf])))[0]  # 0 run,1 pause,2 shutdown
    def title(self): return self._cmd(bytes([0xb]))[4:].rstrip(b'\0').decode()
    def save_state(self, slot): self._cmd(bytes([9, slot]))
    def load_state(self, slot): self._cmd(bytes([10, slot]))

def wait(timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        p = sock_path()
        if p:
            try: return Pine(p)
            except OSError: pass
        time.sleep(1)
    raise TimeoutError

def read_bulk(p, addr, n, batch=4096):
    """Batched read64 (opcode 3) for speed."""
    out = bytearray()
    a = addr
    while a < addr + n:
        cnt = min(batch, (addr + n - a + 7) // 8)
        payload = b''.join(bytes([3]) + struct.pack('<I', a + 8 * i) for i in range(cnt))
        p.s.sendall(struct.pack('<I', len(payload) + 4) + payload)
        hdr = p._recv(4); m = struct.unpack('<I', hdr)[0]
        body = p._recv(m - 4)
        if body[0] != 0: raise RuntimeError('PINE batch fail')
        out += body[1:]
        a += 8 * cnt
    return bytes(out[:n])
