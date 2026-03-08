import json
import os
import random
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
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(
                {"queue": self._queue, "current_index": self._current_index},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _normalize(self) -> None:
        if not isinstance(self._queue, list):
            self._queue = []
        for item in self._queue:
            if "status" not in item:
                item["status"] = "queued"
        if not self._queue:
            self._current_index = -1
        elif self._current_index < 0:
            self._current_index = 0
        elif self._current_index >= len(self._queue):
            self._current_index = len(self._queue) - 1

    def _reset_statuses(self) -> None:
        for item in self._queue:
            item["status"] = "queued"
            item.pop("error", None)

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
            if self._current_index == -1:
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
            else:
                if self._current_index > index:
                    self._current_index -= 1
                elif self._current_index >= len(self._queue):
                    self._current_index = len(self._queue) - 1
            self._save()
            return True

    def get_current_index(self) -> int:
        with self._lock:
            return self._current_index

    def get_item(self, index: int) -> Optional[Dict]:
        with self._lock:
            if 0 <= index < len(self._queue):
                return dict(self._queue[index])
            return None

    def get_current_item(self) -> Optional[Dict]:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                return dict(self._queue[self._current_index])
            return None

    def set_current_index(self, index: int, status: str = "queued") -> bool:
        with self._lock:
            if index < 0 or index >= len(self._queue):
                return False
            self._current_index = index
            self._reset_statuses()
            self._queue[index]["status"] = status
            self._save()
            return True

    def mark_status(self, index: int, status: str, error: str = "") -> bool:
        with self._lock:
            if index < 0 or index >= len(self._queue):
                return False
            self._reset_statuses()
            self._queue[index]["status"] = status
            if error:
                self._queue[index]["error"] = error[:500]
            self._save()
            return True

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

    def shuffle(self) -> bool:
        with self._lock:
            if len(self._queue) < 2:
                return False
            current_item = None
            if 0 <= self._current_index < len(self._queue):
                current_item = self._queue[self._current_index]
            remaining = [item for i, item in enumerate(self._queue) if i != self._current_index]
            random.shuffle(remaining)
            if current_item is not None:
                self._queue = [current_item] + remaining
                self._current_index = 0
            else:
                self._queue = remaining
                self._current_index = 0 if self._queue else -1
            self._reset_statuses()
            if 0 <= self._current_index < len(self._queue):
                self._queue[self._current_index]["status"] = "queued"
            self._save()
            return True

    def current_stream_target(self) -> Tuple[int, Optional[Dict]]:
        with self._lock:
            if 0 <= self._current_index < len(self._queue):
                return self._current_index, dict(self._queue[self._current_index])
            return -1, None
