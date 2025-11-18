import threading
import time

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []})
    try:
        results = yt.search(query)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": "search_failed", "details": str(e)}), 500


@app.route("/api/queue", methods=["GET"])
def api_get_queue():
    return jsonify({"queue": queue_manager.get_queue()})


@app.route("/api/queue/add", methods=["POST"])
def api_add_queue():
    data = request.get_json(force=True, silent=True) or {}
    video_id = data.get("id")
    title = data.get("title")
    channel = data.get("channel")
    duration = data.get("duration")
    webpage_url = data.get("webpage_url")

    if not webpage_url:
        return jsonify({"error": "missing_webpage_url"}), 400

    item = {
        "id": video_id,
        "title": title,
        "channel": channel,
        "duration": duration,
        "webpage_url": webpage_url,
    }
    queue_manager.add_item(item)
    return jsonify({"status": "ok"})


@app.route("/api/queue/clear", methods=["POST"])
def api_clear_queue():
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
    success = queue_manager.remove_index(index)
    if not success:
        return jsonify({"error": "index_out_of_range"}), 400
    return jsonify({"status": "ok"})


@app.route("/api/player/status", methods=["GET"])
def api_player_status():
    status = player.get_status()
    status["queue_size"] = queue_manager.size()
    return jsonify(status)


@app.route("/api/player/pause", methods=["POST"])
def api_player_pause():
    player.pause_toggle()
    return jsonify({"status": "ok"})


@app.route("/api/player/skip", methods=["POST"])
def api_player_skip():
    player.stop()
    return jsonify({"status": "ok"})


def playback_worker():
    """Hintergrund-Thread für Auto-Play der Queue."""
    while True:
        try:
            if not queue_manager.is_empty():
                if not player.is_playing():
                    next_item = queue_manager.pop_next()
                    if next_item is not None:
                        url = next_item.get("webpage_url")
                        if url:
                            try:
                                stream_url = yt.get_stream_url(url)
                                if stream_url:
                                    player.play_url(stream_url)
                            except Exception:
                                pass
            time.sleep(2.0)
        except Exception:
            time.sleep(2.0)


def start_playback_worker_once():
    global _playback_worker_started
    if not _playback_worker_started:
        thread = threading.Thread(target=playback_worker, daemon=True)
        thread.start()
        _playback_worker_started = True


@app.before_serving
def init_background_worker():
    start_playback_worker_once()


if __name__ == "__main__":
    start_playback_worker_once()
    app.run(host=HOST, port=PORT)
