# OnlineTV for Anbernic RG35XXPRO (Knulli)

Python + pygame front-end with mpv as the video back-end.

## Install
Copy the contents of `ports/` to `/userdata/roms/ports/` on the device
(you get `OnlineTV.sh` plus the `onlinetv/` folder), then refresh the game list.

## Controls
D-pad moves focus, **A** activates, **B** goes back / leaves full-screen / closes list and settings.
Keyboard fallback for desktop testing: arrows, Enter/Z = A, Esc/X = B (`APP_WINDOWED=1 python3 main.py`).

## Playback on Knulli
This device's mpv only has the `sdl` video output, which is always full-screen (no drm/gpu/compositor),
so a windowed preview is not possible. While a channel plays, the app hands the display to mpv:
**A** pause/resume, **Left/Right** previous/next channel, **B** stop and return to the interface.
Env overrides: `MPV_VO`, `MPV_HWDEC` (default `no`, software decoding).

## Debug
`APP_DEBUG=1` (set in `OnlineTV.sh`) writes errors and button presses to `onlinetv/onlinetv.log`
and mpv's stderr to `onlinetv/mpv.log`.

## Channels
Edit `ports/onlinetv/channels.json` (`name` + `url` per channel). The bundled entries are public test streams.

## Files
- `main.py` - state machine (main / list / settings / full-screen), input, focus navigation
- `interface.py` - all drawing (layout constants from the spec, icons drawn with `pygame.draw`)
- `mpv.py` - starts/stops mpv, pause + full-screen via JSON IPC, kills the process group on exit

### TODO

- Store channel logos in channels.json
- Radio stations support? :>
