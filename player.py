import json
import os
import socket
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from config import MPV_SOCKET_PATH, MPV_COMMAND, AUDIO_OUTPUT, MPV_LOG_PATH


class MPVPlayer:
    def __init__(self, socket_path: str = MPV_SOCKET_PATH, command=None, log_path: str = MPV_LOG_PATH):
        self.socket_path = socket_path
        self.command = command if command is not None else MPV_COMMAND
        self.log_path = log_path
        self.runtime_dir = "/tmp/screeninvader-xdg"
        self._process = None
        self._lock = threading.Lock()
        self._log_handle = None

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
                "Terminal: Strg+Alt+F1\n"
                "Player: Strg+Alt+F3"
            ).format(ip_text)
        return "ScreenInvader 2.0"

    def _build_command(self) -> list:
        cmd = list(self.command)

        # Nicht mehr manuell einen geratenen ALSA-Gerätenamen setzen.
        # Stattdessen nur den ALSA-AO erzwingen und das echte Device
        # später aus audio-device-list auswählen.
        cmd.append("--ao=alsa")
        return cmd

    def _build_env(self) -> dict:
        env = dict(os.environ)
        os.makedirs(self.runtime_dir, exist_ok=True)
        try:
            os.chmod(self.runtime_dir, 0o700)
        except Exception:
            pass
        env["XDG_RUNTIME_DIR"] = self.runtime_dir
        return env

    def _ensure_log_ready(self) -> None:
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        if self._log_handle is None or self._log_handle.closed:
            self._log_handle = open(self.log_path, "ab", buffering=0)

    def _write_log_marker(self, text: str) -> None:
        try:
            self._ensure_log_ready()
            line = "\n===== {} =====\n".format(text)
            self._log_handle.write(line.encode("utf-8", errors="ignore"))
        except Exception:
            pass

    def _write_log_line(self, text: str) -> None:
        try:
            self._ensure_log_ready()
            line = "{}\n".format(text)
            self._log_handle.write(line.encode("utf-8", errors="ignore"))
        except Exception:
            pass

    def _ensure_mpv_running(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return

            try:
                if os.path.exists(self.socket_path):
                    os.remove(self.socket_path)
            except Exception:
                pass

            self._ensure_log_ready()
            self._write_log_marker("mpv start {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))

            self._process = subprocess.Popen(
                self._build_command(),
                stdout=subprocess.DEVNULL,
                stderr=self._log_handle,
                env=self._build_env(),
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
            s.settimeout(1.5)
            s.connect(self.socket_path)
            payload = json.dumps({"command": command}) + "\n"
            s.sendall(payload.encode("utf-8"))
            try:
                data = s.recv(8192)
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

    def _set_property(self, prop: str, value: Any) -> Optional[Dict]:
        self._ensure_mpv_running()
        return self._send_raw_command(["set_property", prop, value])

    def _get_audio_device_list(self) -> List[Dict]:
        data = self._get_property("audio-device-list")
        if isinstance(data, list):
            return data
        return []

    def _pick_audio_device_name(self, devices: List[Dict], wanted_output: str) -> Optional[str]:
        wanted = (wanted_output or "hdmi").lower()

        normalized = []
        for item in devices:
            name = str(item.get("name") or "")
            description = str(item.get("description") or "")
            combined = (name + " " + description).lower()
            normalized.append(
                {
                    "name": name,
                    "description": description,
                    "combined": combined,
                }
            )

        # Erst genaue Treffer nach Beschreibung / Name
        if wanted == "analog":
            keywords = ["codec", "analog", "sun4icodec", "sun4i-codec"]
        else:
            keywords = ["hdmi", "sun4ihdmi", "sun4i-hdmi"]

        for keyword in keywords:
            for item in normalized:
                if keyword in item["combined"]:
                    return item["name"]

        # Dann allgemeine ALSA-Default-Geräte als Fallback
        for item in normalized:
            if item["name"].startswith("alsa/auto"):
                return item["name"]

        for item in normalized:
            if item["name"].startswith("alsa/default"):
                return item["name"]

        for item in normalized:
            if item["name"] == "auto":
                return item["name"]

        return None

    def _apply_audio_output_preference(self) -> None:
        self._ensure_mpv_running()
        devices = self._get_audio_device_list()

        self._write_log_marker("audio-device-list")
        if not devices:
            self._write_log_line("audio-device-list is empty")
            return

        for item in devices:
            name = str(item.get("name") or "")
            description = str(item.get("description") or "")
            self._write_log_line("device: {} | {}".format(name, description))

        selected_name = self._pick_audio_device_name(devices, AUDIO_OUTPUT)
        if not selected_name:
            self._write_log_line("no matching audio device found for AUDIO_OUTPUT={}".format(AUDIO_OUTPUT))
            return

        response = self._set_property("audio-device", selected_name)
        self._write_log_line("selected audio-device: {}".format(selected_name))
        self._write_log_line("set_property response: {}".format(response))

    def show_idle_overlay(self) -> None:
        self._send_raw_command(["set_property", "osd-level", 3])
        self._send_raw_command(["show-text", self._idle_overlay_text(), 999999, 0])

    def clear_idle_overlay(self) -> None:
        self._send_raw_command(["show-text", "", 1, 0])

    def play_url(self, url: str, start_pos: Optional[float] = None) -> None:
        self.clear_idle_overlay()
        self._write_log_marker("play_url")
        self._apply_audio_output_preference()
        self._send_command(["loadfile", url, "replace"])
        if start_pos is not None and float(start_pos) > 0.5:
            time.sleep(0.8)
            self._send_command(["set_property", "time-pos", float(start_pos)])

    def stop(self) -> None:
        self._write_log_marker("stop")
        self._send_command(["stop"])
        time.sleep(0.2)
        self.show_idle_overlay()

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

            if bool(idle):
                self.show_idle_overlay()
        except Exception:
            pass
        return status

    def get_log_tail(self, max_lines: int = 120, max_chars: int = 24000) -> str:
        try:
            if not os.path.exists(self.log_path):
                return ""

            with open(self.log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            text = "".join(lines[-max_lines:])
            if len(text) > max_chars:
                text = text[-max_chars:]
            return text
        except Exception as e:
            return "Log konnte nicht gelesen werden: {}".format(str(e))