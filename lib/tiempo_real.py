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

import whisper_corto
from frases import Segmentador
from traduccion import precargar, traducir

TASA = 16000
BLOQUE = TASA // 5    # se lee audio en bloques de 0.2 s
RAPIDO = os.environ.get("AUDIOTRANS_RAPIDO") == "1"
PRECISO = os.environ.get("AUDIOTRANS_PRECISO") == "1"
# Medido con voz real (Mini LibriSpeech) en pruebas/: error por palabra 14.9 % sin contexto,
# 8.8 % con contexto, 4.3 % (6.4 % con ruido) con -p
PAUSA = 0.35 if RAPIDO else 0.8 if PRECISO else 0.5  # s de silencio que cierran una frase
MAX_FRASE = 15 if PRECISO else 10  # s; una frase más larga se manda aunque no haya pausa
VENTANA = 15 if PRECISO else 0     # s mínimos de ventana del codificador (0: ajustada)
CONTEXTO = not RAPIDO              # pasar las frases anteriores como pista (no medido con base)

origen = sys.argv[1] or None
destino = sys.argv[2]
# 4 hilos por defecto: en un i3-N305 (8 núcleos eficientes en 2 bloques de 4) más hilos resultaron más lentos
modelo = WhisperModel(os.environ.get("AUDIOTRANS_MODEL", "small"), device="cpu", compute_type="int8", cpu_threads=int(os.environ.get("AUDIOTRANS_HILOS", 4)))

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


anteriores = []  # últimas frases transcritas, para dar contexto a la siguiente
idioma_anterior = None


def transcribir(frase):
    global idioma_anterior
    contexto = " ".join(anteriores[-2:]) if CONTEXTO else ""
    texto, idioma = whisper_corto.transcribir(modelo, frase, origen, ventana_min=VENTANA, contexto=contexto)
    if idioma != idioma_anterior:
        anteriores.clear()  # el contexto en otro idioma confundiría a Whisper
        idioma_anterior = idioma
    if texto:
        anteriores.append(texto)
        frases.put((texto, idioma))


def main():
    threading.Thread(target=leer, daemon=True).start()
    precargar(origen, destino)
    traductor = threading.Thread(target=mostrar, daemon=True)
    traductor.start()
    print("\033[31m●\033[0m Escuchando en tiempo real... (Ctrl+C para salir)\n", file=sys.stderr, flush=True)

    segmentador = Segmentador(PAUSA, MAX_FRASE)
    fin_audio = False
    while not fin_audio:
        bloques = [audio.get()]
        while not audio.empty():  # alcanzar lo que llegó mientras se transcribía
            bloques.append(audio.get())
        if bloques[-1] is None:
            fin_audio = True
            bloques.pop()
        frase = segmentador.agregar(np.concatenate([np.zeros(0, np.float32), *bloques]), fin_audio)
        if frase is not None:
            transcribir(frase)

    frases.put(None)
    traductor.join()


try:
    main()
except KeyboardInterrupt:
    # Salida inmediata: el hilo lector sigue bloqueado leyendo stdin
    sys.stdout.flush()
    os._exit(0)
