# Installation auf Banana Pi mit Armbian (Bookworm, Early Beta)

Diese Anleitung beschreibt die Installation von ScreenInvader 2.0
auf einem Banana Pi (z. B. BPI-M1) mit Armbian (Debian/Ubuntu-basiert).
Der aktuelle Stand ist eine **frühe, ungetestete Beta** – es gibt keine Garantie,
dass ScreenInvader 2.0 oder das verwendete Image auf deiner Hardware stabil läuft.

## 0. Hinweis zum verwendeten Armbian-Image (Quelle / Download)

Empfohlenes Image (Stand: 08.07.2023, Community-Build):

- Dateiname: `Armbian_23.08.0-trunk_Bananapi_bookworm_current_6.1.37.img.xz`
- Basis: Debian 12 „Bookworm“, Kernel 6.1.37, „current“ (ohne Desktop)
- Quelle: Banana Pi / Armbian Community Google-Drive-Verzeichnis
  (verlinkt z. B. im Banana-Pi-Wiki für BPI-M1)

Wichtig:
- Es handelt sich um einen **Community-Build, nicht um ein offiziell voll unterstütztes Image**.
- Weder das Image noch ScreenInvader 2.0 sind ausführlich getestet.
- Abstürze, fehlende Video-/Audio-Ausgabe oder Bootprobleme sind möglich.

## 1. Armbian-Image beschaffen und auf SD-Karte schreiben (Windows mit Balena Etcher)

1. Lade die Datei `Armbian_23.08.0-trunk_Bananapi_bookworm_current_6.1.37.img.xz`
   aus dem offiziellen Banana-Pi-Armbian-Downloadordner (Google Drive / Wiki-Verlinkung) herunter.
2. Installiere **Balena Etcher** unter Windows.
3. Stecke eine geeignete SD-Karte in deinen Kartenleser (alle Daten darauf werden gelöscht).
4. Starte Balena Etcher und wähle:
   - „Flash from file“ → die heruntergeladene `.img.xz`-Datei,
   - „Select target“ → deine SD-Karte,
   - „Flash!“
5. Nach erfolgreichem Schreiben die SD-Karte sicher entfernen und in den Banana Pi einlegen.
6. Banana Pi mit Strom versorgen und booten lassen (erster Boot kann etwas länger dauern).

## 2. Grundsystem vorbereiten

Per SSH oder direkt an der Konsole anmelden (Standardzugangsdaten
laut Armbian-Dokumentation, meistens `root` beim ersten Login, danach
wird ein eigener Benutzer angelegt).

System aktualisieren:

```bash
sudo apt update
sudo apt upgrade -y
```

Benötigte Pakete installieren (Python, Flask, yt-dlp, mpv, ffmpeg):

```bash
sudo apt install -y python3 python3-pip python3-flask yt-dlp mpv ffmpeg
```

Falls `yt-dlp` nicht als Paket verfügbar ist, alternativ via `pip` installieren:

```bash
sudo pip3 install yt-dlp
```

Beachte: Auch diese Paketkombination ist aktuell **nicht umfassend getestet**.
Änderungen in yt-dlp, mpv oder deren Abhängigkeiten können ScreenInvader 2.0
jederzeit brechen.

## 3. Systembenutzer für ScreenInvader anlegen

```bash
sudo useradd -r -s /usr/sbin/nologin screeninvader || true
```

## 4. Projekt nach /opt kopieren

```bash
sudo mkdir -p /opt/screeninvader2
sudo chown "$USER":"$USER" /opt/screeninvader2
```

Nun den Inhalt des Repositories nach `/opt/screeninvader2` kopieren.
Empfohlen wird ein direktes `git clone` (setzt Netzwerk am Banana Pi voraus).

```bash
cd /opt/screeninvader2
git clone https://github.com/Sonstwer/screeninvader2.git .
```

Alternativ kann das Repository auf einem anderen Rechner geklont und
per `scp`/`rsync` auf den Banana Pi übertragen werden.

Danach die Besitzrechte auf den Dienstbenutzer umstellen:

```bash
sudo chown -R screeninvader:screeninvader /opt/screeninvader2
```

## 5. systemd-Unit installieren

Bereitgestellte Unit-Datei kopieren:

```bash
sudo cp /opt/screeninvader2/systemd/screeninvader2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable screeninvader2.service
sudo systemctl start screeninvader2.service
```

Status prüfen:

```bash
sudo systemctl status screeninvader2.service
```

## 6. Zugriff im Netzwerk

Die IP-Adresse des Banana Pi ermitteln (z. B. mit `ip addr` oder über den Router)
und im Browser eines Geräts im selben Netzwerk aufrufen:

```text
http://BANANAPI_IP:5000/
```

Dort sollte das Web-Interface von ScreenInvader 2.0 erscheinen –
sofern alle Komponenten auf diesem Setup funktionieren.
Andernfalls die Hinweise im nächsten Abschnitt beachten.

## 7. Hinweise und Troubleshooting (Beta-Status)

- Wenn kein Audio/Video ausgegeben wird, mpv auf der Kommandozeile testen:

  ```bash
  sudo -u screeninvader -s
  cd /opt/screeninvader2
  mpv https://www.youtube.com/watch?v=dQw4w9WgXcQ
  ```

- Falls yt-dlp Probleme macht, Version aktualisieren:

  ```bash
  sudo yt-dlp -U || sudo pip3 install --upgrade yt-dlp
  ```

- Logs des Dienstes mit `journalctl` einsehen:

  ```bash
  sudo journalctl -u screeninvader2.service -f
  ```

- Beachte noch einmal: Dies ist eine **frühe, ungetestete Beta**.
  Es kann sein, dass ScreenInvader 2.0 auf diesem Image oder mit
  deiner Banana-Pi-Revision gar nicht startet oder nur instabil läuft.

In diesem `docs/`-Verzeichnis können weitere Installationsanleitungen
für andere Boards oder Distributionen ergänzt werden, z. B.

- `INSTALL_RASPBERRYPI.md`
- `INSTALL_GENERIC_DEBIAN.md`
