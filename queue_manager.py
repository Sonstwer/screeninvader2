import json
import os
import threading
from typing import Dict, List, Optional, Tuple


class QueueManager:
    def __init__(self, queue_file: str):
        self.queue_file = queue_file
        self._lock = threading.Lock()
        self._queue: List[Dict] = []
        self._current_index: int = -1
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.queue_file):
            self._queue = []
            self._current_index = -1
            return

        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                self._queue = data.get("queue", [])
                self._current_index = int(data.get("current_index", -1))
            elif isinstance(data, list):
                self._queue = data
                self._current_index = -1
            else:
                self._queue = []
                self._current_index = -1

            self._normalize()
        except Exception:
            self._queue = []
            self._current_index = -1

    def _save(self) -> None:
        data = {
            "queue": self._queue,
            "current_index": self._current_index,
        }
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize(self) -> None:
        if not isinstance(self._queue, list):
            self._queue = []

        for item in self._queue:
            if "status" not in item:
                item["status"] = "queued"

        if not self._queue:
            self._current_index = -1
            return

        if self._current_index < 0 or self._current_index >= len(self._queue):
            self._current_index = -1

    def _reset_statuses(self) -> None:
        for item in self._queue:
            item["status"] = "queued"

    def add_item(self, item: Dict) -> Dict:
        with self._lock:
            entry = {
                "id": item.get("id") or item.get("webpage_url"),
                "title": item.get("title") or "Unbekannt",
                "channel": item.get("channel") or "",
                "duration": item.get("duration"),
                "webpage_url": item.get("webpage_url"),
                "status": "queued",
            }
            self._queue.append(entry)

            if self._current_index == -1 and len(self._queue) == 1:
                self._current_index = 0

            self._save()
            return dict(entry)

    def get_queue(self) -> List[Dict]:
        with self._lock:
            return [dict(item) for item in self._queue]

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue = []
            self._current_index = -1
            self._save()

    def remove_index(self, index: int) -> bool:
        with self._lock:
            if index < 0 or index >= len(self._queue):
                return False

            del self._queue[index]

            if not self._queue:
                self._current_index = -1
            elif self._current_index > index:
                self._current_index -= 1
            elif self._current_index == index:
                if self._current_index >= len(self._queue):
                    self._current_index = len(self._queue) - 1
                self._reset_statuses()
                if self._current_index >= 0:
                    self._queue[self._current_index]["status"] = "queued"

            self._save()
            return True

    def get_current_index(self) -> int:
        with self._lock:
            return self._current_index

    def get_current_item(self) -> Optional[Dict]:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                return dict(self._queue[self._current_index])
            return None

    def set_current_index(self, index: int, playing: bool = False) -> bool:
        with self._lock:
            if index < 0 or index >= len(self._queue):
                return False

            self._current_index = index
            self._reset_statuses()
            self._queue[index]["status"] = "playing" if playing else "queued"
            self._save()
            return True

    def mark_current_playing(self) -> bool:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                self._reset_statuses()
                self._queue[self._current_index]["status"] = "playing"
                self._save()
                return True
            return False

    def mark_current_paused(self) -> bool:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                self._reset_statuses()
                self._queue[self._current_index]["status"] = "paused"
                self._save()
                return True
            return False

    def mark_current_done(self) -> bool:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                self._reset_statuses()
                self._queue[self._current_index]["status"] = "done"
                self._save()
                return True
            return False

    def mark_current_error(self, message: str = "") -> bool:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                self._reset_statuses()
                self._queue[self._current_index]["status"] = "error"
                self._queue[self._current_index]["error"] = message[:500]
                self._save()
                return True
            return False

    def next_index(self) -> int:
        with self._lock:
            if not self._queue:
                return -1
            if self._current_index < len(self._queue) - 1:
                self._current_index += 1
                self._reset_statuses()
                self._queue[self._current_index]["status"] = "queued"
                self._save()
                return self._current_index
            return -1

    def previous_index(self) -> int:
        with self._lock:
            if not self._queue:
                return -1
            if self._current_index > 0:
                self._current_index -= 1
                self._reset_statuses()
                self._queue[self._current_index]["status"] = "queued"
                self._save()
                return self._current_index
            return -1

    def current_stream_target(self) -> Tuple[int, Optional[Dict]]:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                return self._current_index, dict(self._queue[self._current_index])
            return -1, None