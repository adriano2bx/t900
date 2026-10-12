#!/usr/bin/env python3
"""Cliente Linux para relógios do protocolo LaxasFit (ex.: T900 Ultra).

Protocolo (de Gadgetbridge, LaxasFitDeviceSupport):
  DF <len_hi> <len_lo> <crc> <grupo> <tipo=01> <cmd> <dlen_hi> <dlen_lo> <dados>
  len = total - 4; crc = soma de todos os bytes (com crc=0) & 0xFF
  Escrita em 6e400002-...-dcca9f em pedaços de 20 bytes; respostas em 6e400003.

Uso:
  t900.py notify "Título" "Corpo" [--icon sms|whatsapp|facebook|...]
  t900.py call "Nome" | t900.py endcall
  t900.py setup   (hora + liga alertas/vibração; rodar uma vez)
  t900.py find | t900.py battery
"""
import argparse
import datetime
import sys
import time

from bluepy.btle import ADDR_TYPE_PUBLIC, BTLEException, DefaultDelegate, Peripheral

DEFAULT_ADDR = "41:42:F2:3C:AD:E2"
UUID_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9f"
UUID_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9f"
UUID_BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"

GROUP_GENERAL = 0x02
GROUP_REQUEST_DATA = 0x0A
CMD_SET_DATE_TIME = 0x01
CMD_NOTIFICATIONS_ENABLE = 0x07
CMD_SET_DEVICE_VIBRATIONS = 0x08
CMD_FIND_BAND = 0x0B
CMD_INIT1 = 0x0A
CMD_NOTIFICATION_CALL = 0x11
CMD_NOTIFICATION_MESSAGE = 0x12

ICONS = {"sms": 0x01, "qq": 0x02, "wechat": 0x03, "facebook": 0x04, "twitter": 0x05,
         "line": 0x07, "whatsapp": 0x08, "instagram": 0x10}
CHUNK = 20


def craft(group, cmd, data=b""):
    data = bytes(data)
    total = 9 + len(data)
    b = bytearray([0xDF, (total - 4) >> 8, (total - 4) & 0xFF, 0, group, 0x01, cmd,
                   len(data) >> 8, len(data) & 0xFF]) + data
    b[3] = sum(b) & 0xFF
    return bytes(b)


class Watch(DefaultDelegate):
    def __init__(self, addr, verbose=False):
        super().__init__()
        self.verbose = verbose
        self.p = Peripheral(addr, ADDR_TYPE_PUBLIC)
        self.p.setDelegate(self)
        self.tx = self.p.getCharacteristics(uuid=UUID_TX)[0]
        rx = self.p.getCharacteristics(uuid=UUID_RX)[0]
        cccd = rx.getDescriptors(forUUID=0x2902)[0]
        cccd.write(b"\x01\x00", withResponse=True)

    def handleNotification(self, handle, data):
        if self.verbose:
            print(f"  <- {data.hex(' ')}")

    def send(self, frame, wait=0.3):
        if self.verbose:
            print(f"  -> {frame.hex(' ')}")
        for i in range(0, len(frame), CHUNK):
            self.tx.write(frame[i:i + CHUNK], withResponse=False)
            time.sleep(0.03)
        end = time.time() + wait
        while time.time() < end:
            self.p.waitForNotifications(0.1)

    def set_time(self):
        n = datetime.datetime.now()
        v = (n.second | (n.year - 2000) << 26 | n.month << 22 | n.day << 17
             | n.hour << 12 | n.minute << 6)
        self.send(craft(GROUP_GENERAL, CMD_SET_DATE_TIME, v.to_bytes(4, "big")))

    def init(self):
        # Mínimo antes de notificar: mandar configurações na mesma sessão
        # faz o relógio guardar a mensagem sem vibrar.
        self.send(craft(GROUP_GENERAL, CMD_INIT1, b"\x02"))

    def setup(self):
        """Ajusta hora e liga alertas/vibração (rodar uma vez, separado)."""
        self.set_time()
        self.send(craft(GROUP_GENERAL, CMD_NOTIFICATIONS_ENABLE, b"\x01" * 11))
        self.send(craft(GROUP_GENERAL, CMD_SET_DEVICE_VIBRATIONS, b"\x01" * 4))

    def notify(self, title, body, icon="sms"):
        text = " ".join(t for t in (title, body) if t)
        raw = text.encode("utf-8")[:250].decode("utf-8", "ignore").encode("utf-8")
        self.send(craft(GROUP_GENERAL, CMD_NOTIFICATION_MESSAGE,
                        bytes([ICONS[icon], 0, 0]) + raw), wait=1.0)

    def call(self, name):
        self.send(craft(GROUP_GENERAL, CMD_NOTIFICATION_CALL,
                        b"\x01\x00\x00" + (name + " ").encode("utf-8")), wait=1.0)

    def end_call(self):
        self.send(craft(GROUP_GENERAL, CMD_NOTIFICATION_CALL, b"\x00"))

    def find(self, on=True):
        # SettingIssuedUtils.findBracelet (app oficial): 02 0B <01|00>
        self.send(craft(GROUP_GENERAL, CMD_FIND_BAND, b"\x01" if on else b"\x00"))

    def battery(self):
        return self.p.getCharacteristics(uuid=UUID_BATTERY)[0].read()[0]

    def close(self):
        self.p.disconnect()


def main():
    ap = argparse.ArgumentParser(description="Envia comandos ao relógio LaxasFit/T900 Ultra")
    ap.add_argument("--addr", default=DEFAULT_ADDR)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("notify")
    n.add_argument("title")
    n.add_argument("body", nargs="?", default="")
    n.add_argument("--icon", choices=sorted(ICONS), default="sms")
    c = sub.add_parser("call")
    c.add_argument("name")
    for name in ("endcall", "find", "setup", "battery"):
        sub.add_parser(name)
    a = ap.parse_args()

    for attempt in range(3):
        try:
            w = Watch(a.addr, a.verbose)
            break
        except BTLEException as e:
            if attempt == 2:
                sys.exit(f"falha ao conectar em {a.addr}: {e}")
            time.sleep(2)
    try:
        w.init()
        if a.cmd == "notify":
            w.notify(a.title, a.body, a.icon)
        elif a.cmd == "call":
            w.call(a.name)
        elif a.cmd == "endcall":
            w.end_call()
        elif a.cmd == "find":
            w.find()
        elif a.cmd == "battery":
            print(f"bateria: {w.battery()}%")
        elif a.cmd == "setup":
            w.setup()
    finally:
        w.close()


if __name__ == "__main__":
    main()
