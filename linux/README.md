# T900 Ultra no Linux

Ferramentas para controlar o T900 Ultra (protocolo LaxasFit) a partir de um PC Linux.
Detalhes do protocolo em [`../docs/PROTOCOLO.md`](../docs/PROTOCOLO.md).

## Requisitos

- BlueZ, PipeWire (`pactl`, `pw-play`), Python 3 com `bluepy` e Tkinter.
- Relógio pareado/confiável no endereço clássico (áudio) — ajuste `DEFAULT_ADDR`
  (BLE) em `t900.py` e `MAC` em `tocar.sh` para o seu aparelho.

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```

## O que funciona (testado)

| Arquivo | Uso |
|---|---|
| `t900.py` | cliente BLE: `notify "Título" "Texto" --icon whatsapp`, `find`, `battery`, `setup` |
| `app.py` | janela Tkinter: mensagem + "Vibrar ×N" (repete a notificação) + som |
| `tocar.sh` | toca um arquivo no alto-falante do relógio (força A2DP, recusa tocar no PC) |
| `sirene_vibra.py` | vibração ("procurar relógio") → sirene → vibração, em etapas |
| `alerta.py` | sirene contínua + vibração + mensagem **simultâneas** — ⚠️ não funciona: o rádio do relógio não sustenta BLE e áudio juntos |

Sons em `sons/` foram sintetizados aqui (sem direitos de terceiros).

## Ferramentas de pesquisa (`ferramentas/`)

| Arquivo | Uso |
|---|---|
| `par.py` | converte imagem para o formato PAR (wallpaper) emulando `libabpartool.so` com Unicorn |
| `dis.py` | desmonta trechos ARM64 da biblioteca (Capstone) |
| `ler_mostrador.py` | leitura `0F/01` e `0F/04` (ainda não executada com sucesso) |
| `probe_bind.py` | envia vínculo `03/00` e escuta eventos do grupo `0C` |
| `amplificar.py`, `sirene_pm.py` | utilitários de áudio |

`par.py` precisa da biblioteca proprietária, que **não** está no repositório: extraia
`lib/arm64-v8a/libabpartool.so` do `config.arm64_v8a.apk` do app LaxasFit para
`linux/vendor/` (ou defina `T900_ABPARTOOL`).

## Limitações conhecidas

- Áudio A2DP picotado; HFP baixo.
- Conexão BLE instável com sinal fraco; os scripts tentam reconectar.
- Wallpaper: protocolo mapeado, transferência ainda não testada.
- Sem notificações interativas (Sim/Não) no firmware.
