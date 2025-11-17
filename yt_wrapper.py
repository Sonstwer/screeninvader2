from typing import List, Dict, Optional
import yt_dlp

from config import YTDLP_SEARCH_OPTS, YTDLP_STREAM_OPTS, SEARCH_LIMIT


class YTDLPWrapper:
    def __init__(self):
        self.search_opts = dict(YTDLP_SEARCH_OPTS)
        self.stream_opts = dict(YTDLP_STREAM_OPTS)

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> List[Dict]:
        """Youtube-Suche, liefert einfache Liste mit Metadaten."""
        q = "ytsearch{}:{}".format(limit, query)
        opts = dict(self.search_opts)
        opts["default_search"] = "ytsearch"
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(q, download=False)
        entries = []
        if "entries" in info:
            for entry in info["entries"]:
                if not entry:
                    continue
                entries.append({
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "channel": entry.get("uploader"),
                    "duration": entry.get("duration"),
                    "thumbnail": entry.get("thumbnail"),
                    "webpage_url": entry.get("webpage_url"),
                })
        return entries

    def get_stream_url(self, video_url: str) -> Optional[str]:
        """Liefert eine direkte Stream-URL für mpv."""
        opts = dict(self.stream_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        if "url" in info:
            return info["url"]
        if "webpage_url" in info:
            return info["webpage_url"]
        return None
