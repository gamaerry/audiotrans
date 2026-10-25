# CLAUDE.md

Notas para trabajar en el código. Qué hace la herramienta y por qué está diseñada así está en el [README](README.md) (sección *Descubrimientos*); aquí no se repite.

## Estructura de ejecución

- `bin/audiotrans` y `bin/textrans` son bash. Encuentran `lib/` con `readlink -f "$0"`, porque `instalar.sh` los enlaza en `~/.local/bin`, y llaman al Python del venv.
- Datos fuera del repo, en `$AUDIOTRANS_DATOS` (por defecto `~/.local/share/audiotrans`): `venv/` y `modelos/{en-es,es-en}`. Nunca van a git (ver `.gitignore`).
- Los scripts de `lib/` se ejecutan directamente, sin paquete; se importan entre sí porque Python agrega la carpeta del script a `sys.path`.
- Las opciones viajan del bash a Python por variables de entorno: `AUDIOTRANS_MODEL`, `AUDIOTRANS_RAPIDO`, `AUDIOTRANS_EN_LINEA`, `AUDIOTRANS_HILOS`, `AUDIOTRANS_DATOS`.

## Al cambiar algo

- Actualiza juntos el `--help` (`bin/audiotrans` y `lib/texto.py`), `man/audiotrans.1` y el README. Comprueba el manual con `man -l man/audiotrans.1`.
- Una opción o un alias nuevo también va en `alias.sh` y en la lista de páginas `.so` de `instalar.sh`.
- Escribe en español, como el resto: nombres, comentarios y mensajes.

## Cómo probar

- **Sin red:** `unshare -rn bin/textrans es "..."` (o `transcribir.py`) confirma que la traducción local no depende de internet.
- **Tiempo real:** no uses las bocinas, porque `-s` graba *todo* lo que suena (Firefox ya contaminó una prueba). Genera las frases con `espeak-ng -w`, concaténalas con silencios usando `ffmpeg` en un `.raw` s16le de 16 kHz mono, y mándalo a `lib/tiempo_real.py` a velocidad real con un script que escriba bloques y duerma. Así se miden retrasos exactos y la prueba se puede repetir.
- **`practicar` (mpv):** se prueba sin ventana: `mpv --vo=null --ao=null --input-ipc-server=<socket> --msg-level=all=warn,audiotrans=v --script=mpv/audiotrans.lua --script-opts=...`, y con un script que envíe `keypress` y lea `time-pos`/`pause` por el socket. Con `audiotrans=v`, el registro muestra lo que se dibuja en pantalla (`en pantalla: ...`). Usa un `AUDIOTRANS_DATOS` temporal (con enlaces a `venv` y `modelos`) para no mezclar las dudas de prueba con las reales.
- **Instalación:** `AUDIOTRANS_DATOS=$(mktemp -d) ./instalar.sh` prueba la instalación desde cero (descarga ~580 MB). Recuerda que también reescribe los enlaces de `~/.local/bin`.
- `espeak-ng` es más difícil de transcribir que una voz real, sobre todo en español: un error con espeak no siempre es un error real.
- **Precisión de `-r`:** usa `pruebas/` (Mini LibriSpeech, WER contra la referencia). `simular.py` usa el mismo `frases.Segmentador` y el mismo `whisper_corto` que `tiempo_real.py`, sin esperar en tiempo real. Si cambias el corte de frases, cámbialo en `frases.py` y no dupliques la lógica. Para confirmar, pasa un flujo convertido a `.raw` por `tiempo_real.py` a velocidad real.

## Mediciones de rendimiento

- **Avisa al usuario antes de medir:** si la máquina está en uso, los resultados no valen (ya pasó una vez).
- Intercala las configuraciones (A, B, A, B…), haz varias rondas, reporta la mediana y la desviación, y anota la carga (`/proc/loadavg`).
- `transcribe()` de faster-whisper devuelve un generador: mide el tiempo después de consumirlo, no antes.

## Lo frágil

