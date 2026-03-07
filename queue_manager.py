import json
import os
import threading
import time
from typing import Dict, List, Optional


class QueueManager:
    def __init__(self, queue_file: str):
        self.queue_file = queue_file
        self._lock = threading.Lock()
        self._queue: List[Dict] = []
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
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(self._queue, f, ensure_ascii=False, indent=2)

    def _ensure_defaults(self, item: Dict) -> Dict:
        now = int(time.time())
        if "status" not in item:
            item["status"] = "queued"
        if "created_at" not in item:
            item["created_at"] = now
        if "updated_at" not in item:
            item["updated_at"] = now
        return item

    def add_item(self, item: Dict) -> Dict:
        with self._lock:
            item = dict(item)
            item = self._ensure_defaults(item)
            self._queue.append(item)
            self._save()
            return item

    def get_queue(self) -> List[Dict]:
        with self._lock:
            return [dict(item) for item in self._queue]

    def get_next_queued_item(self) -> Optional[Dict]:
        with self._lock:
            for item in self._queue:
                if item.get("status") == "queued":
                    return dict(item)
            return None

    def mark_playing_by_id(self, item_id: str) -> bool:
        with self._lock:
            changed = False
            for item in self._queue:
                if item.get("id") == item_id and item.get("status") != "done":
                    item["status"] = "playing"
                    item["updated_at"] = int(time.time())
                    changed = True
                elif item.get("status") == "playing":
                    item["status"] = "queued"
                    item["updated_at"] = int(time.time())
                    changed = True
            if changed:
                self._save()
            return changed

    def mark_done_by_id(self, item_id: str) -> bool:
        with self._lock:
            for item in self._queue:
                if item.get("id") == item_id:
                    item["status"] = "done"
                    item["updated_at"] = int(time.time())
                    self._save()
                    return True
            return False

    def mark_error_by_id(self, item_id: str, error_message: str = "") -> bool:
        with self._lock:
            for item in self._queue:
                if item.get("id") == item_id:
                    item["status"] = "error"
                    item["error"] = error_message[:500]
                    item["updated_at"] = int(time.time())
                    self._save()
                    return True
            return False

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

    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def has_playing_item(self) -> bool:
        with self._lock:
            for item in self._queue:
                if item.get("status") == "playing":
                    return True
            return False

    def get_playing_item(self) -> Optional[Dict]:
        with self._lock:
            for item in self._queue:
                if item.get("status") == "playing":
                    return dict(item)
            return None