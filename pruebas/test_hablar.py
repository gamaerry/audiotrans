from audiotrans.hablar import comparar, partes


def test_comparar_todo_entendido_ignora_acentos_y_signos():
    assert comparar("¿Qué pasó, Neal?", "que paso neal") == (100, [("¿Qué", True), ("pasó,", True), ("Neal?", True)])


def test_comparar_marca_las_que_faltan():
    porcentaje, palabras = comparar("Cowboy up, Neal.", "Cowboy app, Neal.")
    assert porcentaje == 67
    assert palabras == [("Cowboy", True), ("up,", False), ("Neal.", True)]


def test_comparar_palabras_de_mas_no_cuentan_y_quita_etiquetas():
    assert comparar("<i>Coffee?</i>", "uh coffee please") == (100, [("Coffee?", True)])


def test_comparar_guiones_y_saltos_de_linea():
    assert comparar("- Hi.\n- Hello.", "hi") == (50, [("Hi.", True), ("Hello.", False)])


def test_comparar_nada():
    assert comparar("Hi.", "") == (0, [("Hi.", False)])


def test_partes_cifras_en_ingles():
    assert partes("20,", "en") == ["twenty"]
    assert partes("21", "en") == ["twenty", "one"]
    assert partes("1999", "en") == ["nineteen", "ninety", "nine"]
    assert partes("105", "en") == ["one", "hundred", "five"]
    assert partes("3rd", "en") == ["third"]
    assert partes("3:30?", "en") == ["three", "thirty"]
    assert partes("3:00", "en") == ["three"]
    assert partes("50%", "en") == ["fifty", "percent"]
    assert partes("$5", "en") == ["five", "dollars"]
    assert partes("1,000", "en") == ["one", "thousand"]
    assert partes("2.5", "en") == ["two", "point", "five"]
    assert partes("3.30,", "en") == ["three", "thirty"]  # hora como la escribe Whisper
    assert partes("$2.50", "en") == ["two", "point", "five", "dollars"]


def test_partes_cifras_en_espanol():
    assert partes("1.000", "es") == ["mil"]
    assert partes("21", "es") == ["veintiuno"]
    assert partes("1999", "es") == ["mil", "novecientos", "noventa", "y", "nueve"]


def test_partes_sin_idioma_o_sin_num2words_deja_la_cifra():
    assert partes("20", None) == ["20"]
    assert partes("20", "xx") == ["20"]
    assert partes("20s", "en") == ["20s"]


def test_partes_separa_guiones():
    assert partes("twenty-one", "en") == ["twenty", "one"]


def test_comparar_cifra_contra_palabras():
    assert comparar("I'm 20.", "I'm twenty", "en") == (100, [("I'm", True), ("20.", True)])
    assert comparar("Call me at 3:30.", "call me at three thirty", "en")[0] == 100
    assert comparar("It's twenty-one.", "It's 21.", "en")[0] == 100
    assert comparar("Tengo 1.000 pesos.", "tengo mil pesos", "es")[0] == 100


def test_comparar_cifra_a_medias_cuenta_como_falta():
    assert comparar("Year 1999.", "year nineteen", "en") == (50, [("Year", True), ("1999.", False)])
