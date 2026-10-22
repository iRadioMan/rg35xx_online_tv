#!/usr/bin/env python3
"""OnlineTV for Anbernic RG35XXPRO (Knulli / PortMaster) - entry point."""
import json
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
import pygame

from interface import BUTTONS, H, W, Interface
from mpv import PROBE_TIMEOUT, MpvPlayer, needs_probe, probe_stream

BASE = os.path.dirname(os.path.abspath(__file__))

# Button codes (see PROJECT.md)
BTN_A = (3,)
BTN_B = (4,)
DPAD_LEFT = (9,)
DPAD_RIGHT = (10,)
DPAD_UP = (11,)
DPAD_DOWN = (12,)
JOY_MAP = {BTN_A[0]: "A", BTN_B[0]: "B", DPAD_LEFT[0]: "LEFT",
           DPAD_RIGHT[0]: "RIGHT", DPAD_UP[0]: "UP", DPAD_DOWN[0]: "DOWN"}
# Keyboard fallback for testing on a desktop
KEY_MAP = {pygame.K_RETURN: "A", pygame.K_z: "A", pygame.K_ESCAPE: "B", pygame.K_x: "B",
           pygame.K_LEFT: "LEFT", pygame.K_RIGHT: "RIGHT",
           pygame.K_UP: "UP", pygame.K_DOWN: "DOWN"}

MAIN, LIST, SETTINGS, INFO, FULL = "main", "list", "settings", "info", "full"

DEBUG = os.environ.get("APP_DEBUG") == "1"
log = logging.getLogger("onlinetv")


def setup_logging():
    if DEBUG:
        logging.basicConfig(filename=os.path.join(BASE, "onlinetv.log"), level=logging.DEBUG,
                            format="%(asctime)s %(levelname)s %(message)s")
        sys.excepthook = lambda *a: log.error("uncaught", exc_info=a)
    else:
        log.addHandler(logging.NullHandler())


def load_channels():
    try:
        with open(os.path.join(BASE, "channels.json"), encoding="utf-8") as f:
            data = json.load(f)
        return [c for c in data.get("channels", []) if c.get("name") and c.get("url") and c.get("type")]
    except (OSError, ValueError):
        log.exception("cannot load channels.json")
        return []


