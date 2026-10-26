"""Corta un flujo continuo de audio en frases, usando las pausas que detecta el VAD."""
import numpy as np
from faster_whisper.vad import VadOptions, get_speech_timestamps

TASA = 16000
MARGEN = 0.2  # s de audio que el VAD deja alrededor de la voz


class Segmentador:
    def __init__(self, pausa=0.5, max_frase=10):
        """pausa: s de silencio que cierran una frase; max_frase: s tras los que se corta igual."""
        self.pausa = pausa
        self.max_frase = max_frase
        self.vad = VadOptions(min_silence_duration_ms=int(pausa * 1000), speech_pad_ms=int(MARGEN * 1000))
        self.buf = np.zeros(0, np.float32)

    def agregar(self, audio, fin=False):
        """Agrega audio (float32 a 16 kHz). Devuelve la frase que se haya cerrado, o None."""
        self.buf = np.concatenate([self.buf, audio])
        voz = get_speech_timestamps(self.buf, self.vad)
        if not voz:
            self.buf = self.buf[-TASA // 2:]  # sin voz: conservar solo medio segundo
            return None
        fin_voz = voz[-1]["end"]
        if fin or len(self.buf) - fin_voz >= (self.pausa - MARGEN) * TASA:
            corte = fin_voz
        elif len(self.buf) >= self.max_frase * TASA:
            corte = len(self.buf)
        else:
            return None
        frase = self.buf[voz[0]["start"]:corte]
        self.buf = self.buf[corte:]
        return frase
