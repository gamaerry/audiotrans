"""Práctica de speaking: graba del micrófono cómo repites una línea y la compara con el texto.

Uso: python -m audiotrans.hablar <origen> <texto> <duración de la línea en s> [<archivo para terminar>]
Graba hasta que dejas de hablar, o hasta que aparece <archivo para terminar> (lo crea la tecla s
de mpv), y escribe en stdout:
  línea 1: porcentaje de palabras de la línea que Whisper entendió
  línea 2: lo que entendió
  después, una por palabra de la línea: "ok<TAB>palabra" o "falta<TAB>palabra"
Whisper solo dice qué palabras se entienden, no qué tan nativo suena el acento. Las cifras
se comparan en palabras ("20" y "twenty" cuentan igual).
"""
import difflib
import os
import re
import subprocess
import sys
import threading

TASA = 16000
BLOQUE = TASA // 5     # se lee en bloques de 0.2 s
# s de silencio que terminan la grabación: al repetir se hacen pausas a media línea, y para no
# esperarlos otra s termina en el momento
PAUSA = 2.0
SIN_VOZ = 5            # s sin empezar a hablar tras los que se deja de grabar
GRABAR = ["pw-record", "--rate", str(TASA), "--channels", "1", "--format", "s16", "--raw", "-"]


# Cifras: el .srt y Whisper escriben "20" o "twenty" sin regla fija, así que las dos partes
# se pasan a palabras con num2words antes de comparar
CIFRA = re.compile(r"(?P<moneda>[$€£])?(?P<numero>\d+(?:[.,:]\d+)*)(?P<sufijo>st|nd|rd|th|º|ª|%)?", re.IGNORECASE)
MONEDAS = {
    "en": {"$": "dollars", "€": "euros", "£": "pounds"},
    "es": {"$": "dólares", "€": "euros", "£": "libras"},
    "fr": {"$": "dollars", "€": "euros", "£": "livres"},
}
POR_CIENTO = {"en": "percent", "es": "por ciento", "fr": "pour cent", "it": "per cento", "pt": "por cento", "de": "Prozent"}
# Abreviaturas que uno de los dos lados escribe completas ("Mrs." y "Missus"), ya normalizadas
ABREVIATURAS = {
    "en": {"mr": "mister", "mrs": "missus", "dr": "doctor", "ok": "okay", "vs": "versus"},
    "es": {"sr": "senor", "sra": "senora", "srta": "senorita", "dr": "doctor", "dra": "doctora", "ud": "usted", "uds": "ustedes"},
    "fr": {"mme": "madame", "mlle": "mademoiselle", "dr": "docteur"},
}


def _normalizar(palabra):
    from .alinear import normalizar  # importa faster-whisper: aquí, después de empezar a grabar
    return normalizar(palabra)


def _a_palabras(numero, idioma, ordinal=False):
    from num2words import num2words
    if ":" in numero:  # hora: 3:30 → three thirty; 3:00 → three
        horas, minutos = numero.split(":", 1)
        return _a_palabras(horas, idioma) + ("" if int(minutos) == 0 else " " + _a_palabras(minutos, idioma))
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", numero):  # 1,000 o 1.000: separador de miles
        valor = int(re.sub(r"[.,]", "", numero))
    elif re.search(r"[.,]", numero):  # 2.5 o 2,5: decimal
        valor = float(numero.replace(",", "."))
    else:
        valor = int(numero)
    if ordinal and isinstance(valor, int):
        return num2words(valor, lang=idioma, to="ordinal")
    if idioma == "en" and isinstance(valor, int) and 1100 <= valor <= 1999:
        return num2words(valor, lang=idioma, to="year")  # 1999 → nineteen ninety-nine
    texto = num2words(valor, lang=idioma)
    # "one hundred and five": en EE. UU. casi siempre se dice sin "and"
    return re.sub(r"\band\b", " ", texto) if idioma == "en" else texto


def partes(palabra, idioma=None):
    """Lo que se compara de una palabra: normalizada, separada en los guiones
    ("twenty-one" → twenty, one) y, si es una cifra, en palabras ("$5" → five, dollars)."""
    cifra = idioma and CIFRA.fullmatch(re.sub(r"^[^\w$€£]+|[^\w%]+$", "", palabra))
    if cifra:
        try:
            sufijo = (cifra["sufijo"] or "").lower()
            numero = cifra["numero"]
            hora = re.fullmatch(r"(\d{1,2})\.(\d{2})", numero)
            if hora and not cifra["moneda"] and not sufijo and int(hora[1]) <= 24 and int(hora[2]) < 60:
                numero = numero.replace(".", ":")  # Whisper escribe a veces la hora "3.30"
            texto = _a_palabras(numero, idioma, ordinal=sufijo not in ("", "%"))
            if sufijo == "%":
                texto += " " + POR_CIENTO.get(idioma, "")
            if cifra["moneda"]:
                texto += " " + MONEDAS.get(idioma, {}).get(cifra["moneda"], "")
            palabra = texto
        except (NotImplementedError, ValueError, OverflowError):
            pass  # idioma que num2words no tiene: la cifra se compara tal cual
    abreviaturas = ABREVIATURAS.get(idioma, {})
    return [abreviaturas.get(p, p) for p in (_normalizar(w) for w in re.split(r"[\s\-‐–—]+", palabra)) if p]


