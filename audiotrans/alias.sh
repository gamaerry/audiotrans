# Alias de audiotrans. Cárgalos desde ~/.bashrc o ~/.bash_aliases con:
#   source /ruta/a/audiotrans/alias.sh
# --- Traductores (ver: man audiotrans) ---
# texto
alias es='textrans es'
alias esp='trans -t es'
alias en='textrans en'
alias eng='trans -t en'
# portapapeles (cb: lo copiado con Ctrl+C) y selección (ps: lo subrayado con el mouse)
alias cbes='wl-paste -n | textrans es'
alias cben='wl-paste -n | textrans en'
alias pses='wl-paste -p -n | textrans es'
alias psen='wl-paste -p -n | textrans en'
# micrófono
alias mes='audiotrans es'
alias men='audiotrans en'
# audio del sistema
alias ses='audiotrans -s es'
alias sen='audiotrans -s en'
# ---
