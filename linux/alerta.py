#!/usr/bin/env python3
"""Alarme no T900 Ultra: sirene contínua no alto-falante + vibração + mensagem na tela.

Uso:
  alerta.py "ALERTA: servidor caiu" [--duracao 60] [--volume 100] [--som arquivo]
Ctrl+C encerra antes do fim. Comandos BLE usados (todos confirmados no app oficial):
  02 0A 02 (init), 02 12 (mensagem), 02 0B 01/00 (procurar relógio = vibração liga/desliga).
"""
import argparse
import math
import os
import signal
import struct
import subprocess
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t900  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
SIRENE = os.path.join(AQUI, "sons", "sirene-alerta.wav")
TOCAR = os.path.join(AQUI, "tocar.sh")
INTERVALO_VIBRACAO = 4.0


def gerar_sirene(caminho, segundos=12, taxa=44100):
    """Sirene 'wail' 550→1450 Hz, onda quase quadrada (mais alta percebida), volume máximo."""
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    ciclo = 3.0  # subida + descida
    fase = 0.0
    quadros = bytearray()
    for i in range(int(segundos * taxa)):
        t = (i / taxa) % ciclo
        x = t / (ciclo / 2) if t < ciclo / 2 else 2 - t / (ciclo / 2)
        freq = 550 + 900 * (0.5 - 0.5 * math.cos(math.pi * x))
        fase += 2 * math.pi * freq / taxa
        amostra = math.tanh(4 * math.sin(fase)) / math.tanh(4)
        quadros += struct.pack("<h", int(32000 * amostra))
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(bytes(quadros))


def conectar(tentativas=5):
    for n in range(tentativas):
        try:
            return t900.Watch(t900.DEFAULT_ADDR)
        except t900.BTLEException:
            if n == tentativas - 1:
                raise
            time.sleep(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mensagem")
    ap.add_argument("--duracao", type=float, default=60, help="segundos (padrão 60)")
    ap.add_argument("--volume", type=int, default=100)
    ap.add_argument("--som", default=SIRENE, help="arquivo de áudio (padrão: sirene sintetizada)")
    a = ap.parse_args()

    if a.som == SIRENE and not os.path.exists(SIRENE):
        gerar_sirene(SIRENE)

    parar = False

    def ao_sinal(*_):
        nonlocal parar
        parar = True

    signal.signal(signal.SIGINT, ao_sinal)
    signal.signal(signal.SIGTERM, ao_sinal)

    # Áudio em laço contínuo num processo separado (tocar.sh já força A2DP e volume).
    audio = subprocess.Popen(
        ["bash", "-c", 'while true; do "$0" "$1" "$2" || sleep 1; done', TOCAR, a.som, str(a.volume)],
        start_new_session=True)

    w = None
    try:
        try:
            w = conectar()
            w.init()
            w.notify("⚠ ALERTA", a.mensagem, icon="sms")
        except Exception as e:
            print(f"aviso: BLE indisponível ({e}); seguindo só com a sirene", file=sys.stderr)
            w = None
        fim = time.time() + a.duracao
        proxima = 0.0
        while not parar and time.time() < fim:
            if w and time.time() >= proxima:
                try:
                    w.find(True)
                except Exception as e:
                    print(f"aviso: vibração falhou ({e}); reconectando", file=sys.stderr)
                    try:
                        w.close()
                    except Exception:
                        pass
                    try:
                        w = conectar(2)
                        w.init()
                    except Exception:
                        w = None
                proxima = time.time() + INTERVALO_VIBRACAO
            time.sleep(0.2)
    finally:
        os.killpg(audio.pid, signal.SIGTERM)
        if w:
            try:
                w.find(False)
                w.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
