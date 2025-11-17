function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) {
        return "-";
    }
    seconds = Math.floor(seconds);
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h > 0) {
        return (
            String(h) +
            ":" +
            String(m).padStart(2, "0") +
            ":" +
            String(s).padStart(2, "0")
        );
    }
    return String(m) + ":" + String(s).padStart(2, "0");
}

async function apiGet(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }
    return response.json();
}

async function apiPost(url, bodyObj) {
    const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(bodyObj || {})
    });
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }
    return response.json();
}

async function doSearch() {
    const input = document.getElementById("search-input");
    const q = (input.value || "").trim();
    if (!q) {
        return;
    }
    const resultsDiv = document.getElementById("search-results");
    resultsDiv.innerHTML = "<p>Suche läuft …</p>";
    try {
        const data = await apiGet("/api/search?q=" + encodeURIComponent(q));
        renderSearchResults(data.results || []);
    } catch (err) {
        resultsDiv.innerHTML = "<p>Fehler bei der Suche.</p>";
    }
}

function renderSearchResults(results) {
    const container = document.getElementById("search-results");
    if (!results.length) {
        container.innerHTML = "<p>Keine Ergebnisse.</p>";
        return;
    }
    const fragment = document.createDocumentFragment();
    results.forEach(function (item) {
        const div = document.createElement("div");
        div.className = "result-item";

        const thumb = document.createElement("div");
        thumb.className = "result-thumb";
        if (item.thumbnail) {
            const img = document.createElement("img");
            img.src = item.thumbnail;
            img.alt = "Vorschaubild";
            thumb.appendChild(img);
        }

        const info = document.createElement("div");
        info.className = "result-info";

        const title = document.createElement("p");
        title.className = "result-title";
        title.textContent = item.title || "(ohne Titel)";

        const meta = document.createElement("p");
        meta.className = "result-meta";
        var durationText = formatDuration(item.duration);
        var channel = item.channel || "";
        meta.textContent = durationText + (channel ? " – " + channel : "");

        info.appendChild(title);
        info.appendChild(meta);

        const actions = document.createElement("div");
        actions.className = "result-actions";

        const addButton = document.createElement("button");
        addButton.textContent = "Zur Warteschlange";
        addButton.addEventListener("click", function () {
            addToQueue(item);
        });

        actions.appendChild(addButton);

        div.appendChild(thumb);
        div.appendChild(info);
        div.appendChild(actions);
        fragment.appendChild(div);
    });
    container.innerHTML = "";
    container.appendChild(fragment);
}

async function addToQueue(item) {
    try {
        await apiPost("/api/queue/add", {
            id: item.id,
            title: item.title,
            channel: item.channel,
            duration: item.duration,
            webpage_url: item.webpage_url
        });
        await refreshQueue();
    } catch (err) {
        alert("Fehler beim Hinzufügen zur Warteschlange.");
    }
}

async function refreshQueue() {
    try {
        const data = await apiGet("/api/queue");
        renderQueue(data.queue || []);
    } catch (err) {
        // optional: Fehler behandeln
    }
}

function renderQueue(queue) {
    const container = document.getElementById("queue-list");
    if (!queue.length) {
        container.innerHTML = "<p>Warteschlange ist leer.</p>";
        return;
    }
    const fragment = document.createDocumentFragment();
    queue.forEach(function (item, index) {
        const div = document.createElement("div");
        div.className = "queue-item";

        const info = document.createElement("div");
        info.className = "queue-info";

        const title = document.createElement("p");
        title.className = "queue-title";
        title.textContent = item.title || "(ohne Titel)";

        const meta = document.createElement("p");
        meta.className = "queue-meta";
        var durationText = formatDuration(item.duration);
        var channel = item.channel || "";
        meta.textContent = durationText + (channel ? " – " + channel : "");
        info.appendChild(title);
        info.appendChild(meta);

        const actions = document.createElement("div");
        actions.className = "queue-actions-inline";

        const removeButton = document.createElement("button");
        removeButton.textContent = "Entfernen";
        removeButton.addEventListener("click", function () {
            removeFromQueue(index);
        });

        actions.appendChild(removeButton);

        div.appendChild(info);
        div.appendChild(actions);
        fragment.appendChild(div);
    });
    container.innerHTML = "";
    container.appendChild(fragment);
}

async function removeFromQueue(index) {
    try {
        await apiPost("/api/queue/remove", {index: index});
        await refreshQueue();
    } catch (err) {
        alert("Fehler beim Entfernen aus der Warteschlange.");
    }
}

async function refreshStatus() {
    try {
        const data = await apiGet("/api/player/status");
        const statusText = document.getElementById("status-text");
        const statusTitle = document.getElementById("status-title");
        const statusPosition = document.getElementById("status-position");

        if (data.playing) {
            if (data.paused) {
                statusText.textContent = "Pausiert";
            } else {
                statusText.textContent = "Wiedergabe läuft";
            }
        } else {
            statusText.textContent = "Leerlauf";
        }

        statusTitle.textContent = data.title || "–";

        if (data.time_pos !== null && data.duration !== null) {
            statusPosition.textContent =
                formatDuration(data.time_pos) +
                " / " +
                formatDuration(data.duration);
        } else {
            statusPosition.textContent = "–";
        }
    } catch (err) {
        // optional: Fehlerbehandlung
    }
}

async function clearQueue() {
    if (!confirm("Warteschlange wirklich leeren?")) {
        return;
    }
    try {
        await apiPost("/api/queue/clear", {});
        await refreshQueue();
    } catch (err) {
        alert("Fehler beim Leeren der Warteschlange.");
    }
}

async function playerPause() {
    try {
        await apiPost("/api/player/pause", {});
        await refreshStatus();
    } catch (err) {
        alert("Fehler beim Pausieren/Fortsetzen.");
    }
}

async function playerSkip() {
    try {
        await apiPost("/api/player/skip", {});
        await refreshStatus();
        await refreshQueue();
    } catch (err) {
        alert("Fehler beim Überspringen.");
    }
}

function setupEventHandlers() {
    const searchInput = document.getElementById("search-input");
    const searchButton = document.getElementById("search-button");
    const clearQueueButton = document.getElementById("clear-queue-button");
    const pauseButton = document.getElementById("pause-button");
    const skipButton = document.getElementById("skip-button");

    searchButton.addEventListener("click", doSearch);
    searchInput.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
            doSearch();
        }
    });

    clearQueueButton.addEventListener("click", clearQueue);
    pauseButton.addEventListener("click", playerPause);
    skipButton.addEventListener("click", playerSkip);
}

document.addEventListener("DOMContentLoaded", function () {
    setupEventHandlers();
    refreshQueue();
    refreshStatus();
    setInterval(function () {
        refreshStatus();
        refreshQueue();
    }, 5000);
});
