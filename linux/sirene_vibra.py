#!/usr/bin/env python3
"""Vibração forte -> sirene -> vibração forte, no T900 Ultra.

Uso: sirene_vibra.py [arquivo] [--mensagem TEXTO] [--vibrar SEGUNDOS]
BLE e áudio rodam em etapas separadas (o rádio do relógio não sustenta os dois juntos).
Comandos BLE usados (confirmados no app oficial): 02 0A 02 (init), 02 12 (mensagem),
02 0B 01/00 (procurar relógio = vibração liga/desliga).
"""
import argparse
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import t900  # noqa: E402



def conectar():
    for tentativa in range(4):
        try:
            return t900.Watch(t900.DEFAULT_ADDR)
        except t900.BTLEException:
            time.sleep(2)
    return None


def vibrar(segundos, mensagem=None):
    """Liga o "procurar relógio" e mantém até o fim; se a conexão cair, reconecta e religa."""
    fim = time.time() + segundos
    w = None
    enviada = False
    while time.time() < fim:
        if w is None:
            w = conectar()
            if w is None:
                print("aviso: BLE indisponível, sem vibração", file=sys.stderr)
                return
            try:
                w.init()
                if mensagem and not enviada:
                    w.notify("⚠ ALERTA", mensagem, icon="sms")
                    enviada = True
                w.find(True)
            except t900.BTLEException:
                w = None
                continue
        try:
            w.p.waitForNotifications(0.5)
        except t900.BTLEException:
            w = None
    if w is None:
        w = conectar()
    if w:
        try:
            w.find(False)
            w.close()
        except t900.BTLEException:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo", nargs="?", default=os.path.join(AQUI, "sons", "sirene-alerta.wav"))
    ap.add_argument("--mensagem", default="ALERTA! Verifique agora.")
    ap.add_argument("--vibrar", type=float, default=8)
    a = ap.parse_args()

    vibrar(a.vibrar, a.mensagem)
    time.sleep(1)
    subprocess.run([os.path.join(AQUI, "tocar.sh"), a.arquivo, "100"], check=False)
    time.sleep(1)
    vibrar(a.vibrar)


if __name__ == "__main__":
    main()
