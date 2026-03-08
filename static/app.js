let searchController = null;
let latestSearchToken = 0;

async function apiGet(url, options) {
    const response = await fetch(url, options || {});
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }
    return await response.json();
}

async function apiPost(url, data) {
    const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data || {})
    });
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }
    return await response.json();
}

function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) {
        return "–";
    }
    const s = Math.floor(Number(seconds));
    if (Number.isNaN(s)) {
        return "–";
    }
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;

    if (h > 0) {
        return String(h) + ":" + String(m).padStart(2, "0") + ":" + String(sec).padStart(2, "0");
    }
    return String(m) + ":" + String(sec).padStart(2, "0");
}

function formatTimestamp(ts) {
    if (!ts) {
        return "–";
    }
    const d = new Date(ts * 1000);
    return d.toLocaleString();
}

function setSearchState(running, queryText) {
    const button = document.getElementById("search-button");
    const meta = document.getElementById("search-meta");

    button.disabled = running;
    button.textContent = running ? "Suche läuft ..." : "Suchen";

    if (running && queryText) {
        meta.textContent = "Suche nach: " + queryText;
    } else {
        meta.textContent = "";
    }
}

async function doSearch() {
    const input = document.getElementById("search-input");
    const target = document.getElementById("search-results");
    const query = (input.value || "").trim();

    if (!query) {
        target.innerHTML = "";
        return;
    }

    if (searchController) {
        searchController.abort();
    }

    searchController = new AbortController();
    latestSearchToken += 1;
    const myToken = latestSearchToken;

    setSearchState(true, query);

    try {
        const data = await apiGet(
            "/api/search?q=" + encodeURIComponent(query),
            {signal: searchController.signal}
        );

        if (myToken !== latestSearchToken) {
            return;
        }

        renderSearchResults(data.results || []);
        const meta = document.getElementById("search-meta");
        meta.textContent = data.cached ? "Suchergebnis aus Cache" : "";
    } catch (err) {
        if (err.name === "AbortError") {
            return;
        }
        if (myToken !== latestSearchToken) {
            return;
        }
        target.innerHTML = "<div class='error-text'>Fehler bei der Suche.</div>";
    } finally {
        if (myToken === latestSearchToken) {
            setSearchState(false, "");
        }
    }
}

function createMiniButton(label, className, onClick) {
    const button = document.createElement("button");
    button.className = className || "mini-btn";
    button.textContent = label;
    button.addEventListener("click", onClick);
    return button;
}

function renderSearchResults(results) {
    const target = document.getElementById("search-results");
    target.innerHTML = "";

    if (!results.length) {
        target.innerHTML = "<div class='card'>Keine Treffer.</div>";
        return;
    }

    const fragment = document.createDocumentFragment();

    results.forEach(function (item) {
        const card = document.createElement("div");
        card.className = "card";

        const title = document.createElement("div");
        title.className = "card-title";
        title.textContent = item.title || "Unbekannt";

        const meta = document.createElement("div");
        meta.className = "card-meta";
        const parts = [];
        if (item.channel) {
            parts.push(item.channel);
        }
        if (item.duration !== null && item.duration !== undefined) {
            parts.push(formatDuration(item.duration));
        }
        meta.textContent = parts.join(" • ");

        const actions = document.createElement("div");
        actions.className = "card-actions";

        const addButton = createMiniButton("Zur Playlist", "mini-btn primary", async function () {
            await addToQueue(item);
        });

        actions.appendChild(addButton);
        card.appendChild(title);
        card.appendChild(meta);
        card.appendChild(actions);
        fragment.appendChild(card);
    });

    target.appendChild(fragment);
}

async function addToQueue(item) {
    await apiPost("/api/queue/add", {
        id: item.id,
        title: item.title,
        channel: item.channel,
        duration: item.duration,
        webpage_url: item.webpage_url
    });
    await refreshQueue();
    await refreshDebug();
}

async function removeFromQueue(index) {
    await apiPost("/api/queue/remove", {index: index});
    await refreshQueue();
    await refreshPlayerStatus();
    await refreshDebug();
}

async function playIndex(index) {
    await apiPost("/api/player/play_index", {index: index});
    await refreshAll();
}

async function togglePlayPause() {
    await apiPost("/api/player/toggle", {});
    await refreshAll();
}

async function playerStop() {
    await apiPost("/api/player/stop", {});
    await refreshAll();
}

async function playerNext() {
    await apiPost("/api/player/next", {});
    await refreshAll();
}

async function playerPrevious() {
    await apiPost("/api/player/previous", {});
    await refreshAll();
}

async function clearQueue() {
    await apiPost("/api/queue/clear", {});
    await refreshAll();
}

