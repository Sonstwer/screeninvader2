# ScreenInvader 2.0 (Prototyp, frühe Beta)

Ein schlanker YouTube-Jukebox-Server für Banana Pi & andere Linux-Systeme.

**Wichtiger Hinweis:** Aktueller Stand ist eine **frühe, ungetestete Beta**.
Es gibt keine Garantie, dass ScreenInvader 2.0 auf einem bestimmten
Armbian-/Banana-Pi-Setup stabil läuft.

## License
Dieses Projekt steht unter der **CC0 1.0 Public Domain Dedication**.
Du kannst den Code verwenden, kopieren, verändern und weiterverteilen,
auch für kommerzielle Zwecke, ohne Einschränkungen.

## Funktionen (aktueller Stand)
- Web-Oberfläche im lokalen Netzwerk
- YouTube-Suche über yt-dlp
- Warteschlange (Queue) mit persistentem Speicher
- Wiedergabe über mpv (HDMI / Audio-Ausgang des Boards)
- Steuerung: Pause/Fortsetzen, Überspringen, Queue leeren

Repository:
- https://github.com/Sonstwer/screeninvader2

Verzeichnisstruktur:
- `server.py` – Flask-Server, REST-API, Einstiegspunkt
- `config.py` – zentrale Konfiguration
- `player.py` – mpv-Steuerung via JSON-IPC
- `queue_manager.py` – Verwaltung und Persistenz der Warteschlange
- `yt_wrapper.py` – yt-dlp-Suche und Stream-URL-Ermittlung
- `templates/` – HTML-Templates (Jinja2)
- `static/` – JavaScript & CSS
- `systemd/` – Beispiel-Unit für Autostart
- `docs/` – Installationsanleitungen

Für die Banana-Pi-Installation siehe:
`docs/INSTALL_BANANAPI_ARM.md`
