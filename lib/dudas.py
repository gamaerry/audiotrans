"""Registro de las dudas de listening: cada línea guardada con su audio, para repasarla después.

Uso: dudas.py guardar <video> <inicio> <fin> <texto> <origen> <destino>
     dudas.py listar
Las dudas quedan en $AUDIOTRANS_DATOS/dudas/: dudas.jsonl y un .mp3 por línea.
"""
import datetime
import json
import os
import re
import subprocess
import sys

from traduccion import DATOS, traducir

CARPETA = os.path.join(DATOS, "dudas")
REGISTRO = os.path.join(CARPETA, "dudas.jsonl")
MARGEN = 0.3  # s de audio antes y después de la línea, para no cortar palabras


def guardar(video, inicio, fin, texto, origen, destino):
    inicio, fin = float(inicio), float(fin)
    episodio = os.path.splitext(os.path.basename(video))[0]
    ident = f"{re.sub(r'[^A-Za-z0-9_-]', '_', episodio)}-{inicio:07.1f}"
    os.makedirs(os.path.join(CARPETA, "audio"), exist_ok=True)
    audio = os.path.join("audio", f"{ident}.mp3")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, inicio - MARGEN):.3f}", "-i", video,
         "-t", f"{fin - inicio + 2 * MARGEN:.3f}", "-vn", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "4",
         os.path.join(CARPETA, audio)],
        check=True,
    )
    duda = {
        "id": ident,
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "episodio": episodio,
        "inicio": round(inicio, 2),
        "fin": round(fin, 2),
        "texto": texto,
        "traduccion": traducir(texto.replace("\n", " "), origen, destino),
        "audio": audio,
    }
    with open(REGISTRO, "a") as f:
        f.write(json.dumps(duda, ensure_ascii=False) + "\n")
    minuto = f"{int(inicio // 60)}:{int(inicio % 60):02d}"
    print(f"{episodio} {minuto}")


def leer():
    if not os.path.exists(REGISTRO):
        return []
    with open(REGISTRO) as f:
        return [json.loads(l) for l in f if l.strip()]


def listar():
    for d in leer():
        minuto = f"{int(d['inicio'] // 60)}:{int(d['inicio'] % 60):02d}"
        print(f"\033[2m{d['episodio']} {minuto}\033[0m  {d['texto'].replace(chr(10), ' / ')}\n    {d['traduccion']}")


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    if accion == "guardar" and len(sys.argv) == 8:
        guardar(*sys.argv[2:])
    elif accion == "listar":
        listar()
    else:
        sys.exit(__doc__)
