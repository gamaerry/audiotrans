"""Traducción local con OPUS-MT para los pares instalados en modelos/, y con Google para el resto."""
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request

DATOS = os.environ.get("AUDIOTRANS_DATOS") or os.path.expanduser("~/.local/share/audiotrans")
MODELOS = os.path.join(DATOS, "modelos")
EN_LINEA = os.environ.get("AUDIOTRANS_EN_LINEA") == "1"
_cargados = {}


def _modelo(par):
    if par not in _cargados:
        import ctranslate2
        import sentencepiece as spm

        d = os.path.join(MODELOS, par)
        _cargados[par] = (
            ctranslate2.Translator(d, device="cpu", compute_type="int8", intra_threads=int(os.environ.get("AUDIOTRANS_HILOS", 4))),
            spm.SentencePieceProcessor(os.path.join(d, "source.spm")),
            spm.SentencePieceProcessor(os.path.join(d, "target.spm")),
        )
    return _cargados[par]


def hay_local(origen, destino):
    return bool(origen) and os.path.isdir(os.path.join(MODELOS, f"{origen}-{destino}"))


def precargar(origen, destino):
    # Evita que la primera frase espere a que se cargue el modelo
    if not EN_LINEA and hay_local(origen, destino):
        _modelo(f"{origen}-{destino}")


def _local(texto, origen, destino):
    traductor, sp_origen, sp_destino = _modelo(f"{origen}-{destino}")
    # OPUS-MT se entrenó con oraciones sueltas: se traducen por separado y en un solo lote
    oraciones = [o for o in re.split(r"(?<=[.!?…])\s+", texto.strip()) if o]
    r = traductor.translate_batch([sp_origen.encode(o, out_type=str) for o in oraciones], beam_size=4)
    return " ".join(sp_destino.decode(x.hypotheses[0]) for x in r)


def _google(texto, origen, destino):
    # Misma API de Google que usa trans, pero directa: ~0.1 s en vez de 1-12 s
    url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(
        {"client": "gtx", "sl": origen or "auto", "tl": destino, "dt": "t", "q": texto}
    )
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return "".join(p[0] for p in json.load(r)[0] if p[0])
    except Exception:
        r = subprocess.run(
            ["trans", "-4", *(["-s", origen] if origen else []), "-t", destino, "-b", texto],
            capture_output=True, text=True,
        )
        return r.stdout.strip() or None


def traducir(texto, origen, destino, supuesto=None):
    """supuesto: idioma a usar con el modelo local si no se sabe el origen y no hay conexión."""
    if origen == destino:
        return texto
    if not EN_LINEA and hay_local(origen, destino):
        return _local(texto, origen, destino)
    traducido = _google(texto, origen, destino)
    if traducido is None and not origen and hay_local(supuesto, destino):
        traducido = _local(texto, supuesto, destino)
    return traducido or "(sin traducción: no hay modelo local ni conexión)"
