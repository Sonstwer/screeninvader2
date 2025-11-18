#!/bin/bash
#
# ScreenInvader 2.0 – Auto-Update Script
# - Aktualisiert Git-Repository
# - aktualisiert yt-dlp im venv (falls vorhanden)
# - lädt systemd neu und startet den Dienst
# - sichert ein Log-Snapshot
#

SERVICE="screeninvader2.service"
APP_DIR="/opt/screeninvader2"
USER="screeninvader"
LOG_DIR="/var/log/screeninvader2"

echo "=== ScreenInvader 2.0 – Auto-Update ==="

# Muss als root laufen
if [[ $(id -u) -ne 0 ]]; then
    echo "Dieses Skript muss mit sudo ausgeführt werden."
    exit 1
fi

# Log-Verzeichnis anlegen
mkdir -p "$LOG_DIR"

# Zeitstempel für Log-Dateien
TS=$(date +"%Y%m%d-%H%M%S")

echo "0) Erzeuge Log-Snapshot vor dem Update..."
journalctl -u "$SERVICE" -e > "$LOG_DIR/${SERVICE}-${TS}-before.log" 2>/dev/null || true

echo "1) Stoppe Dienst..."
systemctl stop "$SERVICE" || true

echo "2) Aktualisiere Repository als Benutzer $USER..."
sudo -u "$USER" -H bash -c "
    set -e
    cd '$APP_DIR'
    git reset --hard HEAD
    git pull --rebase
" || {
    echo "Fehler beim Git-Pull – Abbruch."
    exit 1
}

echo "3) Aktualisiere yt-dlp im venv (falls vorhanden)..."
if [[ -x "$APP_DIR/.venv/bin/pip" ]]; then
    sudo -u "$USER" -H bash -c "
        cd '$APP_DIR'
        . .venv/bin/activate
        pip install --upgrade yt-dlp
        deactivate
    " || {
        echo "Warnung: Aktualisierung von yt-dlp im venv ist fehlgeschlagen."
    }
else
    echo "Hinweis: Kein venv unter $APP_DIR/.venv gefunden – überspringe yt-dlp-Update."
fi

echo "4) Lade systemd neu..."
systemctl daemon-reload

echo "5) Starte Dienst neu..."
systemctl start "$SERVICE"

echo "6) Prüfe Dienststatus..."
if systemctl is-active --quiet "$SERVICE"; then
    echo "Dienst $SERVICE läuft."
else
    echo "FEHLER: Dienst $SERVICE ist nicht aktiv."
    echo "Letzte Log-Zeilen:"
    journalctl -u "$SERVICE" -e | tail -n 40
    exit 1
fi

echo "7) Erzeuge Log-Snapshot nach dem Update..."
journalctl -u "$SERVICE" -e > "$LOG_DIR/${SERVICE}-${TS}-after.log" 2>/dev/null || true

echo "=== Update abgeschlossen ==="
