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
YTDLP_STREAM_OPTS = {
    "quiet": True,
    "noplaylist": True,
    "forceipv4": True,
    "format": (
        # zuerst bis 1080p versuchen
        "bv*[height<=1080]+ba / "
        # dann 720, 480, 360
        "bv*[height<=720]+ba / "
        "bv*[height<=480]+ba / "
        "bv*[height<=360]+ba / "
        # generische Fallbacks
        "bestvideo+bestaudio / "
        "bestaudio / "
        "best"
    ),
}


# Spezielle Extraktor-Argumente für YouTube:
# Nutze den Android-Client, der oft weniger restriktiv ist als der Web-Client.
YTDLP_EXTRACTOR_ARGS = {
    "youtube": {
        "player_client": ["android"],
    }
}
