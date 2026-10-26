import numpy as np

from audiotrans import sincronizar as s


def test_leer_srt_con_bom_y_crlf(tmp_path):
    ruta = tmp_path / "a.srt"
    ruta.write_bytes("﻿1\r\n00:00:01,500 --> 00:00:03,250\r\nHola\r\nmundo\r\n\r\n"
                     "2\r\n01:02:03.004 --> 01:02:05,000\r\n<i>Adiós</i>\r\n".encode())
    assert s.leer_srt(ruta) == [(1.5, 3.25, "Hola\nmundo"), (3723.004, 3725.0, "<i>Adiós</i>")]


def test_formato():
    assert s.formato(3723.456) == "01:02:03,456"
    assert s.formato(-0.5) == "00:00:00,000"
    assert s.formato(59.9996) == "00:01:00,000"


def _caso(desfase_real):
    # Líneas de 2 s cada 10 s; la voz real está desplazada según desfase_real(tiempo)
    bloques = [(t, t + 2.0, "x") for t in np.arange(0, 1200, 10.0)]
    voz = np.zeros(1300 * s.RES)
    for inicio, fin, _ in bloques:
        x = desfase_real((inicio + fin) / 2)
        voz[int((inicio + x) * s.RES):int((fin + x) * s.RES)] = 1
    medios = np.array([(i + f) / 2 for i, f, _ in bloques])
    return bloques, medios, voz - voz.mean()


def test_escalon_en_un_corte():
    bloques, medios, voz_c = _caso(lambda t: 1.0 if t < 573 else 3.0)
    centros = np.array([420.0, 480, 540, 600, 660, 720])
    suaves = np.array([1.0, 1, 1, 3, 3, 3])
    d = np.interp(medios, centros, suaves)
    s.escalones(bloques, medios, d, centros, suaves, voz_c)
    assert set(d[medios < 573]) == {1.0}
    assert set(d[medios > 573]) == {3.0}


def test_deriva_gradual_no_cambia():
    bloques, medios, voz_c = _caso(lambda t: 1 + t / 6000)
    centros = np.array([300.0, 360, 420, 480])
    suaves = np.array([1.05, 1.06, 1.07, 1.08])
    d = np.interp(medios, centros, suaves)
    antes = d.copy()
    s.escalones(bloques, medios, d, centros, suaves, voz_c)
    assert np.array_equal(d, antes)
