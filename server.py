import threading
import time
import traceback

from flask import Flask, jsonify, render_template, request

from config import HOST, PORT, QUEUE_FILE
from player import MPVPlayer
from queue_manager import QueueManager
from yt_wrapper import YTDLPWrapper

app = Flask(__name__)

queue_manager = QueueManager(QUEUE_FILE)
player = MPVPlayer()
yt = YTDLPWrapper()

_playback_worker_started = False
_manual_stop_requested = False
_last_play_start_ts = 0.0
_last_confirmed_playback = False

_last_playback_error = ""
_last_debug_event = {
    "timestamp": 0.0,
    "message": "startup",
}

_search_cache = {}
_search_cache_lock = threading.Lock()
_search_cache_ttl_seconds = 300
_search_cache_max_entries = 100


def _set_debug_event(message: str):
    global _last_debug_event
    _last_debug_event = {
        "timestamp": time.time(),
        "message": str(message),
    }


def _set_playback_error(message: str):
    global _last_playback_error
    _last_playback_error = str(message or "")
    _set_debug_event("playback_error: {}".format(_last_playback_error))


def _clear_playback_error():
    global _last_playback_error
    _last_playback_error = ""


def _normalize_search_query(query: str) -> str:
    return (query or "").strip().lower()


def _get_cached_search(query: str):
    key = _normalize_search_query(query)
    if not key:
        return None

    now = time.time()
    with _search_cache_lock:
        entry = _search_cache.get(key)
        if not entry:
            return None
        if (now - entry["timestamp"]) > _search_cache_ttl_seconds:
            _search_cache.pop(key, None)
            return None
        return entry["results"]


def _set_cached_search(query: str, results):
    key = _normalize_search_query(query)
    if not key:
        return

    now = time.time()
    with _search_cache_lock:
        _search_cache[key] = {
            "timestamp": now,
            "results": results,
        }

        expired = []
        for cache_key, entry in _search_cache.items():
            if (now - entry["timestamp"]) > _search_cache_ttl_seconds:
                expired.append(cache_key)

        for cache_key in expired:
            _search_cache.pop(cache_key, None)

        if len(_search_cache) > _search_cache_max_entries:
            sorted_items = sorted(
                _search_cache.items(),
                key=lambda item: item[1]["timestamp"]
            )
            while len(sorted_items) > _search_cache_max_entries:
                oldest_key, _ = sorted_items.pop(0)
                _search_cache.pop(oldest_key, None)


def _wait_for_real_playback_start(timeout_seconds: float = 12.0) -> bool:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            status = player.get_status()

            if status.get("playing"):
                return True

            time_pos = status.get("time_pos")
            duration = status.get("duration")

            if time_pos is not None:
                return True

            if duration is not None:
                return True
        except Exception:
            pass

        time.sleep(0.5)

    return False


def _play_current_item(start_pos: float = 0.0):
    global _last_play_start_ts, _last_confirmed_playback

    current_item = queue_manager.get_current_item()
    if current_item is None:
        _set_playback_error("Kein aktueller Eintrag")
        return False, "Kein aktueller Eintrag"

    url = current_item.get("webpage_url")
    if not url:
        queue_manager.mark_current_status("error", "missing_webpage_url")
        _set_playback_error("missing_webpage_url")
        return False, "missing_webpage_url"

    try:
        _set_debug_event("stream_url_lookup_start")
        stream_url = yt.get_stream_url(url)
        if not stream_url:
            queue_manager.mark_current_status("error", "Keine Stream-URL ermittelbar")
            _set_playback_error("Keine Stream-URL ermittelbar")
            return False, "no_stream_url"

        queue_manager.mark_current_status("queued")
        _set_debug_event("mpv_play_url")
        player.play_url(stream_url, start_pos=start_pos)

        started = _wait_for_real_playback_start(timeout_seconds=12.0)
        if not started:
            queue_manager.mark_current_status("error", "Playback start timeout")
            _last_confirmed_playback = False
            _set_playback_error("Playback start timeout")
            return False, "playback_start_timeout"

        queue_manager.mark_current_status("playing")
        _last_play_start_ts = time.time()
        _last_confirmed_playback = True
        _clear_playback_error()
        _set_debug_event("playback_started")
        return True, None

    except Exception as e:
        print("Playback error:", str(e))
        traceback.print_exc()
        queue_manager.mark_current_status("error", str(e))
        _last_confirmed_playback = False
        _set_playback_error(str(e))
        return False, str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": [], "cached": False})

    try:
        cached = _get_cached_search(query)
        if cached is not None:
            _set_debug_event("search_cache_hit: {}".format(query))
            return jsonify({"results": cached, "cached": True})

        _set_debug_event("search_start: {}".format(query))
        results = yt.search(query)
        _set_cached_search(query, results)
        _set_debug_event("search_done: {} results={}".format(query, len(results)))
        return jsonify({"results": results, "cached": False})
    except Exception as e:
        print("Search error:", str(e))
        traceback.print_exc()
        _set_debug_event("search_error: {}".format(str(e)))
        return jsonify({"error": "search_failed", "details": str(e)}), 500


