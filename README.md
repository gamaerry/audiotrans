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

### Practicar listening con series

`practice episodio.mp4` abre el video en mpv con los subtítulos **ocultos**. Cuando no entiendes algo, lo consultas línea por línea sin salir del video. El orden está pensado para que primero vuelvas a escuchar, luego leas en inglés y al final traduzcas:

| Tecla | |
|---|---|
| `r` | repite la línea que acaba de pasar y pausa al terminarla |
| `R` | la repite más lento (0.75×) y con su texto en pantalla |
| `e` | pasa a la línea anterior, si `r` no cayó en la que querías (cada `e`, una más atrás) |
| `E` | pasa a la línea siguiente |
| `t` | muestra el texto original |
| `y` | muestra la traducción (la revisada del episodio, si la hay) |
| `d` | guarda la duda: texto, traducción y fragmento de audio |
| `c` | sigue viendo con los subtítulos visibles (otra vez `c` para quitarlos) |
| `q` | quita la repetición o el texto y sigue viendo normal; para salir, `Q` (mpv recuerda dónde ibas) |

Cada serie o película va en su carpeta, con un archivo vacío que dice su ID de [IMDb](https://www.imdb.com/) (está en la dirección, `imdb.com/title/tt1358522/`) y el par de idiomas: el original, que es el que se practica, y al que se traduce. Sin par se usa `en-es`.

```bash
touch ~/Videos/white-collar/tt1358522        # en-es
touch ~/Videos/amelie/tt0211915.fr-es
```

Si el nombre del video tiene temporada y episodio (`s1-e3`, `S01E03`, `t1e3`, `1x03`), es un episodio de esa serie; si no, la película, sin importar cómo se llame el archivo. `-<destino>` al abrirlo cambia la traducción solo esa vez.

Usa el `.srt` con el mismo nombre que el video. Si no existe, lo baja de [OpenSubtitles](https://www.opensubtitles.com/) en el idioma original: primero busca por el hash del archivo y, si no hay, por el ID de IMDb. Con el ID no se confunden obras con el mismo nombre (buscando "the office" salían mezcladas la británica, la de EE. UU. y la de 2024). En ese caso baja hasta 3 versiones, la más descargada de cada fuente (TV, WEB, DVD), y se queda con la que, ya sincronizada, mejor coincide con la voz (~10 s más). Antes descarta las que tienen el texto mal hecho, con palabras y signos pegados ("year,it's", "a trainat union square"), si hay alguna limpia: la más descargada de White Collar 1x02 tenía así el 38 % de las líneas, y la coincidencia con la voz no lo nota. `practice --status` avisa si un `.srt` que ya tienes está así. Necesita una clave de API, que se crea en [opensubtitles.com/consumers](https://www.opensubtitles.com/en/consumers) y se guarda como `api_key=<clave>` en `~/.local/share/audiotrans/opensubtitles`; sin iniciar sesión, OpenSubtitles da 100 descargas al día. Muchos `.mkv` traen los subtítulos dentro y se extraen con `ffmpeg -i video.mkv -map 0:s:0 video.srt`. La primera vez que abres un episodio, los subtítulos se **sincronizan con el audio por tramos** (~15 s, se guarda en caché): si el `.srt` es de otra versión del video, cada parte del episodio se corrige por separado. `practice saved` lista lo guardado.

Para que `r` repita con el tiempo exacto, prepara los episodios con anticipación, cuando no uses la computadora: `practice --prepare ~/Videos/serie` (o solo algunos episodios). Whisper ubica cada línea palabra por palabra (~6 min por episodio, con prioridad baja). Al verlos ya no se usa CPU extra. `practice --status` dice cuáles de la carpeta actual ya están preparados; también acepta carpetas o videos sueltos, y salta lo que no es video.

Los dos traductores (el local y Google) van frase por frase y traducen literal los modismos poco comunes: "Cowboy up" sale "Vaquero arriba" en ambos, y "the usual chest pounding", algo como "el golpeteo de pecho habitual". Para esas líneas hay **traducciones revisadas**: un archivo `s1-e1.es.tsv` junto al video, con una fila por línea corregida (número de bloque del `.srt`, texto original y traducción, separados por tabuladores). `y` y `d` las usan en vez de traducir, y el archivo puede tener solo algunas líneas. Lo puede escribir cualquier agente (Claude, Gemini, Codex…), que traduce con el contexto de la escena, con [`audiotrans/traducciones.py`](audiotrans/traducciones.py):

```bash
python -m audiotrans.traducciones revisar s1-e1.mp4 1 150       # original y traducción automática
python -m audiotrans.traducciones buscar s1-e1.mp4 17:35        # las líneas de ese minuto en mpv
python -m audiotrans.traducciones buscar s1-e1.mp4 "cowboy up"
python -m audiotrans.traducciones poner s1-e1.mp4 271 "¿Tengo que quedarme aquí? Aguántate."
python -m audiotrans.traducciones exportar s1-e1.mp4 1 120     # para traducir por tramos
python -m audiotrans.traducciones validar s1-e1.mp4
```

Para no escribir el prompt cada vez, `practice --translate s1-e2.mp4` abre la conversación del agente, en la carpeta del video, con el prompt ya escrito (usar la skill `traducir-episodio` sobre el episodio completo y gastar pocos tokens). `--agent` elige entre `claude` (el de omisión, o `$AUDIOTRANS_AGENTE`), `gemini`, `codex`, `opencode`, `grok` y `agy`, y `--model` el modelo, con el nombre que use ese agente. Con una carpeta o varios videos abre uno tras otro: una conversación por episodio sale más barata que todos en una, porque cada llamada al modelo reenvía la conversación entera. `practice --status` dice cuántas traducciones revisadas tiene cada episodio. La skill vive fuera del repo, en `~/.agents/skills/traducir-episodio/`.

`revisar` traduce con el modelo local, en un lote, las líneas que aún no están revisadas (~18 s el episodio completo) y muestra cada original junto a lo que mostraría `y`. Así el agente solo escribe las que están mal, en vez de traducir el episodio entero, y gasta muchos menos tokens. Cada fila guarda también el texto original: si el `.srt` cambia (se corrige o se baja otra versión), las filas que ya no coinciden se ignoran y esas líneas se traducen como siempre. `migrar` pasa al `.srt` nuevo las que tienen una línea con el mismo texto (en 1x02, 159 de 361; las demás estaban cortadas distinto).

Opciones de los comandos de audio (`audiotrans`):

| Opción | |
|---|---|
| `-r`, `--real-time` | escucha sin parar y traduce cada frase al detectar una pausa |
| `-l`, `--loop` | repite el modo con Enter |
| `-<origen>` | idioma del audio (`-en`, `-ja`…); si no se da, se detecta |
| `-p`, `--accurate` | con `-r`: frases más largas y ventana de 15 s; ~4 % de error en lugar de ~9 %, con ~2 s de retraso |
| `-f`, `--fast` | modelo `base`: la mitad de RAM, ~0.25 s por frase, menos preciso |
| `-g`, `--google` | traduce con Google aunque haya modelo local (entiende jerga) |
| `-s`, `--system` | graba la salida de audio en lugar del micrófono |

`es`, `en`, `cbes` y los demás alias de texto aceptan `-g` y `-<origen>`. Todo está documentado en `man audiotrans` y en `--help`.

## Instalación

```bash
uv tool install git+https://github.com/gamaerry/audiotrans.git
audiotrans --setup
```

[uv](https://docs.astral.sh/uv/) instala los comandos `audiotrans`, `textrans` y `practice` en `~/.local/bin`, con su propio Python 3.12 (faster-whisper no tiene paquetes para 3.13 o posterior). `audiotrans --setup` descarga los dos traductores locales (~580 MB, que quedan en 164 MB) y los convierte a CTranslate2 en int8, instala el manual en `~/.local/share/man` y dice qué línea agregar a `~/.bashrc` para los alias. Sin `--setup` todo funciona, pero la traducción va a Google (y lo avisa). Whisper `small` (~460 MB) se descarga la primera vez que se usa; en total son unos 1.2 GB de disco (`base`, con `-f`, unos 140 MB más).

Para trabajar en el código, `./instalar.sh` desde el repo hace lo mismo con una instalación editable: lo que cambies se usa al instante. `uv run --extra pruebas pytest` corre las pruebas, que también corren en GitHub Actions.

### Qué se necesita

- **Linux con PipeWire** (`pw-record` y `pactl`), para grabar el micrófono o lo que suena. En macOS o Windows no funciona la grabación.
- **mpv** y **ffmpeg**, para `practice`. `trans` ([translate-shell](https://github.com/soimort/translate-shell)) y `wl-paste` son opcionales.
- Se probó en Fedora con un Intel i3-N305 (8 núcleos, sin GPU, 8 GB de RAM). Los parámetros (4 hilos, pausas, ventanas) se midieron ahí; en otro CPU puede convenir otro `AUDIOTRANS_HILOS`.

### Cuándo se usa internet

Whisper siempre corre en la propia máquina. La traducción es local solo entre inglés y español, y solo con los traductores de `--setup`. Va a Google cuando:
- el par de idiomas es otro (p. ej. francés → español, o el destino de una carpeta `tt….fr-es`);
- se pide con `-g`;
- `textrans` no distingue si el texto está en inglés o en español (sin conexión, supone el otro idioma del par y traduce en local);
- faltan los traductores locales.

Para eso usa `translate.googleapis.com/translate_a/single`, el mismo servicio no oficial que translate-shell: no tiene clave ni garantías y puede dejar de funcionar o limitarse sin aviso. Si falla, intenta con `trans`. `practice` también usa la red para bajar subtítulos de OpenSubtitles cuando el video no trae `.srt`.

## Descubrimientos

Todo se midió en una laptop con **Intel i3-N305** (8 núcleos eficientes, AVX2 + AVX-VNNI, sin GPU) y 8 GB de RAM. Las mediciones de velocidad usan frases generadas con `espeak-ng`, una voz robótica más difícil de transcribir que una real. La precisión en tiempo real (sección 5) se midió con voz humana real y su transcripción de referencia.

### 1. Whisper desperdicia el 80 % del tiempo en relleno

faster-whisper rellena todo audio hasta 30 s, y el codificador, que es la parte cara en CPU, procesa esos 30 s aunque la frase dure 3. [`audiotrans/whisper_corto.py`](audiotrans/whisper_corto.py) llama directamente a CTranslate2 con una ventana del tamaño de la frase más 1 s:

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

### 6. Sincronizar subtítulos por tramos

Los `.srt` descargados suelen ser de otra versión del video. En White Collar 1x01, el subtítulo aparecía ~1.25 s antes que la voz, así que repetir una línea la cortaba antes de que el actor terminara. [`audiotrans/sincronizar.py`](audiotrans/sincronizar.py) marca con el VAD dónde hay voz y, en ventanas de 5 min cada minuto, busca el desplazamiento que mejor encima los subtítulos sobre la voz. Cada línea toma el de su zona, de modo que también se corrigen desfases que cambian a lo largo del episodio. Medido con las marcas por palabra de Whisper en 8 zonas ([`pruebas/desfase_srt.py`](pruebas/desfase_srt.py)):

| | desfase |
|---|---|
| `.srt` original | −1.17 a −1.39 s |
| [ffsubsync](https://github.com/smacke/ffsubsync) (un solo desplazamiento) | −0.09 a −0.33 s |
| **por tramos** | **−0.15 a +0.07 s** |

Cada ventana busca a ±8 s del desfase de la anterior, no de 0, porque en las versiones de TV a las que les recortaron los comerciales el desfase se acumula. El `.srt` HDTV de 1x02 que bajó OpenSubtitles se adelanta ~2.5 s más en cada corte, hasta 10.4 s al final. Buscando a ±8 s de 0, la segunda mitad quedaba 2.3 s antes que la voz; con la búsqueda relativa, de −0.3 a +0.25 s en 7 de las 8 zonas, y −0.74 s en la que queda junto a un corte (las ventanas de 5 min suavizan el salto).

Esos cambios son escalones, pero al principio se interpolaban en línea recta entre las ventanas, y cada salto quedaba repartido en un minuto. Ahora, donde dos ventanas seguidas difieren más de 0.3 s, cada línea toma uno u otro desfase, y la frontera es la que mejor encima los subtítulos sobre la voz. Una deriva gradual, como la de 1x01, se sigue interpolando. Medido línea por línea contra las palabras de Whisper (la referencia se busca desde las dos sincronizaciones y solo cuentan las líneas en que coinciden):

| líneas desfasadas más de 1 s | interpolado | escalones |
|---|---|---|
| 1x02 HDTV, todas / a ±2 min de un corte | 14.0 % / 20.4 % | **6.2 % / 3.1 %** |
| 1x03 HDTV, todas / a ±2 min de un corte | 14.6 % / 27.4 % | **5.5 % / 4.3 %** |
| 1x01 y 1x03 WEB (sin cortes) | igual | igual |

Como las versiones de TV tienen otros cortes, cuando OpenSubtitles no tiene el `.srt` del mismo archivo se comparan versiones de fuentes distintas, porque las de una misma fuente tienen los mismos cortes. En 1x03, la más descargada era HDTV (78 717 descargas). Ya sincronizadas, la correlación entre voz y subtítulos fue de 0.518 para HDTV, 0.549 para WEB-DL y 0.545 para DVD. Medido por palabra, WEB y DVD quedaron dentro de ±0.21 s en las 8 zonas; HDTV quedó a −1.21 s en una y tenía menos líneas reconocibles (14 contra 24 en una zona).

Aun sincronizado, cada línea tiene su propio error de tiempo, porque quien hace los subtítulos no los ajusta al milisegundo. Por eso `r` empieza 0.9 s antes y termina 0.5 s después: con el inicio de cada palabra medido en 120 líneas, 0.9 s cubre el 95 % de los inicios (0.3 s solo el 84 %), y 0.5 s el 100 % de los finales. Ajustar cada inicio a donde el VAD detecta voz lo empeoró (de 14 % a 17–24 % de líneas que empezaban tarde), porque con música y efectos el VAD no es preciso al décimo de segundo.

Con `practice --prepare`, [`audiotrans/alinear.py`](audiotrans/alinear.py) transcribe el episodio entero con marcas por palabra y ubica la primera y la última palabra de cada línea cerca de donde dice el `.srt`. En 1x01 encontró el 75 % de las líneas, en 7 min 53 s. Las que faltan son canciones, frases muy cortas y frases que Whisper oyó distinto. Contra una medición aparte, 0.5 s de margen cubre el 95 % de esos inicios y 0.4 s el 100 % de los finales, así que esas líneas se repiten casi sin oír la anterior.

También probé corregir las líneas sin tiempo exacto con el desfase de sus vecinas exactas, y no ayudó: en 1x01 la mediana del error bajó de 0.18 a 0.16 s, pero las que empezaban tarde subieron de 6.4 % a 7.3 %. El error de cada línea es de quien hizo los subtítulos, y no se comparte con las vecinas.

Para que tarde menos medí cuatro configuraciones en 1x01, intercaladas en 3 rondas (mediana; la desviación fue de 1–2 s):

| | tiempo | líneas exactas |
|---|---|---|
| `small`, beam 5, 4 hilos (antes) | 465 s | 801 (75.0 %) |
| **`small`, beam 1, 4 hilos** | **355 s** | **795 (74.4 %)** |
| `small`, beam 1, 8 hilos | 406 s | 795 (74.4 %) |
| `distil-small.en`, beam 1, 8 hilos | 328 s | ~673 (63 %) |

Con beam 1 los finales casi no cambian, pero el 11 % de los inicios se movieron más de 0.2 s, hacia los dos lados. Como árbitro, Whisper `medium` transcribió solo esas líneas: quedó más cerca de beam 1 en 55 y de beam 5 en 31 (error mediano 0.23 s contra 0.39 s). Más hilos no ayudan en el i3-N305, y `distil-small.en` pierde 12 puntos de líneas exactas y solo sirve para inglés.

También probé afinar los bordes con alineación forzada CTC (wav2vec2-base-960h en ONNX): Whisper ubica cada línea y wav2vec2 busca sus letras a ±0.5 s. Contra los bordes de voz de Silero VAD (que coinciden con la energía del audio, mediana 0.01 s), el inicio pasó de 0.32 a 0.07 s de error mediano: Whisper pone los inicios ~0.3 s antes. Pero se adelanta hacia el lado seguro, así que con el margen de 0.5 s al repetir solo se ahorraría ~0.2 s de la línea anterior. Los fines quedaron casi igual (0.19 contra 0.16 s). No lo usé porque las emisiones de 1x01 tardaron 672 s, que se suman a los de Whisper, porque el modelo solo sirve para inglés y porque la versión int8 transcribe con muchos errores.

Una lección: medir con el inicio de los segmentos de Whisper, en lugar de por palabra, sugirió que el desfase cambiaba hacia el final, cuando en realidad era constante.

### 7. Modelos descartados

| Modelo | Por qué no |
|---|---|
| `tiny` | 0.16 s, pero "Thursday afternoon" → "first day after whom" |
| `medium` | 1.3 s, 2.5 GB de RAM, y con ventana corta repetía frases |
| `large-v3-turbo` | más de 12 s por frase y 2.2 GB de RAM en CPU |
| `distil-small.en` | solo inglés, y conserva el codificador completo, que es lo caro |

## Estructura

```
audiotrans/
  sh/audiotrans      graba (micrófono o sistema) y coordina todo
  sh/practice        abre un video en mpv para practicar listening
  lanzar.py          comandos audiotrans y practice: ejecutan sh/ con el Python del paquete
  texto.py           textrans: detección en/es por palabras frecuentes
  traduccion.py      local (OPUS-MT) primero, luego Google y luego trans
  instalar.py        audiotrans --setup: traductores y manual
  mpv/audiotrans.lua teclas r/R/e/E/t/y/d/c/q dentro de mpv
  dudas.py           guarda las dudas con su fragmento de audio
  traducciones.py    traducciones revisadas de un episodio (<video>.<destino>.tsv)
  sincronizar.py     sincroniza el .srt con el audio por tramos
  subtitulos.py      baja el .srt de OpenSubtitles si falta
  alinear.py         ubica cada línea palabra por palabra (practice --prepare)
  whisper_corto.py   Whisper con ventana ajustada (descubrimientos 1 y 2)
  tiempo_real.py     modo -r: contexto entre frases y traducción en paralelo
  frases.py          corta el audio continuo en frases con el VAD
  transcribir.py     modo con Enter
  man/audiotrans.1   manual
  alias.sh           los alias
pruebas/             pruebas automáticas (test_*.py) y medición de precisión con voz real
pyproject.toml       paquete y dependencias
instalar.sh          instalación editable desde el repo
```

## Créditos y licencias

El código de este repositorio usa la licencia [MIT](LICENSE). Usa:
- [Whisper](https://github.com/openai/whisper) (OpenAI, MIT), mediante [faster-whisper](https://github.com/SYSTRAN/faster-whisper) y [CTranslate2](https://github.com/OpenNMT/CTranslate2) (MIT).
- Modelos [Tatoeba-MT / OPUS-MT](https://github.com/Helsinki-NLP/Tatoeba-Challenge) de Helsinki-NLP (Jörg Tiedemann y colaboradores), con licencia **CC-BY 4.0**. `audiotrans --setup` los descarga y no se redistribuyen aquí. Su licencia y su ficha quedan junto a cada modelo.
- La API de Google que usa la traducción en línea es el mismo servicio no oficial que usa translate-shell (ver *Cuándo se usa internet*).
