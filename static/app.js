let searchController = null;
let latestSearchToken = 0;
let currentQueueState = { queue: [], current_index: -1, current_item: null };
let currentPlayerState = { playing: false, paused: false, current_item: null };


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

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) {
        return "–";
    }
    const s = Number(seconds);
    if (Number.isNaN(s)) {
        return "–";
    }
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = Math.floor(s % 60);

    if (h > 0) {
        return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    }
    return `${m}:${String(sec).padStart(2, "0")}`;
}

function setSearchUiState(running, queryText) {
    const button = document.getElementById("search-button");
    const meta = document.getElementById("search-meta");

    button.disabled = running;
    button.querySelector(".btn-label").textContent = running ? "Suche läuft …" : "Suchen";

    if (running && queryText) {
        meta.innerHTML = `Suche nach: <strong>${escapeHtml(queryText)}</strong>`;
    } else if (!running) {
        meta.textContent = "";
    }
}

function statusChip(status) {
    const safe = escapeHtml(status || "queued");
    return `<span class="status-chip status-${safe}">${safe}</span>`;
}

function renderSearchResults(results) {
    const container = document.getElementById("search-results");

    if (!results.length) {
        container.innerHTML = `<div class="empty-state">Keine Treffer.</div>`;
        return;
    }

    container.innerHTML = results.map((item) => {
        const title = escapeHtml(item.title || "(ohne Titel)");
        const channel = escapeHtml(item.channel || "");
        const duration = formatDuration(item.duration);
        const thumb = item.thumbnail
            ? `<img src="${escapeHtml(item.thumbnail)}" alt="">`
            : "";

        return `
            <div class="result-item">
                <div class="result-thumb">${thumb}</div>
                <div class="result-info">
                    <p class="result-title">${title}</p>
                    <p class="result-meta">${duration}${channel ? " · " + channel : ""}</p>
                </div>
                <div class="result-actions">
                    <button class="result-action-button" data-add='${JSON.stringify(item).replaceAll("'", "&apos;")}'>Zur Playlist</button>
                </div>
            </div>
        `;
    }).join("");

    container.querySelectorAll("[data-add]").forEach((button) => {
        button.addEventListener("click", async function () {
            const raw = this.getAttribute("data-add").replaceAll("&apos;", "'");
            await addToQueue(JSON.parse(raw));
        });
    });
}

async function doSearch() {
    const input = document.getElementById("search-input");
    const resultsDiv = document.getElementById("search-results");
    const query = (input.value || "").trim();

    if (!query) {
        resultsDiv.innerHTML = "";
        return;
    }

    if (searchController) {
        searchController.abort();
    }

    searchController = new AbortController();
    latestSearchToken += 1;
    const myToken = latestSearchToken;

    setSearchUiState(true, query);

    try {
        const data = await apiGet("/api/search?q=" + encodeURIComponent(query), {
            signal: searchController.signal
        });

        if (myToken !== latestSearchToken) {
            return;
        }

        renderSearchResults(data.results || []);
    } catch (err) {
        if (err && err.name === "AbortError") {
            return;
        }
        if (myToken !== latestSearchToken) {
            return;
        }
        resultsDiv.innerHTML = `<div class="empty-state">Fehler bei der Suche.</div>`;
    } finally {
        if (myToken === latestSearchToken) {
            setSearchUiState(false, "");
        }
    }
}

async function addToQueue(item) {
    await apiPost("/api/queue/add", {
        id: item.id,
        title: item.title,
        channel: item.channel,
        duration: item.duration,
        webpage_url: item.webpage_url
    });
    await refreshAll();
}

async function removeFromQueue(index) {
    await apiPost("/api/queue/remove", {index: index});
    await refreshAll();
}

async function playIndex(index) {
    await apiPost("/api/player/play_index", {index: index});
    await refreshAll();
}

async function togglePlayPause() {
    await apiPost("/api/player/toggle_pause", {});
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
    if (!confirm("Playlist wirklich leeren?")) {
        return;
    }
    await apiPost("/api/queue/clear", {});
    await refreshAll();
}

async function shuffleQueue() {
    await apiPost("/api/queue/shuffle", {});
    await refreshAll();
}

