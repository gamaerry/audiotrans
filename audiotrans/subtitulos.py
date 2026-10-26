"""Descarga de OpenSubtitles los subtítulos de un video, para practicar cuando no trae .srt.

Uso: python -m audiotrans.subtitulos <video> <salida.srt> <IMDb ID> [idioma]
El IMDb ID es el de la serie o la película (practice lo toma de un archivo tt<número> en la
carpeta del video). Si el nombre del video tiene temporada y episodio (s1-e3, S01E03, 1x03), es
un episodio de esa serie; si no, la película. Busca primero por el hash del archivo (el mismo
video, así que casi no hay desfase) y, si no hay, por el IMDb ID. En ese caso baja hasta CANDIDATOS, uno por cada fuente (TV, WEB, DVD...),
porque las versiones de una misma fuente tienen los mismos cortes, y se queda con el que, ya
sincronizado, mejor coincide con la voz. La clave va en $AUDIOTRANS_DATOS/opensubtitles (api_key=..., y si hace
falta usuario=... y contrasena=... para la cuota de descargas).
"""
import json
import os
import re
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from .traduccion import DATOS

API = "https://api.opensubtitles.com/api/v1"
AGENTE = "audiotrans v1.0"  # OpenSubtitles rechaza peticiones sin User-Agent propio
CONFIG = os.path.join(DATOS, "opensubtitles")
CANDIDATOS = 3  # cada uno gasta una descarga de la cuota diaria


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
    # (temporada, episodio) a partir del nombre, o (None, None) si es una película
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    m = re.search(r"[sS](\d{1,2})[ ._-]*[eE](\d{1,3})", nombre) or re.search(r"\b(\d{1,2})x(\d{1,3})\b", nombre)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def de_la_obra(r, imdb):
    # El hash puede coincidir con otra obra (archivos idénticos mal etiquetados): se exige el ID
    d = r["attributes"].get("feature_details") or {}
    return imdb in (d.get("parent_imdb_id"), d.get("imdb_id"))


def buscar(config, **filtros):
    # La API pide los parámetros en orden alfabético y en minúsculas; si no, redirige
    params = urllib.parse.urlencode(sorted((k, str(v).lower()) for k, v in filtros.items() if v is not None))
    return _pedir(f"/subtitles?{params}", config).get("data", [])


def ordenar(resultados, temporada, episodio):
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
    return buenos


def fuente(release):
    # Las versiones de TV recortan los comerciales distinto que las de WEB o DVD
    for nombre, patron in (("tv", r"HDTV|PDTV|DSR"), ("web", r"WEB|AMZN|NF\b|HULU"),
                           ("disco", r"DVD|BLU-?RAY|BDRIP|BRRIP")):
        if re.search(patron, release or "", re.I):
            return nombre
    return "?"


def candidatos(ordenados):
    # El mejor de cada fuente, con las desconocidas al final; si hay menos fuentes que
    # CANDIDATOS, solo esos
    vistos, elegidos = set(), []
    for r in ordenados:
        f = fuente(r["attributes"].get("release"))
        if f not in vistos:
            vistos.add(f)
            elegidos.append(r)
    elegidos.sort(key=lambda r: fuente(r["attributes"].get("release")) == "?")
    return elegidos[:CANDIDATOS]


def describir(r):
    a = r["attributes"]
    d = a.get("feature_details") or {}
    return (f"{d.get('title') or d.get('movie_name')}: {a.get('release')} "
            f"({'mismo archivo' if a.get('moviehash_match') else 'otra versión'}, {a.get('download_count')} descargas)")


def bajar(r, salida, config, token):
    enlace = _pedir("/download", config, {"file_id": r["attributes"]["files"][0]["file_id"]}, token)
    pet = urllib.request.Request(enlace["link"], headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pet, timeout=30) as resp:
        contenido = resp.read()
    with open(salida, "wb") as f:
        f.write(contenido)
    return enlace.get("remaining")


def descargar(video, salida, imdb, idioma="en"):
    config = _config()
    imdb = int(re.sub(r"^tt", "", imdb))
    temporada, episodio = episodio_de(video)
    resultados = [r for r in buscar(config, languages=idioma, moviehash=hash_video(video))
                  if r["attributes"].get("moviehash_match") and de_la_obra(r, imdb)]
    ordenados = ordenar(resultados, temporada, episodio)
    if ordenados:
        elegidos = ordenados[:1]  # del mismo archivo: no hace falta comparar
    elif temporada is not None:
        resultados = buscar(config, languages=idioma, parent_imdb_id=imdb, season_number=temporada, episode_number=episodio)
        elegidos = candidatos(ordenar(resultados, temporada, episodio))
    else:
        elegidos = candidatos(ordenar(buscar(config, languages=idioma, imdb_id=imdb), None, None))
    if not elegidos:
        etiqueta = f"tt{imdb:07d}" + (f" {temporada}x{episodio:02d}" if temporada is not None else "")
        sys.exit(f"subtitulos: no encontré subtítulos en '{idioma}' para {etiqueta}")

    token = None
    if config.get("usuario") and config.get("contrasena"):
        token = _pedir("/login", config, {"username": config["usuario"], "password": config["contrasena"]})["token"]
    if len(elegidos) == 1:
        print(f"  {describir(elegidos[0])}", file=sys.stderr)
        quedan = bajar(elegidos[0], salida, config, token)
    else:
        from . import sincronizar  # numpy y el VAD solo hacen falta para comparar

        print(f"  comparando {len(elegidos)} versiones con el audio...", file=sys.stderr)
        voz = sincronizar.senal_voz(video)
        with tempfile.TemporaryDirectory() as tmp:
            puntos = []
            for n, r in enumerate(elegidos):
                ruta = os.path.join(tmp, f"{n}.srt")
                quedan = bajar(r, ruta, config, token)
                ajustados, _ = sincronizar.ajustar(sincronizar.leer_srt(ruta), voz)
                puntos.append(sincronizar.coincidencia(voz, ajustados))
                print(f"  {puntos[-1]:.3f}  {describir(r)}", file=sys.stderr)
            mejor = max(range(len(elegidos)), key=puntos.__getitem__)
            print(f"  elegido: {elegidos[mejor]['attributes'].get('release')}", file=sys.stderr)
            with open(os.path.join(tmp, f"{mejor}.srt"), "rb") as f, open(salida, "wb") as g:
                g.write(f.read())
    if quedan is not None:
        print(f"  quedan {quedan} descargas hoy", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    descargar(sys.argv[1], sys.argv[2], *sys.argv[3:])
