"""Descarga de OpenSubtitles los subtítulos de un video, para practicar cuando no trae .srt.

Uso: subtitulos.py <video> <salida.srt> [idioma]
Busca primero por el hash del archivo (el mismo video, así que casi no hay desfase) y, si no
hay, por serie, temporada y episodio sacados de la ruta: ~/Videos/white-collar/s1-e3.mp4 busca
"white collar" 1x03. La clave va en $AUDIOTRANS_DATOS/opensubtitles (api_key=..., y si hace
falta usuario=... y contrasena=... para la cuota de descargas).
"""
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request

from traduccion import DATOS

API = "https://api.opensubtitles.com/api/v1"
AGENTE = "audiotrans v1.0"  # OpenSubtitles rechaza peticiones sin User-Agent propio
CONFIG = os.path.join(DATOS, "opensubtitles")


def _config():
    datos = {}
    if os.path.isfile(CONFIG):
        for linea in open(CONFIG, encoding="utf-8"):
            clave, _, valor = linea.strip().partition("=")
            if valor:
                datos[clave.strip()] = valor.strip()
    if os.environ.get("OPENSUBTITLES_API_KEY"):
        datos["api_key"] = os.environ["OPENSUBTITLES_API_KEY"]
    if not datos.get("api_key"):
        sys.exit(f"subtitulos: falta la clave de OpenSubtitles; escribe api_key=<clave> en {CONFIG}")
    return datos


def _pedir(ruta, config, datos=None, token=None):
    cabeceras = {"Api-Key": config["api_key"], "User-Agent": AGENTE, "Accept": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    if datos is not None:
        cabeceras["Content-Type"] = "application/json"
        datos = json.dumps(datos).encode()
    pet = urllib.request.Request(API + ruta, data=datos, headers=cabeceras)
    try:
        with urllib.request.urlopen(pet, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"subtitulos: OpenSubtitles respondió {e.code}: {e.read().decode(errors='replace')[:300]}")


def hash_video(ruta):
    # Hash de OpenSubtitles: tamaño + suma de los primeros y últimos 64 KB como enteros de 64 bits
    tam = os.path.getsize(ruta)
    total = tam
    with open(ruta, "rb") as f:
        for inicio in (0, max(0, tam - 65536)):
            f.seek(inicio)
            bloque = f.read(65536)
            bloque += b"\0" * (-len(bloque) % 8)
            total += sum(struct.unpack(f"<{len(bloque) // 8}Q", bloque))
    return f"{total & 0xFFFFFFFFFFFFFFFF:016x}"


def episodio_de(ruta):
    # (título, temporada, episodio) a partir del nombre; sin título en el nombre, usa la carpeta
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    m = re.search(r"[sS](\d{1,2})[ ._-]*[eE](\d{1,3})", nombre) or re.search(r"\b(\d{1,2})x(\d{1,3})\b", nombre)
    titulo = nombre[: m.start()] if m else nombre
    titulo = re.sub(r"[._-]+", " ", titulo).strip()
    if not titulo:
        titulo = re.sub(r"[._-]+", " ", os.path.basename(os.path.dirname(os.path.abspath(ruta)))).strip()
    return titulo, (int(m.group(1)) if m else None), (int(m.group(2)) if m else None)


def buscar(config, **filtros):
    # La API pide los parámetros en orden alfabético y en minúsculas; si no, redirige
    params = urllib.parse.urlencode(sorted((k, str(v).lower()) for k, v in filtros.items() if v is not None))
    return _pedir(f"/subtitles?{params}", config).get("data", [])


def elegir(resultados, temporada, episodio):
    # Sin traducciones automáticas y del episodio correcto; primero los del mismo archivo, luego
    # los que no son para sordos (sin "[suspira]", que estorba al practicar) y los más descargados
    buenos = []
    for r in resultados:
        a = r["attributes"]
        d = a.get("feature_details") or {}
        if a.get("ai_translated") or a.get("machine_translated") or not a.get("files"):
            continue
        if temporada is not None and (d.get("season_number"), d.get("episode_number")) != (temporada, episodio):
            continue
        buenos.append(r)
    buenos.sort(key=lambda r: (bool(r["attributes"].get("moviehash_match")),
                               not r["attributes"].get("hearing_impaired"),
                               r["attributes"].get("download_count", 0)), reverse=True)
    return buenos[0] if buenos else None


def descargar(video, salida, idioma="en"):
    config = _config()
    titulo, temporada, episodio = episodio_de(video)
    resultados = [r for r in buscar(config, languages=idioma, moviehash=hash_video(video))
                  if r["attributes"].get("moviehash_match")]
    elegido = elegir(resultados, temporada, episodio)
    if not elegido:
        resultados = buscar(config, languages=idioma, query=titulo, season_number=temporada, episode_number=episodio)
        elegido = elegir(resultados, temporada, episodio)
    if not elegido:
        etiqueta = f"{titulo} {temporada}x{episodio:02d}" if temporada is not None else titulo
        sys.exit(f"subtitulos: no encontré subtítulos en '{idioma}' para {etiqueta}")

    a = elegido["attributes"]
    d = a.get("feature_details") or {}
    print(f"  {d.get('title') or d.get('movie_name')}: {a.get('release')} "
          f"({'mismo archivo' if a.get('moviehash_match') else 'otra versión'}, {a.get('download_count')} descargas)",
          file=sys.stderr)

    token = None
    if config.get("usuario") and config.get("contrasena"):
        token = _pedir("/login", config, {"username": config["usuario"], "password": config["contrasena"]})["token"]
    enlace = _pedir("/download", config, {"file_id": a["files"][0]["file_id"]}, token)
    pet = urllib.request.Request(enlace["link"], headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pet, timeout=30) as r:
        contenido = r.read()
    with open(salida, "wb") as f:
        f.write(contenido)
    if "remaining" in enlace:
        print(f"  quedan {enlace['remaining']} descargas hoy", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    descargar(sys.argv[1], sys.argv[2], *sys.argv[3:])