async function shuffleQueue() {
    await apiPost("/api/player/shuffle", {});
    await refreshAll();
}

async function refreshQueue() {
    const target = document.getElementById("queue-list");
    const data = await apiGet("/api/queue");
    const queue = data.queue || [];
    const currentIndex = data.current_index;

    target.innerHTML = "";

    if (!queue.length) {
        target.innerHTML = "<div class='card'>Playlist ist leer.</div>";
        return;
    }

    const fragment = document.createDocumentFragment();

    queue.forEach(function (item, index) {
        const card = document.createElement("div");
        card.className = "card";
        if (index === currentIndex) {
            card.classList.add("is-current");
        }

        const title = document.createElement("div");
        title.className = "card-title";
        title.textContent = item.title || "Unbekannt";

        const meta = document.createElement("div");
        meta.className = "card-meta";
        const parts = [];
        if (item.channel) {
            parts.push(item.channel);
        }
        if (item.duration !== null && item.duration !== undefined) {
            parts.push(formatDuration(item.duration));
        }
        meta.textContent = parts.join(" • ");

        const status = document.createElement("div");
        status.className = "card-status status-" + (item.status || "queued");
        status.textContent = "Status: " + (item.status || "queued");

        const actions = document.createElement("div");
        actions.className = "card-actions";

        const playButton = createMiniButton("Abspielen", "mini-btn primary", async function () {
            await playIndex(index);
        });

        const removeButton = createMiniButton("Entfernen", "mini-btn", async function () {
            await removeFromQueue(index);
        });

        actions.appendChild(playButton);
        actions.appendChild(removeButton);

        card.appendChild(title);
        card.appendChild(meta);
        card.appendChild(status);

        if (item.error) {
            const error = document.createElement("div");
            error.className = "error-text";
            error.textContent = item.error;
            card.appendChild(error);
        }

        card.appendChild(actions);
        fragment.appendChild(card);
    });

    target.appendChild(fragment);
}

async function refreshPlayerStatus() {
    const data = await apiGet("/api/player/status");

    const statusText = document.getElementById("status-text");
    const statusTitle = document.getElementById("status-title");
    const statusPosition = document.getElementById("status-position");
    const toggleButtonLabel = document.getElementById("toggle-button-label");

    const currentItem = data.current_item;
    const queueStatus = currentItem ? (currentItem.status || "queued") : "idle";

    if (queueStatus === "paused") {
        statusText.textContent = "Pausiert";
        toggleButtonLabel.textContent = "Resume";
    } else if (queueStatus === "playing") {
        statusText.textContent = "Wiedergabe läuft";
        toggleButtonLabel.textContent = "Pause";
    } else {
        statusText.textContent = "Leerlauf";
        toggleButtonLabel.textContent = "Play";
    }

    statusTitle.textContent = currentItem && currentItem.title ? currentItem.title : "–";

    if (data.time_pos !== null && data.duration !== null) {
        statusPosition.textContent = formatDuration(data.time_pos) + " / " + formatDuration(data.duration);
    } else if (currentItem && currentItem.duration !== null && currentItem.duration !== undefined) {
        statusPosition.textContent = "0:00 / " + formatDuration(currentItem.duration);
    } else {
        statusPosition.textContent = "–";
    }
}

async function refreshDebug() {
    const data = await apiGet("/api/debug");

    document.getElementById("debug-last-event").textContent =
        (data.last_debug_event ? data.last_debug_event.message : "–") + " @ " +
        (data.last_debug_event ? formatTimestamp(data.last_debug_event.timestamp) : "–");

    document.getElementById("debug-last-error").textContent = data.last_playback_error || "–";
    document.getElementById("debug-manual-stop").textContent = String(data.manual_stop_requested);
    document.getElementById("debug-confirmed").textContent = String(data.last_confirmed_playback);

    document.getElementById("debug-json").textContent = JSON.stringify(data, null, 2);
}

async function refreshAll() {
    await refreshPlayerStatus();
    await refreshQueue();
    await refreshDebug();
}

function bindUi() {
    document.getElementById("search-button").addEventListener("click", doSearch);
    document.getElementById("search-input").addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            doSearch();
        }
    });

    document.getElementById("toggle-button").addEventListener("click", togglePlayPause);
    document.getElementById("stop-button").addEventListener("click", playerStop);
    document.getElementById("prev-button").addEventListener("click", playerPrevious);
    document.getElementById("next-button").addEventListener("click", playerNext);
    document.getElementById("shuffle-button").addEventListener("click", shuffleQueue);
    document.getElementById("clear-button").addEventListener("click", clearQueue);
    document.getElementById("debug-refresh-button").addEventListener("click", refreshDebug);
}

bindUi();
refreshAll();
setInterval(refreshAll, 3000);