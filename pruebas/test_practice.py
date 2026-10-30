"""practice lee el idioma de la carpeta (tt<ID>.<original>-<destino>) y arma la llamada a mpv."""
import os
import subprocess
import sys

import pytest

PRACTICE = os.path.join(os.path.dirname(__file__), "..", "audiotrans", "sh", "practice")


@pytest.fixture
def carpeta(tmp_path):
    falso = tmp_path / "bin"
    falso.mkdir()
    (falso / "mpv").write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    (falso / "mpv").chmod(0o755)
    serie = tmp_path / "serie"
    serie.mkdir()
    (serie / "a.mp4").write_bytes(b"")
    (serie / "a.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHola\n")
    return serie, {**os.environ, "PATH": f"{falso}:{os.environ['PATH']}", "AUDIOTRANS_PYTHON": sys.executable,
                   "AUDIOTRANS_DATOS": str(tmp_path / "datos")}


def practice(serie, entorno, *args):
    return subprocess.run(["bash", PRACTICE, *args], cwd=serie, env=entorno, capture_output=True, text=True)


def test_idiomas_de_la_carpeta(carpeta):
    serie, entorno = carpeta
    (serie / "tt0211915.fr-es").write_text("")
    r = practice(serie, entorno, "--no-sync", "a.mp4")
    assert r.returncode == 0, r.stderr
    assert "audiotrans-origen=fr,audiotrans-destino=es" in r.stdout
    r = practice(serie, entorno, "--no-sync", "a.mp4", "-it")
    assert "audiotrans-destino=it" in r.stdout


def test_sin_marca_es_en_es(carpeta):
    serie, entorno = carpeta
    r = practice(serie, entorno, "--no-sync", "a.mp4")
    assert "audiotrans-origen=en,audiotrans-destino=es" in r.stdout


def test_dos_marcas_es_un_error(carpeta):
    serie, entorno = carpeta
    (serie / "tt1").write_text("")
    (serie / "tt2.en-es").write_text("")
    r = practice(serie, entorno, "--no-sync", "a.mp4")
    assert r.returncode == 2
    assert "más de un archivo tt" in r.stderr


def test_opcion_desconocida(carpeta):
    serie, entorno = carpeta
    r = practice(serie, entorno, "--estado")
    assert r.returncode == 2
    assert "opción desconocida" in r.stderr


def test_traducciones_revisadas(carpeta):
    serie, entorno = carpeta
    r = practice(serie, entorno, "--no-sync", "a.mp4")
    assert "audiotrans-traducciones=," in r.stdout
    # Uno de antes, junto al video, se mueve a la carpeta oculta
    (serie / "a.es.tsv").write_text("1\tHola\tHello\n")
    r = practice(serie, entorno, "--no-sync", "a.mp4")
    assert f"audiotrans-traducciones={serie / '.audiotrans' / 'a.es.tsv'}," in r.stdout
    assert not (serie / "a.es.tsv").exists()
    # El .tsv es del idioma al que se traduce: con -fr no se usa el de español
    r = practice(serie, entorno, "--no-sync", "a.mp4", "-fr")
    assert "audiotrans-traducciones=," in r.stdout


def test_status_cuenta_las_traducciones_revisadas(carpeta):
    serie, entorno = carpeta
    (serie / "a.es.tsv").write_text("# número\toriginal\ttraducción\n1\tHola\tHello\n")
    r = practice(serie, entorno, "--status", "a.mp4")
    assert "a.mp4 · 1 traducciones revisadas" in r.stdout


def _con_skill(entorno, tmp_path, *carpetas):
    # Un HOME aparte con la skill en las carpetas dadas (la real puede no estar, como en CI)
    casa = tmp_path / "casa"
    for c in carpetas:
        (casa / c / "traducir-episodio").mkdir(parents=True, exist_ok=True)
        (casa / c / "traducir-episodio" / "SKILL.md").write_text("---\nname: traducir-episodio\n---\n")
    return {**entorno, "HOME": str(casa)}


@pytest.mark.parametrize("agente, esperado", [
    ("claude", ["--model", "M", "PROMPT"]), ("gemini", ["-m", "M", "-i", "PROMPT"]),
    ("codex", ["-m", "M", "PROMPT"]), ("opencode", ["-m", "M", "--prompt", "PROMPT"]),
    ("grok", ["-m", "M", "PROMPT"]), ("agy", ["--model", "M", "-i", "PROMPT"]),
])
def test_translate_abre_el_agente_con_el_prompt(carpeta, tmp_path, agente, esperado):
    serie, entorno = carpeta
    entorno = _con_skill(entorno, tmp_path, ".agents/skills", ".claude/skills", ".grok/skills", ".gemini/config/skills")
    falso = entorno["PATH"].split(":")[0]
    with open(os.path.join(falso, agente), "w") as f:
        f.write('#!/bin/sh\nprintf "[%s]\\n" "$PWD" "$@"\n')
    os.chmod(os.path.join(falso, agente), 0o755)
    r = practice(serie, entorno, "--translate", "a.mp4", "--agent", agente, "--model", "M")
    assert r.returncode == 0, r.stderr
    salida = [l[1:-1] for l in r.stdout.splitlines() if l.startswith("[")]
    assert salida[0] == str(serie)  # se abre en la carpeta del video
    prompt = next(a for a in salida if "traducir-episodio" in a)
    assert f"{serie}/a.mp4" in prompt
    assert salida[1:] == [prompt if x == "PROMPT" else x for x in esperado]


def test_translate_sin_modelo_ni_agente_usa_claude(carpeta, tmp_path):
    serie, entorno = carpeta
    entorno = _con_skill(entorno, tmp_path, ".claude/skills")
    falso = entorno["PATH"].split(":")[0]
    with open(os.path.join(falso, "claude"), "w") as f:
        f.write('#!/bin/sh\nprintf "[%s]\\n" "$@"\n')
    os.chmod(os.path.join(falso, "claude"), 0o755)
    r = practice(serie, entorno, "--translate", ".")
    assert r.returncode == 0, r.stderr
    assert len([l for l in r.stdout.splitlines() if l.startswith("[")]) == 1  # solo el prompt


def test_translate_agente_desconocido(carpeta):
    serie, entorno = carpeta
    r = practice(serie, entorno, "--translate", "a.mp4", "--agent", "chatgpt")
    assert r.returncode == 2
    assert "agente desconocido" in r.stderr


def test_translate_sin_la_skill_no_abre_el_agente(carpeta, tmp_path):
    serie, entorno = carpeta
    falso = entorno["PATH"].split(":")[0]
    with open(os.path.join(falso, "grok"), "w") as f:
        f.write('#!/bin/sh\necho ABIERTO\n')
    os.chmod(os.path.join(falso, "grok"), 0o755)
    # Grok no lee ~/.agents/skills: con la skill solo ahí, falta
    r = practice(serie, _con_skill(entorno, tmp_path, ".agents/skills"), "--translate", "a.mp4", "--agent", "grok")
    assert r.returncode == 2
    assert "audiotrans --setup" in r.stderr and "ABIERTO" not in r.stdout
