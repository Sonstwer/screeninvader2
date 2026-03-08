import threading
import time
import traceback

from flask import Flask, request, jsonify, render_template

from config import (
    HOST,
    PORT,
    QUEUE_FILE,
    SEARCH_CACHE_TTL_SECONDS,
    SEARCH_CACHE_MAX_ITEMS,
)
from queue_manager import QueueManager
from player import MPVPlayer
from yt_wrapper import YTDLPWrapper

app = Flask(__name__)

queue_manager = QueueManager(QUEUE_FILE)
player = MPVPlayer()
yt = YTDLPWrapper()

_playback_worker_started = False
_manual_stop_requested = False
_paused = False
_paused_position = 0.0

_search_cache = {}
_search_cache_lock = threading.Lock()


def _prune_search_cache() -> None:
    now = time.time()
    stale_keys = []
    for key, value in _search_cache.items():
        if now - value["ts"] > SEARCH_CACHE_TTL_SECONDS:
            stale_keys.append(key)
    for key in stale_keys:
        _search_cache.pop(key, None)

    if len(_search_cache) > SEARCH_CACHE_MAX_ITEMS:
        ordered = sorted(_search_cache.items(), key=lambda x: x[1]["ts"])
        overflow = len(_search_cache) - SEARCH_CACHE_MAX_ITEMS
        for key, _ in ordered[:overflow]:
            _search_cache.pop(key, None)


def _get_search_results(query: str):
    cache_key = query.strip().lower()
    now = time.time()
    with _search_cache_lock:
        cached = _search_cache.get(cache_key)
        if cached and now - cached["ts"] <= SEARCH_CACHE_TTL_SECONDS:
            return cached["results"]

    results = yt.search(query)

    with _search_cache_lock:
        _search_cache[cache_key] = {"ts": now, "results": results}
        _prune_search_cache()

    return results


def _start_index(index: int, resume_position: float = 0.0) -> bool:
    global _manual_stop_requested, _paused, _paused_position

    item = queue_manager.get_item(index)
    if item is None:
        return False

    url = item.get("webpage_url")
    if not url:
        queue_manager.mark_status(index, "error", "missing_webpage_url")
        return False

    try:
        stream_url = yt.get_stream_url(url)
        if not stream_url:
            queue_manager.mark_status(index, "error", "Keine Stream-URL ermittelbar")
            return False

        player.play_url(stream_url, start_time=resume_position)
        queue_manager.set_current_index(index, status="playing")
        _manual_stop_requested = False
        _paused = False
        _paused_position = 0.0
        return True
    except Exception as e:
        traceback.print_exc()
        queue_manager.mark_status(index, "error", str(e))
        return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []})

    try:
        results = _get_search_results(query)
        return jsonify({"results": results})
    except Exception as e:
        print("Search error:", str(e))
        traceback.print_exc()
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
    return jsonify({"status": "ok", "item": saved})


@app.route("/api/queue/clear", methods=["POST"])
def api_clear_queue():
    global _manual_stop_requested, _paused, _paused_position
    _manual_stop_requested = True
    _paused = False
    _paused_position = 0.0
    queue_manager.clear()
    player.stop()
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

    current_index = queue_manager.get_current_index()
    removed_current = index == current_index

    ok = queue_manager.remove_index(index)
    if not ok:
        return jsonify({"error": "index_out_of_range"}), 400

    if removed_current:
        player.stop()

    return jsonify({"status": "ok"})


@app.route("/api/queue/shuffle", methods=["POST"])
def api_shuffle_queue():
    ok = queue_manager.shuffle()
    return jsonify({"status": "ok" if ok else "unchanged"})


@app.route("/api/player/status", methods=["GET"])
def api_player_status():
    status = player.get_status()
    status["queue_size"] = queue_manager.size()
    status["current_index"] = queue_manager.get_current_index()
    status["current_item"] = queue_manager.get_current_item()

    if _paused:
        status["playing"] = False
        status["paused"] = True

    return jsonify(status)


@app.route("/api/player/play", methods=["POST"])
def api_player_play():
    global _manual_stop_requested, _paused, _paused_position

    if queue_manager.size() == 0:
        return jsonify({"status": "empty_queue"})

    current_index = queue_manager.get_current_index()
    if current_index < 0:
        queue_manager.set_current_index(0, status="queued")
        current_index = 0

    current_item = queue_manager.get_current_item()
    current_status = current_item.get("status") if current_item else "queued"

    if _paused:
        ok = _start_index(current_index, _paused_position)
        return jsonify({"status": "ok" if ok else "error"})

    if player.is_playing():
        return jsonify({"status": "already_playing"})

    if current_status in ("done", "error"):
        queue_manager.set_current_index(current_index, status="queued")

    _manual_stop_requested = False
    ok = _start_index(current_index, 0.0)
    return jsonify({"status": "ok" if ok else "error"})


