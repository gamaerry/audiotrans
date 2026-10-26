from audiotrans.texto import detectar


def test_detectar():
    assert detectar("Hello, how are you? I am fine") == "en"
    assert detectar("¿Dónde está la estación?") == "es"
    # "la" y "est" existen en francés: no debe salir como español
    assert detectar("Bonjour, où est la gare?") is None
