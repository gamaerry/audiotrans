"""Mide el desfase entre uno o más .srt y el audio del video, en varias zonas del episodio.

Uso: desfase_srt.py <video> <srt> [<srt> ...]
Para cada línea del .srt busca sus tres primeras palabras en las marcas por palabra de
Whisper y compara cuándo empiezan. Negativo: el subtítulo aparece antes que la voz.
Los inicios de segmento de Whisper (sin marcas por palabra) son demasiado imprecisos
para esto: llegaron a sugerir un desfase que cambiaba cuando en realidad era constante.
"""
import re, subprocess, sys, statistics
import numpy as np
from faster_whisper import WhisperModel
video, srts = sys.argv[1], sys.argv[2:]
def leer(srt):
    txt = open(srt, encoding="utf-8-sig").read().replace("\r", "")
    out = []
    for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+) --> [^\n]*\n(.*?)(?:\n\n|\Z)", txt, re.S):
        h, mi, s, ms, t = m.groups()
        t = re.sub(r"<[^>]+>|\{[^}]*\}", "", t).replace("\n", " ").lower()
        out.append((int(h)*3600+int(mi)*60+int(s)+int(ms)/1000, re.sub(r"[^a-z' ]", " ", t).split()))
    return out
subs = {s: leer(s) for s in srts}
modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
norm = lambda w: re.sub(r"[^a-z']", "", w.lower())
duracion = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                                capture_output=True, text=True).stdout)
for zona in np.linspace(240, duracion - 240, 8).astype(int):
    pcm = subprocess.run(["ffmpeg","-v","error","-ss",str(zona),"-t","90","-i",video,"-vn","-ac","1","-ar","16000","-f","s16le","-"],capture_output=True).stdout
    a = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    segs, _ = modelo.transcribe(a, language="en", word_timestamps=True, condition_on_previous_text=False, vad_filter=True)
    pal = [(norm(w.word), zona + w.start) for s in segs for w in s.words]
    fila = f"min {zona/60:5.1f}:"
    for srt, lineas in subs.items():
        ds = []
        for inicio, ws in lineas:
            if not (zona + 2 < inicio < zona + 88) or len(ws) < 3: continue
            # la primera palabra de la línea seguida de las otras dos, en el audio, cerca del inicio del .srt
            for i in range(len(pal) - 2):
                if [p for p, _ in pal[i:i+3]] == ws[:3] and abs(pal[i][1] - inicio) < 6:
                    ds.append(inicio - pal[i][1]); break
        fila += f"  {srt.split('/')[-1]:22} {statistics.median(ds):+.2f} s ({len(ds):2d} líneas)" if ds else f"  {srt.split('/')[-1]:22}  sin datos"
    print(fila, flush=True)
