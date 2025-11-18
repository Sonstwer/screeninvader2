from typing import List, Dict, Optional

import yt_dlp

from config import (
    YTDLP_SEARCH_OPTS,
    YTDLP_STREAM_OPTS,
    YTDLP_EXTRACTOR_ARGS,
    SEARCH_LIMIT,
)


class YTDLPWrapper:
    def __init__(self) -> None:
        # Lokale Kopien der Basis-Optionen
        self.search_opts = dict(YTDLP_SEARCH_OPTS)
        self.stream_opts = dict(YTDLP_STREAM_OPTS)
        self.extractor_args = dict(YTDLP_EXTRACTOR_ARGS)

    def _is_url(self, text: str) -> bool:
        lower = (text or "").lower().strip()
        if lower.startswith("http://") or lower.startswith("https://"):
            return True
        if "youtube.com" in lower or "youtu.be" in lower:
            return True
        return False

    def _build_opts(self, base: Dict) -> Dict:
        """
        Kombiniert Basisoptionen mit den Extraktor-Argumenten.
        """
        opts = dict(base)
        if self.extractor_args:
            opts["extractor_args"] = self.extractor_args
        return opts

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> List[Dict]:
        """
        YouTube-Suche, liefert eine Liste mit Metadaten.

        - Bei direkter URL: genau dieses Video/Playlist wird aufgelöst.
        - Bei normalem Text: ytsearchN:query
        """
        query = (query or "").strip()
        if not query:
            return []

        # Direkte URL?
        if self._is_url(query):
            opts = self._build_opts(self.stream_opts)
            entries: List[Dict] = []
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)
            # Kann Video oder Playlist sein
            if "entries" in info:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    entries.append(
                        {
                            "id": entry.get("id"),
                            "title": entry.get("title"),
                            "channel": entry.get("uploader"),
                            "duration": entry.get("duration"),
                            "thumbnail": entry.get("thumbnail"),
                            "webpage_url": entry.get("webpage_url"),
                        }
                    )
                return entries
            # Einzelnes Video
            return [
                {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "channel": info.get("uploader"),
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url"),
                }
            ]

        # Normale Textsuche mit mehreren Wörtern
        search_query = "ytsearch{}:{}".format(limit, query)
        opts = self._build_opts(self.search_opts)
        opts["default_search"] = "ytsearch"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_query, download=False)

        results: List[Dict] = []
        if "entries" in info:
            for entry in info["entries"]:
                if not entry:
                    continue
                results.append(
                    {
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "channel": entry.get("uploader"),
                        "duration": entry.get("duration"),
                        "thumbnail": entry.get("thumbnail"),
                        "webpage_url": entry.get("webpage_url"),
                    }
                )
        return results

    def get_stream_url(self, video_url: str) -> Optional[str]:
        """
        Liefert eine direkte Stream-URL für mpv.
        """
        if not video_url:
            return None

        opts = self._build_opts(self.stream_opts)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        # Je nach yt-dlp-Version:
        # - Direkt 'url'
        # - oder 'webpage_url' (Fallback)
        if "url" in info:
            return info["url"]
        if "webpage_url" in info:
            return info["webpage_url"]
        return None
