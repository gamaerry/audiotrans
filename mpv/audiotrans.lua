-- Práctica de listening en mpv: los subtítulos van ocultos y se consultan línea por línea.
--   r  repetir la línea que acaba de pasar (y pausar al terminarla)
--   R  ir a la línea anterior
--   t  mostrar el texto original de la línea
--   y  mostrar la traducción
--   d  guardar la línea como duda, con su audio (para repasar en Anki)
-- Se carga con el comando practicar, que le pasa las rutas en script-opts.

local mp = require "mp"
local utils = require "mp.utils"
local options = require "mp.options"

local opts = { srt = "", python = "", lib = "", textrans = "", destino = "es", origen = "en" }
options.read_options(opts, "audiotrans")

local lineas = {}        -- { inicio = s, fin = s, texto = "..." } en el tiempo del .srt
local foco = nil         -- índice de la línea con la que se está trabajando
local pausar_en = nil    -- tiempo (del video) en el que pausar al terminar una repetición
local overlay = mp.create_osd_overlay("ass-events")
local mostrado = {}      -- lo que se ve en pantalla: { original = ..., traduccion = ... }

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
    overlay.data = table.concat(partes, "\\N")
    mp.msg.verbose("en pantalla: " .. overlay.data)
    overlay:update()
end

local function ocultar()
    mostrado = {}
    overlay:remove()
end

local function repetir(i)
    if not i then return mp.osd_message("No hay una línea anterior") end
    foco = i
    ocultar()
    local l = lineas[i]
    pausar_en = l.fin + retraso() + 0.3
    mp.commandv("seek", tostring(math.max(0, l.inicio + retraso() - 0.3)), "absolute+exact")
    mp.set_property_bool("pause", false)
end

mp.observe_property("time-pos", "number", function(_, t)
    if not t then return end
    if pausar_en and t >= pausar_en then
        pausar_en = nil
        mp.set_property_bool("pause", true)
    elseif not pausar_en and foco and t - retraso() > lineas[foco].fin + 1.5 then
        foco = nil  -- la reproducción siguió: la siguiente duda será sobre otra línea
    end
end)

mp.observe_property("pause", "bool", function(_, pausado)
    if pausado == false and not pausar_en then ocultar() end  -- al reanudar se quita el texto
end)

local function mostrar_texto()
    local i = linea_en_foco()
    if not i then return mp.osd_message("Todavía no hay diálogo") end
    pausar_en = nil
    mp.set_property_bool("pause", true)
    mostrado.original = lineas[i].texto
    dibujar()
end

local function mostrar_traduccion()
    local i = linea_en_foco()
    if not i then return mp.osd_message("Todavía no hay diálogo") end
    pausar_en = nil
    mp.set_property_bool("pause", true)
    mostrado.original = lineas[i].texto
    mostrado.traduccion = "…"
    dibujar()
    mp.command_native_async({
        name = "subprocess", capture_stdout = true, playback_only = false,
        args = { opts.textrans, opts.destino, "-" .. opts.origen, (lineas[i].texto:gsub("\n", " ")) },
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
    mp.command_native_async({
        name = "subprocess", capture_stdout = true, capture_stderr = true, playback_only = false,
        args = { opts.python, utils.join_path(opts.lib, "dudas.py"), "guardar",
                 mp.get_property("path"), tostring(l.inicio + retraso()), tostring(l.fin + retraso()),
                 l.texto, opts.origen, opts.destino },
    }, function(ok, r)
        if ok and r.status == 0 then
            mp.osd_message("✓ Duda guardada: " .. r.stdout:gsub("%s+$", ""), 3)
        else
            mp.osd_message("No se pudo guardar la duda: " .. ((r and r.stderr) or "error"), 5)
        end
    end)
end

if opts.srt ~= "" and cargar_srt(opts.srt) then
    mp.add_forced_key_binding("r", "audiotrans-repetir", function() repetir(foco or linea_reciente()) end)
    mp.add_forced_key_binding("R", "audiotrans-anterior", function()
        local i = foco or linea_reciente()
        repetir(i and i > 1 and i - 1 or nil)
    end)
    mp.add_forced_key_binding("t", "audiotrans-texto", mostrar_texto)
    mp.add_forced_key_binding("y", "audiotrans-traduccion", mostrar_traduccion)
    mp.add_forced_key_binding("d", "audiotrans-duda", guardar_duda)
    mp.register_event("file-loaded", function()
        mp.osd_message(#lineas .. " líneas · r repetir · R anterior · t texto · y traducción · d guardar duda", 6)
    end)
else
    mp.msg.warn("audiotrans: no se pudo leer el .srt: " .. opts.srt)
end
