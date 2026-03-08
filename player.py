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
        self._idle_visible = False

    def _get_ip_text(self) -> Optional[str]:
        try:
            out = subprocess.check_output(["hostname", "-I"], timeout=1.0)
            text = out.decode("utf-8", errors="ignore").strip()
            if text:
                return text.split()[0]
        except Exception:
            return None
        return None

    def _idle_overlay_text(self) -> str:
        ip_text = self._get_ip_text()
        if ip_text:
            return (
                "ScreenInvader 2.0\n"
                "http://{}:5000/\n\n"
                "Tastatur: Strg+Alt+F1 = Terminal, Strg+Alt+F3 = Player"
            ).format(ip_text)
        return "ScreenInvader 2.0"

    def _build_command(self) -> list:
        cmd = list(self.command)

        # Audio-Ausgabe wählen
        # Bei deinem Board:
        #   HDMI   = hw:0,0
        #   Analog = hw:1,0
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

            time.sleep(0.3)
            self.show_idle_overlay()

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

    def show_idle_overlay(self) -> None:
        text = self._idle_overlay_text()
        self._send_command(["set_property", "osd-level", 3])
        self._send_command(["show-text", text, 999999, 0])
        self._idle_visible = True

    def clear_idle_overlay(self) -> None:
        self._send_command(["show-text", "", 1, 0])
        self._idle_visible = False

    def play_url(self, url: str, start_time: Optional[float] = None) -> None:
        self.clear_idle_overlay()
        self._send_command(["loadfile", url, "replace"])
        if start_time is not None and start_time > 0:
            def _resume_seek():
                time.sleep(1.0)
                self._send_raw_command(["seek", float(start_time), "absolute"])
            threading.Thread(target=_resume_seek, daemon=True).start()

    def stop(self) -> None:
        self._send_command(["stop"])
        time.sleep(0.2)
        self.show_idle_overlay()

    def pause_hard(self) -> None:
        """Stabile 'Pause' für Audio-only: Stop plus Overlay."""
        self.stop()

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

            if bool(idle) and not self._idle_visible:
                self.show_idle_overlay()
        except Exception:
            pass
        return status
