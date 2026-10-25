"""Arma flujos continuos de voz real (Mini LibriSpeech) con su texto de referencia.

Uso: preparar.py <carpeta con LibriSpeech/dev-clean-2> <carpeta de salida>
Genera, por lector, <nombre>.npy (limpio), <nombre>-ruido.npy (ruido rosa a 10 dB) y <nombre>.txt.
"""
import glob, os, sys
import numpy as np
from faster_whisper import decode_audio
L, salida = sys.argv[1], sys.argv[2]
rng = np.random.default_rng(0)
for capitulo in ["777/126732", "3752/4944", "1462/170142"]:
    d = f"{L}/LibriSpeech/dev-clean-2/{capitulo}"
    ref = dict(l.split(" ", 1) for l in open(glob.glob(f"{d}/*.trans.txt")[0]).read().splitlines())
    partes, textos, dur = [], [], 0
    for clave in sorted(ref):
        a = decode_audio(f"{d}/{clave}.flac")
        partes += [a, np.zeros(int(16000 * rng.uniform(0.25, 0.6)), np.float32)]  # pausa natural entre frases
        textos.append(ref[clave]); dur += len(a) / 16000
        if dur > 150: break
    a = np.concatenate(partes)
    nombre = capitulo.replace("/", "-")
    open(f"{salida}/{nombre}.txt", "w").write(" ".join(textos))
    np.save(f"{salida}/{nombre}.npy", a)
    # ruido de fondo tipo película: ruido rosa a 10 dB por debajo de la voz
    blanco = rng.standard_normal(len(a)); f = np.fft.rfftfreq(len(a)); f[0] = f[1]
    rosa = np.fft.irfft(np.fft.rfft(blanco) / np.sqrt(f), n=len(a)).astype(np.float32)
    rosa *= np.sqrt(np.mean(a**2) / np.mean(rosa**2)) / np.sqrt(10)
    np.save(f"{salida}/{nombre}-ruido.npy", (a + rosa).astype(np.float32))
    print(f"{nombre}: {len(a)/16000:.0f} s, {len(textos)} frases, {len(' '.join(textos).split())} palabras")
