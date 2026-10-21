#!/bin/bash
# PortMaster-style launcher for OnlineTV (Anbernic RG35XXPRO / Knulli)

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

[ -f "$controlfolder/control.txt" ] && source "$controlfolder/control.txt"
[ -n "$CFW_NAME" ] && [ -f "$controlfolder/mod_${CFW_NAME}.txt" ] && source "$controlfolder/mod_${CFW_NAME}.txt"
command -v get_controls >/dev/null && get_controls

GAMEDIR="$(cd "$(dirname "$0")" && pwd)/onlinetv"
cd "$GAMEDIR" || exit 1

# Debug mode: logs errors and button presses to onlinetv.log (mpv.log for mpv stderr)
export APP_DEBUG=0

# Optional mpv tuning (uncomment if the preview window does not appear):
# export MPV_VO=gpu
# export MPV_GPU_CONTEXT=drm
# export MPV_HWDEC=auto-safe

export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-}"
[ -z "$SDL_VIDEODRIVER" ] && unset SDL_VIDEODRIVER

python3 main.py

# Safety net: make sure no mpv is left behind
pkill -f "onlinetv-mpv.sock" 2>/dev/null
command -v pm_finish >/dev/null && pm_finish
