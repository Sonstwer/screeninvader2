import threading
import time
import traceback

from flask import Flask, request, jsonify, render_template

from config import HOST, PORT, QUEUE_FILE
from queue_manager import QueueManager
from player import MPVPlayer
from yt_wrapper import YTDLPWrapper

app = Flask(__name__)

queue_manager = QueueManager(QUEUE_FILE)
player = MPVPlayer()
yt = YTDLPWrapper()

_playback_worker_started = False
_manual_stop_requested = False
_last_started_index = -1

# Such-Cache:
# - Key: normalisierter Suchstring
# - Value: {"timestamp": <unix>, "results": [...]}
_search_cache = {}
_search_cache_lock = threading.Lock()
_search_cache_ttl_seconds = 180
_search_cache_max_entries = 50


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

        age = now - entry.get("timestamp", 0)
        if age > _search_cache_ttl_seconds:
            _search_cache.pop(key, None)
            return None

        return entry.get("results")


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

        # Alte Einträge entfernen
        expired_keys = []
        for k, entry in _search_cache.items():
            if (now - entry.get("timestamp", 0)) > _search_cache_ttl_seconds:
                expired_keys.append(k)

        for k in expired_keys:
            _search_cache.pop(k, None)

        # Wenn zu groß: älteste Einträge entfernen
        if len(_search_cache) > _search_cache_max_entries:
            sorted_items = sorted(
                _search_cache.items(),
                key=lambda item: item[1].get("timestamp", 0)
            )
            while len(sorted_items) > _search_cache_max_entries:
                oldest_key, _ = sorted_items.pop(0)
                _search_cache.pop(oldest_key, None)


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
            return jsonify({"results": cached, "cached": True})

        results = yt.search(query)
        _set_cached_search(query, results)
        return jsonify({"results": results, "cached": False})
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
    global _manual_stop_requested, _last_started_index
    _manual_stop_requested = True
    _last_started_index = -1
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

    ok = queue_manager.remove_index(index)
    if not ok:
        return jsonify({"error": "index_out_of_range"}), 400

    return jsonify({"status": "ok"})


@app.route("/api/player/status", methods=["GET"])
def api_player_status():
    status = player.get_status()
    status["queue_size"] = queue_manager.size()
    status["current_index"] = queue_manager.get_current_index()
    status["current_item"] = queue_manager.get_current_item()
    return jsonify(status)


@app.route("/api/player/play", methods=["POST"])
def api_player_play():
    global _manual_stop_requested
    _manual_stop_requested = False

    current = queue_manager.get_current_item()
    if current is None and queue_manager.size() > 0:
        queue_manager.set_current_index(0, playing=False)

    return jsonify({"status": "ok"})


@app.route("/api/player/pause", methods=["POST"])
def api_player_pause():
    """
    Stabilerer Workaround für Streaming-Quellen:
    statt mpv-internem Pause-State stoppen wir das Playback
    und markieren den aktuellen Eintrag als paused.
    """
    global _manual_stop_requested, _last_started_index

    try:
        _manual_stop_requested = True
        _last_started_index = -1
        player.stop()
        queue_manager.mark_current_paused()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": "pause_failed", "details": str(e)}), 500


@app.route("/api/player/resume", methods=["POST"])
def api_player_resume():
    global _manual_stop_requested, _last_started_index

    try:
        _manual_stop_requested = False
        _last_started_index = -1
        player.set_pause(False)
        current_index = queue_manager.get_current_index()
        if current_index >= 0:
            queue_manager.set_current_index(current_index, playing=False)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": "resume_failed", "details": str(e)}), 500


@app.route("/api/player/toggle", methods=["POST"])
def api_player_toggle():
    """
    Ein einziger Button:
    - läuft etwas -> pausieren (Stop + Status paused)
    - sonst -> resumieren / starten
    """
    try:
        status = player.get_status()
        if status.get("playing"):
            return api_player_pause()
        return api_player_resume()
    except Exception as e:
        return jsonify({"error": "toggle_failed", "details": str(e)}), 500


