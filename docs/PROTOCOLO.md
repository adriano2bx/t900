# Protocolo do T900 Ultra (LaxasFit)

Engenharia reversa feita em 2026-10-12 num T900 Ultra que usa o app **LaxasFit**
(`com.lianhezhuli.laxasfit`, v1.5.25, Shenzhen United Power Technology). Fontes:

- testes ao vivo a partir de um notebook Linux (BlueZ 5.72, Intel AX201);
- o driver *LaxasFit* do [Gadgetbridge](https://codeberg.org/Freeyourgadget/Gadgetbridge) (AGPL);
- leitura do app oficial decompilado (não incluído neste repositório).

> ⚠️ **Aviso de segurança.** O grupo `0x13` é o **OTA de firmware**. `0x13 / 02` é
> `requestStartOTA`: enviado por engano durante a pesquisa, travou o relógio em modo de
> atualização (dois quadrados na tela, sem BLE) até ele reiniciar. **Nunca envie comandos
> sem confirmar o significado.** Os grupos `0x13`, `0x0A` (flash read), `0x0D` (reset) e
> `0x07`/`0x0B` (testes de fábrica) devem ser tratados como perigosos.

## 1. Rádio e endereços

O relógio é *dual-mode* e aparece duas vezes com o nome `Watch`:

| Endereço | Transporte | Uso |
|---|---|---|
| `41:42:F2:3C:AD:B7` | Bluetooth clássico (BR/EDR) | áudio: A2DP sink, HFP (viva-voz), AVRCP, HID |
| `41:42:F2:3C:AD:E2` | BLE | dados/comandos (protocolo abaixo) |

- *Manufacturer data* do anúncio BLE: chave `0x314c`, valor = MAC + `12 34`
  (o app procura o sufixo `:12:34`; em modo DFU, `:56:10`).
- **Pegadinha do BlueZ:** como o anúncio não marca "BR/EDR not supported", o BlueZ tenta
  conectar o endereço BLE por BR/EDR e falha com `Page Timeout`. Soluções: conectar o
  socket ATT/LE diretamente (bluepy, `addrType=public`) ou `Adapter1.ConnectDevice` com
  `AddressType=public` (exige `bluetoothd` experimental).
- O rádio do relógio **não sustenta BLE e áudio ao mesmo tempo**: com A2DP tocando, a
  conexão BLE cai e mensagens/vibração não chegam. Faça as etapas em sequência.
- Sinal típico medido: −82 a −94 dBm mesmo perto; conexões BLE falham com frequência —
  repita a tentativa.

## 2. Serviços GATT (BLE)

| Serviço | Características | Função |
|---|---|---|
| `180F` | `2A19` read/notify | bateria (%) |
| `180A` | `2A25`, `2A27`, `2A26`, `2A28` read | info; **`2A28` = bitmap de recursos** (§6) |
| `6e400001-b5a3-f393-e0a9-e50e24dcca9f` | `…0002` write (sem resposta), `…0003` notify | **canal principal de comandos** |
| `0000ff00-…` | `ff02` write, `ff01` notify | **canal de transferência/OTA** (wallpaper, mostrador, firmware) |
| `0000ff12-…` | `ff13` write, `ff14` notify | OTA Bluetrum (chip Bluetrum) |
| `0000ff10-…` | `fff1` write | não usado pelo app |

Observações: `6e400002` recusa *write with response* ("Invalid handle"); use
*write without response* em pedaços de 20 bytes. Habilite notificações escrevendo
`01 00` no CCCD de `6e400003` (handle `0x1a` neste aparelho).

## 3. Canal principal — formato do quadro

```
DF  LL LL  CK  GG  01  KK  DD DD  <dados…>
│   │      │   │   │   │   │
│   │      │   │   │   │   └ tamanho dos dados (big-endian)
│   │      │   │   │   └──── comando (chave)
│   │      │   │   └──────── versão do protocolo (sempre 01; 10 = "ação")
│   │      │   └──────────── grupo
│   │      └──────────────── checksum = soma de todos os bytes (com CK=0) & 0xFF
│   └─────────────────────── tamanho total − 4 (big-endian)
└─────────────────────────── cabeçalho de dados
```

- O relógio confirma cada quadro com um **ACK**: `FD 00 05 CK GG KK 00 NN 01`
  (`NN` = tamanho do quadro recebido, `01` = ok).
- Quadros do relógio para o telefone usam o mesmo formato `DF…`; o app responde com ACK
  `FD 00 05 CK GG KK 00 00 01`.
- Quadros maiores que o MTU são simplesmente cortados em pedaços de 20 bytes.

## 4. Comandos confirmados

Todos testados no aparelho, salvo indicação.

| Grupo / chave | Dados | Efeito |
|---|---|---|
| `02 / 0A` | `02` | inicialização (o app manda ao conectar) |
| `02 / 01` | data/hora em 32 bits: `s | min<<6 | h<<12 | dia<<17 | mês<<22 | (ano−2000)<<26` | acerta o relógio |
| `02 / 07` | 11 × `01` | habilita notificações de todos os apps |
| `02 / 08` | 4 × `01` | habilita vibração dos alertas (não vibra sozinho) |
| `02 / 0B` | `01` liga / `00` desliga | **"procurar relógio"**: vibra forte com tela de "pulseira encontrada" |
| `02 / 11` | `01 00 00 <nome UTF-8>` / `00` | alerta de chamada (aceito, mas **não aparece** neste aparelho) |
| `02 / 12` | `<ícone> 00 00 <texto UTF-8>` (≤ 250 bytes) | **notificação**: aparece na lista e **vibra uma vez** |
| `03 / 00` | id de usuário (8 ASCII) | vínculo; o relógio aceita sozinho (`0C/08`) — não há tela ✓/✗ |
| `0F / 01` | — | pede lista de mostradores (resposta `0F/02`) — *não testado* |
| `0F / 04` | — | pede config. do mostrador personalizado (resposta `0F/05`) — *não testado* |

Ícones de notificação: `01` SMS, `02` QQ, `03` WeChat, `04` Facebook, `05` Twitter,
`07` LINE, `08` WhatsApp, `10` Instagram. Acentos em UTF-8 funcionam.

**Pegadinha:** mandar configurações (`02/01`, `02/07`, `02/08`, `02/14`) na mesma conexão
logo antes da notificação faz o relógio guardá-la **sem vibrar**. Para notificar, mande só
`02/0A` + `02/12`.

Não existe comando "só vibrar": as opções são a vibração da própria notificação (pulso
curto) ou o "procurar relógio" (longo, com tela própria).

## 5. Eventos do relógio → telefone (grupo `0x0C`)

| Chave | Significado |
|---|---|
| `01` | procurar celular |
| `03` / `04` | entrar / sair da câmera remota |
| `08` | vínculo aceito (`dados=01` = primeira vez) |
| `09` | vínculo recusado |
| `0A` / `0B` | play / pause (música) |
| `0C` / `0D` | faixa anterior / próxima |
| `0F` | sair do "procurar celular" |
| `12` | estado do BT clássico |

Não há evento de "responder" ou de botões de notificação; o firmware não oferece
notificações interativas (Sim/Não). Os botões de música chegam por BLE e podem ser
usados como gambiarra de resposta.

## 6. Recursos (`2A28`)

Valor lido neste aparelho: `aa cf ea 81 9f f6 fc 38 00 00 00 00 00 00 10 c6 40 08 cf 10`.

- byte 2 `0xEA`: suporta mostradores, mostrador personalizado e envio de mostrador;
  **código de resolução `10` = 240 × 286 px**.
- byte 3: formato de tela `1`.
- byte 17 `0x08`: `codeFormat = 8`.
- byte 18 `0xCF`: `is565Bmp = 1`, `is8Bytes = 1` (imagem em PAR/RGB565, códigos de 8 bytes).

## 7. Canal de transferência (`ff00/ff01/ff02`) — wallpaper

Mapeado a partir do app; **ainda não testado no aparelho**.

Quadro de controle: `D5 MM SS TT 00 00 LL LL <dados> CK` (CK = soma de todos os bytes).
`MM` = tipo: `01` firmware, **`02` wallpaper ("PAPER")**, `04` contatos, `05` mostrador,
`0D` mostrador "badge". Para wallpaper de repouso: `MM=02`, `SS=01`.

1. Habilita notify em `ff01`; envia início `TT=01` com `[MTU(2)] [tamanho do arquivo(4)]`.
2. Relógio responde `D5 … 81 …` com bytes por pacote, intervalo, pacotes por grupo e timeout.
3. Pacotes de dados: `D6 <pedaço>`; ao fim de cada grupo, `TT=02` com CRC-8 do grupo
   (polinômio `0x31`, inicial 0). Relógio responde `82` (`[5]=00` → próximo grupo).
4. Ao fim, `TT=03` com CRC-8 do arquivo inteiro; relógio responde `83` (`[5]=00` → ok).
5. Para tipo `02` o app **não** manda reboot.

Antes da transferência o app envia `0F / 05` (mostrador personalizado: código de 8 bytes,
posição X/Y e cor RGB565 da hora, itens acima/abaixo, `bgUpdate=1`) e espera a resposta
`0F/06` com `01`.

Formato da imagem: **PAR** da Bluetrum, gerado pela função nativa
`raw_to_par(saida, entrada_ARGB, w, h, false, false, false)` de `libabpartool.so`
(saída alocada com `w*h*4`; retorna o tamanho). Cabeçalho observado:
`50 41 00 00 F0 00 1E 01 …` ("PA", largura 240, altura 286, little-endian). Uma imagem de
teste 240 × 286 virou 7 346 bytes. `linux/ferramentas/par.py` executa a função original
num emulador ARM64 (Unicorn) — a biblioteca não é distribuída aqui.

## 8. Áudio (Bluetooth clássico)

- A2DP (`a2dp-sink`, SBC) funciona como alto-falante, mas o áudio chega **picotado**
  mesmo com o relógio encostado no notebook e Wi-Fi em 5 GHz.
- HFP/mSBC toca **baixo**; amplificado, distorce.
- Depois de reiniciar, o relógio às vezes sobe só no perfil HFP; force A2DP com
  `ConnectProfile 0000110b-…` + `pactl set-card-profile … a2dp-sink`.
- O relógio derruba o link clássico quando ocioso; reconecte antes de tocar.
- Se a saída `bluez_output.*` não existir, `pw-play --target` toca **no alto-falante do
  notebook** — verifique a saída antes.

## 9. Outras descobertas

- Servidor de OTA do app: `GET https://ota.lianhezhuli.com/api/hry/get_update` com
  `unique_code` (resposta do relógio a `0x13/01`) e assinatura MD5 dos parâmetros.
  **Não consultado.**
- Chip Bluetrum (série AB56xx provável): não há firmware customizado conhecido.
- O canal `ff02`, quando recebe quadros em formato errado, responde ecoando o cabeçalho
  com o 4º byte `| 0x80` e código de erro `01`.

## Pendências

- Testar a leitura `0F/01` e `0F/04` e depois a transferência de wallpaper.
- Investigar a qualidade do A2DP (bitpool SBC menor, testar com o celular).
