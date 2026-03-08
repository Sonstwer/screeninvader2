import json
import os
import socket
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from config import MPV_SOCKET_PATH, MPV_COMMAND, AUDIO_OUTPUT


class MPVPlayer:
    def __init__(self, socket_path: str = MPV_SOCKET_PATH, command=None):
        self.socket_path = socket_path
        self.command = command if command is not None else MPV_COMMAND
        self._process = None  # type: Optional[subprocess.Popen]
        self._lock = threading.Lock()

    def _build_command(self) -> list:
        cmd = list(self.command)

        # Audio-Ausgabe wählen
        # Bei deinem Banana Pi:
        # HDMI   = hw:0,0
        # Analog = hw:1,0
        ao = (AUDIO_OUTPUT or "hdmi").lower()
        if ao == "analog":
            cmd.append("--audio-device=alsa/hw:1,0")
        else:
            cmd.append("--audio-device=alsa/hw:0,0")

        return cmd

    def _ensure_mpv_running(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return

            try:
                if os.path.exists(self.socket_path):
                    os.remove(self.socket_path)
            except Exception:
                pass

            self._process = subprocess.Popen(
                self._build_command(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            for _ in range(80):
                if os.path.exists(self.socket_path):
                    break
                time.sleep(0.1)

    def _send_raw_command(self, command: Any) -> Optional[Dict]:
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(self.socket_path)
            payload = json.dumps({"command": command}) + "\n"
            s.sendall(payload.encode("utf-8"))
            try:
                data = s.recv(4096)
                if not data:
                    s.close()
                    return None
                line = data.decode("utf-8", errors="ignore").strip()
                if not line:
                    s.close()
                    return None
                response = json.loads(line)
                s.close()
                return response
            except socket.timeout:
                s.close()
                return None
        except Exception:
            return None

    def _send_command(self, command: Any) -> Optional[Dict]:
        self._ensure_mpv_running()
        return self._send_raw_command(command)

    def _get_property(self, prop: str) -> Optional[Any]:
        self._ensure_mpv_running()
        response = self._send_raw_command(["get_property", prop])
        if response and response.get("error") == "success":
            return response.get("data")
        return None

    def play_url(self, url: str) -> None:
        self._send_command(["loadfile", url, "replace"])

    def stop(self) -> None:
        self._send_command(["stop"])

    def pause_toggle(self) -> None:
        self._send_command(["cycle", "pause"])

    def set_pause(self, pause_state: bool) -> None:
        self._send_command(["set_property", "pause", pause_state])

    def is_idle(self) -> bool:
        value = self._get_property("idle-active")
        return bool(value)

    def is_playing(self) -> bool:
        return not self.is_idle()

    def get_status(self) -> Dict:
        status = {
            "playing": False,
            "paused": False,
            "time_pos": None,
            "duration": None,
            "title": None,
        }
        try:
            pause = self._get_property("pause")
            title = self._get_property("media-title")
            time_pos = self._get_property("time-pos")
            duration = self._get_property("duration")
            idle = self._get_property("idle-active")

            status["paused"] = bool(pause)
            status["title"] = title
            status["time_pos"] = time_pos
            status["duration"] = duration
            status["playing"] = not bool(idle)
        except Exception:
            pass
        return status