import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = "0.0.0.0"
PORT = 5000

QUEUE_FILE = os.path.join(BASE_DIR, "queue.json")
MPV_SOCKET_PATH = "/tmp/screeninvader2_mpv.sock"

# "hdmi" oder "analog"
AUDIO_OUTPUT = "hdmi"

# Audio-only, aber mit sichtbarem Idle-Fenster
MPV_COMMAND = [
    "mpv",
    "--idle=yes",
    "--force-window=yes",
    "--no-video",
    "--title=ScreenInvader 2.0",
    "--no-terminal",
    "--input-ipc-server={}".format(MPV_SOCKET_PATH),
    "--osc=no",
    "--osd-bar=no",
    "--audio-display=no",
    "--player-operation-mode=cplayer",
    "--cache=yes",
    "--demuxer-readahead-secs=8",
]

SEARCH_LIMIT = 6

YTDLP_SEARCH_OPTS = {
    "quiet": True,
    "skip_download": True,
    "extract_flat": "in_playlist",
    "playlistend": SEARCH_LIMIT,
    "default_search": "ytsearch",
    "noplaylist": False,
    "forceipv4": True,
}

YTDLP_STREAM_OPTS = {
    "quiet": True,
    "noplaylist": True,
    "forceipv4": True,
    "format": "bestaudio[acodec!=none]/bestaudio/best",
}