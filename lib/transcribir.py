"""Transcribe una grabación y muestra el texto con su traducción.

Uso: transcribir.py <wav> <origen|""> <destino>
"""
import os
import sys

import numpy as np
from faster_whisper import WhisperModel, decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps

import whisper_corto
from traduccion import traducir

wav, origen, destino = sys.argv[1], sys.argv[2] or None, sys.argv[3]
beam = 5 if os.environ.get("AUDIOTRANS_RAPIDO") == "1" else 10

# 4 hilos por defecto: en un i3-N305 (8 núcleos eficientes en 2 bloques de 4) más hilos resultaron más lentos
modelo = WhisperModel(os.environ.get("AUDIOTRANS_MODEL", "small"), device="cpu", compute_type="int8", cpu_threads=int(os.environ.get("AUDIOTRANS_HILOS", 4)))
audio = decode_audio(wav)
voz = get_speech_timestamps(audio, VadOptions(speech_pad_ms=600))
audio = np.concatenate([audio[v["start"]:v["end"]] for v in voz]) if voz else audio[:0]

if len(audio) == 0:
    texto, idioma = "", origen
elif len(audio) <= whisper_corto.MAX_DURACION * whisper_corto.TASA:
    # Aquí importa más la precisión que la velocidad: ventana de al menos 15 s
    texto, idioma = whisper_corto.transcribir(modelo, audio, origen, beam, ventana_min=15)
else:
    segmentos, info = modelo.transcribe(audio, language=origen, beam_size=beam, condition_on_previous_text=False)
    texto, idioma = " ".join(s.text.strip() for s in segmentos).strip(), info.language

if not texto:
    print("(no se escuchó nada)")
else:
    print(f"\033[2m{texto}\033[0m")
    # Con el idioma detectado por Whisper se usa el modelo local aunque no se indicara -<origen>
    print(traducir(texto, idioma, destino))
