"""Etapa A (só leitura): 0F 01 (lista de mostradores) e 0F 04 (mostrador personalizado)."""
import sys, time
sys.path.insert(0, sys.argv[1])
import t900
buf = bytearray(); frames = []
w = t900.Watch(t900.DEFAULT_ADDR)
def on(h, data):
    global buf
    if not buf and data[0] == 0xFD:
        return
    buf += data
    while len(buf) >= 4 and buf[0] == 0xDF:
        total = ((buf[1] << 8) | buf[2]) + 4
        if len(buf) < total: break
        fr = bytes(buf[:total]); buf = buf[total:]; frames.append(fr)
        ack = bytearray([0xFD, 0, 5, 0, fr[4], fr[6], 0, 0, 1]); ack[3] = sum(ack) & 255
        w.tx.write(bytes(ack), withResponse=False)
    if buf and buf[0] not in (0xDF,): buf = bytearray()
w.handleNotification = on
w.init()
for cmd in (0x01, 0x04):
    w.send(t900.craft(0x0F, cmd), wait=3)
w.close()
for fr in frames:
    print(f"grupo {fr[4]:02x} chave {fr[6]:02x} ({len(fr)} B): {fr[9:].hex(' ')}")
