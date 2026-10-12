# T900 Explorer

App Android mínimo (Kotlin + Compose) para pesquisa e conexão **não oficial** por Bluetooth LE com o smartwatch **T900 Ultra**, no mesmo princípio do projeto [miband3](https://github.com/adriano2bx/miband3).

O T900 Ultra não tem protocolo público documentado, então este app é um **explorador GATT**: procura dispositivos BLE (sem filtro), conecta, lista serviços/características, e permite **ler, escrever hex e assinar notificações**, com log exportável. O objetivo é mapear o protocolo real (UUIDs e pacotes de comando) para depois implementar o controle.

## Uso

1. Baixe o APK do CI (artefato `t900-explorer-apk` em *Actions*) ou compile: `./gradlew assembleDebug`.
2. Feche o app oficial do relógio (ele só aceita uma conexão).
3. *Procurar relógio* → escolha o T900 → toque numa característica → Ler / Assinar / Escrever.
4. *Exportar log* e guarde em `docs/` para documentar o protocolo.

Perfis padrão (FC `2A37`) são decodificados no log. Requisitos: Android 8.0+ com BLE; JDK 17.

## Estado

Ainda **não compilado/testado em aparelho** (o ambiente de desenvolvimento não alcança o Google Maven); a compilação e o `HexTest` rodam no CI. Se o T900 não aparecer na varredura LE ou expuser pouco, o controle provavelmente passa por Bluetooth clássico.

## Linux (protocolo LaxasFit) — `linux/`

O protocolo foi mapeado: o T900 Ultra usa o protocolo do app **LaxasFit** (quadros `DF…`
no serviço `6e400001-…-dcca9f`). Do Linux já é possível enviar **notificações com
acentos e ícones**, **vibrar** ("procurar relógio"), ler bateria e **tocar áudio** no
alto-falante do relógio (A2DP), além de um app desktop mínimo para mandar mensagens.

- Protocolo completo, comandos confirmados e armadilhas: [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md)
- Ferramentas e uso: [`linux/README.md`](linux/README.md)

> ⚠️ O grupo `0x13` é OTA de firmware — `0x13/02` trava o relógio em modo de atualização.
