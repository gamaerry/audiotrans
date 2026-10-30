-- Práctica de listening en mpv: los subtítulos van ocultos y se consultan línea por línea.
--   r  repetir la línea que acaba de pasar (y pausar al terminarla)
--   R  repetirla más lento (0.75×) y con su texto en pantalla
--   e  ir a la línea anterior, por si r no cayó en la que se quería (cada e, una más atrás)
--   E  ir a la línea siguiente (lo contrario de e)
--   t  mostrar el texto original de la línea
--   y  mostrar la traducción (la revisada del .tsv del episodio, si la hay)
--   d  guardar la línea como duda, con su audio (para repasar en Anki)
--   c  seguir viendo con los subtítulos de mpv visibles (otra vez c para quitarlos)
--   C  seguir viendo con los subtítulos y su traducción debajo (otra vez C para quitarlos)
--   q  quitar la repetición o el texto y seguir viendo normal (ya no cierra mpv: eso queda en Q)
-- Se carga con el comando practice, que le pasa las rutas en script-opts.

local mp = require "mp"
local utils = require "mp.utils"
local options = require "mp.options"

local opts = { srt = "", json = "", traducciones = "", python = "", destino = "es", origen = "en" }
options.read_options(opts, "audiotrans")

-- Cada línea del .srt tiene su propio error de tiempo, aunque esté sincronizada. Medido con
-- Whisper por palabra en White Collar 1x01: empezar 0.9 s antes cubre el 95 % de las líneas
-- (0.3 s solo el 84 %), y terminar 0.5 s después, el 100 %
local MARGEN_INICIO = 0.9
local MARGEN_FIN = 0.5
-- Con practice --prepare, las líneas que Whisper ubicó palabra por palabra (75 % en 1x01)
-- tienen su tiempo casi exacto: contra una medición aparte, 0.5 s antes cubre el 95 % de los
-- inicios y 0.4 s después el 100 % de los finales
local MARGEN_INICIO_EXACTO = 0.5
local MARGEN_FIN_EXACTO = 0.4
local LENTO = 0.75

local lineas = {}        -- { inicio = s, fin = s, texto = "...", pos, inicio_exacto, fin_exacto, traduccion, automatica }
                         -- (tiempo del .srt; pos: número de bloque en el .srt original;
                         -- automatica: la del traductor, pedida en lote por C)
local foco = nil         -- índice de la línea con la que se está trabajando
local pausar_en = nil    -- tiempo (del video) en el que pausar al terminar una repetición
local velocidad = nil    -- velocidad de antes de una repetición lenta, para restaurarla
local buscando = false   -- mientras llega el salto de una repetición, time-pos aún puede ser el de antes
local overlay = mp.create_osd_overlay("ass-events")
local mostrado = {}      -- lo que se ve en pantalla: { original = ..., traduccion = ... }
local subs_ocultos = false  -- dibujar() quitó los subtítulos de mpv para que no se encimen
local overlay_dobles = mp.create_osd_overlay("ass-events")
local dobles = false     -- C: cada línea se ve al pasar, con su traducción debajo
local doble_actual = nil -- índice de la línea dibujada en overlay_dobles
local pedidas = false    -- ya se pidieron las traducciones automáticas que faltan

local function a_segundos(h, m, s, ms)
    return tonumber(h) * 3600 + tonumber(m) * 60 + tonumber(s) + tonumber(ms) / 1000
end

local function limpiar(texto)
    texto = texto:gsub("<[^>]+>", ""):gsub("{[^}]*}", "")  -- etiquetas HTML y de estilo ASS
    return texto:gsub("^%s+", ""):gsub("%s+$", "")
end

