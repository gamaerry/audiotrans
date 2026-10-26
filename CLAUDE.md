# CLAUDE.md

Notas para trabajar en el código. Qué hace la herramienta y por qué está diseñada así está en el [README](README.md) (sección *Descubrimientos*); aquí no se repite.

## Estructura de ejecución

- Es un paquete de Python (`audiotrans/`, `pyproject.toml`) que se instala con `uv tool install`; `instalar.sh` lo instala editable desde el repo y corre `audiotrans --setup` (`instalar.py`: traductores y manual).
- `audiotrans` y `practice` son bash (`audiotrans/sh/`). Sus puntos de entrada (`lanzar.py`) los ejecutan con `AUDIOTRANS_PYTHON` = el Python del paquete, y ellos llaman a los módulos con `"$python" -m audiotrans.<módulo>`; el Lua también (`python -m audiotrans.texto` y `audiotrans.dudas`). `textrans` es Python directo (`texto:principal`).
- Los módulos se importan entre sí de forma relativa (`from .traduccion import ...`): ya no se pueden correr como `python archivo.py`.
- Todo lo que no es `.py` (`sh/`, `mpv/`, `man/`, `alias.sh`) va dentro del paquete para que se instale. Una instalación editable no detecta si falta algo: pruébalo con una no editable (abajo).
- Datos fuera del repo, en `$AUDIOTRANS_DATOS` (por defecto `~/.local/share/audiotrans`): `modelos/{en-es,es-en}`, `dudas/` y la clave de OpenSubtitles. Nunca van a git.
- Las opciones viajan del bash a Python por variables de entorno: `AUDIOTRANS_MODEL`, `AUDIOTRANS_RAPIDO`, `AUDIOTRANS_EN_LINEA`, `AUDIOTRANS_HILOS`, `AUDIOTRANS_DATOS`.

## Al cambiar algo

- Actualiza juntos el `--help` (`audiotrans/sh/audiotrans`, `audiotrans/sh/practice` y `audiotrans/texto.py`), `audiotrans/man/audiotrans.1` y el README. Comprueba el manual con `man -l audiotrans/man/audiotrans.1` y `groff -k -man -ww -z` (sin avisos, como en CI).
- Una opción o un alias nuevo también va en `audiotrans/alias.sh` y en `PAGINAS` de `instalar.py` (las páginas `.so` del manual).
- Escribe en español, como el resto: nombres, comentarios y mensajes. La excepción son los comandos, subcomandos y opciones (`practice --prepare`, `--real-time`), que van en inglés para quien no habla español.

## Cómo probar

- **Sin red:** `unshare -rn textrans es "..."` (o `transcribir`) confirma que la traducción local no depende de internet.
- **Tiempo real:** no uses las bocinas, porque `-s` graba *todo* lo que suena (Firefox ya contaminó una prueba). Genera las frases con `espeak-ng -w`, concaténalas con silencios usando `ffmpeg` en un `.raw` s16le de 16 kHz mono, y mándalo a `python -m audiotrans.tiempo_real` a velocidad real con un script que escriba bloques y duerma. Así se miden retrasos exactos y la prueba se puede repetir.
- **`practice` (mpv):** se prueba sin ventana: `mpv --vo=null --ao=null --input-ipc-server=<socket> --msg-level=all=warn,audiotrans=v --script=audiotrans/mpv/audiotrans.lua --script-opts=audiotrans-python=...,audiotrans-srt=...`, y con un script que envíe `keypress` y lea `time-pos`/`pause` por el socket. Con `audiotrans=v`, el registro muestra lo que se dibuja en pantalla (`en pantalla: ...`). Usa un `AUDIOTRANS_DATOS` temporal (con un enlace a `modelos`) para no mezclar las dudas de prueba con las reales. La ruta del socket no puede pasar de ~107 caracteres: con una carpeta larga, ejecuta mpv desde ella y usa una ruta relativa.
- **Instalación:** `UV_TOOL_DIR=<tmp>/tools UV_TOOL_BIN_DIR=<tmp>/bin uv tool install .` instala sin tocar `~/.local/bin`, y no editable, así que detecta los archivos que no se empaquetan. Con `AUDIOTRANS_DATOS` temporal y un enlace a `modelos` se evita bajar otra vez ~580 MB; `HOME=<tmp> audiotrans --setup` no toca el manual real. Para `practice`, un `mpv` falso en el `PATH` que imprima sus argumentos muestra lo que se le pasa sin abrir ventana (así lo hace `pruebas/test_practice.py`).
- `espeak-ng` es más difícil de transcribir que una voz real, sobre todo en español: un error con espeak no siempre es un error real.
- **Precisión de `-r`:** usa `pruebas/` (Mini LibriSpeech, WER contra la referencia). `simular.py` usa el mismo `frases.Segmentador` y el mismo `whisper_corto` que `tiempo_real.py`, sin esperar en tiempo real. Si cambias el corte de frases, cámbialo en `frases.py` y no dupliques la lógica. Para confirmar, pasa un flujo convertido a `.raw` por `tiempo_real.py` a velocidad real.

## Mediciones de rendimiento

- **Avisa al usuario antes de medir:** si la máquina está en uso, los resultados no valen (ya pasó una vez).
- Intercala las configuraciones (A, B, A, B…), haz varias rondas, reporta la mediana y la desviación, y anota la carga (`/proc/loadavg`).
- `transcribe()` de faster-whisper devuelve un generador: mide el tiempo después de consumirlo, no antes.

## Lo frágil

