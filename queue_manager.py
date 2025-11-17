import json
import threading
import os
from typing import List, Dict, Optional


class QueueManager:
    def __init__(self, queue_file: str):
        self.queue_file = queue_file
        self._lock = threading.Lock()
        self._queue = []  # type: List[Dict]
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.queue_file):
            self._queue = []
            return
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._queue = data
            else:
                self._queue = []
        except Exception:
            self._queue = []

    def _save(self) -> None:
        try:
            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(self._queue, f, ensure_ascii=False, indent=2)
        except Exception:
            # Fehler beim Speichern ignorieren, aber Queue im RAM weiterführen
            pass

    def add_item(self, item: Dict) -> None:
        with self._lock:
            self._queue.append(item)
            self._save()

    def get_queue(self) -> List[Dict]:
        with self._lock:
            return list(self._queue)

    def pop_next(self) -> Optional[Dict]:
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.pop(0)
            self._save()
            return item

    def clear(self) -> None:
        with self._lock:
            self._queue = []
            self._save()

    def remove_index(self, index: int) -> bool:
        with self._lock:
            if 0 <= index < len(self._queue):
                del self._queue[index]
                self._save()
                return True
            return False

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._queue) == 0

    def size(self) -> int:
        with self._lock:
            return len(self._queue)
