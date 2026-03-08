import threading
import time
from typing import Dict, List, Optional

import yt_dlp

from config import YTDLP_SEARCH_OPTS, YTDLP_STREAM_OPTS, SEARCH_LIMIT


class YTDLPWrapper:
    def __init__(self):
        self.search_opts = dict(YTDLP_SEARCH_OPTS)
        self.stream_opts = dict(YTDLP_STREAM_OPTS)

        self._stream_cache = {}
        self._stream_cache_lock = threading.Lock()
        self._stream_cache_ttl_seconds = 1800

    def _is_url(self, text: str) -> bool:
        lower = (text or "").lower().strip()
        return lower.startswith("http://") or lower.startswith("https://")

    def _stream_cache_get(self, video_url: str) -> Optional[str]:
        now = time.time()
        with self._stream_cache_lock:
            entry = self._stream_cache.get(video_url)
            if not entry:
                return None
            if (now - entry["timestamp"]) > self._stream_cache_ttl_seconds:
                self._stream_cache.pop(video_url, None)
                return None
            return entry["stream_url"]

    def _stream_cache_set(self, video_url: str, stream_url: str) -> None:
        now = time.time()
        with self._stream_cache_lock:
            self._stream_cache[video_url] = {
                "timestamp": now,
                "stream_url": stream_url,
            }

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> List[Dict]:
        query = (query or "").strip()
        if not query:
            return []

        if self._is_url(query):
            opts = {
                "quiet": True,
                "skip_download": True,
                "forceipv4": True,
                "noplaylist": False,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)

            results: List[Dict] = []

            if "entries" in info and info["entries"]:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    results.append(
                        {
                            "id": entry.get("id"),
                            "title": entry.get("title"),
                            "channel": entry.get("uploader") or entry.get("channel") or "",
                            "duration": entry.get("duration"),
                            "thumbnail": entry.get("thumbnail"),
                            "webpage_url": entry.get("webpage_url"),
                        }
                    )
                return results

            return [
                {
                    "id": info.get("id"),
                    "title": info.get("title"),
                    "channel": info.get("uploader") or info.get("channel") or "",
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url"),
                }
            ]

        search_query = "ytsearch{}:{}".format(limit, query)
        opts = dict(self.search_opts)
        opts["playlistend"] = limit
        opts["extract_flat"] = "in_playlist"
        opts["skip_download"] = True
        opts["default_search"] = "ytsearch"
        opts["forceipv4"] = True

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_query, download=False)

        results: List[Dict] = []

        if "entries" in info and info["entries"]:
            for entry in info["entries"]:
                if not entry:
                    continue

                video_id = entry.get("id") or entry.get("url")
                webpage_url = entry.get("webpage_url")

                if not webpage_url and video_id:
                    webpage_url = "https://www.youtube.com/watch?v={}".format(video_id)

                results.append(
                    {
                        "id": video_id,
                        "title": entry.get("title"),
                        "channel": entry.get("uploader") or entry.get("channel") or entry.get("uploader_id") or "",
                        "duration": entry.get("duration"),
                        "thumbnail": entry.get("thumbnail"),
                        "webpage_url": webpage_url,
                    }
                )

        return results

    def get_stream_url(self, video_url: str) -> Optional[str]:
        if not video_url:
            return None

        cached = self._stream_cache_get(video_url)
        if cached is not None:
            return cached

        opts = dict(self.stream_opts)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        stream_url = None

        if "url" in info:
            stream_url = info["url"]
        elif info.get("requested_downloads"):
            requested = info.get("requested_downloads") or []
            if requested and requested[0].get("url"):
                stream_url = requested[0]["url"]
        elif info.get("requested_formats"):
            requested = info.get("requested_formats") or []
            if requested and requested[0].get("url"):
                stream_url = requested[0]["url"]
        elif "webpage_url" in info:
            stream_url = info["webpage_url"]

        if stream_url:
            self._stream_cache_set(video_url, stream_url)

        return stream_url