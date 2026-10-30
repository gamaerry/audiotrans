-- Práctica de listening en mpv: los subtítulos van ocultos y se consultan línea por línea.
--   r  repetir la línea que acaba de pasar (y pausar al terminarla)
--   R  repetirla más lento (0.75×) y con su texto en pantalla
--   e  ir a la línea anterior, por si r no cayó en la que se quería (cada e, una más atrás)
--   E  ir a la línea siguiente (lo contrario de e)
--   t  mostrar el texto original de la línea
--   y  mostrar la traducción
--   d  guardar la línea como duda, con su audio (para repasar en Anki)
--   c  seguir viendo con los subtítulos de mpv visibles (otra vez c para quitarlos)
--   q  quitar la repetición o el texto y seguir viendo normal (ya no cierra mpv: eso queda en Q)
-- Se carga con el comando practice, que le pasa las rutas en script-opts.

local mp = require "mp"
local utils = require "mp.utils"
local options = require "mp.options"

local opts = { srt = "", json = "", python = "", destino = "es", origen = "en" }
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

local lineas = {}        -- { inicio = s, fin = s, texto = "...", inicio_exacto, fin_exacto } (tiempo del .srt)
local foco = nil         -- índice de la línea con la que se está trabajando
local pausar_en = nil    -- tiempo (del video) en el que pausar al terminar una repetición
local velocidad = nil    -- velocidad de antes de una repetición lenta, para restaurarla
local buscando = false   -- mientras llega el salto de una repetición, time-pos aún puede ser el de antes
local overlay = mp.create_osd_overlay("ass-events")
local mostrado = {}      -- lo que se ve en pantalla: { original = ..., traduccion = ... }
local subs_ocultos = false  -- dibujar() quitó los subtítulos de mpv para que no se encimen

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
    for bloque in (contenido .. "\n\n"):gmatch("(.-)\n\n+") do
        local h1, m1, s1, ms1, h2, m2, s2, ms2, resto = bloque:match(
            "(%d+):(%d+):(%d+)[,.](%d+)%s*%-%->%s*(%d+):(%d+):(%d+)[,.](%d+)[^\n]*\n?(.*)")
        if h1 then
            local texto = limpiar(resto)
            if texto ~= "" then
                table.insert(lineas, { inicio = a_segundos(h1, m1, s1, ms1), fin = a_segundos(h2, m2, s2, ms2), texto = texto })
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
    for _, l in ipairs((datos and datos.lineas) or {}) do
        if l.texto ~= "" then table.insert(lineas, l) end
    end
    table.sort(lineas, function(a, b) return a.inicio < b.inicio end)
    return #lineas > 0
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

local function dibujar()
    local partes = {}
    if mostrado.original then
        table.insert(partes, "{\\an2\\fs40\\bord2\\1c&HFFFFFF&}" .. escapar_ass(mostrado.original))
    end
    if mostrado.traduccion then
        table.insert(partes, "{\\an2\\fs34\\bord2\\1c&H66DDFF&}" .. escapar_ass(mostrado.traduccion))
    end
    if not subs_ocultos and mp.get_property_bool("sub-visibility") then
        mp.set_property_bool("sub-visibility", false)
        subs_ocultos = true
    end
    overlay.data = table.concat(partes, "\\N")
    mp.msg.verbose("en pantalla: " .. overlay.data)
    overlay:update()
end

local function ocultar()
    if mostrado.original then mp.msg.verbose("en pantalla: (nada)") end
    mostrado = {}
    overlay:remove()
    if subs_ocultos then
        mp.set_property_bool("sub-visibility", true)
        subs_ocultos = false
    end
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
                 tostring(l.inicio + retraso() - antes), tostring(l.fin + retraso() + despues) },
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
    terminar_repeticion()
    ocultar()
    mp.set_property_bool("sub-visibility", visibles)
    mp.set_property_bool("pause", false)
    mp.osd_message(visibles and "Con subtítulos (c para quitarlos)" or "Sin subtítulos")
end

local cargado
if opts.json ~= "" then cargado = cargar_json(opts.json) else cargado = opts.srt ~= "" and cargar_srt(opts.srt) end
if cargado then
    mp.add_forced_key_binding("r", "audiotrans-repetir", function() repetir(foco or linea_reciente()) end)
    mp.add_forced_key_binding("R", "audiotrans-lento", function() repetir(foco or linea_reciente(), true) end)
    mp.add_forced_key_binding("e", "audiotrans-anterior", repetir_anterior)
    mp.add_forced_key_binding("E", "audiotrans-siguiente", repetir_siguiente)
    mp.add_forced_key_binding("t", "audiotrans-texto", mostrar_texto)
    mp.add_forced_key_binding("y", "audiotrans-traduccion", mostrar_traduccion)
    mp.add_forced_key_binding("d", "audiotrans-duda", guardar_duda)
    mp.add_forced_key_binding("c", "audiotrans-subtitulos", continuar_con_subtitulos)
    mp.add_forced_key_binding("q", "audiotrans-seguir", seguir_normal)
    local exactas = 0
    for _, l in ipairs(lineas) do if l.inicio_exacto and l.fin_exacto then exactas = exactas + 1 end end
    local preparado = opts.json ~= "" and string.format(" (%d %% con tiempo exacto)", math.floor(100 * exactas / #lineas)) or ""
    mp.register_event("file-loaded", function()
        mp.osd_message(#lineas .. " líneas" .. preparado .. " · r repetir · R más lento · e/E anterior/siguiente · t texto · y traducción · d guardar duda · c con subtítulos · q seguir normal", 6)
    end)
else
    mp.msg.warn("audiotrans: no se pudieron leer los subtítulos: " .. (opts.json ~= "" and opts.json or opts.srt))
end