- **Python 3.12 en el venv:** faster-whisper no tiene paquetes para 3.13 o posterior (el sistema tiene 3.15).
- **`av==15.1.0`:** PyAV 16 o posterior rompe faster-whisper 1.2.1, porque `av.open()` ya no acepta `metadata_errors`.
- **El venv no se puede mover:** los ejecutables de `venv/bin` tienen la ruta absoluta en el shebang. Si se mueve, hay que corregirlos con `sed` (ya pasó).
- **`lib/whisper_corto.py`:** llama directamente a `modelo.model.encode/detect_language/generate` de CTranslate2, que es API interna de faster-whisper. Revísalo al actualizar faster-whisper o CTranslate2. Con la ventana corta son necesarios el tope `max_length` (~10 tokens por segundo) y `_sin_bucle`, porque sin ellos Whisper repite la frase en bucle, sobre todo `base` con beam=1. Los cuadros de la ventana deben ser pares.
- **El contexto de `-r`** (las 2 frases anteriores con `<|startofprev|>`, máximo 100 tokens) se reinicia si cambia el idioma detectado. No se usa con `-f`, porque no se midió con `base`.
- **La detección en/es de `lib/texto.py`** exige una ventaja de 2 palabras, porque palabras como "la", "de" o "que" existen en francés, italiano y portugués ("Bonjour, où est la gare?" salía como español). Si no está clara, va a Google, y sin red supone el otro idioma del par.
- **`lib/traduccion.py`** usa la API no oficial `translate.googleapis.com/translate_a/single?client=gtx`, la misma de translate-shell. Si deja de funcionar, cae a `trans -4`; sin `-4`, `trans` se colgaba por IPv6.
- **Medir sincronización** de subtítulos solo con marcas por palabra (`pruebas/desfase_srt.py`). Los inicios de segmento de Whisper tienen errores de ±1 s y llegaron a sugerir un desfase que cambiaba cuando era constante.
- **`lib/sincronizar.py`** busca cada ventana a ±8 s (`MAX_DESFASE`) del desfase de la anterior, porque en versiones de TV sin comerciales el desfase se acumula (+10.4 s al final de 1x02 HDTV). Si el máximo cae en el borde, la ventana se omite y no mueve el centro, para que una ventana mal emparejada no arrastre a las siguientes. Un `.srt` con escenas de más al inicio (más de 8 s desde la primera ventana) necesitaría un primer ajuste global.
- **`lib/subtitulos.py`** (OpenSubtitles): descargar no requiere sesión (la API reportó 100 al día), pero sí `Api-Key` y un `User-Agent` propio. La búsqueda pide los parámetros en orden alfabético y en minúsculas, o la API redirige. Cada prueba gasta una descarga (bajar otra vez el mismo archivo no contó): reutiliza el `.srt` ya bajado. Sin coincidencia por hash, compara hasta `CANDIDATOS` (una por fuente, según el nombre del release) con `sincronizar.coincidencia`. La diferencia entre WEB y DVD es mínima (0.549 contra 0.545); lo que de verdad separa es la versión de TV.
- **mpv usa Lua 5.1 (LuaJIT):** no hay `//`, `goto` ni operadores de bits, y `string.format("%d")` necesita enteros (`math.floor`). Un error de sintaxis no aparece hasta que mpv carga el script: pruébalo siempre en mpv.
- **`lib/alinear.py`** busca las 3 primeras y 3 últimas palabras de cada línea a ±3 s (`BUSQUEDA`) y exige al menos 2 coincidencias; si la duración resultante no es razonable, conserva el tiempo del `.srt`. El `.json` marca por separado `inicio_exacto` y `fin_exacto`, y el Lua elige el margen de cada extremo según eso.
- **`mpv/audiotrans.lua`** recibe las rutas por `--script-opts`, que separa con comas: `practicar` rechaza rutas con comas. Los tiempos del `.srt` se desplazan con `sub-delay`. Lua no trae JSON fácil, por eso guardar una duda va en `lib/dudas.py` (subproceso asíncrono, para no congelar el video).
- **Ctrl+C en tiempo real** termina con `os._exit(0)`, porque el hilo lector queda bloqueado en stdin y un cierre normal aborta Python.
- Los parámetros (hilos, ventana mínima de 15 s, pausa de 0.5 s) se midieron en un i3-N305. En otro CPU pueden cambiar.