@app.route("/api/player/stop", methods=["POST"])
def api_player_stop():
    global _manual_stop_requested, _last_started_index
    _manual_stop_requested = True
    _last_started_index = -1
    try:
        player.stop()
        current_index = queue_manager.get_current_index()
        if current_index >= 0:
            queue_manager.set_current_index(current_index, playing=False)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": "stop_failed", "details": str(e)}), 500


@app.route("/api/player/next", methods=["POST"])
def api_player_next():
    global _manual_stop_requested, _last_started_index
    _manual_stop_requested = False
    _last_started_index = -1

    next_idx = queue_manager.next_index()
    if next_idx == -1:
        player.stop()
        return jsonify({"status": "end_of_queue"})

    player.stop()
    return jsonify({"status": "ok", "current_index": next_idx})


@app.route("/api/player/previous", methods=["POST"])
def api_player_previous():
    global _manual_stop_requested, _last_started_index
    _manual_stop_requested = False
    _last_started_index = -1

    prev_idx = queue_manager.previous_index()
    if prev_idx == -1:
        return jsonify({"status": "start_of_queue"})

    player.stop()
    return jsonify({"status": "ok", "current_index": prev_idx})


@app.route("/api/player/play_index", methods=["POST"])
def api_player_play_index():
    global _manual_stop_requested, _last_started_index
    data = request.get_json(force=True, silent=True) or {}
    index = data.get("index")

    if index is None:
        return jsonify({"error": "missing_index"}), 400

    try:
        index = int(index)
    except ValueError:
        return jsonify({"error": "invalid_index"}), 400

    ok = queue_manager.set_current_index(index, playing=False)
    if not ok:
        return jsonify({"error": "index_out_of_range"}), 400

    _manual_stop_requested = False
    _last_started_index = -1
    player.stop()
    return jsonify({"status": "ok", "current_index": index})


@app.route("/api/player/shuffle", methods=["POST"])
def api_player_shuffle():
    data = queue_manager.get_queue()
    current_index = queue_manager.get_current_index()

    if not data or len(data) < 2:
        return jsonify({"status": "ok", "message": "nothing_to_shuffle"})

    import random

    current_item = None
    if 0 <= current_index < len(data):
        current_item = data[current_index]

    remaining = data[:]
    if current_item is not None:
        remaining.pop(current_index)

    random.shuffle(remaining)

    if current_item is not None:
        new_queue = [current_item] + remaining
        new_current_index = 0
    else:
        new_queue = remaining
        new_current_index = 0 if new_queue else -1

    # Direkt in queue.json schreiben über QueueManager-Interna
    queue_manager._queue = new_queue
    queue_manager._current_index = new_current_index
    queue_manager._save()

    return jsonify({"status": "ok"})


def playback_worker():
    global _manual_stop_requested, _last_started_index

    while True:
        try:
            if player.is_playing():
                time.sleep(1.0)
                continue

            current_index, current_item = queue_manager.current_stream_target()

            if current_item is None:
                time.sleep(1.0)
                continue

            if _manual_stop_requested:
                time.sleep(1.0)
                continue

            if current_index == _last_started_index and current_item.get("status") in ("done", "error"):
                time.sleep(1.0)
                continue

            url = current_item.get("webpage_url")
            if not url:
                queue_manager.mark_current_error("missing_webpage_url")
                time.sleep(1.0)
                continue

            try:
                stream_url = yt.get_stream_url(url)
                if not stream_url:
                    queue_manager.mark_current_error("Keine Stream-URL ermittelbar")
                    time.sleep(1.0)
                    continue

                player.play_url(stream_url)
                queue_manager.mark_current_playing()
                _last_started_index = current_index

                time.sleep(2.0)

                if not player.is_playing():
                    queue_manager.mark_current_error("Playback start failed")
            except Exception as e:
                print("Playback error:", str(e))
                traceback.print_exc()
                queue_manager.mark_current_error(str(e))

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