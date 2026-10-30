"""Descarga de OpenSubtitles los subtítulos de un video, para practicar cuando no trae .srt.

Uso: python -m audiotrans.subtitulos <video> <salida.srt> <IMDb ID> [idioma]
El IMDb ID es el de la serie o la película (practice lo toma de un archivo tt<número> en la
carpeta del video). Si el nombre del video tiene temporada y episodio (s1-e3, S01E03, t1e3, 1x03), es
un episodio de esa serie; si no, la película. Busca primero por el hash del archivo (el mismo
video, así que casi no hay desfase) y, si no hay, por el IMDb ID. En ese caso baja hasta CANDIDATOS, uno por cada fuente (TV, WEB, DVD...),
porque las versiones de una misma fuente tienen los mismos cortes, y se queda con el que, ya
sincronizado, mejor coincide con la voz. Antes descarta los que tienen el texto mal hecho
(palabras y signos pegados: "year,it's", "eveningI"), si hay alguno limpio: el más descargado
de White Collar 1x02 tenía así el 38 % de las líneas, y el traductor las destrozaba ("a trainat
union square" → "una plaza del sindicato del trenat"). La coincidencia con la voz no lo nota.
También el del mismo archivo (por hash) se cambia por otro si está mal hecho. La clave va en $AUDIOTRANS_DATOS/opensubtitles (api_key=..., y si hace
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
# Fracción de líneas con palabras o signos pegados a partir de la cual un .srt está mal hecho.
# En 1x02: 38 % y 36 % en las dos versiones HDTV, 0.1 % y 0.3 % en las de DVD
DEFECTUOSO = 0.05


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
    # s1e3 o t1e3 (temporada); 1x03 sin otros dígitos pegados, para no tomar 1920x1080
    m = (re.search(r"[sStT](\d{1,2})[ ._-]*[eE](\d{1,3})", nombre)
         or re.search(r"(?<!\d)(\d{1,2})[xX](\d{1,3})(?!\d)", nombre))
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


def defectos(bloques):
    """Fracción de líneas con un signo pegado a la palabra siguiente ("year,it's") o con dos
    palabras unidas por la mayúscula ("eveningI"). Los números ("1,500") no cuentan."""
    if not bloques:
        return 0.0
    pegadas = sum(bool(re.search(r"[a-z][,.?!][A-Za-z]|[a-z]{2}[A-Z]", re.sub(r"<[^>]+>|\{[^}]*\}", "", b[2])))
                  for b in bloques)
    return pegadas / len(bloques)


def defectos_de(ruta):
    """defectos() de un .srt, sin importar sincronizar (numpy y el VAD): para practice --status."""
    texto = open(ruta, encoding="utf-8-sig", errors="replace").read().replace("\r", "")
    return defectos([(0, 0, b.split("-->", 1)[1].partition("\n")[2])
                     for b in re.split(r"\n\s*\n", texto.strip()) if "-->" in b])


def elegir(versiones):
    """Índice de la mejor de [(defectos, coincidencia con la voz)]: la que mejor coincide entre
    las bien hechas, o entre todas si ninguna lo está."""
    limpias = [i for i, (d, _) in enumerate(versiones) if d <= DEFECTUOSO] or range(len(versiones))
    return max(limpias, key=lambda i: versiones[i][1])


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
    del_archivo = ordenar(resultados, temporada, episodio)[:1]

    token = None
    if config.get("usuario") and config.get("contrasena"):
        token = _pedir("/login", config, {"username": config["usuario"], "password": config["contrasena"]})["token"]
    from . import sincronizar  # numpy y el VAD solo hacen falta para medir

    with tempfile.TemporaryDirectory() as tmp:
        bajados = []  # (resultado, ruta, bloques)

        def bajar_a_tmp(r):
            ruta = os.path.join(tmp, f"{len(bajados)}.srt")
            quedan = bajar(r, ruta, config, token)
            bajados.append((r, ruta, sincronizar.leer_srt(ruta)))
            return quedan

        quedan = None
        if del_archivo:
            # Del mismo archivo casi no hay desfase: no hace falta comparar, salvo que esté mal hecho
            quedan = bajar_a_tmp(del_archivo[0])
            d = defectos(bajados[0][2])
            print(f"  {describir(del_archivo[0])}", file=sys.stderr)
            if d <= DEFECTUOSO:
                return _copiar(bajados[0][1], salida, quedan)
            print(f"  tiene {100 * d:.0f} % de líneas con palabras pegadas: busco otras versiones", file=sys.stderr)
        if temporada is not None:
            resultados = buscar(config, languages=idioma, parent_imdb_id=imdb, season_number=temporada, episode_number=episodio)
        else:
            resultados = buscar(config, languages=idioma, imdb_id=imdb)
        ya = {r["attributes"]["files"][0]["file_id"] for r, _, _ in bajados}
        for r in candidatos([r for r in ordenar(resultados, temporada, episodio)
                             if r["attributes"]["files"][0]["file_id"] not in ya]):
            quedan = bajar_a_tmp(r)
        if not bajados:
            etiqueta = f"tt{imdb:07d}" + (f" {temporada}x{episodio:02d}" if temporada is not None else "")
            sys.exit(f"subtitulos: no encontré subtítulos en '{idioma}' para {etiqueta}")

        if len(bajados) == 1:
            versiones = [(defectos(bajados[0][2]), 0.0)]
            print(f"  {describir(bajados[0][0])}", file=sys.stderr)
        else:
            print(f"  comparando {len(bajados)} versiones con el audio...", file=sys.stderr)
            voz = sincronizar.senal_voz(video)
            versiones = []
            for r, _, bloques in bajados:
                ajustados, _ = sincronizar.ajustar(bloques, voz)
                versiones.append((defectos(bloques), sincronizar.coincidencia(voz, ajustados)))
                print(f"  {versiones[-1][1]:.3f}  {100 * versiones[-1][0]:4.1f} % pegadas  {describir(r)}", file=sys.stderr)
        mejor = elegir(versiones)
        if versiones[mejor][0] > DEFECTUOSO:
            print(f"  aviso: todas tienen palabras pegadas ({100 * versiones[mejor][0]:.0f} % de las líneas en la elegida)",
                  file=sys.stderr)
        if len(bajados) > 1:
            print(f"  elegido: {bajados[mejor][0]['attributes'].get('release')}", file=sys.stderr)
        return _copiar(bajados[mejor][1], salida, quedan)


def _copiar(ruta, salida, quedan):
    with open(ruta, "rb") as f, open(salida, "wb") as g:
        g.write(f.read())
    if quedan is not None:
        print(f"  quedan {quedan} descargas hoy", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    descargar(sys.argv[1], sys.argv[2], *sys.argv[3:])
