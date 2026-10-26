"""Ubica cada línea de un .srt ya sincronizado en el audio, palabra por palabra, con Whisper.

Uso: python -m audiotrans.alinear <video> <srt sincronizado> <salida.json> <salida.srt> [idioma]

Aun sincronizado por tramos, cada línea del .srt tiene su propio error (hasta ~1 s), así
que practice usa márgenes amplios al repetir. Aquí se transcribe el episodio entero con
marcas por palabra y se buscan la primera y la última palabra de cada línea cerca de donde
dice el .srt. Las líneas que se encuentran quedan con su tiempo exacto; las demás (canciones,
números, frases que Whisper oyó distinto) conservan el del .srt. Tarda ~6 min por episodio en
CPU (White Collar 1x01: 5 min 55 s, 74 % de las líneas exactas), por eso se hace con
anticipación (practice --prepare) y no al ver el episodio.
"""
import json
import os
import re
import subprocess
import sys
import unicodedata

import numpy as np
from faster_whisper import WhisperModel

from .sincronizar import formato, leer_srt

BUSQUEDA = 3.0  # s alrededor de la línea en los que se buscan sus palabras


def normalizar(palabra):
    # Sin acentos ni puntuación, para que "été" del .srt coincida con "ete" o "été" de Whisper
    sin_acentos = "".join(c for c in unicodedata.normalize("NFKD", palabra.lower()) if not unicodedata.combining(c))
    return re.sub(r"[^\w']|_", "", sin_acentos)


def palabras_de(texto):
    texto = re.sub(r"<[^>]+>|\{[^}]*\}", "", texto)
    return [p for p in (normalizar(w) for w in texto.split()) if p]


def transcribir(video, idioma):
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    modelo = WhisperModel(os.environ.get("AUDIOTRANS_MODEL", "small"), device="cpu", compute_type="int8",
                          cpu_threads=int(os.environ.get("AUDIOTRANS_HILOS", 4)))
    # beam 1: 23 % más rápido que el 5 por defecto, casi las mismas líneas exactas y los
    # inicios más cerca de los de Whisper medium (ver README, descubrimiento 6)
    segmentos, _ = modelo.transcribe(audio, language=idioma, word_timestamps=True, beam_size=1,
                                     condition_on_previous_text=False, vad_filter=True)
    total, palabras = len(audio) / 16000, []
    for s in segmentos:
        palabras += [(normalizar(w.word), w.start, w.end) for w in s.words if normalizar(w.word)]
        print(f"\r  transcribiendo: {100 * s.end / total:3.0f} %", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return palabras


def coincidencias(palabras, j, buscadas, sentido):
    """Cuántas de `buscadas` coinciden con las palabras desde j hacia adelante (1) o hacia atrás (-1)."""
    n = 0
    for k, b in enumerate(buscadas):
        i = j + sentido * k
        if 0 <= i < len(palabras) and palabras[i][0] == b:
            n += 1
    return n


def alinear_linea(palabras, tiempos, inicio, fin, texto):
    """Devuelve (inicio, fin, inicio_exacto, fin_exacto)."""
    ws = palabras_de(texto)
    if not ws:
        return inicio, fin, False, False
    a = np.searchsorted(tiempos, inicio - BUSQUEDA)
    b = np.searchsorted(tiempos, fin + BUSQUEDA)
    minimo = min(2, len(ws))  # dos palabras seguidas iguales, o la única si la línea es de una

    nuevo_inicio, j_inicio = inicio, None
    mejor = None
    for j in range(a, b):
        n = coincidencias(palabras, j, ws[:3], 1)
        if n >= minimo:
            clave = (n, -abs(palabras[j][1] - inicio))
            if mejor is None or clave > mejor:
                mejor, j_inicio = clave, j
    if j_inicio is not None:
        nuevo_inicio = palabras[j_inicio][1]

    nuevo_fin, j_fin = fin, None
    mejor = None
    for j in range(j_inicio if j_inicio is not None else a, b):
        n = coincidencias(palabras, j, ws[::-1][:3], -1)
        if n >= minimo and palabras[j][2] > nuevo_inicio:
            clave = (n, -abs(palabras[j][2] - fin))
            if mejor is None or clave > mejor:
                mejor, j_fin = clave, j
    if j_fin is not None:
        nuevo_fin = palabras[j_fin][2]

    if nuevo_fin - nuevo_inicio < 0.2 or nuevo_fin - nuevo_inicio > (fin - inicio) + 2 * BUSQUEDA:
        return inicio, fin, False, False  # emparejamiento dudoso: mejor el tiempo del .srt
    return nuevo_inicio, nuevo_fin, j_inicio is not None, j_fin is not None


def alinear(video, srt, salida_json, salida_srt, idioma="en"):
    palabras = transcribir(video, idioma)
    tiempos = np.array([p[1] for p in palabras])
    lineas = []
    for inicio, fin, texto in leer_srt(srt):
        i, f, ie, fe = alinear_linea(palabras, tiempos, inicio, fin, texto)
        texto_limpio = re.sub(r"<[^>]+>|\{[^}]*\}", "", texto).strip()
        lineas.append({"inicio": round(i, 3), "fin": round(f, 3), "texto": texto_limpio,
                       "inicio_exacto": ie, "fin_exacto": fe})
    with open(salida_json, "w") as f:
        json.dump({"lineas": lineas}, f, ensure_ascii=False)
    with open(salida_srt, "w") as f:
        for n, l in enumerate(lineas, 1):
            f.write(f"{n}\n{formato(l['inicio'])} --> {formato(l['fin'])}\n{l['texto']}\n\n")
    exactas = sum(l["inicio_exacto"] and l["fin_exacto"] for l in lineas)
    print(f"  {exactas} de {len(lineas)} líneas con tiempo exacto")


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6):
        sys.exit(__doc__)
    alinear(*sys.argv[1:])
