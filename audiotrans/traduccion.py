"""Traducción local con OPUS-MT para los pares instalados en modelos/, y con Google para el resto.

Uso: python -m audiotrans.traduccion <origen> <destino> < líneas
Traduce cada renglón de stdin en un solo lote y escribe su traducción en el mismo renglón
(lo usa mpv/audiotrans.lua para la tecla C de practice).
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

DATOS = os.environ.get("AUDIOTRANS_DATOS") or os.path.expanduser("~/.local/share/audiotrans")
MODELOS = os.path.join(DATOS, "modelos")
EN_LINEA = os.environ.get("AUDIOTRANS_EN_LINEA") == "1"
PARES = ("en-es", "es-en")  # los que audiotrans --setup instala
_cargados = {}
_avisado = False


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


def _oraciones(texto):
    # OPUS-MT se entrenó con oraciones sueltas: se traducen por separado y en un solo lote
    return [o for o in re.split(r"(?<=[.!?…])\s+", texto.strip()) if o]


def _local(texto, origen, destino):
    return _local_lote([texto], origen, destino)[0]


def _local_lote(textos, origen, destino):
    traductor, sp_origen, sp_destino = _modelo(f"{origen}-{destino}")
    partes = [_oraciones(t) for t in textos]
    r = traductor.translate_batch([sp_origen.encode(o, out_type=str) for p in partes for o in p], beam_size=4)
    traducidas = iter(sp_destino.decode(x.hypotheses[0]) for x in r)
    return [" ".join(next(traducidas) for _ in p) for p in partes]


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


def traducir_lote(textos, origen, destino):
    """Como traducir() con cada texto, pero con el modelo local van todos en un lote (1x02 completo:
    18 s). El relleno del lote a veces cambia la variante elegida (2 de 150 líneas en 1x02)."""
    if origen != destino and not EN_LINEA and hay_local(origen, destino):
        return _local_lote(textos, origen, destino)
    return [traducir(t, origen, destino) for t in textos]


def traducir(texto, origen, destino, supuesto=None):
    """supuesto: idioma a usar con el modelo local si no se sabe el origen y no hay conexión."""
    if origen == destino:
        return texto
    if not EN_LINEA and hay_local(origen, destino):
        return _local(texto, origen, destino)
    global _avisado
    par = f"{origen or supuesto}-{destino}"
    if not EN_LINEA and par in PARES and not os.path.isdir(os.path.join(MODELOS, par)) and not _avisado:
        # Sin esto, quien no corrió --setup creería que traduce sin internet
        print("audiotrans: faltan los traductores locales (audiotrans --setup); uso Google", file=sys.stderr)
        _avisado = True
    traducido = _google(texto, origen, destino)
    if traducido is None and not origen and hay_local(supuesto, destino):
        traducido = _local(texto, supuesto, destino)
    return traducido or "(sin traducción: no hay modelo local ni conexión)"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    for traducido in traducir_lote([l.rstrip("\n") for l in sys.stdin], sys.argv[1], sys.argv[2]):
        print(" ".join((traducido or "").split()))
