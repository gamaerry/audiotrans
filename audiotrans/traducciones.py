"""Traducciones revisadas de un episodio, para las líneas que el traductor automático traduce mal.

Uso: python -m audiotrans.traducciones revisar <video> [<desde> <hasta>] [-<destino>]
     python -m audiotrans.traducciones buscar <video> <texto o minuto> [-<destino>]
     python -m audiotrans.traducciones exportar <video> [<desde> <hasta>] [-<destino>]
     python -m audiotrans.traducciones poner <video> <número> <traducción> [-<destino>]
     python -m audiotrans.traducciones poner <video> - [-<destino>]    (líneas "número<TAB>traducción")
     python -m audiotrans.traducciones quitar <video> <número> [-<destino>]
     python -m audiotrans.traducciones validar <video> [-<destino>]

OPUS-MT y Google traducen frase por frase y no entienden los modismos ("Cowboy up" sale
"Vaquero arriba"). Un agente (o el usuario) puede escribir la traducción buena de esas líneas
en <video>.<destino>.tsv, junto al video: una fila por línea corregida, con el número de bloque
del .srt original, su texto original y la traducción, separados por tabuladores. practice lo
pasa a mpv, y ahí y la muestra en vez de traducir y d la guarda con la duda. El archivo puede
tener solo algunas líneas. Si el texto original de una fila ya no coincide con el del .srt (se
editó o se cambió por otra versión), esa fila se ignora y se traduce como siempre.

El destino sale del archivo tt<ID>.<original>-<destino> de la carpeta (sin él, es). El minuto
de buscar y exportar es el que se ve en mpv: el del .srt sincronizado de la caché de practice.

revisar muestra, de las líneas que aún no tienen traducción revisada, el original y la
traducción automática que mostraría y (con el modelo local, en un lote). Así un agente solo
escribe las que están mal, en vez de traducir el episodio entero.
"""
import hashlib
import os
import re
import sys

from .sincronizar import leer_srt
from .traduccion import traducir_lote

CACHE = os.path.expanduser("~/.cache/audiotrans/sincronizados")
PRACTICE = os.path.join(os.path.dirname(__file__), "sh", "practice")
VENTANA = 6  # s alrededor del minuto que se busca: el tiempo que se lee en mpv es aproximado
ENCABEZADO = "# número\toriginal\ttraducción\n"


