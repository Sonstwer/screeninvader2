import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# HTTP-Server
HOST = "0.0.0.0"
PORT = 5000

# Queue-Datei (persistente Warteschlange)
QUEUE_FILE = os.path.join(BASE_DIR, "queue.json")

# mpv IPC Socket (für JSON-API)
MPV_SOCKET_PATH = "/tmp/screeninvader2_mpv.sock"

# Standard-Audioausgabe:
#   "hdmi"   -> HDMI-Ausgang
#   "analog" -> 3,5mm-Klinke
AUDIO_OUTPUT = "hdmi"

# Basis-Startbefehl für mpv (weitere Optionen werden in player.py ergänzt)
MPV_COMMAND = [
    "mpv",
    "--idle=yes",
    "--force-window=yes",
    "--no-terminal",
    "--input-ipc-server={}".format(MPV_SOCKET_PATH),
]

# Anzahl Suchergebnisse
SEARCH_LIMIT = 10

# yt-dlp: Optionen für Suchanfragen
YTDLP_SEARCH_OPTS = {
    "quiet": True,
    "skip_download": True,
    "default_search": "ytsearch",
    "noplaylist": True,
    # forceipv4 kannst du bei Bedarf auf False setzen, aber auf vielen
    # Heimnetzen ist es stabiler mit IPv4.
    "forceipv4": True,
}

# yt-dlp: Optionen für das Ermitteln der Stream-URL
# Deine gewünschte Kette:
#   zuerst bis 1080p, dann 720, 480, 360, dann generische Fallbacks.
YTDLP_STREAM_OPTS = {
    "quiet": True,
    "noplaylist": True,
    "forceipv4": True,
    "format": (
        "bv*[height<=1080]+ba / "
        "bv*[height<=720]+ba / "
        "bv*[height<=480]+ba / "
        "bv*[height<=360]+ba / "
        "bestvideo+bestaudio / "
        "bestaudio / "
        "best"
    ),
}
