"""audiotrans --setup: descarga los traductores locales en-es y es-en, e instala el manual y la skill.

Se puede volver a correr sin problema: solo hace lo que falte. Whisper no se descarga aquí:
faster-whisper lo baja la primera vez que se usa (small ≈ 460 MB).
"""
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

from .traduccion import MODELOS

# Modelos OPUS-MT de Helsinki-NLP (Tatoeba-MT, CC-BY 4.0), convertidos a CTranslate2 en int8
OPUS = {
    "en-es": "eng-spa/opus+bt-2021-04-10",
    "es-en": "spa-eng/opus+bt-2021-04-30",
}
PAQUETE = os.path.dirname(os.path.abspath(__file__))
MAN1 = os.path.expanduser("~/.local/share/man/man1")
# Páginas que llevan a audiotrans.1: los comandos y los alias de alias.sh
PAGINAS = "textrans practice es en cbes cben pses psen mes men ses sen".split()
SKILL = "traducir-episodio"
# Gemini CLI, Codex, opencode y agy leen ~/.agents/skills; Claude Code y Grok, solo su carpeta
AGENTES_APARTE = (".claude", ".grok")


def _bajar(url, destino):
    with urllib.request.urlopen(url, timeout=60) as r, open(destino, "wb") as f:
        total, hecho = int(r.headers.get("Content-Length", 0)), 0
        while bloque := r.read(1 << 20):
            f.write(bloque)
            hecho += len(bloque)
            if total and sys.stderr.isatty():
                print(f"\r  {hecho >> 20} de {total >> 20} MB", end="", file=sys.stderr, flush=True)
    if sys.stderr.isatty():
        print(file=sys.stderr)


def traductor(par, origen):
    import ctranslate2.converters

    destino = os.path.join(MODELOS, par)
    if os.path.isfile(os.path.join(destino, "model.bin")):
        return
    print(f"== Traductor {par} (descarga de ~290 MB; queda en 82 MB)")
    with tempfile.TemporaryDirectory() as tmp:
        zip_ = os.path.join(tmp, "m.zip")
        _bajar(f"https://object.pouta.csc.fi/Tatoeba-MT-models/{origen}.zip", zip_)
        src, ct2 = os.path.join(tmp, "src"), os.path.join(tmp, "ct2")
        with zipfile.ZipFile(zip_) as z:
            z.extractall(src)
        ctranslate2.converters.OpusMTConverter(src).convert(ct2, quantization="int8")
        os.makedirs(destino, exist_ok=True)
        for nombre in os.listdir(ct2):
            shutil.copy(os.path.join(ct2, nombre), destino)
        for nombre in ("source.spm", "target.spm", "LICENSE", "README.md"):
            shutil.copy(os.path.join(src, nombre), destino)


def manual():
    os.makedirs(MAN1, exist_ok=True)
    enlace = os.path.join(MAN1, "audiotrans.1")
    if os.path.lexists(enlace):
        os.remove(enlace)
    os.symlink(os.path.join(PAQUETE, "man", "audiotrans.1"), enlace)
    for p in PAGINAS:
        with open(os.path.join(MAN1, f"{p}.1"), "w") as f:
            f.write(".so man1/audiotrans.1\n")
    print(f"== Manual en {MAN1} (man audiotrans)")


def skill(casa=None):
    """Enlaza la skill del paquete en ~/.agents/skills (así se actualiza con el paquete) y en las
    carpetas de los agentes que no leen esa. No toca una skill propia con el mismo nombre."""
    casa = casa or os.path.expanduser("~")
    fuente = os.path.join(PAQUETE, "skills", SKILL)
    comun = os.path.join(casa, ".agents", "skills", SKILL)
    if os.path.islink(comun):
        os.remove(comun)  # de otra instalación del paquete: se apunta a la de ahora
    if os.path.lexists(comun):
        print(f"== Skill {SKILL}: ya hay una en {comun} que no es de audiotrans; no la toco")
    else:
        os.makedirs(os.path.dirname(comun), exist_ok=True)
        os.symlink(fuente, comun)
    for agente in AGENTES_APARTE:
        if not os.path.isdir(os.path.join(casa, agente)):
            continue  # ese agente no está instalado
        enlace = os.path.join(casa, agente, "skills", SKILL)
        if os.path.islink(enlace) and not os.path.exists(enlace):
            os.remove(enlace)  # enlace roto
        if not os.path.lexists(enlace):
            os.makedirs(os.path.dirname(enlace), exist_ok=True)
            os.symlink(os.path.join("..", "..", ".agents", "skills", SKILL), enlace)
    print(f"== Skill {SKILL} para los agentes (practice --translate)")


def main():
    for par, origen in OPUS.items():
        traductor(par, origen)
    manual()
    skill()
    print("Listo. Para los alias (es, en, mes, ses, cbes, pses...), agrega a ~/.bashrc:")
    print(f"    source {os.path.join(PAQUETE, 'alias.sh')}")


if __name__ == "__main__":
    main()
