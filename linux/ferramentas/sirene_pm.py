"""Sintetiza uma sirene eletrônica estilo viatura PM / Força Tática: wail -> yelp -> phaser.

Uso: python3 sirene_pm.py saida.wav [ciclos]
Onda quase quadrada (soft clip) no volume máximo, como os amplificadores de sirene.
"""
import math
import struct
import sys
import wave

TAXA = 44100
BAIXO, ALTO = 650.0, 1650.0


def varredura(periodo, duracao, fase0=0.0):
    """Gera (freq por amostra) para sweeps sobe/desce com o período dado."""
    n = int(duracao * TAXA)
    for i in range(n):
        t = (i / TAXA) % periodo
        x = t / (periodo / 2) if t < periodo / 2 else 2 - t / (periodo / 2)
        yield BAIXO + (ALTO - BAIXO) * (0.5 - 0.5 * math.cos(math.pi * x))


def subida_rapida(periodo, duracao):
    """Yelp/phaser reais sobem rápido e caem de uma vez (dente de serra suavizado)."""
    n = int(duracao * TAXA)
    for i in range(n):
        x = ((i / TAXA) % periodo) / periodo
        yield BAIXO + (ALTO - BAIXO) * math.sin(math.pi / 2 * x)


def main():
    saida = sys.argv[1]
    ciclos = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    trechos = []
    for _ in range(ciclos):
        trechos += [varredura(4.0, 8.0), subida_rapida(0.32, 5.0), subida_rapida(0.09, 3.0)]
    fase = 0.0
    k = math.tanh(5)
    quadros = bytearray()
    for trecho in trechos:
        for f in trecho:
            fase += 2 * math.pi * f / TAXA
            quadros += struct.pack("<h", int(32000 * math.tanh(5 * math.sin(fase)) / k))
    with wave.open(saida, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(bytes(quadros))


if __name__ == "__main__":
    main()