local function cargar_srt(ruta)
    local f = io.open(ruta, "r")
    if not f then return false end
    local contenido = f:read("*a"):gsub("^\239\187\191", ""):gsub("\r", "")  -- quita BOM y CRLF
    f:close()
    local pos = 0
    for bloque in (contenido .. "\n\n"):gmatch("(.-)\n\n+") do
        local h1, m1, s1, ms1, h2, m2, s2, ms2, resto = bloque:match(
            "(%d+):(%d+):(%d+)[,.](%d+)%s*%-%->%s*(%d+):(%d+):(%d+)[,.](%d+)[^\n]*\n?(.*)")
        if h1 then
            -- sincronizar.py y alinear.py conservan todos los bloques en orden: la posición
            -- es la misma que en el .srt original, aunque los bloques vacíos se salten
            pos = pos + 1
            local texto = limpiar(resto)
            if texto ~= "" then
                table.insert(lineas, { inicio = a_segundos(h1, m1, s1, ms1), fin = a_segundos(h2, m2, s2, ms2), texto = texto, pos = pos })
            end
        end
    end
    table.sort(lineas, function(a, b) return a.inicio < b.inicio end)
    return #lineas > 0
end

local function cargar_json(ruta)
    -- Generado por audiotrans/alinear.py (practice --prepare)
    local f = io.open(ruta, "r")
    if not f then return false end
    local datos = utils.parse_json(f:read("*a"))
    f:close()
    for pos, l in ipairs((datos and datos.lineas) or {}) do
        l.pos = pos
        if l.texto ~= "" then table.insert(lineas, l) end
    end
    table.sort(lineas, function(a, b) return a.inicio < b.inicio end)
    return #lineas > 0
end

local function normalizar(texto)
    -- Lo mismo que normalizar() de audiotrans/traducciones.py: solo letras y números ASCII
    return (limpiar(texto):lower():gsub("[^a-z0-9]", ""))
end

local function cargar_traducciones(ruta)
    -- <video>.<destino>.tsv (audiotrans/traducciones.py): número de bloque, original y traducción.
    -- Una fila cuyo original ya no coincide con la línea (el .srt cambió) se ignora
    local f = io.open(ruta, "r")
    if not f then return 0 end
    local filas = {}
    for linea in f:read("*a"):gmatch("[^\n]+") do
        local n, original, traduccion = linea:match("^(%d+)\t([^\t]*)\t(.-)%s*$")
        if n and traduccion ~= "" then filas[tonumber(n)] = { original = original, traduccion = traduccion } end
    end
    f:close()
    local usadas = 0
    for _, l in ipairs(lineas) do
        local fila = l.pos and filas[l.pos]
        if fila and normalizar(fila.original) == normalizar(l.texto) then
            l.traduccion = fila.traduccion
            usadas = usadas + 1
        end
    end
    return usadas
end

local function margenes(l)
    return l.inicio_exacto and MARGEN_INICIO_EXACTO or MARGEN_INICIO,
           l.fin_exacto and MARGEN_FIN_EXACTO or MARGEN_FIN
end

-- Los tiempos del .srt se desplazan con sub-delay (teclas z/x de mpv) por si el archivo va desfasado
local function retraso() return mp.get_property_number("sub-delay", 0) end
local function ahora() return (mp.get_property_number("time-pos", 0) or 0) - retraso() end

local function linea_reciente()
    -- La última línea que empezó; si apenas empezó (<0.7 s), probablemente la duda es la anterior
    local t, elegida = ahora(), nil
    for i, l in ipairs(lineas) do
        if l.inicio > t then break end
        elegida = i
    end
    if elegida and elegida > 1 and t - lineas[elegida].inicio < 0.7 then elegida = elegida - 1 end
    return elegida
end

local function linea_en_foco()
    if not foco then foco = linea_reciente() end
    return foco
end

local function escapar_ass(texto)
    return texto:gsub("\\", "\\\\"):gsub("{", "\\{"):gsub("}", "\\}"):gsub("\n", "\\N")
end

