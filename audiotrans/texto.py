"""Traduce texto: inglés↔español con el modelo local; jerga u otros idiomas, con Google.

Uso: textrans <destino> [-g] [-<origen>] [texto...]   (sin texto, se lee de stdin)
"""
import re
import sys

from . import traduccion

AYUDA = """Uso: textrans <destino> [opciones] [texto...]

Traduce texto al idioma <destino>. Inglés↔español se traduce en local
(OPUS-MT, sin internet, ~0.3 s); los demás idiomas, con Google.
Sin texto, lo lee de la entrada estándar (p. ej. wl-paste -p | es).

Opciones:
  -<origen>     idioma del texto (p. ej. -en, -fr); sin esto se detecta entre
                inglés y español, y si no está claro se usa Google
  -g, --google  traducir con Google aunque haya modelo local (entiende mejor
                modismos y jerga, p. ej. "la neta", pero necesita internet)
  -h, --help    mostrar esta ayuda

Atajos: es/en (texto), cbes/cben (portapapeles), pses/psen (selección),
        mes/men (micrófono), ses/sen (audio del sistema)
Más detalles: man audiotrans"""

# Palabras muy frecuentes de cada idioma; varias del español (la, de, que, en...) también
# existen en francés, italiano o portugués, por eso se exige una ventaja de 2 para decidir
ES = set("el la los las de del que y en un una es son por para con se lo le les su sus al como más pero "
         "ya está estoy estás qué cómo dónde cuándo muy también hay me te mi tu yo él ella esto eso "
         "porque cuando sí bien todo nada".split())
EN = set("the an of and to in is are it you that for on with be this was were have has not i my your "
         "what how where when do does did can will at from they we he she just don't i'm it's".split())


def detectar(texto):
    palabras = re.findall(r"[\w']+", texto.lower())
    es = sum(p in ES for p in palabras) + 2 * len(re.findall(r"[ñ¿¡]", texto))
    en = sum(p in EN for p in palabras)
    if es - en >= 2:
        return "es"
    if en - es >= 2:
        return "en"
    return None  # no está claro: se le deja a Google


def main(args):
    destino, origen, texto = None, None, []
    for arg in args:
        if arg in ("-h", "--help"):
            print(AYUDA)
            return 0
        if arg in ("-g", "--google"):
            traduccion.EN_LINEA = True
        elif re.fullmatch(r"-[a-z]{2,3}", arg) and destino:
            origen = arg[1:]
        elif destino is None:
            destino = arg
        else:
            texto.append(arg)
    if not destino:
        print(AYUDA, file=sys.stderr)
        return 2
    texto = " ".join(texto) if texto else sys.stdin.read()
    if not texto.strip():
        return 0
    # Sin conexión y sin idioma claro, se supone que el texto está en el otro idioma del par en-es
    supuesto = {"es": "en", "en": "es"}.get(destino)
    print(traduccion.traducir(texto.strip(), origen or detectar(texto), destino, supuesto))
    return 0


def principal():
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    principal()
