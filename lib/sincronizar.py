"""Sincroniza un .srt con el audio del video, por tramos.

Uso: sincronizar.py <video> <srt> <salida.srt>

Un solo desplazamiento no basta: si la versión del video tiene un corte o una pausa
distinta, el desfase cambia a lo largo del episodio (en White Collar 1x01 iba de -1.3 s
a -0.1 s). Se marca dónde hay voz con el VAD, y en ventanas de VENTANA segundos, cada
PASO, se busca el desplazamiento que mejor encima los subtítulos sobre la voz. Cada
línea toma el desplazamiento de su zona, interpolado entre ventanas.

Cada ventana busca cerca del desfase de la anterior y no cerca de 0, porque en una versión
de TV con los cortes comerciales recortados el desfase se acumula: en el .srt HDTV de
White Collar 1x02 sube ~2.5 s en cada corte, hasta +10.4 s al final.
"""
import re
import subprocess
import sys

import numpy as np
from faster_whisper.vad import VadOptions, get_speech_timestamps

TASA = 16000
RES = 100           # muestras por segundo de las señales de voz y subtítulos
VENTANA = 300       # s de audio que se comparan para estimar cada desfase
PASO = 60           # s entre una ventana y la siguiente
MAX_DESFASE = 8     # s: cuánto puede cambiar el desfase de una ventana a la siguiente

PATRON = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def leer_srt(ruta):
    """Devuelve [(inicio, fin, línea de tiempos original, resto del bloque)]."""
    texto = open(ruta, encoding="utf-8-sig", errors="replace").read().replace("\r", "")
    bloques = []
    for bloque in re.split(r"\n\s*\n", texto.strip()):
        m = PATRON.search(bloque)
        if m:
            g = [int(x) for x in m.groups()]
            inicio = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            fin = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            bloques.append((inicio, fin, bloque[m.end():].strip("\n")))
    return bloques


def formato(t):
    t = max(0.0, t)
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def senal_voz(video):
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(TASA), "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    voz = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=100, speech_pad_ms=0))
    s = np.zeros(int(len(audio) / TASA * RES) + 1, np.float32)
    for v in voz:
        s[v["start"] * RES // TASA:v["end"] * RES // TASA] = 1
    return s


def senal_subtitulos(bloques, largo):
    s = np.zeros(largo, np.float32)
    for inicio, fin, _ in bloques:
        s[int(inicio * RES):int(fin * RES)] = 1
    return s


def desfases(voz, subs):
    """[(centro de la ventana en s, desfase en s)]: cuánto hay que sumar a los subtítulos."""
    # Señales centradas: así una zona sin voz ni subtítulos no favorece ningún desplazamiento
    voz_c, subs_c = voz - voz.mean(), subs - subs.mean()
    m = MAX_DESFASE * RES
    previo = 0  # cada ventana busca alrededor del desfase de la anterior, en muestras
    resultado = []
    for centro in range(VENTANA // 2, int(len(voz) / RES) - VENTANA // 2 + PASO, PASO):
        a = max(abs(previo) + m, (centro - VENTANA // 2) * RES)
        b = min(len(voz) - abs(previo) - m, (centro + VENTANA // 2) * RES)
        if b - a < RES * 60 or subs[a:b].sum() < RES * 10:
            continue  # ventana muy corta o casi sin diálogo
        # correlación de la voz con los subtítulos desplazados `d` muestras
        rango = range(previo - m, previo + m + 1)
        correl = [np.dot(voz_c[a:b], subs_c[a - d:b - d]) for d in rango]
        i = int(np.argmax(correl))
        if i in (0, len(rango) - 1):
            # En el borde no es una medición: seguramente emparejó con otra escena
            print(f"sincronizar: min {centro / 60:.1f} sin desfase claro, se omite", file=sys.stderr)
            continue
        previo = rango[i]
        resultado.append((centro, previo / RES))
    return resultado


def ajustar(bloques, voz):
    """Devuelve los bloques desplazados y [(centro, desfase)] de cada tramo."""
    estimados = desfases(voz, senal_subtitulos(bloques, len(voz)))
    if not estimados:
        raise SystemExit("sincronizar: no hay suficiente diálogo para estimar el desfase")
    centros = np.array([c for c, _ in estimados], float)
    # Mediana de 3 ventanas vecinas: quita estimaciones sueltas que se salen (música, efectos)
    crudos = np.array([d for _, d in estimados])
    suaves = np.array([np.median(crudos[max(0, i - 1):i + 2]) for i in range(len(crudos))])
    ajustados = []
    for inicio, fin, resto in bloques:
        d = float(np.interp((inicio + fin) / 2, centros, suaves))
        ajustados.append((inicio + d, fin + d, resto))
    return ajustados, list(zip(centros, suaves))


def coincidencia(voz, bloques):
    """Correlación entre la voz y los subtítulos: 1 si coinciden del todo, 0 si no tienen relación."""
    return float(np.corrcoef(voz, senal_subtitulos(bloques, len(voz)))[0, 1])


def sincronizar(video, srt, salida):
    ajustados, tramos = ajustar(leer_srt(srt), senal_voz(video))
    with open(salida, "w") as f:
        for n, (inicio, fin, resto) in enumerate(ajustados, 1):
            f.write(f"{n}\n{formato(inicio)} --> {formato(fin)}\n{resto}\n\n")
    return tramos


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    for centro, d in sincronizar(*sys.argv[1:]):
        print(f"min {centro / 60:5.1f}: {d:+.2f} s")