local function linea_actual()
    -- La que está en pantalla según el .srt (la última que empezó, si se enciman)
    local t, actual = ahora(), nil
    for i, l in ipairs(lineas) do
        if l.inicio > t then break end
        if t <= l.fin then actual = i end
    end
    return actual
end

local function texto_ass(original, traduccion)
    local partes = {}
    if original then table.insert(partes, "{\\an2\\fs40\\bord2\\1c&HFFFFFF&}" .. escapar_ass(original)) end
    if traduccion then table.insert(partes, "{\\an2\\fs34\\bord2\\1c&H66DDFF&}" .. escapar_ass(traduccion)) end
    return table.concat(partes, "\\N")
end

local function actualizar_dobles(forzar)
    -- Mientras t, y o R muestran una línea, no se dibuja encima
    local i = dobles and not mostrado.original and linea_actual() or nil
    if i == doble_actual and not forzar then return end
    doble_actual = i
    if not i then return overlay_dobles:remove() end
    local l = lineas[i]
    overlay_dobles.data = texto_ass(l.texto, l.traduccion or l.automatica or "…")
    mp.msg.verbose("con traducción: " .. overlay_dobles.data)
    overlay_dobles:update()
end

local function pedir_automaticas(indices)
    -- Un solo proceso traduce el lote (el modelo se carga una vez): en 1x02 completo, ~18 s
    if #indices == 0 then return end
    local textos = {}
    for _, i in ipairs(indices) do table.insert(textos, (lineas[i].texto:gsub("\n", " "))) end
    mp.command_native_async({
        name = "subprocess", capture_stdout = true, playback_only = false,
        stdin_data = table.concat(textos, "\n") .. "\n",
        args = { opts.python, "-m", "audiotrans.traduccion", opts.origen, opts.destino },
    }, function(ok, r)
        if not (ok and r.status == 0) then
            return mp.osd_message("No se pudieron traducir los subtítulos", 3)
        end
        local n = 0
        for traducida in r.stdout:gmatch("([^\n]*)\n") do
            n = n + 1
            if indices[n] and traducida ~= "" then lineas[indices[n]].automatica = traducida end
        end
        actualizar_dobles(true)
    end)
end

