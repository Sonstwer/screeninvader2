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

# yt-dlp Basiskonfiguration

# Optionen für Suchanfragen
YTDLP_SEARCH_OPTS = {
    "quiet": True,
    "skip_download": True,
    "default_search": "ytsearch",
    "noplaylist": True,
    "forceipv4": True,
}

# Optionen für das Ermitteln der Stream-URL
# 720p-Limit, damit der Banana Pi nicht überfordert wird
YTDLP_STREAM_OPTS = {
    "quiet": True,
    "format": "bv*[height<=720]+ba / best[height<=720] / best",
    "noplaylist": True,
    "forceipv4": True,
}

# Spezielle Extraktor-Argumente für YouTube:
# Nutze den Android-Client, der oft weniger restriktiv ist als der Web-Client.
YTDLP_EXTRACTOR_ARGS = {
    "youtube": {
        "player_client": ["android"],
    }
}
