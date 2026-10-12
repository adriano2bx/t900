#!/usr/bin/env bash
# Toca um arquivo de áudio no alto-falante do T900 Ultra (Bluetooth clássico, A2DP).
# Uso: tocar.sh arquivo.(wav|mp3|ogg|flac) [volume%]
set -euo pipefail
MAC=41:42:F2:3C:AD:B7
DEV_PATH=/org/bluez/hci0/dev_${MAC//:/_}
SINK=bluez_output.${MAC//:/_}.1
CARD=bluez_card.${MAC//:/_}
ARQ=${1:?uso: tocar.sh arquivo [volume%]}
VOL=${2:-100}

if ! bluetoothctl info "$MAC" | grep -q 'Connected: yes'; then
    bluetoothctl connect "$MAC" >/dev/null
    sleep 2
fi
# Após reiniciar, o relógio às vezes sobe só no perfil de chamada (HFP); força A2DP.
if ! pactl list cards | sed -n "/$CARD/,/^Card/p" | grep -q 'Perfil ativo: a2dp\|Active Profile: a2dp'; then
    busctl call org.bluez "$DEV_PATH" org.bluez.Device1 ConnectProfile s 0000110b-0000-1000-8000-00805f9b34fb >/dev/null 2>&1 || true
    sleep 2
    pactl set-card-profile "$CARD" a2dp-sink
fi
if ! pactl list short sinks | grep -q "$SINK"; then
    echo "erro: saída de áudio do relógio ($SINK) indisponível" >&2
    exit 1
fi
pactl set-sink-mute "$SINK" 0
pactl set-sink-volume "$SINK" "${VOL}%"
pw-play --target "$SINK" "$ARQ"
