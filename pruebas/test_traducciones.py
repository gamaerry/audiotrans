import pytest

from audiotrans import traducciones as t

SRT = ("1\n00:00:01,000 --> 00:00:02,000\nDo I have to stay\nhere? <i>Cowboy up.</i>\n\n"
       "2\n00:00:03,000 --> 00:00:04,000\nYeah.\n\n"
       "3\n00:00:05,000 --> 00:00:06,000\nDid you get a load of\nthat granddaughter?\n")


@pytest.fixture
def video(tmp_path):
    (tmp_path / "s1-e1.mp4").write_bytes(b"")
    (tmp_path / "s1-e1.srt").write_text(SRT)
    (tmp_path / "tt1358522").write_text("")
    return tmp_path / "s1-e1.mp4"


def test_normalizar_ignora_etiquetas_saltos_y_signos():
    # Lo mismo que compara mpv/audiotrans.lua: " / " (del .tsv) contra el salto de línea del .srt
    assert t.normalizar("Do I have to stay / here? Cowboy up.") == t.normalizar("Do I have to stay\nhere? <i>Cowboy up.</i>")
    assert t.normalizar("load") != t.normalizar("loan")


def test_una_linea():
    assert t.una_linea("Do I have to stay\nhere? <i>Cowboy up.</i>\n") == "Do I have to stay / here? Cowboy up."


def test_destino_de_la_carpeta(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"")
    assert t.destino_de(tmp_path / "v.mp4") == "es"
    (tmp_path / "tt0211915.fr-it").write_text("")
    assert t.destino_de(tmp_path / "v.mp4") == "it"


def test_poner_quitar_y_validar(video, capsys):
    ruta = video.with_name("s1-e1.es.tsv")
    assert t.main(["poner", str(video), "1", "¿Tengo que quedarme aquí? Aguántate."]) == 0
    assert t.main(["poner", str(video), "3", "¿Ya   viste a la nieta?"]) == 0
    filas = t.leer_tsv(ruta)
    assert filas == {1: ("Do I have to stay / here? Cowboy up.", "¿Tengo que quedarme aquí? Aguántate."),
                     3: ("Did you get a load of / that granddaughter?", "¿Ya viste a la nieta?")}
    assert ruta.read_text().startswith("# ")
    assert t.main(["validar", str(video)]) == 0
    assert t.main(["quitar", str(video), "3"]) == 0
    assert list(t.leer_tsv(ruta)) == [1]


def test_poner_desde_la_entrada(video, monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("# comentario\n2\tSí.\n3\t¿Ya viste a la nieta?\n"))
    assert t.main(["poner", str(video), "-"]) == 0
    assert sorted(t.leer_tsv(video.with_name("s1-e1.es.tsv"))) == [2, 3]


def test_poner_rechaza_bloques_que_no_existen(video):
    with pytest.raises(SystemExit):
        t.main(["poner", str(video), "9", "nada"])
    assert not video.with_name("s1-e1.es.tsv").exists()


def test_validar_detecta_filas_que_mpv_ignoraria(video, capsys):
    video.with_name("s1-e1.es.tsv").write_text(
        "1\tDo I have to stay / here? Cowboy up.\tAguántate.\n"
        "3\tDid you get a loan of / that granddaughter?\t¿Ya viste a la nieta?\n"
        "7\tNada\tNada\n")
    assert t.main(["validar", str(video)]) == 1
    salida = capsys.readouterr().out
    assert "bloque 3: el original no coincide" in salida
    assert "bloque 7: no hay bloque 7" in salida
    assert "1 de 3 traducciones se usarán" in salida


