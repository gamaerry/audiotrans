from audiotrans import subtitulos as s


def test_episodio_de():
    assert s.episodio_de("s1-e3.mp4") == (1, 3)
    assert s.episodio_de("White.Collar.S01E03.720p.mkv") == (1, 3)
    assert s.episodio_de("/v/1x03.mp4") == (1, 3)
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
