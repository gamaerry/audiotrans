"""Registro de las dudas de listening: cada línea guardada con su audio, para repasarla después.

Uso: python -m audiotrans.dudas guardar <video> <inicio> <fin> <texto> <origen> <destino> [<inicio audio> <fin audio>]
     python -m audiotrans.dudas listar
Las dudas quedan en $AUDIOTRANS_DATOS/dudas/: dudas.jsonl y un .mp3 por línea.
"""
import datetime
import json
import os
import re
import subprocess
import sys

from .traduccion import DATOS, traducir

CARPETA = os.path.join(DATOS, "dudas")
REGISTRO = os.path.join(CARPETA, "dudas.jsonl")
# s de audio antes y después de la línea si mpv no indica otros (mpv/audiotrans.lua pasa los
# mismos que usa r): el .srt tiene errores por línea y empezar 0.9 s antes cubre el 95 %
MARGEN_INICIO = 0.9
MARGEN_FIN = 0.5


def guardar(video, inicio, fin, texto, origen, destino, audio_inicio=None, audio_fin=None):
    inicio, fin = float(inicio), float(fin)
    audio_inicio = max(0.0, float(audio_inicio) if audio_inicio else inicio - MARGEN_INICIO)
    audio_fin = float(audio_fin) if audio_fin else fin + MARGEN_FIN
    episodio = os.path.splitext(os.path.basename(video))[0]
    ident = f"{re.sub(r'[^A-Za-z0-9_-]', '_', episodio)}-{inicio:07.1f}"
    os.makedirs(os.path.join(CARPETA, "audio"), exist_ok=True)
    audio = os.path.join("audio", f"{ident}.mp3")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{audio_inicio:.3f}", "-i", video,
         "-t", f"{audio_fin - audio_inicio:.3f}", "-vn", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "4",
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
    if accion == "guardar" and len(sys.argv) in (8, 10):
        guardar(*sys.argv[2:])
    elif accion == "listar":
        listar()
    else:
        sys.exit(__doc__)
