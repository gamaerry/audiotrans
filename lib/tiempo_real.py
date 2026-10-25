"""Transcribe y traduce en tiempo real audio PCM (s16, 16 kHz, mono) leído de stdin.

Uso: tiempo_real.py <origen|""> <destino>
Cada frase se cierra al detectar una pausa y se traduce mientras se sigue escuchando.
"""
import os
import queue
import sys
import threading

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.vad import VadOptions, get_speech_timestamps

import whisper_corto
from traduccion import precargar, traducir

TASA = 16000
BLOQUE = TASA // 5    # se lee audio en bloques de 0.2 s
RAPIDO = os.environ.get("AUDIOTRANS_RAPIDO") == "1"
PAUSA = 0.35 if RAPIDO else 0.5  # s de silencio después de la voz que cierran una frase
MAX_FRASE = 10        # s; una frase más larga se manda aunque no haya pausa
MARGEN = 0.2          # s de audio que el VAD deja alrededor de la voz

origen = sys.argv[1] or None
destino = sys.argv[2]
# 4 hilos por defecto: en un i3-N305 (8 núcleos eficientes en 2 bloques de 4) más hilos resultaron más lentos
modelo = WhisperModel(os.environ.get("AUDIOTRANS_MODEL", "small"), device="cpu", compute_type="int8", cpu_threads=int(os.environ.get("AUDIOTRANS_HILOS", 4)))
vad = VadOptions(min_silence_duration_ms=int(PAUSA * 1000), speech_pad_ms=int(MARGEN * 1000))

audio = queue.Queue()
frases = queue.Queue()


def leer():
    # Hilo aparte para vaciar la tubería aunque Whisper esté ocupado
    while bloque := sys.stdin.buffer.read(BLOQUE * 2):
        audio.put(np.frombuffer(bloque, np.int16).astype(np.float32) / 32768)
    audio.put(None)


def mostrar():
    # Un solo hilo para que las traducciones salgan en orden
    while (frase := frases.get()) is not None:
        texto, idioma = frase
        print(f"\033[2m{texto}\033[0m\n{traducir(texto, idioma, destino)}\n", flush=True)


def transcribir(frase):
    texto, idioma = whisper_corto.transcribir(modelo, frase, origen)
    if texto:
        frases.put((texto, idioma))


def main():
    threading.Thread(target=leer, daemon=True).start()
    precargar(origen, destino)
    traductor = threading.Thread(target=mostrar, daemon=True)
    traductor.start()
    print("\033[31m●\033[0m Escuchando en tiempo real... (Ctrl+C para salir)\n", file=sys.stderr, flush=True)

    buf = np.zeros(0, np.float32)
    fin_audio = False
    while not fin_audio:
        bloques = [audio.get()]
        while not audio.empty():  # alcanzar lo que llegó mientras se transcribía
            bloques.append(audio.get())
        if bloques[-1] is None:
            fin_audio = True
            bloques.pop()
        buf = np.concatenate([buf, *bloques])

        voz = get_speech_timestamps(buf, vad)
        if not voz:
            buf = buf[-TASA // 2:]  # sin voz: conservar solo medio segundo
            continue
        fin_voz = voz[-1]["end"]
        if fin_audio or len(buf) - fin_voz >= (PAUSA - MARGEN) * TASA:
            corte = fin_voz
        elif len(buf) >= MAX_FRASE * TASA:
            corte = len(buf)
        else:
            continue
        transcribir(buf[voz[0]["start"]:corte])
        buf = buf[corte:]

    frases.put(None)
    traductor.join()


try:
    main()
except KeyboardInterrupt:
    # Salida inmediata: el hilo lector sigue bloqueado leyendo stdin
    sys.stdout.flush()
    os._exit(0)
