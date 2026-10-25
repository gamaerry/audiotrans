#!/usr/bin/env bash
# Instala audiotrans: entorno de Python, traductores locales en-es/es-en y enlaces a los comandos.
# Se puede volver a correr sin problema: solo hace lo que falte.
set -euo pipefail

repo="$(dirname "$(readlink -f "$0")")"
datos="${AUDIOTRANS_DATOS:-$HOME/.local/share/audiotrans}"
bin="$HOME/.local/bin"
man1="$HOME/.local/share/man/man1"

for c in uv pw-record pactl; do
    command -v "$c" >/dev/null || { echo "Falta $c (uv: https://docs.astral.sh/uv/; pw-record y pactl: PipeWire)" >&2; exit 1; }
done
for c in trans wl-paste; do
    command -v "$c" >/dev/null || echo "Aviso: no está $c (opcional: $([[ $c == trans ]] && echo 'esp/eng y respaldo de Google' || echo 'cbes/cben/pses/psen'))"
done

echo "== Entorno de Python en $datos/venv"
# faster-whisper no tiene paquetes para Python 3.13+; 3.12 se instala aparte con uv
uv python find 3.12 >/dev/null 2>&1 || uv python install 3.12
[[ -x "$datos/venv/bin/python" ]] || uv venv -q --python 3.12 "$datos/venv"
VIRTUAL_ENV="$datos/venv" uv pip install -q -r "$repo/requirements.txt"

# Modelos OPUS-MT de Helsinki-NLP (Tatoeba-MT, CC-BY 4.0), convertidos a CTranslate2 en int8
declare -A opus=(
    [en-es]="eng-spa/opus+bt-2021-04-10"
    [es-en]="spa-eng/opus+bt-2021-04-30"
)
for par in "${!opus[@]}"; do
    destino="$datos/modelos/$par"
    [[ -f "$destino/model.bin" ]] && continue
    echo "== Traductor $par (descarga de ~290 MB; queda en 82 MB)"
    tmp="$(mktemp -d)"
    # Barra de progreso solo en una terminal; en un registro quedaría ilegible
    curl -fL "$([[ -t 2 ]] && echo --progress-bar || echo -sS)" -o "$tmp/m.zip" "https://object.pouta.csc.fi/Tatoeba-MT-models/${opus[$par]}.zip"
    mkdir "$tmp/src" && unzip -q "$tmp/m.zip" -d "$tmp/src"
    "$datos/venv/bin/ct2-opus-mt-converter" --model_dir "$tmp/src" --output_dir "$tmp/ct2" --quantization int8 >/dev/null
    mkdir -p "$destino"
    cp "$tmp"/ct2/* "$destino/"
    cp "$tmp"/src/{source.spm,target.spm,LICENSE,README.md} "$destino/"
    rm -rf "$tmp"
done

echo "== Comandos y manual"
mkdir -p "$bin" "$man1"
ln -sfn "$repo/bin/audiotrans" "$bin/audiotrans"
ln -sfn "$repo/bin/textrans" "$bin/textrans"
ln -sfn "$repo/man/audiotrans.1" "$man1/audiotrans.1"
for a in textrans es en cbes cben pses psen mes men ses sen; do
    echo ".so man1/audiotrans.1" > "$man1/$a.1"
done

echo
echo "Listo. Para los alias (es, en, mes, ses, cbes, pses...), agrega a ~/.bashrc:"
echo "    source $repo/alias.sh"
echo "El modelo de Whisper (small, ~460 MB) se descarga la primera vez que uses audiotrans."