def comparar(esperado, oido, idioma=None):
    """Devuelve (porcentaje, [(palabra del texto, entendida)]): cada palabra de `esperado`
    (con su puntuación, tal como se muestra) y si aparece en orden en lo que se oyó.
    Una palabra que se compara en varias partes ("20" → twenty) cuenta si se oyeron todas."""
    texto = re.sub(r"<[^>]+>|\{[^}]*\}", "", esperado)
    visibles = [(p, partes(p, idioma)) for p in texto.split()]
    visibles = [(p, ps) for p, ps in visibles if ps]
    a = [(i, x) for i, (_, ps) in enumerate(visibles) for x in ps]
    b = [x for w in oido.split() for x in partes(w, idioma)]
    oidas = set()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [x for _, x in a], b, autojunk=False).get_opcodes():
        # replace con las mismas letras: la misma palabra unida o separada distinto en cada
        # lado ("corncakes" y "corn cakes", "T V" y "TV")
        if op == "equal" or (op == "replace" and "".join(x for _, x in a[i1:i2]) == "".join(b[j1:j2])):
            oidas.update(range(i1, i2))
    ok = [True] * len(visibles)
    for j, (i, _) in enumerate(a):
        if j not in oidas:
            ok[i] = False
    porcentaje = round(100 * sum(ok) / len(visibles)) if visibles else 0
    return porcentaje, [(p, o) for (p, _), o in zip(visibles, ok)]


def _morir_con_el_padre():
    # Cancelar en mpv mata este proceso con SIGKILL, que no deja correr el finally de grabar():
    # sin esto, pw-record quedaba huérfano con el micrófono abierto
    import ctypes
    import signal
    ctypes.CDLL(None).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG


def grabar(duracion, terminar=None):
    """Graba del micrófono (la fuente predeterminada) hasta una pausa o hasta que exista el
    archivo `terminar`. Devuelve float32 o None."""
    # Antes de importar, para no perder las primeras palabras
    proceso = subprocess.Popen(GRABAR, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, preexec_fn=_morir_con_el_padre)
    import numpy as np
    from . import whisper_corto
    from .frases import Segmentador

    maximo = min(2 * duracion + 3, whisper_corto.MAX_DURACION)
    segmentador = Segmentador(PAUSA, maximo)
    leido = 0
    try:
        while bloque := proceso.stdout.read(BLOQUE * 2):
            leido += len(bloque) // 2
            ya = bool(terminar) and os.path.exists(terminar)
            frase = segmentador.agregar(np.frombuffer(bloque, np.int16).astype(np.float32) / 32768, fin=ya)
            if ya:
                return frase
            if frase is not None:
                return frase
            if leido >= SIN_VOZ * TASA and len(segmentador.buf) <= TASA // 2:
                return None  # sin voz, el segmentador solo guarda medio segundo
        return segmentador.agregar(np.zeros(0, np.float32), fin=True)  # se acabó el audio
    finally:
        proceso.kill()
        proceso.wait()


def ventana_min(origen):
    # En inglés la ventana ajustada marcó en rojo las mismas palabras que la de 15 s (21 de 753
    # en 60 frases de LibriSpeech dichas bien, de 1.5 a 8 s) y tarda 0.67 s en vez de 1.21 s.
    # En español la ajustada se equivoca más (ver whisper_corto.py), y los demás no se midieron
    return 0 if origen == "en" else 15


def principal(origen, esperado, duracion, terminar=None):
    # Las importaciones y el modelo tardan más de 1 s: se cargan mientras ya se graba, para
    # no perder las primeras palabras
    modelo = {}

    def cargar():
        from . import whisper_corto
        modelo["m"] = whisper_corto.cargar()

    hilo = threading.Thread(target=cargar, daemon=True)
    hilo.start()
    try:
        audio = grabar(duracion, terminar)
    finally:
        if terminar and os.path.exists(terminar):
            os.remove(terminar)
    if audio is None or len(audio) == 0:
        sys.exit("no se escuchó nada")
    hilo.join()
    from . import whisper_corto
    # Sin la línea como contexto: Whisper la "oiría" aunque no se dijera bien
    oido, _ = whisper_corto.transcribir(modelo["m"], audio, origen, beam_size=5, ventana_min=ventana_min(origen))
    if not oido:
        sys.exit("no se escuchó nada")
    porcentaje, palabras = comparar(esperado, oido, origen)
    print(porcentaje)
    print(oido.replace("\n", " "))
    for palabra, ok in palabras:
        print(f"{'ok' if ok else 'falta'}\t{palabra}")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    principal(sys.argv[1], sys.argv[2], float(sys.argv[3]), *sys.argv[4:])
