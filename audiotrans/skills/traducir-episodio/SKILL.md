---
name: traducir-episodio
description: Corrige las traducciones de los subtítulos de un episodio o película que el usuario practica con audiotrans/practice en mpv (p. ej. ~/Videos/white-collar/s1-e1.mp4). Úsala cuando diga que una línea se traduce mal o literal ("Cowboy up" sale "Vaquero arriba"), pregunte qué significa una frase de un episodio y quiera dejarla bien traducida, o pida traducir o arreglar las traducciones de un episodio completo ("arregla las traducciones del s1-e2 de White Collar"). Tú haces la traducción, con el contexto de la escena, y la guardas para que la tecla y de practice la muestre.
---

# Traducir bien las líneas de un episodio

El usuario practica listening con `practice <video>` ([audiotrans](https://github.com/gamaerry/audiotrans)), casi siempre en inglés. En mpv, la tecla `y` muestra la traducción de la línea que acaba de pasar. Normalmente la hace el traductor automático (OPUS-MT, o Google), que va frase por frase y traduce literal los modismos: "Cowboy up" → "Vaquero arriba", "the usual chest pounding" → algo como "el golpeteo de pecho habitual".

Tú eres el traductor: lees la línea con su contexto, entiendes qué quiere decir y guardas la traducción buena en `.audiotrans/<video>.<destino>.tsv`, una carpeta oculta junto al video. Desde ahí `y` y `d` (guardar duda) la usan en vez de traducir. El archivo puede tener solo las líneas que corregiste.

Habla con el usuario en español. Si existe `~/.local/share/audiotrans/preferencias-traduccion.md` (o en `$AUDIOTRANS_DATOS`), léelo antes de empezar, una sola vez: ahí el usuario anota sus preferencias (la variante del español, palabras que prefiere, cosas que no debes hacer). Lo que diga ahí manda sobre esta guía.

## Encontrar el episodio

Cada serie o película está en su carpeta (normalmente dentro de `~/Videos/`, p. ej. `~/Videos/white-collar/`), con el video, su `.srt` del mismo nombre y un archivo `tt<ID>…`. Si el usuario da la ruta completa, usa esa. El usuario lo nombra a su manera ("el s1-ep2 de White Collar", "el 1x02", "el segundo capítulo"), y los archivos pueden llamarse `s1-e2.mp4`, `S01E02.mkv`, `1x02…`:

```bash
ls ~/Videos/                       # las series (si no están ahí, pregunta dónde)
ls ~/Videos/white-collar/          # sus episodios
```

Si no hay una coincidencia clara, o el episodio no tiene `.srt` (falta abrirlo una vez con `practice`, que lo baja), pregúntale al usuario antes de seguir.

Antes de traducir, revisa el `.srt` con `practice --status <video>`. Si avisa que tiene palabras pegadas ("year,it's", "trainat"), **díselo al usuario antes de corregir nada**. Un `.srt` así hace que el traductor falle en buena parte de las líneas (en 1x02, el 52 %) y corregirlas gasta muchos tokens; es mejor que baje otra versión:

1. `mv s1-e2.srt s1-e2.srt.malo`, y luego abre el episodio con `practice` (lo baja de nuevo y descarta las versiones mal hechas).
2. Si ya había un `.tsv`, `$PY -m audiotrans.traducciones migrar <video>` pasa al `.srt` nuevo las traducciones que tienen una línea igual.
3. Si el episodio estaba preparado, recuérdale volver a correr `practice --prepare`.

## La herramienta

```bash
PY="$(dirname "$(readlink -f "$(command -v practice)")")/python"   # el Python con el que se instaló audiotrans
$PY -m audiotrans.traducciones revisar  <video> 1 150              # original y traducción automática (lo que muestra y)
$PY -m audiotrans.traducciones buscar   <video> 17:35              # líneas de ±6 s alrededor de ese minuto en mpv
$PY -m audiotrans.traducciones buscar   <video> "cowboy up"        # por texto
$PY -m audiotrans.traducciones exportar <video> 250 290            # un tramo, para leer el contexto
$PY -m audiotrans.traducciones poner    <video> 271 "¿Tengo que quedarme aquí? Aguántate."
printf '271\t...\n272\t...\n' | $PY -m audiotrans.traducciones poner <video> -   # varias de una vez
$PY -m audiotrans.traducciones quitar   <video> 271
$PY -m audiotrans.traducciones validar  <video>
$PY -m audiotrans.traducciones migrar   <video>                    # después de cambiar el .srt por otra versión
```

- `buscar` y `exportar` dan una línea por bloque: número, minuto en mpv, original (los saltos de línea como ` / `) y traducción revisada, si ya la hay.
- `revisar` da solo las líneas que **aún no** tienen traducción revisada: número, original y la traducción automática que mostraría `y`. El traductor local la calcula gratis en la CPU del usuario (~18 s un episodio entero). Es la forma barata de saber qué está mal.
- El **número** es la posición del bloque en el `.srt` original. Es lo que se le pasa a `poner`. `poner` vuelve a mostrar el original de ese número: revísalo para confirmar que pusiste la traducción en la línea correcta.
- El idioma de la traducción sale del archivo `tt<ID>.<original>-<destino>` de la carpeta (sin par, `es`); para otro, agrega `-fr`, etc.
- Si `buscar` avisa que no hay `.srt` sincronizado en la caché, el usuario todavía no ha abierto el episodio con `practice`. Los minutos que muestra son entonces los del original, que pueden diferir ~1 s de lo que ve en mpv.

## Una línea puntual

1. Ubícala con `buscar`, por el minuto que dice el usuario o por un fragmento del texto. Si hay varias candidatas, confirma con él cuál es.
2. Lee el contexto: `revisar` (o `exportar`, si ya hay revisadas) unas 10–15 líneas antes y 5 después. Muchas frases solo se entienden con la anterior ("— Customs playing nice? — The usual chest pounding.").
3. Explícale en una o dos frases qué significa, si te lo preguntó o si el modismo no es obvio.
4. Guarda la traducción con `poner` y corre `validar`.
5. Dile que vuelva a abrir el episodio con `practice` para que la cargue, porque mpv la lee al abrirlo.

## Un episodio completo

Por defecto **revisa**, no traduzcas todo: la mayoría de las líneas ("Sí, está bien.", "¿Qué sabes de él?") ya salen bien, y escribir ~700 traducciones gasta muchos tokens de salida. Solo traduce el episodio entero si el usuario lo pide expresamente.

Cada llamada al modelo vuelve a enviar toda la conversación, así que **cada comando de más cuesta decenas de miles de tokens de entrada**. Haz un episodio en unas 6–8 llamadas:

- **No explores.** La ruta de `$PY`, los archivos y los comandos son los de esta guía. No busques `practice`, no cuentes bloques con tus propios scripts ni vuelvas a leer el `.srt`: `revisar` ya trae el original completo de cada línea.
- **Lee la salida de `revisar` directamente.** No la guardes en un archivo para leerlo después: son dos llamadas en vez de una.
- **Junta guardar y pedir el siguiente tramo en un solo comando**, por ejemplo:

```bash
printf '%s\n' $'3\t...' $'17\t...' | $PY -m audiotrans.traducciones poner <video> - | tail -1; $PY -m audiotrans.traducciones revisar <video> 151 300
```

1. Lee el episodio por tramos de ~150 bloques con `revisar <video> <desde> <hasta>` (un episodio tiene ~600–1000). Cada tramo una sola vez: no vuelvas a pedir tramos ya leídos ni muestres su contenido al usuario.
2. De cada tramo, elige solo las líneas cuya traducción automática esté mal (ver abajo) y guárdalas juntas en un solo `poner <video> -` (una línea `número<TAB>traducción` por bloque). Sin comentarios por línea. Decide rápido: casi todas las líneas están bien o mal a simple vista, y no hace falta pensar mucho cada una.
3. Pasa al tramo siguiente. Si la sesión se corta, se retoma donde iba: `revisar` ya no muestra las líneas guardadas.
4. Al terminar, corre `validar` y dale al usuario un resumen breve: cuántas líneas corregiste y 3–5 ejemplos de los modismos o errores más interesantes.

**Qué corregir:**
- Modismos y frases hechas traducidos literal ("Vaquero arriba", "el golpeteo de pecho habitual").
- Sentido equivocado o sin sentido. Incluye los errores del `.srt`, como palabras pegadas ("a trainat union square" → "una plaza del sindicato del trenat").
- Persona, género, número o tiempo verbal equivocados, cuando cambian lo que se entiende.
- Palabras que en la variante del usuario significan otra cosa o suenan vulgares (en México y buena parte de Latinoamérica, "coger un taxi" → "tomar un taxi").

**Qué no corregir** (a menos que el usuario lo pida):
- Preferencias de estilo o regionales que no confunden ("de acuerdo"/"está bien", "vale" en lugar de "ok"), ni traducciones aceptables que tú dirías de otra forma.
- Las líneas que no son diálogo: créditos y publicidad de quien hizo los subtítulos (direcciones web, "proudly presents", "subtitles by…") y datos técnicos ("23.976"). Sáltalas.

**Números y unidades como se dicen.** Es práctica de listening: si se oye "two miles", la traducción dice "dos millas", no "tres kilómetros". No conviertas millas, pies, libras ni dólares, y no corrijas una línea solo por eso.

## Cómo traducir

- **El sentido, no las palabras.** Un modismo se traduce por su equivalente en español ("Cowboy up" → "Aguántate" o "Sé fuerte"; "Get a load of that…" → "¿Ya viste a…?"), y una frase hecha, por la frase hecha que se usaría en esa situación.
- **Español natural y hablado**, en la variante del usuario (la de su archivo de preferencias; si no la sabes, un español latinoamericano neutro), como lo diría la gente en esa escena. Conserva el registro: si es grosero, que siga siéndolo; si es formal, formal.
- **Breve, como un subtítulo.** Sin notas, explicaciones ni corchetes dentro de la traducción: las explicaciones van en tu respuesta al usuario.
- Mantén los nombres propios, y las siglas y los términos del FBI o legales tal como se dicen en español ("FBI", "orden de cateo").
- Si el bloque tiene dos personas hablando (`- …` / `- …`), conserva los dos guiones en la traducción.
- Si el original está mal transcrito (por ejemplo "loan" donde por el sentido es "load"), traduce lo que se dice en la escena y avísale al usuario. El `.srt` no lo corrijas, a menos que te lo pida: si cambia, las filas que ya no coinciden se ignoran.

## No hagas

- No edites el `.srt`, los archivos de la caché (`~/.cache/audiotrans/`) ni el código de audiotrans, y tampoco `.audiotrans/<video>.<destino>.automaticas.tsv`: ahí `revisar` guarda solo las automáticas, para no calcularlas otra vez. Todo va en el `.tsv` y siempre con `poner` y `quitar`, no a mano: el formato lleva tabuladores y el original de cada fila tiene que coincidir con el `.srt`.
- No uses Google ni `textrans` para traducir: el punto es que traduzcas tú, con el contexto.
- No instales, actualices ni configures nada: todo lo que necesitas ya está instalado.
