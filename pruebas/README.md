# Pruebas de precisión

Miden el error por palabra (WER) del modo `-r` con voz humana real y su transcripción de referencia: [Mini LibriSpeech](https://www.openslr.org/31/), de dominio público (CC-BY 4.0).

```bash
D=$(mktemp -d)
curl -L https://www.openslr.org/resources/31/dev-clean-2.tar.gz | tar xz -C $D
PY=~/.local/share/audiotrans/venv/bin/python
$PY pruebas/preparar.py $D $D/flujos
$PY pruebas/simular.py $D/flujos '[
  {"nombre": "normal (-r)",   "pausa": 0.5, "max": 10, "ctx": 1, "ventana": 0},
  {"nombre": "preciso (-r -p)", "pausa": 0.8, "max": 15, "ctx": 1, "ventana": 15}
]' ',-ruido'
```

`preparar.py` une unos 2.5 min de frases seguidas de tres lectores, con pausas de 0.25–0.6 s como en una plática, y hace una copia con ruido rosa 10 dB por debajo de la voz. `simular.py` pasa el audio por el mismo `Segmentador` y el mismo `whisper_corto` que el modo `-r`, en bloques de 0.2 s y sin esperar, así que ~8 min de voz se evalúan en ~1–3 min por configuración.

Usa toda la CPU: no midas tiempos con la máquina ocupada.

## Sincronización de subtítulos

`desfase_srt.py video.mp4 original.srt sincronizado.srt` mide, en 8 zonas del episodio, cuánto se adelanta o se atrasa cada `.srt` respecto a la voz. Usa las marcas por palabra de Whisper. Con White Collar 1x01, el original iba −1.2 a −1.4 s, `ffsubsync` (un solo desplazamiento) dejaba −0.1 a −0.33 s, y `lib/sincronizar.py` (por tramos) dejó −0.15 a +0.07 s.