class App:
    def __init__(self):
        # SDL_VIDEODRIVER as the launcher gave it; mpv must get exactly this back.
        self.orig_driver = os.environ.get("SDL_VIDEODRIVER")
        pygame.init()
        pygame.joystick.init()
        self.joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
        for j in self.joysticks:
            j.init()
        # While mpv owns the display the video subsystem is shut down, so button
        # presses are polled straight from SDL's joystick layer instead of events.
        self.can_poll = False
        self.display_released = False
        self.pad_prev = {}
        try:
            from pygame._sdl2 import controller as sdl_controller
            sdl_controller.init()
            self._ctl = sdl_controller
            self.can_poll = True
        except Exception:
            log.exception("pygame._sdl2.controller unavailable; display will not be released")
        self.flags = 0 if os.environ.get("APP_WINDOWED") else pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((W, H), self.flags)
        pygame.display.set_caption("OnlineTV")
        pygame.mouse.set_visible(False)

        self.ui = Interface(self.screen, os.path.join(BASE, "font.ttf"))
        self.player = MpvPlayer(
            binary=os.environ.get("MPV_BIN", "/usr/bin/mpv"),
            log_path=os.path.join(BASE, "mpv.log") if DEBUG else None)
        self.channels = load_channels()

        self.state = MAIN
        self.focus = "play"
        self.index = 0
        self.status = "stopped" if self.channels else "empty"   # stopped/playing/paused/error/empty
        self.list_sel = 0
        self.message = ""            # error text shown in the preview area
        self.probe_token = 0         # identifies the current URL pre-check
        self.probe_result = None     # (token, ok, reason) set by the worker thread
        self.info_rows = []
        self.running = True
        self.clock = pygame.time.Clock()
        log.info("started, %d channels, %d joysticks", len(self.channels), len(self.joysticks))

    # ------------------------------------------------- display hand-over to mpv
    def release_display(self):
        """Give the real display to mpv (this SDL only has the 'mali' driver,
        there is no 'dummy', so the video subsystem is simply shut down)."""
        if not self.can_poll:
            log.warning("cannot poll joystick without video; keeping display")
            return
        pygame.display.quit()
        self.display_released = True
        self.poll_joystick()          # remember buttons already held down
        log.debug("display released")

    def acquire_display(self):
        if self.display_released:
            pygame.display.init()
            self.screen = pygame.display.set_mode((W, H), self.flags)
            self.ui.screen = self.screen
            pygame.mouse.set_visible(False)
            self.display_released = False
            log.debug("display acquired")
        pygame.event.clear()

    def poll_joystick(self):
        """Edge-detected actions from raw joystick state (works without video)."""
        self._ctl.update()
        cur = {}
        for j in self.joysticks:
            nb = j.get_numbuttons()
            for btn, act in JOY_MAP.items():
                if btn < nb and j.get_button(btn):
                    cur[act] = True
            if j.get_numhats():
                x, y = j.get_hat(0)
                for flag, act in ((x < 0, "LEFT"), (x > 0, "RIGHT"), (y > 0, "UP"), (y < 0, "DOWN")):
                    if flag:
                        cur[act] = True
        acts = [a for a in cur if not self.pad_prev.get(a)]
        self.pad_prev = cur
        for a in acts:
            log.debug("poll -> %s", a)
        return acts

    # ------------------------------------------------------------------ input
    def translate(self, ev):
        if ev.type == pygame.JOYBUTTONDOWN:
            act = JOY_MAP.get(ev.button)
            log.debug("joy button %s -> %s", ev.button, act)
            return act
        if ev.type == pygame.JOYHATMOTION:
            act = {(-1, 0): "LEFT", (1, 0): "RIGHT", (0, 1): "UP", (0, -1): "DOWN"}.get(ev.value)
            if act:
                log.debug("hat %s -> %s", ev.value, act)
            return act
        if ev.type == pygame.KEYDOWN:
            act = KEY_MAP.get(ev.key)
            if act:
                log.debug("key %s -> %s", pygame.key.name(ev.key), act)
            return act
        return None

    def handle(self, act):
        {MAIN: self.on_main, LIST: self.on_list,
         INFO: self.on_info, FULL: self.on_full}[self.state](act)

    def on_main(self, act):
        if self.status == "connecting":           # URL pre-check running: only B (cancel)
            if act == "B":
                self.probe_token += 1
                self.status = "stopped"
                log.info("connection cancelled")
            return
        if act in ("LEFT", "RIGHT", "UP", "DOWN"):
            self.move_focus(act)
        elif act == "A":
            self.activate(self.focus)

    def on_list(self, act):
        n, cap = len(self.channels), self.ui.list_capacity()
        if act == "UP":
            self.list_sel = (self.list_sel - 1) % n
        elif act == "DOWN":
            self.list_sel = (self.list_sel + 1) % n
        elif act == "LEFT":
            self.list_sel = max(0, self.list_sel - cap)
        elif act == "RIGHT":
            self.list_sel = min(n - 1, self.list_sel + cap)
        elif act == "A":
            self.play_channel(self.list_sel)
        elif act == "B":
            self.state = MAIN

    def on_info(self, act):
        if act == "B":
            self.state = MAIN

    def on_full(self, act):
        if act == "B":
            self.stop_playback()
        elif act == "A":                       # pause / resume
            if self.status == "playing":
                self.player.set_pause(True)
                self.status = "paused"
            elif self.status == "paused":
                self.player.set_pause(False)
                self.status = "playing"
        elif act == "LEFT":
            self.play_channel(self.index - 1, probe=False)
        elif act == "RIGHT":
            self.play_channel(self.index + 1, probe=False)

    # ------------------------------------------------------------------ focus
    def move_focus(self, act):
        dx = {"LEFT": -1, "RIGHT": 1}.get(act, 0)
        dy = {"UP": -1, "DOWN": 1}.get(act, 0)
        cur = BUTTONS[self.focus].center
        best, best_score = None, None
        for name, r in BUTTONS.items():
            if name == self.focus:
                continue
            ox, oy = r.centerx - cur[0], r.centery - cur[1]
            primary, secondary = (ox * dx, abs(oy)) if dx else (oy * dy, abs(ox))
            if primary <= 0:
                continue
            score = primary + 2 * secondary
            if best_score is None or score < best_score:
                best, best_score = name, score
        if best:
            self.focus = best

    # ---------------------------------------------------------------- actions
    def activate(self, name):
        log.debug("activate %s", name)
        if name == "prev":
            self.select_channel(self.index - 1)
        elif name == "next":
            self.select_channel(self.index + 1)
        elif name == "play":
            if self.channels[self.index]["type"] == "tv" or self.status != "playing":
                self.play_channel(self.index)
            else:
                self.stop_playback()
        elif name == "list":
            if self.channels:
                self.state = LIST
                self.list_sel = self.index
        elif name == "info":
            self.state = INFO
            self.info_rows = self.collect_info()
        elif name == "exit":
            self.running = False

    def select_channel(self, idx):
        """Switch the current channel without starting playback."""
        if not self.channels:
            return
        self.index = idx % len(self.channels)
        self.status = "stopped"
        self.message = ""
        log.debug("selected #%d %s type: %s", self.index, self.channels[self.index]["name"], self.channels[self.index]["type"])

    def play_channel(self, idx, probe=True):
        if not self.channels:
            return
        self.index = idx % len(self.channels)
        ch = self.channels[self.index]
        self.message = ""
        log.info("play #%d %s %s %s", self.index, ch["name"], ch["url"], ch["type"])
        if probe and self.state != FULL and needs_probe(ch["url"]):
            # Check the URL in the background first; the UI shows "Connecting..." and B cancels.
            self.state = MAIN
            self.status = "connecting"
            self.probe_token += 1
            token, url = self.probe_token, ch["url"]

            def work():
                ok, reason = probe_stream(url, PROBE_TIMEOUT)
                log.info("probe %s -> %s (%s)", url, ok, reason)
                self.probe_result = (token, ok, reason)
            threading.Thread(target=work, daemon=True).start()
            return
        self.start_mpv(ch)

    def tick_probe(self):
        res, self.probe_result = self.probe_result, None
        if not res:
            return
        token, ok, reason = res
        if token != self.probe_token or self.status != "connecting":
            return                                # cancelled or superseded
        if ok:
            self.start_mpv(self.channels[self.index])
        else:
            self.status = "error"
            self.message = reason

    def start_mpv(self, ch):
        if self.state != FULL:
            if ch["type"] == "tv": # release display only not in fullscreen and start playing TV
                self.release_display()
        if self.player.play(ch["url"]):
            self.status = "playing"
            if ch["type"] == "tv":
                self.state = FULL # go to fullscreen playback if tv is playing
            else:
                self.leave_playback() # leave fullscreen playback if radio is playing
        else:
            self.status = "error"
            self.message = "Cannot start mpv"
            self.leave_playback()

    def stop_playback(self):
        self.player.stop()
        self.status = "stopped"
        self.leave_playback()

    def leave_playback(self):
        self.acquire_display()
        self.state = MAIN

    # --------------------------------------------------------------- info
    def collect_info(self):
        def mem():
            try:
                with open("/proc/meminfo") as f:
                    kv = dict(line.split(":", 1) for line in f if ":" in line)
                total = int(kv["MemTotal"].split()[0]) // 1024
                avail = int(kv["MemAvailable"].split()[0]) // 1024
                return f"{avail} / {total} MB free"
            except (OSError, KeyError, ValueError):
                return "n/a"

        def mpv_version():
            try:
                out = subprocess.run([self.player.binary, "--version"], capture_output=True,
                                     text=True, timeout=3).stdout
                return out.splitlines()[0].replace("mpv ", "")[:40]
            except (OSError, subprocess.SubprocessError, IndexError):
                return "not found"

        un = platform.uname()
        sdl = ".".join(map(str, pygame.get_sdl_version()))
        return [
            ("Device", "Anbernic RG35XXPRO"),
            ("System", f"{un.system} {un.release}"),
            ("Architecture", un.machine),
            ("Python", platform.python_version()),
            ("pygame / SDL", f"{pygame.version.ver} / {sdl}"),
            ("Video driver", pygame.display.get_driver()),
            ("mpv", mpv_version()),
            ("Memory", mem()),
            ("Controller", self.joysticks[0].get_name() if self.joysticks else "none"),
            ("Channels", str(len(self.channels))),
        ]

    # ------------------------------------------------------------------- loop
    def check_player(self):
        if self.state == FULL and not self.player.running:
            reason = self.player.failure_reason()
            log.error("mpv stopped: %s", reason)
            self.status = "error"
            self.message = reason
            self.leave_playback()

    def draw(self):
        if self.state == MAIN:
            name = self.channels[self.index]["name"] if self.channels else ""
            logo = self.channels[self.index]["logo"] if self.channels else ""
            self.ui.draw_main(self.focus, self.status, name, logo, self.index, len(self.channels), self.message)
        elif self.state == LIST:
            self.ui.draw_list(self.channels, self.list_sel, self.index)
        elif self.state == INFO:
            self.ui.draw_info(self.info_rows)
        # FULL: mpv owns the screen, nothing to draw

    def run(self):
        while self.running:
            if self.display_released:
                for act in self.poll_joystick():
                    self.handle(act)
            else:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        self.running = False
                        continue
                    act = self.translate(ev)
                    if act:
                        self.handle(act)
            self.tick_probe()
            self.check_player()
            self.draw()
            self.clock.tick(30)

    def shutdown(self):
        log.info("shutting down")
        self.player.stop()      # MPV must always die with the application
        pygame.quit()


def main():
    setup_logging()
    app = App()
    signal.signal(signal.SIGTERM, lambda *_: setattr(app, "running", False))
    try:
        app.run()
    except Exception:
        log.exception("fatal error")
        raise
    finally:
        app.shutdown()


if __name__ == "__main__":
    main()