@app.route("/api/queue", methods=["GET"])
def api_get_queue():
    return jsonify(
        {
            "queue": queue_manager.get_queue(),
            "current_index": queue_manager.get_current_index(),
            "current_item": queue_manager.get_current_item(),
        }
    )


@app.route("/api/queue/add", methods=["POST"])
def api_add_queue():
    data = request.get_json(force=True, silent=True) or {}
    webpage_url = data.get("webpage_url")

    if not webpage_url:
        return jsonify({"error": "missing_webpage_url"}), 400

    item = {
        "id": data.get("id") or webpage_url,
        "title": data.get("title"),
        "channel": data.get("channel"),
        "duration": data.get("duration"),
        "webpage_url": webpage_url,
    }
    saved = queue_manager.add_item(item)
    _set_debug_event("queue_add: {}".format(saved.get("title") or saved.get("id")))
    return jsonify({"status": "ok", "item": saved})


@app.route("/api/queue/clear", methods=["POST"])
def api_clear_queue():
    global _manual_stop_requested, _last_confirmed_playback
    _manual_stop_requested = True
    _last_confirmed_playback = False
    queue_manager.clear()
    player.stop()
    _set_debug_event("queue_clear")
    return jsonify({"status": "ok"})


@app.route("/api/queue/remove", methods=["POST"])
def api_remove_from_queue():
    data = request.get_json(force=True, silent=True) or {}
    index = data.get("index")

    if index is None:
        return jsonify({"error": "missing_index"}), 400

    try:
        index = int(index)
    except ValueError:
        return jsonify({"error": "invalid_index"}), 400

    ok = queue_manager.remove_index(index)
    if not ok:
        return jsonify({"error": "index_out_of_range"}), 400

    _set_debug_event("queue_remove_index: {}".format(index))
    return jsonify({"status": "ok"})


@app.route("/api/player/status", methods=["GET"])
def api_player_status():
    raw_status = player.get_status()
    current_item = queue_manager.get_current_item()
    queue_status = current_item.get("status") if current_item else "idle"

    status = dict(raw_status)
    status["queue_size"] = queue_manager.size()
    status["current_index"] = queue_manager.get_current_index()
    status["current_item"] = current_item

    status["playing"] = queue_status == "playing"
    status["paused"] = queue_status == "paused"

    if current_item and not status.get("title"):
        status["title"] = current_item.get("title")

    return jsonify(status)


@app.route("/api/debug", methods=["GET"])
def api_debug():
    raw_status = player.get_status()
    current_item = queue_manager.get_current_item()
    queue = queue_manager.get_queue()

    return jsonify(
        {
            "timestamp": time.time(),
            "manual_stop_requested": _manual_stop_requested,
            "last_play_start_ts": _last_play_start_ts,
            "last_confirmed_playback": _last_confirmed_playback,
            "last_playback_error": _last_playback_error,
            "last_debug_event": _last_debug_event,
            "player_status": raw_status,
            "current_item": current_item,
            "current_index": queue_manager.get_current_index(),
            "queue_size": len(queue),
            "queue": queue,
        }
    )


@app.route("/api/player/play", methods=["POST"])
def api_player_play():
    global _manual_stop_requested

    if queue_manager.size() == 0:
        return jsonify({"error": "queue_empty"}), 400

    if queue_manager.get_current_item() is None:
        queue_manager.set_current_index(0)

    _manual_stop_requested = False
    paused_position = queue_manager.get_paused_position()
    _set_debug_event("player_play")
    ok, error = _play_current_item(start_pos=paused_position)

    if ok:
        queue_manager.clear_paused_position()
        return jsonify({"status": "ok"})

    return jsonify({"error": "play_failed", "details": error}), 500


@app.route("/api/player/toggle", methods=["POST"])
def api_player_toggle():
    global _manual_stop_requested, _last_confirmed_playback

    current_item = queue_manager.get_current_item()
    if current_item is None and queue_manager.size() > 0:
        queue_manager.set_current_index(0)
        current_item = queue_manager.get_current_item()

    if current_item is None:
        return jsonify({"error": "queue_empty"}), 400

    current_status = current_item.get("status")

    if current_status == "playing":
        raw_status = player.get_status()
        pos = raw_status.get("time_pos") or 0.0
        queue_manager.set_paused_position(pos)
        _manual_stop_requested = True
        _last_confirmed_playback = False
        player.stop()
        queue_manager.mark_current_status("paused")
        _set_debug_event("player_paused")
        return jsonify({"status": "paused", "position": pos})

    _manual_stop_requested = False
    start_pos = queue_manager.get_paused_position() if current_status == "paused" else 0.0
    _set_debug_event("player_resume_or_play")
    ok, error = _play_current_item(start_pos=start_pos)

    if ok:
        queue_manager.clear_paused_position()
        return jsonify({"status": "playing"})

    return jsonify({"error": "resume_failed", "details": error}), 500


