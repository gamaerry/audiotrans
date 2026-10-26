#!/usr/bin/env bash
# Instala audiotrans desde el repo, editable: lo que cambies aquí se usa al instante.
# Se puede volver a correr sin problema: solo hace lo que falte.
set -euo pipefail

repo="$(dirname "$(readlink -f "$0")")"

for c in uv pw-record pactl; do
    command -v "$c" >/dev/null || { echo "Falta $c (uv: https://docs.astral.sh/uv/; pw-record y pactl: PipeWire)" >&2; exit 1; }
done
declare -A opcional=([trans]="esp/eng y respaldo de Google" [wl-paste]="cbes/cben/pses/psen" [mpv]="practice" [ffmpeg]="practice")
for c in "${!opcional[@]}"; do
    command -v "$c" >/dev/null || echo "Aviso: no está $c (opcional, para ${opcional[$c]})"
done

echo "== Comandos audiotrans, textrans y practice"
# uv baja Python 3.12 si hace falta (faster-whisper no tiene paquetes para 3.13+)
uv tool install -q --force --editable "$repo"
audiotrans --setup
echo "El modelo de Whisper (small, ~460 MB) se descarga la primera vez que uses audiotrans."
