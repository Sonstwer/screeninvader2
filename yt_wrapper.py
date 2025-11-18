from typing import List, Dict, Optional
import yt_dlp

from config import YTDLP_SEARCH_OPTS, YTDLP_STREAM_OPTS, SEARCH_LIMIT


class YTDLPWrapper:
    def __init__(self):
        self.search_opts = dict(YTDLP_SEARCH_OPTS)
        self.stream_opts = dict(YTDLP_STREAM_OPTS)

    def _is_url(self, text: str) -> bool:
        lower = text.lower().strip()
        if lower.startswith("http://") or lower.startswith("https://"):
            return True
        if "youtube.com" in lower or "youtu.be" in lower:
            return True
        return False

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> List[Dict]:
        """
        Youtube-Suche, liefert einfache Liste mit Metadaten.

        - Bei einer direkten URL wird genau dieses Video aufgelöst.
        - Bei normalem Text wird ytsearch verwendet.
        """
        query = (query or "").strip()
        if not query:
            return []

        # Direkte URL
        if self._is_url(query):
            opts = dict(self.stream_opts)
            opts["quiet"] = True
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)
            entry = {
                "id": info.get("id"),
                "title": info.get("title"),
                "channel": info.get("uploader"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "webpage_url": info.get("webpage_url"),
            }
            return [entry]

        # Normale Textsuche
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
        """
        Liefert eine direkte Stream-URL für mpv.
        """
        opts = dict(self.stream_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        if "url" in info:
            return info["url"]
        if "webpage_url" in info:
            return info["webpage_url"]
        return None
