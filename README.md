# audiotrans

Traduce desde la terminal lo que escucha el micrófono, lo que suena en la computadora o un texto, sin depender de internet para inglés↔español. Funciona en una laptop modesta sin GPU, con tiempo real de ~0.5 s por frase.

```console
$ ses -r -p                   # lo que suena en la computadora → español, en tiempo real
● Escuchando en tiempo real... (Ctrl+C para salir)

Where is the nearest pharmacy?
¿Dónde está la farmacia más cercana?

$ en No dijo ni una palabra, pero sus ojos me lo dijeron todo.
He didn't say a word, but his eyes told me everything.
```

- **Transcripción:** [Whisper](https://github.com/openai/whisper) con [faster-whisper](https://github.com/SYSTRAN/faster-whisper), en CPU y en local.
- **Traducción:** inglés↔español en local con [OPUS-MT](https://github.com/Helsinki-NLP/Tatoeba-Challenge) (~50 ms por frase). Para otros idiomas, o para jerga con `-g`, usa Google.
- **Audio:** PipeWire (`pw-record`), tanto del micrófono como del monitor de la salida de audio.

## Comandos

| Alias | Qué hace |
|---|---|
| `es` / `en` | traduce texto al español / inglés (`textrans`) |
| `cbes` / `cben` | traduce el portapapeles (lo copiado) |
| `pses` / `psen` | traduce la selección (lo subrayado con el mouse) |
| `mes` / `men` | escucha el micrófono hasta presionar Enter y traduce |
| `ses` / `sen` | lo mismo con el audio de la computadora |
| `esp` / `eng` | salida completa de `trans` (diccionario, sinónimos) |

Opciones de los comandos de audio (`audiotrans`):

| Opción | |
|---|---|
| `-r`, `--tiempo-real` | escucha sin parar y traduce cada frase al detectar una pausa |
| `-l`, `--loop` | repite el modo con Enter |
| `-<origen>` | idioma del audio (`-en`, `-ja`…); si no se da, se detecta |
| `-p`, `--preciso` | con `-r`: frases más largas y ventana de 15 s; ~4 % de error en lugar de ~9 %, con ~2 s de retraso |
| `-f`, `--rapido` | modelo `base`: la mitad de RAM, ~0.25 s por frase, menos preciso |
| `-g`, `--google` | traduce con Google aunque haya modelo local (entiende jerga) |
| `-s`, `--sistema` | graba la salida de audio en lugar del micrófono |

`es`, `en`, `cbes` y los demás alias de texto aceptan `-g` y `-<origen>`. Todo está documentado en `man audiotrans` y en `--help`.

## Instalación

Requiere Linux con PipeWire, [uv](https://docs.astral.sh/uv/) y unos 1.5 GB de disco: venv, Whisper `small` y los dos traductores. `trans` ([translate-shell](https://github.com/soimort/translate-shell)) y `wl-paste` son opcionales.

```bash
git clone https://github.com/gamaerry/audiotrans.git
cd audiotrans
./instalar.sh
echo "source $PWD/alias.sh" >> ~/.bashrc
```

`instalar.sh` hace lo siguiente:
1. Crea un venv con Python 3.12 en `~/.local/share/audiotrans/venv`. Usa 3.12 porque faster-whisper no tiene paquetes para 3.13 o posterior.
2. Descarga los modelos OPUS-MT y los convierte a CTranslate2 en int8.
3. Enlaza los comandos en `~/.local/bin` y el manual en `~/.local/share/man`.

Como son enlaces, lo que cambies en el repo se usa al instante.

## Descubrimientos

Todo se midió en una laptop con **Intel i3-N305** (8 núcleos eficientes, AVX2 + AVX-VNNI, sin GPU) y 8 GB de RAM. Las mediciones de velocidad usan frases generadas con `espeak-ng`, una voz robótica más difícil de transcribir que una real. La precisión en tiempo real (sección 5) se midió con voz humana real y su transcripción de referencia.

### 1. Whisper desperdicia el 80 % del tiempo en relleno

faster-whisper rellena todo audio hasta 30 s, y el codificador, que es la parte cara en CPU, procesa esos 30 s aunque la frase dure 3. [`lib/whisper_corto.py`](lib/whisper_corto.py) llama directamente a CTranslate2 con una ventana del tamaño de la frase más 1 s:

| Modelo | Ventana de 30 s | Ventana ajustada |
|---|---|---|
| `small` | 2.2 s | **0.5 s** |
| `base` | 0.8 s | **0.25 s** |

En inglés la precisión es la misma. En español baja un poco ("llévaten para aguas" en vez de "llévate un paraguas"), y se recupera con una ventana mínima de 15 s (~1.1 s). Por eso el tiempo real usa la ventana corta y el modo con Enter usa la mínima de 15 s.

Hay un efecto secundario: con ventanas cortas Whisper a veces repite la frase en bucle ("Good morning everyone. Good morning everyone…"). `no_repeat_ngram_size` y `repetition_penalty` no ayudaron. Lo que funcionó fue limitar la generación a ~10 tokens por segundo de audio y quitar las repeticiones exactas de 3 palabras o más.

### 2. Detectar el idioma costaba más que transcribir

faster-whisper detecta el idioma con una pasada extra del codificador:

| Modelo | Idioma indicado | Idioma detectado |
|---|---|---|
| `base` | 0.84 s | 1.53 s |
| `small` | 2.36 s | 6.02 s |

Con `model.detect_language()` sobre la codificación que ya se hizo para transcribir, detectar el idioma no cuesta nada. Detectarlo aparte con `tiny` no sirve: confundió el español con tailandés.

### 3. Más hilos no es más rápido

Mediana de 15 mediciones, con las configuraciones intercaladas y la máquina libre:

| | 2 hilos | **4 hilos** | 6 hilos | 8 hilos |
|---|---|---|---|---|
| `small`, ventana corta | 0.73 s | **0.63 s** | 0.75 s | 0.73 s |
| `small`, ventana de 15 s | 1.76 s | **1.35 s** | 1.49 s | 1.55 s |

El i3-N305 agrupa sus 8 núcleos en 2 bloques de 4 que comparten caché L2. Con 8 hilos los dos bloques tienen que coordinarse y la variación sube (±0.3 s contra ±0.1 s). El valor se cambia con `AUDIOTRANS_HILOS`; en otro CPU conviene medir.

### 4. `trans` era el cuello de botella, no la traducción

| | Tiempo por frase |
|---|---|
| `trans -b` | 0.6–12.6 s (y a veces se colgaba por IPv6) |
| API de Google directa (`translate_a/single?client=gtx`) | ~0.12 s |
| **OPUS-MT local** (CTranslate2 int8) | **30–90 ms** |

OPUS-MT traduce casi igual que Google en frases normales, pero es inconsistente con los modismos. "La neta no tengo idea de qué estás hablando." → "The net has no idea what you're talking about." (aunque "la neta no tengo idea" sí sale bien), y "Me late que va a llover, mejor llévate un paraguas." → "It beats me that it's going to rain…". Para eso está `-g`. Argos Translate también funciona con CTranslate2, pero su modelo español→inglés usa otro formato de tokenizador y pesa 300 MB.

### 5. En tiempo real, lo que más ayuda es el contexto

Para medir la precisión con voz real usé [Mini LibriSpeech](https://www.openslr.org/31/): ~8 min de frases seguidas de tres lectores, con su transcripción de referencia, en versión limpia y con ruido rosa 10 dB por debajo de la voz. El audio pasa por el mismo código del modo `-r` (ver [`pruebas/`](pruebas/)):

| Configuración | Error por palabra | Con ruido | Transcribir una frase |
|---|---|---|---|
| frases sueltas (como estaba) | 14.9 % | 16.8 % | 0.48 s |
| **+ las 2 frases anteriores como contexto** (`-r`) | **8.8 %** | **8.9 %** | 0.62 s |
| + frases más largas (pausa de 0.8 s, hasta 15 s) | 4.5 % | 7.5 % | 0.75 s |
| **+ ventana de 15 s** (`-r -p`) | **4.3 %** | **6.4 %** | 1.34 s |
| + ventana de 30 s | 4.9 % | 6.5 % | 2.81 s |

Whisper acepta el texto anterior como pista (`<|startofprev|>`). Eso le da el tema y los nombres, y casi divide los errores entre dos por 0.14 s más. Además, cortar con una pausa de 0.5 s parte las frases a la mitad; esperar 0.8 s da frases más completas. Con el código real de `-r` a velocidad real, uno de los flujos con ruido pasó de 17.2 % a 6.2 % de error con `-r`, y a 2.6 % con `-p`.

### 6. Modelos descartados

| Modelo | Por qué no |
|---|---|
| `tiny` | 0.16 s, pero "Thursday afternoon" → "first day after whom" |
| `medium` | 1.3 s, 2.5 GB de RAM, y con ventana corta repetía frases |
| `large-v3-turbo` | más de 12 s por frase y 2.2 GB de RAM en CPU |
| `distil-small.en` | solo inglés, y conserva el codificador completo, que es lo caro |

## Estructura

```
bin/audiotrans      graba (micrófono o sistema) y coordina todo
bin/textrans        traduce texto
lib/whisper_corto.py   Whisper con ventana ajustada (descubrimientos 1 y 2)
lib/tiempo_real.py     modo -r: contexto entre frases y traducción en paralelo
lib/frases.py          corta el audio continuo en frases con el VAD
lib/transcribir.py     modo con Enter
lib/traduccion.py      local (OPUS-MT) primero, luego Google y luego trans
lib/texto.py           detección en/es por palabras frecuentes, para textrans
man/audiotrans.1       manual
pruebas/               medición de precisión con voz real (Mini LibriSpeech)
alias.sh            los alias
instalar.sh         instalación
```

## Créditos y licencias

El código de este repositorio usa la licencia [MIT](LICENSE). Usa:
- [Whisper](https://github.com/openai/whisper) (OpenAI, MIT), mediante [faster-whisper](https://github.com/SYSTRAN/faster-whisper) y [CTranslate2](https://github.com/OpenNMT/CTranslate2) (MIT).
- Modelos [Tatoeba-MT / OPUS-MT](https://github.com/Helsinki-NLP/Tatoeba-Challenge) de Helsinki-NLP (Jörg Tiedemann y colaboradores), con licencia **CC-BY 4.0**. `instalar.sh` los descarga y no se redistribuyen aquí. Su licencia y su ficha quedan junto a cada modelo.
- La API de Google que usa `-g` es el mismo servicio no oficial que usa translate-shell.
