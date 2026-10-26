"""Whisper con la ventana del codificador ajustada a la duración del audio.

faster-whisper siempre rellena el audio hasta 30 s, y el codificador (lo más caro en CPU)
procesa esos 30 s aunque la frase dure 3. Con la ventana ajustada, small pasa de ~2.2 s
a ~0.5 s por frase en esta máquina. En inglés la calidad es la misma; en español pierde
algo (con voz sintética: "llévaten para aguas" en vez de "llévate un paraguas"), que se
recupera con una ventana mínima de 15 s (~1.1 s). Solo sirve para audio de hasta
MAX_DURACION segundos; lo más largo se transcribe con faster-whisper normal.
"""
import re

import ctranslate2
import numpy as np

MAX_DURACION = 28
TASA = 16000
MAX_CONTEXTO = 100  # tokens del texto anterior que se le pasan a Whisper (admite hasta 223)


def _sin_bucle(texto):
    """'A b c. A b c. A b' -> 'A b c.': Whisper repitiendo la frase hasta el tope de tokens."""
    palabras = texto.split()
    # Sin puntuación ni mayúsculas: la última repetición suele quedar cortada y sin punto
    comparables = [re.sub(r"[^\w']", "", p).lower() for p in palabras]
    for n in range(3, len(palabras) // 2 + 1):  # desde 3 palabras, para no tocar "ja ja ja"
        if all(comparables[i] == comparables[i % n] for i in range(len(palabras))):
            return " ".join(palabras[:n])
    return texto


def transcribir(modelo, audio, idioma=None, beam_size=5, ventana_min=0, contexto=""):
    """Devuelve (texto, idioma). audio: float32 mono a 16 kHz. Texto vacío si no hay voz.

    ventana_min: segundos mínimos de ventana; más grande es más lento pero más preciso.
    contexto: texto anterior; Whisper lo usa como pista para nombres y el tema.
    """
    tok = modelo.hf_tokenizer
    caracteristicas = modelo.feature_extractor(audio)
    # 100 cuadros por segundo, con 1 s de margen; el codificador reduce los cuadros a la
    # mitad, así que deben ser pares
    cuadros = min(3000, max(caracteristicas.shape[-1] + 100, ventana_min * 100) // 2 * 2)
    caracteristicas = np.pad(caracteristicas, ((0, 0), (0, max(0, cuadros - caracteristicas.shape[-1]))))
    entrada = np.ascontiguousarray(caracteristicas[None, :, :cuadros], dtype=np.float32)
    codificado = modelo.model.encode(ctranslate2.StorageView.from_array(entrada), to_cpu=False)

    if not idioma:
        # Reutiliza lo ya codificado: detectar el idioma no cuesta otra pasada del codificador
        idioma = modelo.model.detect_language(codificado)[0][0][0][2:-2]

    inicio = [tok.token_to_id(t) for t in ("<|startoftranscript|>", f"<|{idioma}|>", "<|transcribe|>", "<|notimestamps|>")]
    if contexto:
        previo = tok.encode(" " + contexto.strip(), add_special_tokens=False).ids[-MAX_CONTEXTO:]
        inicio = [tok.token_to_id("<|startofprev|>"), *previo, *inicio]
    r = modelo.model.generate(
        codificado,
        [inicio],
        beam_size=beam_size,
        return_no_speech_prob=True,
        suppress_blank=True,
        suppress_tokens=[-1],
        # Con ventanas cortas Whisper a veces repite la frase en bucle; ~10 tokens por segundo
        # de audio sobra para cualquier ritmo de habla y corta esas repeticiones
        max_length=len(inicio) + int(len(audio) / TASA * 10) + 10,
    )[0]
    if r.no_speech_prob > 0.6:
        return "", idioma
    fin = tok.token_to_id("<|endoftext|>")
    return _sin_bucle(tok.decode([i for i in r.sequences_ids[0] if i < fin]).strip()), idioma
