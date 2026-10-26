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
