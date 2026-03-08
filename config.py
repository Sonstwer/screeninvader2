import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# HTTP-Server
HOST = "0.0.0.0"
PORT = 5000

# Queue-Datei
QUEUE_FILE = os.path.join(BASE_DIR, "queue.json")

# mpv IPC Socket
MPV_SOCKET_PATH = "/tmp/screeninvader2_mpv.sock"

# Standard-Audioausgabe:
#   "hdmi"   -> HDMI-Ausgang (bei deinem Board hw:0,0)
#   "analog" -> 3,5mm-Klinke (bei deinem Board hw:1,0)
AUDIO_OUTPUT = "hdmi"

# Such-Cache
SEARCH_CACHE_TTL_SECONDS = 300
SEARCH_CACHE_MAX_ITEMS = 50

# mpv-Startbefehl – Audio-only mit sichtbarem Idle-Fenster
MPV_COMMAND = [
    "mpv",
    "--idle=yes",
    "--force-window=yes",
    "--no-video",
    "--no-terminal",
    "--input-ipc-server={}".format(MPV_SOCKET_PATH),

    # UI / OSD
    "--osc=no",
    "--osd-bar=no",
    "--audio-display=no",
    "--player-operation-mode=cplayer",
    "--osd-level=3",

    # Audio-only konservativ puffern
    "--cache=yes",
    "--demuxer-readahead-secs=8",
]

# Anzahl Suchergebnisse
SEARCH_LIMIT = 10

# yt-dlp: Suche
YTDLP_SEARCH_OPTS = {
    "quiet": True,
    "skip_download": True,
    "default_search": "ytsearch",
    "noplaylist": True,
    "forceipv4": True,
}

# yt-dlp: Stream-URL-Ermittlung – nur Audio
YTDLP_STREAM_OPTS = {
    "quiet": True,
    "noplaylist": True,
    "forceipv4": True,
    "format": (
        "bestaudio[acodec!=none] / "
        "bestaudio / "
        "best"
    ),
}