- **Python 3.12** (`requires-python` en `pyproject.toml`): faster-whisper no tiene paquetes para 3.13 o posterior (el sistema tiene 3.15). uv lo baja solo.
- **`av==15.1.0`:** PyAV 16 o posterior rompe faster-whisper 1.2.1, porque `av.open()` ya no acepta `metadata_errors`.
- **`audiotrans/whisper_corto.py`:** llama directamente a `modelo.model.encode/detect_language/generate` de CTranslate2, que es API interna de faster-whisper. Revísalo al actualizar faster-whisper o CTranslate2. Con la ventana corta son necesarios el tope `max_length` (~10 tokens por segundo) y `_sin_bucle`, porque sin ellos Whisper repite la frase en bucle, sobre todo `base` con beam=1. Los cuadros de la ventana deben ser pares.
- **El contexto de `-r`** (las 2 frases anteriores con `<|startofprev|>`, máximo 100 tokens) se reinicia si cambia el idioma detectado. No se usa con `-f`, porque no se midió con `base`.
- **La detección en/es de `audiotrans/texto.py`** exige una ventaja de 2 palabras, porque palabras como "la", "de" o "que" existen en francés, italiano y portugués ("Bonjour, où est la gare?" salía como español). Si no está clara, va a Google, y sin red supone el otro idioma del par.
- **`audiotrans/traduccion.py`** usa la API no oficial `translate.googleapis.com/translate_a/single?client=gtx`, la misma de translate-shell. Si deja de funcionar, cae a `trans -4`; sin `-4`, `trans` se colgaba por IPv6.
- **Medir sincronización** de subtítulos solo con marcas por palabra (`pruebas/desfase_srt.py`). Los inicios de segmento de Whisper tienen errores de ±1 s y llegaron a sugerir un desfase que cambiaba cuando era constante.
- **`audiotrans/sincronizar.py`** busca cada ventana a ±8 s (`MAX_DESFASE`) del desfase de la anterior, porque en versiones de TV sin comerciales el desfase se acumula (+10.4 s al final de 1x02 HDTV). Si el máximo cae en el borde, la ventana se omite y no mueve el centro, para que una ventana mal emparejada no arrastre a las siguientes. Donde dos ventanas seguidas difieren más de `SALTO` (0.3 s) se pone un escalón en lugar de interpolar (`escalones()`); la deriva gradual de 1x01 (≤0.17 s entre ventanas) no lo activa y sale idéntica. Corregir con el desfase de las líneas exactas vecinas se probó y no ayudó. Un `.srt` con escenas de más al inicio (más de 8 s desde la primera ventana) necesitaría un primer ajuste global.
- **El archivo `tt<ID>[.<original>-<destino>]`** de la carpeta del video lo lee `marca_de` en `audiotrans/sh/practice`, con la carpeta del enlace y no la del archivo enlazado (las pruebas usan enlaces). El original llega a `subtitulos.py`, a `alinear.py` (idioma de Whisper; `normalizar` quita acentos para comparar) y al Lua (`audiotrans-origen`).
- **`audiotrans/subtitulos.py`** (OpenSubtitles): las series se buscan con `parent_imdb_id` más temporada y episodio, y las películas con `imdb_id`; los resultados por hash también se filtran por el ID. descargar no requiere sesión (la API reportó 100 al día), pero sí `Api-Key` y un `User-Agent` propio. La búsqueda pide los parámetros en orden alfabético y en minúsculas, o la API redirige. Cada prueba gasta una descarga (bajar otra vez el mismo archivo no contó): reutiliza el `.srt` ya bajado. Sin coincidencia por hash, compara hasta `CANDIDATOS` (una por fuente, según el nombre del release) con `sincronizar.coincidencia`. La diferencia entre WEB y DVD es mínima (0.549 contra 0.545); lo que de verdad separa es la versión de TV.
- **mpv usa Lua 5.1 (LuaJIT):** no hay `//`, `goto` ni operadores de bits, y `string.format("%d")` necesita enteros (`math.floor`). Un error de sintaxis no aparece hasta que mpv carga el script: pruébalo siempre en mpv.
- **`audiotrans/alinear.py`** busca las 3 primeras y 3 últimas palabras de cada línea a ±3 s (`BUSQUEDA`) y exige al menos 2 coincidencias; si la duración resultante no es razonable, conserva el tiempo del `.srt`. El `.json` marca por separado `inicio_exacto` y `fin_exacto`, y el Lua elige el margen de cada extremo según eso. Afinar con wav2vec2 (CTC) se probó: inicios más precisos, pero +11 min por episodio y solo inglés (ver README, descubrimiento 6). Para medir bordes sin depender de Whisper sirve Silero VAD con `speech_pad_ms=0`, aunque en las colas toma voz de otras líneas.
- **`audiotrans/mpv/audiotrans.lua`** recibe las rutas por `--script-opts`, que separa con comas: `practice` rechaza rutas con comas. Los tiempos del `.srt` se desplazan con `sub-delay`. Lua no trae JSON fácil, por eso guardar una duda va en `audiotrans/dudas.py` (subproceso asíncrono, para no congelar el video).
- **Ctrl+C en tiempo real** termina con `os._exit(0)`, porque el hilo lector queda bloqueado en stdin y un cierre normal aborta Python.
- Los parámetros (hilos, ventana mínima de 15 s, pausa de 0.5 s) se midieron en un i3-N305. En otro CPU pueden cambiar. En `alinear.py`, 8 hilos fueron más lentos que 4 (406 s contra 355 s).