def normalizar(texto):
    """Lo que se compara entre la fila y el .srt; igual que normalizar() de mpv/audiotrans.lua."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>|\{[^}]*\}", "", texto).lower())


def una_linea(texto):
    texto = re.sub(r"<[^>]+>|\{[^}]*\}", "", texto)
    return " / ".join(l.strip() for l in texto.split("\n") if l.strip())


def segundos(texto):
    s = 0.0
    for p in texto.split(":"):
        s = s * 60 + float(p)
    return s


def minuto(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def idiomas_de(video):
    """(original, destino). Como marca_de() en practice: el archivo tt<ID>[.<original>-<destino>]"""
    carpeta = os.path.dirname(os.path.abspath(video))
    for nombre in os.listdir(carpeta):
        m = re.fullmatch(r"tt\d+(?:\.([a-z]{2,3})-([a-z]{2,3}))?", nombre)
        if m and os.path.isfile(os.path.join(carpeta, nombre)):
            return m.group(1) or "en", m.group(2) or "es"
    return "en", "es"


def destino_de(video):
    return idiomas_de(video)[1]


def ruta_tsv(video, destino):
    return f"{os.path.splitext(video)[0]}.{destino}.tsv"


def leer_tsv(ruta):
    """{número: (original, traducción)}"""
    filas = {}
    if os.path.exists(ruta):
        for linea in open(ruta, encoding="utf-8"):
            m = re.match(r"(\d+)\t([^\t]*)\t(.*)$", linea.rstrip("\n"))
            if m:
                filas[int(m.group(1))] = (m.group(2), m.group(3))
    return filas


def escribir_tsv(ruta, filas):
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        f.write(ENCABEZADO)
        for n in sorted(filas):
            f.write(f"{n}\t{filas[n][0]}\t{filas[n][1]}\n")
    os.replace(ruta + ".tmp", ruta)


def sincronizado(video, srt):
    # La misma clave que base_de() en practice: versión de la caché y ruta, fecha y tamaño
    version = re.search(r"^version_cache=(\d+)", open(PRACTICE).read(), re.M).group(1)
    datos = version + "\n"
    for ruta in (os.path.realpath(video), os.path.realpath(srt)):
        st = os.stat(ruta)
        datos += f"{ruta} {int(st.st_mtime)} {st.st_size}\n"
    base = os.path.join(CACHE, os.path.splitext(os.path.basename(video))[0] + "-"
                        + hashlib.sha1(datos.encode()).hexdigest()[:12])
    for sufijo in (".exacto.srt", ".srt"):
        if os.path.exists(base + sufijo):
            return base + sufijo
    return None


def tiempos_en_mpv(video, srt, bloques):
    """Los bloques con los tiempos que se ven en mpv: los del .srt sincronizado, en el mismo orden."""
    sinc = sincronizado(video, srt)
    tiempos = leer_srt(sinc) if sinc else []
    if len(tiempos) != len(bloques):
        print("(sin .srt sincronizado en la caché: los minutos son los del original)", file=sys.stderr)
        return bloques
    return tiempos


def problemas(bloques, filas):
    """Las filas que practice ignoraría, con el motivo."""
    malas = []
    for n, (original, traduccion) in sorted(filas.items()):
        if not 1 <= n <= len(bloques):
            malas.append((n, f"no hay bloque {n} (el .srt tiene {len(bloques)})"))
        elif normalizar(original) != normalizar(bloques[n - 1][2]):
            malas.append((n, f"el original no coincide: el .srt dice {una_linea(bloques[n - 1][2])!r}"))
        elif not traduccion.strip():
            malas.append((n, "la traducción está vacía"))
    return malas


def fila(n, bloque, filas, t):
    return f"{n}\t{minuto(t)}\t{una_linea(bloque[2])}\t{filas.get(n, (None, ''))[1]}"


def main(args):
    destino = None
    resto = []
    for a in args:
        if re.fullmatch(r"-[a-z]{2,3}", a):
            destino = a[1:]
        else:
            resto.append(a)
    if len(resto) < 2:
        sys.exit(__doc__)
    accion, video, resto = resto[0], resto[1], resto[2:]
    srt = os.path.splitext(video)[0] + ".srt"
    if not os.path.exists(srt):
        sys.exit(f"traducciones: no encuentro el .srt del video: {srt}")
    bloques = leer_srt(srt)
    ruta = ruta_tsv(video, destino or destino_de(video))
    filas = leer_tsv(ruta)

    if accion == "revisar":
        desde, hasta = (int(resto[0]), int(resto[1])) if len(resto) >= 2 else (1, len(bloques))
        # Sin el minuto y sin las que ya están revisadas: lo justo para decidir cuáles corregir
        numeros = [n for n in range(max(1, desde), min(hasta, len(bloques)) + 1) if n not in filas]
        textos = [una_linea(bloques[n - 1][2]).replace(" / ", " ") for n in numeros]
        automaticas = traducir_lote(textos, idiomas_de(video)[0], destino or destino_de(video))
        print("número\toriginal\ttraducción automática")
        for n, automatica in zip(numeros, automaticas):
            print(f"{n}\t{una_linea(bloques[n - 1][2])}\t{automatica}")
    elif accion == "buscar" and resto:
        consulta = " ".join(resto)
        tiempos = tiempos_en_mpv(video, srt, bloques)
        print("número\tminuto\toriginal\ttraducción revisada")
        if re.fullmatch(r"\d+(:\d+){1,2}(\.\d+)?", consulta):
            t = segundos(consulta)
            for n, (b, s) in enumerate(zip(bloques, tiempos), 1):
                if s[1] >= t - VENTANA and s[0] <= t + VENTANA:
                    print(fila(n, b, filas, s[0]))
        else:
            buscado = " ".join(consulta.lower().split())
            for n, (b, s) in enumerate(zip(bloques, tiempos), 1):
                if buscado in una_linea(b[2]).lower().replace(" / ", " "):
                    print(fila(n, b, filas, s[0]))
    elif accion == "exportar":
        desde, hasta = (int(resto[0]), int(resto[1])) if len(resto) >= 2 else (1, len(bloques))
        tiempos = tiempos_en_mpv(video, srt, bloques)
        print("número\tminuto\toriginal\ttraducción revisada")
        for n in range(max(1, desde), min(hasta, len(bloques)) + 1):
            print(fila(n, bloques[n - 1], filas, tiempos[n - 1][0]))
    elif accion == "poner" and resto:
        if resto[0] == "-":
            nuevas = [l.rstrip("\n").split("\t", 1) for l in sys.stdin if l.strip() and not l.startswith("#")]
        elif len(resto) >= 2:
            nuevas = [[resto[0], " ".join(resto[1:])]]
        else:
            sys.exit(__doc__)
        for partes in nuevas:
            if len(partes) != 2 or not partes[0].strip().isdigit():
                sys.exit(f"traducciones: la línea debe ser número<TAB>traducción: {partes!r}")
            n, traduccion = int(partes[0]), " ".join(partes[1].replace("\t", " ").split())
            if not 1 <= n <= len(bloques):
                sys.exit(f"traducciones: no hay bloque {n} (el .srt tiene {len(bloques)})")
            if not traduccion:
                sys.exit(f"traducciones: la traducción del bloque {n} está vacía")
            filas[n] = (una_linea(bloques[n - 1][2]), traduccion)
            print(f"{n}\t{filas[n][0]}\t→ {traduccion}")
        escribir_tsv(ruta, filas)
        print(f"{len(filas)} traducciones revisadas en {ruta}", file=sys.stderr)
    elif accion == "quitar" and resto:
        for n in resto:
            filas.pop(int(n), None)
        escribir_tsv(ruta, filas)
    elif accion == "validar":
        malas = problemas(bloques, filas)
        for n, motivo in malas:
            print(f"bloque {n}: {motivo}")
        print(f"{len(filas) - len(malas)} de {len(filas)} traducciones se usarán ({ruta})")
        return 1 if malas else 0
    else:
        sys.exit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