def test_revisar_muestra_solo_las_que_faltan_con_su_automatica(video, capsys, monkeypatch):
    pedidos = []

    def lote(textos, origen, destino):
        pedidos.append((textos, origen, destino))
        return [f"[{x}]" for x in textos]

    monkeypatch.setattr(t, "traducir_lote", lote)
    assert t.main(["poner", str(video), "2", "Sí."]) == 0
    capsys.readouterr()
    assert t.main(["revisar", str(video)]) == 0
    salida = capsys.readouterr().out.splitlines()
    # Al traductor van con los saltos como espacios, como los manda mpv; la 2 ya está revisada
    assert pedidos == [(["Do I have to stay here? Cowboy up.", "Did you get a load of that granddaughter?"], "en", "es")]
    assert salida[1:] == ["1\tDo I have to stay / here? Cowboy up.\t[Do I have to stay here? Cowboy up.]",
                          "3\tDid you get a load of / that granddaughter?\t[Did you get a load of that granddaughter?]"]


def test_las_automaticas_se_guardan_y_no_se_traducen_otra_vez(video, capsys, monkeypatch):
    import io
    pedidos = []

    def lote(textos, origen, destino):
        pedidos.append(textos)
        return [f"[{x}]" for x in textos]

    monkeypatch.setattr(t, "traducir_lote", lote)
    assert t.main(["revisar", str(video), "1", "1"]) == 0
    capsys.readouterr()
    # C pide la 3 y la 1: la 1 ya la tradujo revisar, y salen en el orden pedido
    monkeypatch.setattr("sys.stdin", io.StringIO("3\n1\n"))
    assert t.main(["automaticas", str(video)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "3\t[Did you get a load of that granddaughter?]", "1\t[Do I have to stay here? Cowboy up.]"]
    assert pedidos == [["Do I have to stay here? Cowboy up."], ["Did you get a load of that granddaughter?"]]
    # Si el .srt cambia, la fila que ya no coincide se traduce otra vez
    video.with_suffix(".srt").write_text(SRT.replace("Cowboy up.", "Saddle up."))
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n3\n"))
    assert t.main(["automaticas", str(video)]) == 0
    assert pedidos[2:] == [["Do I have to stay here? Saddle up."]]


def test_revisar_sigue_si_no_puede_escribir_la_cache(video, capsys, monkeypatch):
    # Una carpeta en la que no se puede escribir
    monkeypatch.setattr(t, "traducir_lote", lambda textos, o, d: [f"[{x}]" for x in textos])
    def solo_lectura(ruta, filas):
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(t, "escribir_tsv", solo_lectura)
    assert t.main(["revisar", str(video), "1", "1"]) == 0
    salida = capsys.readouterr()
    assert salida.out.splitlines()[1:] == ["1\tDo I have to stay / here? Cowboy up.\t[Do I have to stay here? Cowboy up.]"]
    assert "no se guardó la caché" in salida.err


def test_traducir_lote_sin_modelo_local_traduce_una_por_una(monkeypatch):
    from audiotrans import traduccion
    monkeypatch.setattr(traduccion, "hay_local", lambda o, d: False)
    monkeypatch.setattr(traduccion, "traducir", lambda texto, o, d, supuesto=None: texto.upper())
    assert traduccion.traducir_lote(["hi", "bye"], "en", "fr") == ["HI", "BYE"]


def test_migrar_a_otra_version_del_srt():
    viejos = [(0, 0, "Finally squeezed into\na trainat union square."), (0, 0, "Yeah."), (0, 0, "Bye.")]
    filas = {1: (t.una_linea(viejos[0][2]), "Por fin me metí en un tren en Union Square."),
             2: ("Yeah.", "Sí."), 3: ("Bye.", "Adiós.")}
    # La versión nueva separa las palabras, agrega una línea al inicio y repite "Yeah."
    nuevos = [(0, 0, "Yeah."), (0, 0, "Finally squeezed into a train\nat Union Square."), (0, 0, "Yeah."),
              (0, 0, "See you.")]
    migradas, perdidas = t.migrar(nuevos, filas)
    assert migradas == {2: ("Finally squeezed into a train / at Union Square.", "Por fin me metí en un tren en Union Square."),
                        3: ("Yeah.", "Sí.")}  # la "Yeah." de posición más parecida
    assert perdidas == 1