local function traducir_faltantes()
    -- Primero las próximas 20 (llegan en unos segundos), luego todas las demás
    if pedidas then return end
    pedidas = true
    local desde = linea_reciente() or 1
    local primeras, resto = {}, {}
    for i = 1, #lineas do
        local j = (desde + i - 2) % #lineas + 1
        if not lineas[j].traduccion then table.insert(#primeras < 20 and primeras or resto, j) end
    end
    pedir_automaticas(primeras)
    pedir_automaticas(resto)
end

local function dibujar()
    if not subs_ocultos and mp.get_property_bool("sub-visibility") then
        mp.set_property_bool("sub-visibility", false)
        subs_ocultos = true
    end
    overlay.data = texto_ass(mostrado.original, mostrado.traduccion)
    mp.msg.verbose("en pantalla: " .. overlay.data)
    overlay:update()
    actualizar_dobles()
end

local function ocultar()
    if mostrado.original then mp.msg.verbose("en pantalla: (nada)") end
    mostrado = {}
    overlay:remove()
    if subs_ocultos then
        mp.set_property_bool("sub-visibility", true)
        subs_ocultos = false
    end
    actualizar_dobles()
end

local function terminar_repeticion()
    pausar_en = nil
    if velocidad then
        mp.set_property_number("speed", velocidad)
        velocidad = nil
    end
end

local function repetir(i, lento)
    if not i then return mp.osd_message("Todavía no hay diálogo") end
    terminar_repeticion()
    foco = i
    ocultar()
    local l = lineas[i]
    if lento then
        velocidad = mp.get_property_number("speed", 1)
        mp.set_property_number("speed", LENTO)
        mostrado.original = l.texto  -- queda al pausar, como con t, y se quita al reanudar
        dibujar()
    end
    local antes, despues = margenes(l)
    pausar_en = l.fin + retraso() + despues
    buscando = true
    mp.msg.verbose("repetir: " .. l.texto:gsub("\n", " "))
    mp.commandv("seek", tostring(math.max(0, l.inicio + retraso() - antes)), "absolute+exact")
    mp.set_property_bool("pause", false)
end

mp.register_event("playback-restart", function() buscando = false end)

mp.observe_property("time-pos", "number", function(_, t)
    if t then actualizar_dobles() end
    if not t or buscando then return end
    if pausar_en then
        local l = lineas[foco]
        if t < l.inicio + retraso() - margenes(l) - 1 or t > pausar_en + 1 then
            -- Se fue a otra parte durante la repetición: se cancela, sin pausar, y la siguiente
            -- r es sobre donde está ahora y no sobre la línea de antes
            terminar_repeticion()
            foco = nil
            ocultar()
        elseif t >= pausar_en then
            terminar_repeticion()
            mp.set_property_bool("pause", true)
        end
    elseif foco then
        -- Se suelta en cuanto el tiempo sale del tramo que repite r y ya apunta a otra línea
        -- (la reproducción siguió o se regresó). Soltarla 1.5 s después del final saltaba
        -- líneas cortas como "Coffee?" y, al regresar, se quedaba con la línea de antes
        local l, actual = lineas[foco], t - retraso()
        local antes, despues = margenes(l)
        if (actual < l.inicio - antes or actual > l.fin + despues) and linea_reciente() ~= foco then
            foco = nil
        end
    end
end)

mp.observe_property("pause", "bool", function(_, pausado)
    if pausado == false and not pausar_en then ocultar() end  -- al reanudar se quita el texto
end)

local function mostrar_texto()
    local i = linea_en_foco()
    if not i then return mp.osd_message("Todavía no hay diálogo") end
    terminar_repeticion()
    mp.set_property_bool("pause", true)
    mostrado.original = lineas[i].texto
    dibujar()
end

local function mostrar_traduccion()
    local i = linea_en_foco()
    if not i then return mp.osd_message("Todavía no hay diálogo") end
    terminar_repeticion()
    mp.set_property_bool("pause", true)
    mostrado.original = lineas[i].texto
    if lineas[i].traduccion or lineas[i].automatica then
        mostrado.traduccion = lineas[i].traduccion or lineas[i].automatica
        return dibujar()
    end
    mostrado.traduccion = "…"
    dibujar()
    mp.command_native_async({
        name = "subprocess", capture_stdout = true, playback_only = false,
        args = { opts.python, "-m", "audiotrans.texto", opts.destino, "-" .. opts.origen, (lineas[i].texto:gsub("\n", " ")) },
    }, function(ok, r)
        if foco ~= i or not mostrado.original then return end  -- ya se cambió de línea
        mostrado.traduccion = (ok and r.status == 0) and r.stdout:gsub("%s+$", "") or "(no se pudo traducir)"
        dibujar()
    end)
end

local function guardar_duda()
    local i = linea_en_foco()
    if not i then return mp.osd_message("Todavía no hay diálogo") end
    local l = lineas[i]
    local antes, despues = margenes(l)
    mp.command_native_async({
        name = "subprocess", capture_stdout = true, capture_stderr = true, playback_only = false,
        args = { opts.python, "-m", "audiotrans.dudas", "guardar",
                 mp.get_property("path"), tostring(l.inicio + retraso()), tostring(l.fin + retraso()),
                 l.texto, opts.origen, opts.destino,
                 tostring(l.inicio + retraso() - antes), tostring(l.fin + retraso() + despues),
                 l.traduccion },  -- sin traducción revisada, dudas.py traduce como siempre
    }, function(ok, r)
        if ok and r.status == 0 then
            mp.osd_message("✓ Duda guardada: " .. r.stdout:gsub("%s+$", ""), 3)
        else
            mp.osd_message("No se pudo guardar la duda: " .. ((r and r.stderr) or "error"), 5)
        end
    end)
end

local function repetir_anterior()
    local i = foco or linea_reciente()
    if i == 1 then return mp.osd_message("Es la primera línea") end
    repetir(i and i - 1)  -- repetir() deja el foco en la anterior: otra e retrocede una más
end

local function repetir_siguiente()
    local i = foco or linea_reciente()
    if i == #lineas then return mp.osd_message("Es la última línea") end
    repetir((i or 0) + 1)  -- antes del primer diálogo, la siguiente es la primera
end

local function seguir_normal()
    -- Sin esto había que esperar a que la repetición terminara y se pausara
    terminar_repeticion()
    ocultar()
    mp.set_property_bool("pause", false)
end

local function continuar_con_subtitulos()
    -- Solo cambia sub-visibility (la v de mpv) y reanuda: r, t, y y d siguen igual
    local visibles = not (mp.get_property_bool("sub-visibility") or subs_ocultos)
    dobles = false
    terminar_repeticion()
    ocultar()
    mp.set_property_bool("sub-visibility", visibles)
    mp.set_property_bool("pause", false)
    mp.osd_message(visibles and "Con subtítulos (c para quitarlos)" or "Sin subtítulos")
end

local function continuar_con_traduccion()
    -- Como c, pero los dibuja el script para poner la traducción debajo de cada línea
    dobles = not dobles
    terminar_repeticion()
    ocultar()
    mp.set_property_bool("sub-visibility", false)
    if dobles then traducir_faltantes() end
    actualizar_dobles(true)
    mp.set_property_bool("pause", false)
    mp.osd_message(dobles and "Con subtítulos y traducción (C para quitarlos)" or "Sin subtítulos")
end

local cargado
if opts.json ~= "" then cargado = cargar_json(opts.json) else cargado = opts.srt ~= "" and cargar_srt(opts.srt) end
if cargado then
    local revisadas = opts.traducciones ~= "" and cargar_traducciones(opts.traducciones) or 0
    mp.add_forced_key_binding("r", "audiotrans-repetir", function() repetir(foco or linea_reciente()) end)
    mp.add_forced_key_binding("R", "audiotrans-lento", function() repetir(foco or linea_reciente(), true) end)
    mp.add_forced_key_binding("e", "audiotrans-anterior", repetir_anterior)
    mp.add_forced_key_binding("E", "audiotrans-siguiente", repetir_siguiente)
    mp.add_forced_key_binding("t", "audiotrans-texto", mostrar_texto)
    mp.add_forced_key_binding("y", "audiotrans-traduccion", mostrar_traduccion)
    mp.add_forced_key_binding("d", "audiotrans-duda", guardar_duda)
    mp.add_forced_key_binding("c", "audiotrans-subtitulos", continuar_con_subtitulos)
    mp.add_forced_key_binding("C", "audiotrans-subtitulos-traduccion", continuar_con_traduccion)
    mp.add_forced_key_binding("q", "audiotrans-seguir", seguir_normal)
    local exactas = 0
    for _, l in ipairs(lineas) do if l.inicio_exacto and l.fin_exacto then exactas = exactas + 1 end end
    local preparado = opts.json ~= "" and string.format(" (%d %% con tiempo exacto)", math.floor(100 * exactas / #lineas)) or ""
    if revisadas > 0 then preparado = preparado .. string.format(" · %d traducciones revisadas", revisadas) end
    mp.msg.verbose(revisadas .. " traducciones revisadas")
    mp.register_event("file-loaded", function()
        mp.osd_message(#lineas .. " líneas" .. preparado .. " · r repetir · R más lento · e/E anterior/siguiente · t texto · y traducción · d guardar duda · c con subtítulos · C con traducción · q seguir normal", 6)
    end)
else
    mp.msg.warn("audiotrans: no se pudieron leer los subtítulos: " .. (opts.json ~= "" and opts.json or opts.srt))
end