@app.route("/api/player/stop", methods=["POST"])
def api_player_stop():
    global _manual_stop_requested, _last_confirmed_playback
    _manual_stop_requested = True
    _last_confirmed_playback = False
    player.stop()
    queue_manager.clear_paused_position()
    if queue_manager.get_current_item() is not None:
        queue_manager.mark_current_status("queued")
    _set_debug_event("player_stop")
    return jsonify({"status": "ok"})


@app.route("/api/player/next", methods=["POST"])
def api_player_next():
    global _manual_stop_requested, _last_confirmed_playback
    _manual_stop_requested = False
    _last_confirmed_playback = False

    player.stop()
    queue_manager.clear_paused_position()

    next_idx = queue_manager.next_index()
    if next_idx == -1:
        _set_debug_event("player_next_end_of_queue")
        return jsonify({"status": "end_of_queue"})

    _set_debug_event("player_next_index: {}".format(next_idx))
    ok, error = _play_current_item(start_pos=0.0)
    if ok:
        return jsonify({"status": "ok", "current_index": next_idx})
    return jsonify({"error": "next_failed", "details": error}), 500


@app.route("/api/player/previous", methods=["POST"])
def api_player_previous():
    global _manual_stop_requested, _last_confirmed_playback
    _manual_stop_requested = False
    _last_confirmed_playback = False

    player.stop()
    queue_manager.clear_paused_position()

    prev_idx = queue_manager.previous_index()
    if prev_idx == -1:
        _set_debug_event("player_previous_start_of_queue")
        return jsonify({"status": "start_of_queue"})

    _set_debug_event("player_previous_index: {}".format(prev_idx))
    ok, error = _play_current_item(start_pos=0.0)
    if ok:
        return jsonify({"status": "ok", "current_index": prev_idx})
    return jsonify({"error": "previous_failed", "details": error}), 500


@app.route("/api/player/play_index", methods=["POST"])
def api_player_play_index():
    global _manual_stop_requested, _last_confirmed_playback
    data = request.get_json(force=True, silent=True) or {}
    index = data.get("index")

    if index is None:
        return jsonify({"error": "missing_index"}), 400

    try:
        index = int(index)
    except ValueError:
        return jsonify({"error": "invalid_index"}), 400

    ok = queue_manager.set_current_index(index)
    if not ok:
        return jsonify({"error": "index_out_of_range"}), 400

    _manual_stop_requested = False
    _last_confirmed_playback = False
    player.stop()
    queue_manager.clear_paused_position()

    _set_debug_event("player_play_index: {}".format(index))
    ok, error = _play_current_item(start_pos=0.0)
    if ok:
        return jsonify({"status": "ok", "current_index": index})
    return jsonify({"error": "play_index_failed", "details": error}), 500


@app.route("/api/player/shuffle", methods=["POST"])
def api_player_shuffle():
    ok = queue_manager.shuffle_keep_current()
    _set_debug_event("player_shuffle")
    return jsonify({"status": "ok", "changed": ok})


def playback_worker():
    global _manual_stop_requested, _last_play_start_ts, _last_confirmed_playback

    while True:
        try:
            current_item = queue_manager.get_current_item()
            if current_item is None:
                time.sleep(1.0)
                continue

            current_status = current_item.get("status")

            if current_status == "playing":
                enough_time_passed = (time.time() - _last_play_start_ts) > 5.0

                if enough_time_passed and _last_confirmed_playback and not player.is_playing():
                    queue_manager.mark_current_status("done")
                    queue_manager.clear_paused_position()
                    _last_confirmed_playback = False
                    _set_debug_event("playback_finished_mark_done")

                    next_idx = queue_manager.next_index()
                    if next_idx != -1:
                        _manual_stop_requested = False
                        _set_debug_event("autoplay_next_index: {}".format(next_idx))
                        _play_current_item(start_pos=0.0)

            time.sleep(1.0)
        except Exception as e:
            print("Worker error:", str(e))
            traceback.print_exc()
            _set_playback_error("worker_error: {}".format(str(e)))
            time.sleep(1.0)


def start_playback_worker_once():
    global _playback_worker_started
    if not _playback_worker_started:
        thread = threading.Thread(target=playback_worker, daemon=True)
        thread.start()
        _playback_worker_started = True
        _set_debug_event("playback_worker_started")


if __name__ == "__main__":
    start_playback_worker_once()
    app.run(host=HOST, port=PORT)