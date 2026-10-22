"""MPV wrapper: start/stop, arguments, start-up watchdog, stream pre-check.

This Knulli build of mpv only has a usable `sdl` video output (no drm, no
gpu context, no compositor, no Lua), which always plays full-screen. So the app
hands the display over to mpv while a channel plays (see main.py).
"""
import atexit
import http.client
import json
import logging
import os
import signal
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("onlinetv")

PROBE_TIMEOUT = 5.0      # s: pre-check of the URL before mpv is started
NETWORK_TIMEOUT = 5      # s: mpv --network-timeout
START_TIMEOUT = 8.0      # s: mpv must show video/audio within this time, else it is killed


# ------------------------------------------------------------ URL pre-check
_OK_EXACT = {
    "application/vnd.apple.mpegurl", "application/x-mpegurl", "application/mpegurl",
    "application/octet-stream", "binary/octet-stream", "application/ogg",
    "application/dash+xml", "application/mp4", "application/x-matroska",
}


def needs_probe(url):
    return url.lower().startswith(("http://", "https://"))


def probe_stream(url, timeout=PROBE_TIMEOUT):
    """Quick check that `url` answers and looks like video/audio.
    Returns (ok, reason). When unsure, returns ok so that mpv gets the final say."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (OnlineTV)", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get_content_type() or "").lower()
            body = resp.read(1024)
    except urllib.error.HTTPError as e:
        return False, f"Server returned HTTP {e.code}"
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError):
            return True, "TLS check skipped"
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            return False, "Timeout: server not responding"
        return False, "Server unreachable (no network?)"
    except (socket.timeout, TimeoutError):
        return False, "Timeout: server not responding"
    except ssl.SSLError:
        return True, "TLS check skipped"         # e.g. no CA bundle here; let mpv try
    except http.client.HTTPException:
        return True, "non-standard reply"        # e.g. Shoutcast 'ICY 200 OK'; let mpv try
    except (OSError, ValueError):
        return False, "Connection error"

    head = body.lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"#EXTM3U") or body[:1] == b"\x47":      # HLS playlist / MPEG-TS
        return True, "ok"
    if head[:200].lower().startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        return False, "Server returned a web page, not a stream"
    if ctype.startswith(("video/", "audio/")) or ctype in _OK_EXACT:
        return True, "ok"
    return False, f"Not a video/audio stream ({ctype or 'unknown type'})"


# ------------------------------------------------------------------- player
class MpvPlayer:
    def __init__(self, binary="/usr/bin/mpv", socket_path="/tmp/onlinetv-mpv.sock",
                 log_path=None):
        self.binary = binary
        self.socket_path = socket_path
        self.log_path = log_path          # set in debug mode -> verbose mpv log
        self.proc = None
        self.started = False              # True once mpv reports a playback position
        self.timed_out = False            # True if the watchdog killed mpv
        atexit.register(self.stop)

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def _build_args(self, url):
        args = [
            self.binary,
            "--no-config",
            f"--input-ipc-server={self.socket_path}",
            "--no-input-default-bindings",
            "--osd-level=0",      # no --no-osc: this mpv is built without Lua/OSC
            "--vo=" + os.environ.get("MPV_VO", "sdl"),
            "--fullscreen",
            "--keepaspect=yes",
            "--framedrop=vo",
            "--sid=no",
            "--hwdec=" + os.environ.get("MPV_HWDEC", "no"),
            "--cache=yes",
            "--demuxer-max-bytes=24MiB",
            "--demuxer-readahead-secs=10",
            f"--network-timeout={NETWORK_TIMEOUT}",
        ]
        if self.log_path:
            args += ["--msg-level=all=v", f"--log-file={self.log_path}"]
        else:
            args += ["--no-terminal", "--really-quiet"]
        args.append(url)
        return args

    def play(self, url, env=None):
        """Start mpv full-screen and a watchdog that kills it if nothing plays in time."""
        self.stop()
        self.started = False
        self.timed_out = False
        args = self._build_args(url)
        log.debug("mpv start: %s", " ".join(args))
        err = subprocess.DEVNULL
        if self.log_path:       # debug: keep mpv's raw stderr (crash messages) separately
            err = open(self.log_path.replace(".log", "-stderr.log"), "ab")
            err.write(("\n===== " + " ".join(args) + "\n").encode())
            err.flush()
        try:
            self.proc = subprocess.Popen(
                args, stdin=subprocess.DEVNULL, stdout=err,
                stderr=subprocess.STDOUT if err is not subprocess.DEVNULL else subprocess.DEVNULL,
                start_new_session=True, env=env)
        except OSError:
            log.exception("cannot start mpv")
            self.proc = None
            return False
        threading.Thread(target=self._watch, args=(self.proc,), daemon=True).start()
        return True

    def _watch(self, proc):
        t0 = time.monotonic()
        while proc.poll() is None and self.proc is proc:
            pos = self.get_property("time-pos")
            if isinstance(pos, (int, float)):
                self.started = True
                log.debug("playback started after %.1f s", time.monotonic() - t0)
                return
            if time.monotonic() - t0 > START_TIMEOUT:
                if self.proc is proc:
                    log.error("no playback within %.0f s, killing mpv", START_TIMEOUT)
                    self.timed_out = True
                    self._kill(proc)
                return
            time.sleep(0.25)

    def failure_reason(self):
        """Human-readable reason why mpv is no longer running."""
        rc = self.proc.returncode if self.proc else None
        if self.timed_out:
            return f"No video received within {START_TIMEOUT:.0f} s"
        if rc == 2:
            return "Cannot play stream (network or format error)"
        if rc == 0 and self.started:
            return "Stream ended"
        if rc == 1:
            return "mpv failed to start"
        return f"Playback stopped (code {rc})"

    @staticmethod
    def _kill(proc):
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except (ProcessLookupError, PermissionError):
                pass

    def stop(self):
        """Terminate the MPV process (whole process group)."""
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            self._kill(proc)
            log.debug("mpv stopped")
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass

    # -------------------------------------------------------------------- IPC
    def set_pause(self, paused):
        return self._command("set_property", "pause", bool(paused))

    def get_property(self, name):
        """Read an mpv property over IPC; None if unavailable or mpv is not answering."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.4)
                s.connect(self.socket_path)
                s.sendall((json.dumps({"command": ["get_property", name], "request_id": 7}) + "\n").encode())
                buf, end = b"", time.monotonic() + 0.6
                while time.monotonic() < end:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    for line in buf.split(b"\n"):
                        try:
                            msg = json.loads(line)
                        except ValueError:
                            continue
                        if msg.get("request_id") == 7:
                            return msg.get("data") if msg.get("error") == "success" else None
        except OSError:
            pass
        return None

    def _command(self, *command, wait=2.0):
        deadline = time.monotonic() + wait
        payload = (json.dumps({"command": list(command)}) + "\n").encode()
        while self.running and time.monotonic() < deadline:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    s.connect(self.socket_path)
                    s.sendall(payload)
                return True
            except OSError:
                time.sleep(0.05)
        log.error("mpv IPC command failed: %s", command)
        return False