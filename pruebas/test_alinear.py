import numpy as np

from audiotrans import alinear as a


def test_normalizar():
    assert a.normalizar("Été,") == "ete"
    assert a.normalizar("Don't!") == "don't"
    assert a.normalizar("—") == ""


def test_palabras_de_quita_etiquetas():
    assert a.palabras_de("<i>Neal</i> {\\an8}Caffrey, escaped.") == ["neal", "caffrey", "escaped"]


def _palabras(*ps):
    palabras = list(ps)
    return palabras, np.array([p[1] for p in palabras])


def test_alinear_linea_encontrada():
    palabras, tiempos = _palabras(("so", 8.0, 8.3), ("neal", 10.4, 10.7), ("caffrey", 10.7, 11.1),
                                  ("escaped", 11.1, 11.8), ("what", 13.0, 13.2))
    assert a.alinear_linea(palabras, tiempos, 10.0, 12.0, "Neal Caffrey escaped.") == (10.4, 11.8, True, True)


def test_alinear_linea_no_encontrada_conserva_el_srt():
    palabras, tiempos = _palabras(("something", 10.2, 10.6), ("else", 10.6, 11.0))
    assert a.alinear_linea(palabras, tiempos, 10.0, 12.0, "Neal Caffrey escaped.") == (10.0, 12.0, False, False)
