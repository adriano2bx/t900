"""Deixa um WAV 16-bit o mais alto possível: normaliza, aplica ganho e limita com tanh."""
import sys, wave, struct, math
src, dst = sys.argv[1], sys.argv[2]
ganho = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
with wave.open(src) as r:
    p = r.getparams(); raw = r.readframes(p.nframes)
s = struct.unpack(f"<{len(raw)//2}h", raw)
pico = max(1, max(abs(x) for x in s))
k = math.tanh(ganho)
out = [int(32000 * math.tanh(ganho * x / pico) / k) for x in s]
with wave.open(dst, "wb") as w:
    w.setparams(p); w.writeframes(struct.pack(f"<{len(out)}h", *out))
