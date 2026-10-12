import sys, time, uuid
sys.path.insert(0, sys.argv[1])
import t900
w = t900.Watch(t900.DEFAULT_ADDR, verbose=False)
def on(h, data):
    print(f"  <- {data.hex(' ')}", flush=True)
    if data[0] == 0xDF and len(data) >= 9:  # ACK como o app oficial
        ack = bytearray([0xFD, 0, 5, 0, data[4], data[6], 0, 0, 1]); ack[3] = sum(ack) & 255
        w.tx.write(bytes(ack), withResponse=False)
w.handleNotification = on
w.send(t900.craft(2, 0x0a, b"\x02"))
uid = uuid.uuid4().hex[:8].encode()
print("bind uid", uid, flush=True)
w.send(t900.craft(0x03, 0x00, uid), wait=40)
w.close()
