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
        """Baut den mpv-Startbefehl inklusive Audio-Device und IP-Overlay."""
        cmd = list(self.command)

        # Audio-Ausgabe wählen (Standard: HDMI)
        # Hinweis: Devices können je nach Board variieren.
        # Häufig:
        #   hw:0,0 -> HDMI
        #   hw:0,1 -> Analog (3,5mm)
        ao = (AUDIO_OUTPUT or "hdmi").lower()
        if ao == "analog":
            cmd.append("--audio-device=alsa/hw:0,1")
        else:
            cmd.append("--audio-device=alsa/hw:0,0")

        # IP-Adresse ermitteln und als OSD-Text einblenden
        ip_text = None
        try:
            out = subprocess.check_output(["hostname", "-I"], timeout=1.0)
            text = out.decode("utf-8", errors="ignore").strip()
            if text:
                ip_text = text.split()[0]
        except Exception:
            ip_text = None

        if ip_text:
            msg = "ScreenInvader 2.0 – http://{}:5000/".format(ip_text)
            cmd.append("--osd-msg1={}".format(msg))

        # Vollbild für Kiosk-Modus
        cmd.append("--fs")

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
            for _ in range(50):
                if os.path.exists(self.socket_path):
                    break
                time.sleep(0.1)

    def _send_command(self, command: Any) -> Optional[Dict]:
        self._ensure_mpv_running()
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
        idle = self.is_idle()
        return not idle

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