@app.route("/api/player/toggle_pause", methods=["POST"])
def api_player_toggle_pause():
    global _manual_stop_requested, _paused, _paused_position

    current_index = queue_manager.get_current_index()
    if current_index < 0 and queue_manager.size() > 0:
        queue_manager.set_current_index(0, status="queued")
        current_index = 0

    if current_index < 0:
        return jsonify({"status": "empty_queue"})

    if player.is_playing():
        status = player.get_status()
        _paused_position = float(status.get("time_pos") or 0.0)
        _paused = True
        _manual_stop_requested = False
        queue_manager.mark_status(current_index, "paused")
        player.pause_hard()
        return jsonify({"status": "paused", "position": _paused_position})

    if _paused:
        ok = _start_index(current_index, _paused_position)
        return jsonify({"status": "resumed" if ok else "error"})

    ok = _start_index(current_index, 0.0)
    return jsonify({"status": "started" if ok else "error"})


@app.route("/api/player/stop", methods=["POST"])
def api_player_stop():
    global _manual_stop_requested, _paused, _paused_position
    _manual_stop_requested = True
    _paused = False
    _paused_position = 0.0

    current_index = queue_manager.get_current_index()
    if current_index >= 0:
        queue_manager.mark_status(current_index, "queued")

    player.stop()
    return jsonify({"status": "ok"})


@app.route("/api/player/next", methods=["POST"])
def api_player_next():
    global _manual_stop_requested, _paused, _paused_position
    _manual_stop_requested = False
    _paused = False
    _paused_position = 0.0

    next_idx = queue_manager.next_index()
    if next_idx == -1:
        player.stop()
        return jsonify({"status": "end_of_queue"})

    ok = _start_index(next_idx, 0.0)
    return jsonify({"status": "ok" if ok else "error"})


@app.route("/api/player/previous", methods=["POST"])
def api_player_previous():
    global _manual_stop_requested, _paused, _paused_position
    _manual_stop_requested = False
    _paused = False
    _paused_position = 0.0

    prev_idx = queue_manager.previous_index()
    if prev_idx == -1:
        return jsonify({"status": "start_of_queue"})

    ok = _start_index(prev_idx, 0.0)
    return jsonify({"status": "ok" if ok else "error"})


@app.route("/api/player/play_index", methods=["POST"])
def api_player_play_index():
    global _manual_stop_requested, _paused, _paused_position
    data = request.get_json(force=True, silent=True) or {}
    index = data.get("index")

    if index is None:
        return jsonify({"error": "missing_index"}), 400

    try:
        index = int(index)
    except ValueError:
        return jsonify({"error": "invalid_index"}), 400

    ok = queue_manager.set_current_index(index, status="queued")
    if not ok:
        return jsonify({"error": "index_out_of_range"}), 400

    _manual_stop_requested = False
    _paused = False
    _paused_position = 0.0

    ok = _start_index(index, 0.0)
    return jsonify({"status": "ok" if ok else "error"})


def playback_worker():
    global _manual_stop_requested, _paused, _paused_position

    while True:
        try:
            if _paused:
                time.sleep(1.0)
                continue

            if player.is_playing():
                time.sleep(1.0)
                continue

            if _manual_stop_requested:
                time.sleep(1.0)
                continue

            current_index, current_item = queue_manager.current_stream_target()

            if current_item is None:
                time.sleep(1.0)
                continue

            current_status = current_item.get("status", "queued")

            if current_status == "playing":
                queue_manager.mark_status(current_index, "done")
                next_idx = queue_manager.next_index()
                if next_idx != -1:
                    _start_index(next_idx, 0.0)
                time.sleep(1.0)
                continue

            if current_status == "queued":
                _start_index(current_index, 0.0)
                time.sleep(1.0)
                continue

            time.sleep(1.0)
        except Exception as e:
            print("Worker error:", str(e))
            traceback.print_exc()
            time.sleep(1.0)


def start_playback_worker_once():
    global _playback_worker_started
    if not _playback_worker_started:
        thread = threading.Thread(target=playback_worker, daemon=True)
        thread.start()
        _playback_worker_started = True


if __name__ == "__main__":
    start_playback_worker_once()
    app.run(host=HOST, port=PORT)
