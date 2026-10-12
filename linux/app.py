#!/usr/bin/env python3
"""App mínimo: envia uma mensagem ao T900 Ultra, com vibração extra e som opcionais.

A própria notificação já vibra uma vez; "Vibrar ×N" reenvia a mensagem para mais pulsos.
O som toca depois, separado do BLE (o rádio do relógio não sustenta os dois juntos).
"""
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import t900  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
SOM = os.path.join(AQUI, "sons", "notificacao.wav")
TOCAR = os.path.join(AQUI, "tocar.sh")
INTERVALO_REPETICAO = 2.0


def enviar_ao_relogio(mensagem, repeticoes, som):
    w = None
    for tentativa in range(4):
        try:
            w = t900.Watch(t900.DEFAULT_ADDR)
            break
        except t900.BTLEException:
            if tentativa == 3:
                raise
            time.sleep(2)
    try:
        w.init()
        for i in range(repeticoes):
            if i:
                time.sleep(INTERVALO_REPETICAO)
            w.notify(mensagem, "", icon="sms")
    finally:
        try:
            w.close()
        except Exception:
            pass
    if som:
        r = subprocess.run([TOCAR, SOM, "100"], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("mensagem enviada, mas o som falhou: " + (r.stderr.strip() or "erro no áudio"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("T900 – Enviar mensagem")
        self.resizable(False, False)
        quadro = ttk.Frame(self, padding=12)
        quadro.grid()

        ttk.Label(quadro, text="Mensagem:").grid(row=0, column=0, sticky="w")
        self.texto = tk.Text(quadro, width=40, height=4, wrap="word")
        self.texto.grid(row=1, column=0, columnspan=2, pady=(2, 8))
        self.texto.focus_set()

        opcoes = ttk.Frame(quadro)
        opcoes.grid(row=2, column=0, sticky="w")
        self.vibrar = tk.BooleanVar(value=True)
        ttk.Checkbutton(opcoes, text="Vibrar ×", variable=self.vibrar).pack(side="left")
        self.vezes = tk.IntVar(value=3)
        ttk.Spinbox(opcoes, from_=1, to=10, width=3, textvariable=self.vezes).pack(side="left")
        self.som = tk.BooleanVar(value=True)
        ttk.Checkbutton(opcoes, text="Som", variable=self.som).pack(side="left", padx=(12, 0))
        self.botao = ttk.Button(quadro, text="Enviar", command=self.enviar)
        self.botao.grid(row=2, column=1, sticky="e")

        self.status = ttk.Label(quadro, text="", foreground="gray")
        self.status.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.bind("<Control-Return>", lambda _e: self.enviar())

    def enviar(self):
        mensagem = self.texto.get("1.0", "end").strip()
        if not mensagem:
            self.status.config(text="Digite uma mensagem.", foreground="gray")
            return
        self.botao.config(state="disabled")
        self.status.config(text="Enviando…", foreground="gray")
        try:
            vezes = max(1, min(10, int(self.vezes.get()))) if self.vibrar.get() else 1
        except (tk.TclError, ValueError):
            vezes = 1
        threading.Thread(target=self._enviar, args=(mensagem, vezes, self.som.get()), daemon=True).start()

    def _enviar(self, mensagem, vezes, som):
        try:
            enviar_ao_relogio(mensagem, vezes, som)
            self.after(0, self._fim, "Enviada.", "green")
        except Exception as e:
            self.after(0, self._fim, f"Falhou: {e}", "red")

    def _fim(self, texto, cor):
        self.status.config(text=texto, foreground=cor)
        self.botao.config(state="normal")


if __name__ == "__main__":
    App().mainloop()
