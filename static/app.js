let searchController = null;
let latestSearchToken = 0;
let currentSearchToken = 0;
let isSearchRunning = false;

async function apiGet(url, options) {
  const response = await fetch(url, options || {});
  return await response.json();
}

async function apiPost(url, data) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {})
  });
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
    return "";
  }

  const s = Number(seconds);
  if (Number.isNaN(s)) {
    return "";
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
  const input = document.getElementById("search-input");
  const results = document.getElementById("search-results");

  isSearchRunning = running;
  button.disabled = running;

  if (running) {
    button.textContent = "Suche läuft ...";
    if (queryText) {
      results.innerHTML = `<div class="small">Suche nach: <strong>${escapeHtml(queryText)}</strong></div>`;
    }
  } else {
    button.disabled = false;
    button.textContent = "Suchen";
  }

  input.disabled = false;
}

function renderSearchResults(results) {
  const target = document.getElementById("search-results");

  if (!results.length) {
    target.innerHTML = "<div class='small'>Keine Treffer.</div>";
    return;
  }

  target.innerHTML = results.map((item) => {
    const title = escapeHtml(item.title || "Unbekannt");
    const channel = escapeHtml(item.channel || "");
    const duration = formatDuration(item.duration);

    return `
      <div class="list-item">
        <div class="title">${title}</div>
        <div class="meta">${channel} ${duration ? "• " + duration : ""}</div>
        <div class="controls">
          <button onclick='addToQueue(${JSON.stringify(item)})'>Zur Playlist hinzufügen</button>
        </div>
      </div>
    `;
  }).join("");
}

async function doSearch() {
  const input = document.getElementById("search-input");
  const target = document.getElementById("search-results");
  const query = input.value.trim();

  if (!query) {
    target.innerHTML = "";
    return;
  }

  // Frühere Suche abbrechen
  if (searchController) {
    searchController.abort();
  }

  searchController = new AbortController();
  latestSearchToken += 1;
  const myToken = latestSearchToken;
  currentSearchToken = myToken;

  setSearchUiState(true, query);

  try {
    const data = await apiGet(
      `/api/search?q=${encodeURIComponent(query)}`,
      { signal: searchController.signal }
    );

    // Wenn inzwischen schon eine neuere Suche gestartet wurde:
    if (myToken !== latestSearchToken) {
      return;
    }

    const results = data.results || [];
    renderSearchResults(results);
  } catch (err) {
    // Abgebrochene Suche still ignorieren
    if (err && err.name === "AbortError") {
      return;
    }

    // Auch hier nur reagieren, wenn das noch die aktuellste Suche ist
    if (myToken !== latestSearchToken) {
      return;
    }

    target.innerHTML = "<div class='status status-error'>Fehler bei der Suche.</div>";
  } finally {
    if (myToken === latestSearchToken) {
      setSearchUiState(false, "");
    }
  }
}

async function addToQueue(item) {
  await apiPost("/api/queue/add", item);
  await refreshQueue();
}

async function removeFromQueue(index) {
  await apiPost("/api/queue/remove", { index: index });
  await refreshQueue();
  await refreshPlayerStatus();
}

async function playIndex(index) {
  await apiPost("/api/player/play_index", { index: index });
  await refreshQueue();
  await refreshPlayerStatus();
}

async function playerPlay() {
  await apiPost("/api/player/play", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function playerPause() {
  await apiPost("/api/player/pause", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function playerResume() {
  await apiPost("/api/player/resume", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function playerStop() {
  await apiPost("/api/player/stop", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function playerNext() {
  await apiPost("/api/player/next", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function playerPrevious() {
  await apiPost("/api/player/previous", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function clearQueue() {
  await apiPost("/api/queue/clear", {});
  await refreshPlayerStatus();
  await refreshQueue();
}

async function refreshQueue() {
  const target = document.getElementById("queue-list");
  const data = await apiGet("/api/queue");
  const queue = data.queue || [];
  const currentIndex = data.current_index;

  if (!queue.length) {
    target.innerHTML = "<div class='small'>Playlist ist leer.</div>";
    return;
  }

  target.innerHTML = queue.map((item, index) => {
    const title = escapeHtml(item.title || "Unbekannt");
    const channel = escapeHtml(item.channel || "");
    const duration = formatDuration(item.duration);
    const status = escapeHtml(item.status || "queued");
    const isCurrent = index === currentIndex;
    const errorText = item.error ? `<div class="small status-error">${escapeHtml(item.error)}</div>` : "";

    return `
      <div class="list-item">
        <div class="title">${isCurrent ? "▶ " : ""}${title}</div>
        <div class="meta">${channel} ${duration ? "• " + duration : ""}</div>
        <div class="status status-${status}">Status: ${status}</div>
        ${errorText}
        <div class="controls">
          <button onclick="playIndex(${index})">Abspielen</button>
          <button onclick="removeFromQueue(${index})">Entfernen</button>
        </div>
      </div>
    `;
  }).join("");
}

async function refreshPlayerStatus() {
  const target = document.getElementById("player-status");
  const data = await apiGet("/api/player/status");

  const currentItem = data.current_item;
  const title = currentItem && currentItem.title ? escapeHtml(currentItem.title) : "Kein Titel";
  const state = data.playing ? "Wiedergabe läuft" : (data.paused ? "Pausiert" : "Leerlauf");

  let html = `<div><strong>Status:</strong> ${state}</div>`;

  if (currentItem) {
    html += `<div><strong>Titel:</strong> ${title}</div>`;
    if (currentItem.channel) {
      html += `<div><strong>Kanal:</strong> ${escapeHtml(currentItem.channel)}</div>`;
    }
  }

  if (data.time_pos !== null && data.duration !== null) {
    html += `<div><strong>Fortschritt:</strong> ${formatDuration(data.time_pos)} / ${formatDuration(data.duration)}</div>`;
  }

  target.innerHTML = html;
}

function bindUi() {
  document.getElementById("search-button").addEventListener("click", doSearch);
  document.getElementById("search-input").addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      doSearch();
    }
  });

  document.getElementById("btn-play").addEventListener("click", playerPlay);
  document.getElementById("btn-pause").addEventListener("click", playerPause);
  document.getElementById("btn-resume").addEventListener("click", playerResume);
  document.getElementById("btn-stop").addEventListener("click", playerStop);
  document.getElementById("btn-prev").addEventListener("click", playerPrevious);
  document.getElementById("btn-next").addEventListener("click", playerNext);
  document.getElementById("btn-clear").addEventListener("click", clearQueue);
}

async function refreshAll() {
  await refreshPlayerStatus();
  await refreshQueue();
}

bindUi();
refreshAll();
setInterval(refreshAll, 3000);