function renderQueue(queue, currentIndex) {
    const container = document.getElementById("queue-list");
    const meta = document.getElementById("queue-meta");

    meta.textContent = queue.length ? `${queue.length} Einträge` : "";

    if (!queue.length) {
        container.innerHTML = `<div class="empty-state">Playlist ist leer.</div>`;
        return;
    }

    container.innerHTML = queue.map((item, index) => {
        const title = escapeHtml(item.title || "(ohne Titel)");
        const channel = escapeHtml(item.channel || "");
        const duration = formatDuration(item.duration);
        const status = item.status || "queued";
        const isCurrent = index === currentIndex;
        const error = item.error ? `<div class="error-text">${escapeHtml(item.error)}</div>` : "";

        return `
            <div class="queue-item ${isCurrent ? "current" : ""}">
                <div class="queue-info">
                    <p class="queue-title">${isCurrent ? "▶ " : ""}${title}</p>
                    <p class="queue-meta">${duration}${channel ? " · " + channel : ""}</p>
                    <div>${statusChip(status)}</div>
                    ${error}
                </div>
                <div class="queue-actions-inline">
                    <button class="queue-action-button" data-play-index="${index}">Abspielen</button>
                    <button class="queue-action-button" data-remove-index="${index}">Entfernen</button>
                </div>
            </div>
        `;
    }).join("");

    container.querySelectorAll("[data-play-index]").forEach((button) => {
        button.addEventListener("click", async function () {
            const index = parseInt(this.getAttribute("data-play-index"), 10);
            await playIndex(index);
        });
    });

    container.querySelectorAll("[data-remove-index]").forEach((button) => {
        button.addEventListener("click", async function () {
            const index = parseInt(this.getAttribute("data-remove-index"), 10);
            await removeFromQueue(index);
        });
    });
}

function updateToggleButton() {
    const label = document.getElementById("toggle-play-label");
    const icon = document.getElementById("toggle-play-icon");

    if (currentPlayerState.paused) {
        label.textContent = "Weiter";
        icon.innerHTML = `<path d="M8 5v14l11-7z"></path>`;
    } else if (currentPlayerState.playing) {
        label.textContent = "Pause";
        icon.innerHTML = `<rect x="7" y="5" width="4" height="14"></rect><rect x="13" y="5" width="4" height="14"></rect>`;
    } else {
        label.textContent = "Play";
        icon.innerHTML = `<path d="M8 5v14l11-7z"></path>`;
    }
}

async function refreshQueue() {
    const data = await apiGet("/api/queue");
    currentQueueState = data;
    renderQueue(data.queue || [], data.current_index);
}

async function refreshStatus() {
    const data = await apiGet("/api/player/status");
    currentPlayerState = data;

    const statusText = document.getElementById("status-text");
    const statusTitle = document.getElementById("status-title");
    const statusPosition = document.getElementById("status-position");

    const currentItem = data.current_item;
    let state = "Leerlauf";
    if (data.paused) {
        state = "Pausiert";
    } else if (data.playing) {
        state = "Wiedergabe läuft";
    }

    statusText.textContent = state;
    statusTitle.textContent = currentItem && currentItem.title ? currentItem.title : "–";

    if (data.time_pos !== null && data.duration !== null) {
        statusPosition.textContent = `${formatDuration(data.time_pos)} / ${formatDuration(data.duration)}`;
    } else {
        statusPosition.textContent = "–";
    }

    updateToggleButton();
}

async function refreshAll() {
    try {
        await refreshStatus();
        await refreshQueue();
    } catch (err) {
        // absichtlich still
    }
}

function setupEventHandlers() {
    document.getElementById("search-button").addEventListener("click", doSearch);
    document.getElementById("search-input").addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            doSearch();
        }
    });

    document.getElementById("toggle-play-button").addEventListener("click", togglePlayPause);
    document.getElementById("stop-button").addEventListener("click", playerStop);
    document.getElementById("prev-button").addEventListener("click", playerPrevious);
    document.getElementById("next-button").addEventListener("click", playerNext);
    document.getElementById("shuffle-button").addEventListener("click", shuffleQueue);
    document.getElementById("clear-queue-button").addEventListener("click", clearQueue);
}

setupEventHandlers();
refreshAll();
setInterval(refreshAll, 3000);
