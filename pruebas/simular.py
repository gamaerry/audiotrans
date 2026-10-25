"""Simula el modo -r sobre flujos con referencia y mide error por palabra (WER) y retraso.

Uso: simular.py <carpeta de preparar.py> '<configuraciones JSON>' '<variantes>'
  configuraciones: [{"nombre": "...", "pausa": 0.5, "max": 10, "ctx": 1, "ventana": 0}, ...]
  variantes: "" (limpio), "-ruido" o ",-ruido" (ambas)
Usa el mismo Segmentador y whisper_corto que el modo -r, pero sin esperar en tiempo real.
"""
import glob, os, re, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import numpy as np
import whisper_corto
from frases import Segmentador
from faster_whisper import WhisperModel

FLUJOS = sys.argv[1]
CONFIGS = json.loads(sys.argv[2])  # [{"nombre":..., "pausa":..., "max":..., "ctx":0/1, "ventana":...}, ...]
VARIANTES = sys.argv[3].split(",")  # "" (limpio) y/o "-ruido"
modelo = WhisperModel(os.environ.get("AUDIOTRANS_MODEL", "small"), device="cpu", compute_type="int8",
                      cpu_threads=int(os.environ.get("AUDIOTRANS_HILOS", 4)))

def normalizar(t):
    return re.sub(r"[^a-z0-9' ]", " ", t.lower().replace("-", " ")).split()

def wer(ref, hip):
    r, h = normalizar(ref), normalizar(hip)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / len(r)

for c in CONFIGS:
    for var in VARIANTES:
        errores, tiempos, frases_dur = [], [], []
        for npy in sorted(glob.glob(f"{FLUJOS}/*{var}.npy")):
            if var == "" and "-ruido" in npy: continue
            audio = np.load(npy); ref = open(npy.replace("-ruido", "").replace(".npy", ".txt")).read()
            seg = Segmentador(c["pausa"], c["max"]); hip, ctx = [], []
            for i in range(0, len(audio), 3200):
                fin = i + 3200 >= len(audio)
                frase = seg.agregar(audio[i:i + 3200], fin)
                if frase is None: continue
                t = time.perf_counter()
                txt, _ = whisper_corto.transcribir(modelo, frase, "en", ventana_min=c["ventana"],
                                                   contexto=" ".join(ctx[-2:]) if c["ctx"] else "")
                tiempos.append(time.perf_counter() - t); frases_dur.append(len(frase) / 16000)
                if txt: hip.append(txt); ctx.append(txt)
            errores.append(wer(ref, " ".join(hip)))
        print(f"{c['nombre']:28} {'ruido ' if var else 'limpio'} WER {100*np.mean(errores):5.1f}%  "
              f"(por flujo: {', '.join(f'{100*e:.1f}' for e in errores)})  "
              f"transcribir: mediana {np.median(tiempos):.2f}s, p90 {np.percentile(tiempos,90):.2f}s  "
              f"frases: {len(tiempos)}, duración mediana {np.median(frases_dur):.1f}s", flush=True)
