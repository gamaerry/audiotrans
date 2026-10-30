from audiotrans import subtitulos as s


def test_episodio_de():
    assert s.episodio_de("s1-e3.mp4") == (1, 3)
    assert s.episodio_de("White.Collar.S01E03.720p.mkv") == (1, 3)
    assert s.episodio_de("/v/1x03.mp4") == (1, 3)
    assert s.episodio_de("2x3.mp4") == (2, 3)
    assert s.episodio_de("Show_2x3.mkv") == (2, 3)
    assert s.episodio_de("2X03.mp4") == (2, 3)
    assert s.episodio_de("t2e1.mp4") == (2, 1)
    assert s.episodio_de("Serie.T02E01.mkv") == (2, 1)
    assert s.episodio_de("pelicula.1920x1080.mkv") == (None, None)
    assert s.episodio_de("amelie.mp4") == (None, None)


def test_fuente():
    assert s.fuente("White.Collar.S01E02.HDTV.XviD-XII") == "tv"
    assert s.fuente("White.Collar.S01E02.720p.WEB-DL") == "web"
    assert s.fuente("Amelie.2001.BluRay.x264") == "disco"
    assert s.fuente(None) == "?"


def _r(release, descargas=0, **extra):
    a = {"release": release, "download_count": descargas, "files": [{"file_id": 1}],
         "feature_details": {"season_number": 1, "episode_number": 2, "parent_imdb_id": 1358522}}
    a.update(extra)
    return {"attributes": a}


def test_ordenar_filtra_y_prioriza_el_hash():
    malos = [_r("x", 900, ai_translated=True), _r("y", 900, files=[]),
             _r("z", 900, feature_details={"season_number": 1, "episode_number": 3})]
    hash_ = _r("hash", 1, moviehash_match=True)
    sordos = _r("sordos", 500, hearing_impaired=True)
    normal = _r("normal", 100)
    assert s.ordenar(malos + [sordos, normal, hash_], 1, 2) == [hash_, normal, sordos]


def test_candidatos_uno_por_fuente_y_desconocidas_al_final():
    ordenados = [_r("?raro"), _r("A.HDTV"), _r("B.HDTV"), _r("C.WEB-DL"), _r("D.DVDRip")]
    assert [r["attributes"]["release"] for r in s.candidatos(ordenados)] == ["A.HDTV", "C.WEB-DL", "D.DVDRip"]


def test_de_la_obra():
    assert s.de_la_obra(_r("x"), 1358522)
    assert not s.de_la_obra(_r("x"), 211915)


def test_defectos_cuenta_palabras_y_signos_pegados():
    # Líneas reales del .srt HDTV de White Collar 1x02; los números con coma no cuentan
    pegadas = ["Every year -- every\nyear,it's like this.", "I have a show this eveningI\nmust be prepared for.",
               "<i>Bethesda fountain.That's 300 yards.</i>"]
    bien = ["1,500 square feet, service", "Finally squeezed into a train\nat Union Square.", "Mr. Caffrey?"]
    assert s.defectos([(0, 0, t) for t in pegadas + bien]) == 0.5
    assert s.defectos([]) == 0.0


def test_defectos_de_un_archivo(tmp_path):
    ruta = tmp_path / "a.srt"
    ruta.write_text("1\n00:00:01,000 --> 00:00:02,000\nyear,it's\n\n2\n00:00:03,000 --> 00:00:04,000\nOkay.\n")
    assert s.defectos_de(ruta) == 0.5


def test_elegir_prefiere_las_bien_hechas():
    # La pegada coincide mejor con la voz, pero hay una limpia (1x02: 0.559 contra 0.561 y 0.612)
    assert s.elegir([(0.38, 0.70), (0.001, 0.561), (0.003, 0.612)]) == 2
    assert s.elegir([(0.38, 0.70), (0.001, 0.561)]) == 1
    # Si todas están mal hechas, la que mejor coincide
    assert s.elegir([(0.38, 0.559), (0.36, 0.60)]) == 1
