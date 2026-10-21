"""MPV wrapper: start/stop, arguments, full-screen, process cleanup.

This Knulli build of mpv only has a usable `sdl` video output (no drm, no
gpu context, no compositor), which always plays full-screen. So the app hands
the display over to mpv while a channel plays (see main.py).
Pause is controlled through mpv's JSON IPC socket.
"""
import atexit
import json
import logging
import os
import signal
import socket
import subprocess
import time

log = logging.getLogger("onlinetv")


class MpvPlayer:
    def __init__(self, binary="/usr/bin/mpv", socket_path="/tmp/onlinetv-mpv.sock",
                 log_path=None):
        self.binary = binary
        self.socket_path = socket_path
        self.log_path = log_path          # set in debug mode -> verbose mpv log
        self.proc = None
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
            "--network-timeout=15",
        ]
        if self.log_path:
            args += ["--msg-level=all=v", f"--log-file={self.log_path}"]
        else:
            args += ["--no-terminal", "--really-quiet"]
        args.append(url)
        return args

    def play(self, url, env=None):
        """Start mpv full-screen. `env` lets the caller hand over a clean SDL environment."""
        self.stop()
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
        return True

    def stop(self):
        """Terminate the MPV process (whole process group)."""
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except (ProcessLookupError, PermissionError):
                pass
            log.debug("mpv stopped")
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass

    def set_pause(self, paused):
        return self._command("set_property", "pause", bool(paused))

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
