import json
import os
import socket
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from config import MPV_SOCKET_PATH, MPV_COMMAND


class MPVPlayer:
    def __init__(self, socket_path: str = MPV_SOCKET_PATH, command=None):
        self.socket_path = socket_path
        self.command = command if command is not None else MPV_COMMAND
        self._process = None  # type: Optional[subprocess.Popen]
        self._lock = threading.Lock()

    def _ensure_mpv_running(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            # alten Socket entfernen, falls vorhanden
            try:
                if os.path.exists(self.socket_path):
                    os.remove(self.socket_path)
            except Exception:
                pass
            # mpv starten
            self._process = subprocess.Popen(
                self.command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # kurz warten, bis Socket verfügbar ist
            for _ in range(50):
                if os.path.exists(self.socket_path):
                    break
                time.sleep(0.1)

    def _send_command(self, command: Any) -> Optional[Dict]:
        """
        command: z.B. ["loadfile", "URL", "replace"]
        """
        self._ensure_mpv_running()
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(self.socket_path)
            payload = json.dumps({"command": command}) + "\n"
            s.sendall(payload.encode("utf-8"))
            # Antwortzeile lesen (optional)
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

    def _get_property(self, prop: str) -> Optional[Any]:
        self._ensure_mpv_running()
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(self.socket_path)
            payload = json.dumps({"command": ["get_property", prop]}) + "\n"
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
                if response.get("error") == "success":
                    return response.get("data")
                return None
            except socket.timeout:
                s.close()
                return None
        except Exception:
            return None

    def play_url(self, url: str) -> None:
        """Lädt und spielt eine URL ab (ersetzt aktuelle Wiedergabe)."""
        self._send_command(["loadfile", url, "replace"])

    def stop(self) -> None:
        self._send_command(["stop"])

    def pause_toggle(self) -> None:
        self._send_command(["cycle", "pause"])

    def set_pause(self, pause_state: bool) -> None:
        self._send_command(["set_property", "pause", pause_state])

    def is_idle(self) -> bool:
        """True, wenn mpv im Idle-Modus ist (nichts spielt)."""
        value = self._get_property("idle-active")
        return bool(value)

    def is_playing(self) -> bool:
        """True, wenn aktuell ein Medium abgespielt wird."""
        idle = self.is_idle()
        return not idle

    def get_status(self) -> Dict:
        """
        Liefert Basisstatus: spielt ja/nein, pause,
        time-pos, duration, media-title.
        """
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
            idle = self._get_property("idle-active")  # noqa: F841

            status["paused"] = bool(pause)
            status["title"] = title
            status["time_pos"] = time_pos
            status["duration"] = duration
            status["playing"] = not bool(self._get_property("idle-active"))
        except Exception:
            pass
        return status
