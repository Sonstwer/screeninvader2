# ScreenInvader 2.0 auf Banana Pi (Armbian, frühe Beta)

Dieser Leitfaden beschreibt die Installation von ScreenInvader 2.0 auf einem
Banana Pi (erste Generation) mit Armbian.

**Wichtiger Hinweis:**  
Der aktuelle Stand von ScreenInvader 2.0 ist eine _frühe, ungetestete Beta_.
Es gibt keine Garantie, dass die Software auf einem bestimmten Board / Image
stabil läuft. YouTube und andere Plattformen ändern ihre Schnittstellen
regelmäßig – Funktionen können jederzeit ausfallen.

---

## 1. Passendes Armbian-Image für den Banana Pi besorgen

Für den Banana Pi (BPI-M1) gibt es keine aktuellen „Mainline“-Images mehr auf
der Haupt-Armbian-Downloadseite. Stattdessen werden Images im Forum und über
ein Google-Drive-Verzeichnis bereitgestellt.

Empfohlene Startpunkte:

- Armbian-Image-Ordner für den Banana Pi (BPI-M1):  
  https://drive.google.com/drive/folders/1erfCb_sPspu3ilHW8yv4ooM66hJF7KLb

- Forum-Thread mit Infos zum aktuellen BPI-M1-Armbian-Image:  
  https://forum.banana-pi.org/t/banana-pi-bpi-m1-new-armbian-image/15157

Vorgehen:

1. Im Forum-Thread nachlesen, welche Images zuletzt erfolgreich genutzt wurden.
2. Aus dem verlinkten Google-Drive-Ordner das passende Image für den
   Banana Pi (BPI-M1) herunterladen.
3. Das Image mit einem Tool wie Balena Etcher oder Raspberry Pi Imager
   auf die microSD-Karte schreiben.

---

## 2. Erster Start von Armbian

1. microSD in den Banana Pi stecken, Banana Pi mit Netzwerk und Monitor
   verbinden und einschalten.
2. Beim ersten Boot:
   - Root-Passwort setzen
   - eigenen Benutzer anlegen (z. B. `metalab`)
   - ggf. SSH aktivieren
3. Nach dem ersten Login (als dein Benutzer):

   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

---

## 3. Grundpakete installieren

Auf dem Banana Pi (als dein Benutzer, z. B. `metalab`):

```bash
sudo apt update
sudo apt install -y     git     python3     python3.11-venv     mpv     ffmpeg
```

Hinweis:
- `mpv` übernimmt die Video-/Audio-Wiedergabe.
- `ffmpeg` wird von yt-dlp genutzt, um getrennte Audio-/Videostreams
  zusammenzuführen, wenn nötig.
- `python3.11-venv` wird für ein eigenes virtuelles Python-Umfeld verwendet.

---

## 4. Systemuser für ScreenInvader anlegen

Ein eigener User sorgt dafür, dass ScreenInvader nicht als `root` läuft.

```bash
sudo adduser --system --group --home /opt/screeninvader2 screeninvader
sudo usermod -aG audio,video,tty screeninvader
```

Damit bekommt `screeninvader` Zugriff auf Audio/Video-Geräte und TTY.

---

## 5. ScreenInvader 2.0 aus GitHub klonen

```bash
cd /opt
sudo git clone https://github.com/Sonstwer/screeninvader2.git
sudo chown -R screeninvader:screeninvader /opt/screeninvader2
```

---

## 6. Virtuelle Python-Umgebung (venv) einrichten

Als User `screeninvader` arbeiten:

```bash
sudo -u screeninvader -s
cd /opt/screeninvader2

# venv erstellen
python3 -m venv .venv

# venv aktivieren
source .venv/bin/activate

# pip aktualisieren
pip install --upgrade pip

# benötigte Python-Pakete installieren
pip install flask yt-dlp

# Version von yt-dlp prüfen (optional)
python -c "import yt_dlp, yt_dlp.version as v; print(v.__version__, '\n', yt_dlp.__file__)"

# venv verlassen
deactivate
exit
```

Hinweise:

- Durch das venv nutzt ScreenInvader eine eigene, aktuelle `yt-dlp`-Version,
  unabhängig von eventuell veralteten Distribution-Paketen.
- Bei Bedarf können später weitere Python-Pakete hinzugefügt werden, ohne
  das System-Python zu „verschmutzen“.

---

## 7. systemd-Service einrichten

ScreenInvader 2.0 soll beim Boot automatisch starten.

### 7.1 Service-Unit anlegen

```bash
sudo nano /etc/systemd/system/screeninvader2.service
```

Inhalt:

```ini
[Unit]
Description=ScreenInvader 2.0 Player + Webserver
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=screeninvader
Group=screeninvader

WorkingDirectory=/opt/screeninvader2

# mpv auf TTY3 ausführen – TTY1 bleibt für Terminal nutzbar
TTYPath=/dev/tty3
StandardInput=tty
StandardOutput=tty
StandardError=tty

# kleine Verzögerung, damit beim Boot kurz ein Terminal sichtbar bleibt
ExecStartPre=/bin/sleep 3

# Python-Server im venv starten (mpv wird von server.py / player.py gesteuert)
ExecStart=/opt/screeninvader2/.venv/bin/python server.py

Restart=always
RestartSec=2

# Zugriff auf TTY-Konfiguration (für mpv auf separatem TTY)
AmbientCapabilities=CAP_SYS_TTY_CONFIG

[Install]
WantedBy=multi-user.target
```

Speichern und schließen.

### 7.2 systemd neu laden und Service aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable screeninvader2.service
sudo systemctl start screeninvader2.service
sudo systemctl status screeninvader2.service
```

Der Status sollte `active (running)` anzeigen.

---

## 8. Weboberfläche aufrufen

1. IP-Adresse des Banana Pi herausfinden:

   ```bash
   hostname -I
   ```

   Beispielausgabe: `10.0.0.57 192.168.0.10 ...`  
   Die erste IPv4-Adresse ist meist die korrekte.

2. Von einem anderen Gerät im selben Netzwerk:

   - Browser öffnen
   - `http://IP_DES_BANANAPI:5000` aufrufen  
     Beispiel: `http://10.0.0.57:5000`

3. Es sollte die ScreenInvader-Weboberfläche erscheinen:
   - Suchfeld für YouTube/andere URLs
   - Anzeige der Warteschlange
   - Player-Steuerung

---

## 9. Direktes Debugging (optional)

Falls etwas nicht funktioniert, kannst du ScreenInvader direkt im Vordergrund starten:

```bash
sudo systemctl stop screeninvader2.service

sudo -u screeninvader -s
cd /opt/screeninvader2
source .venv/bin/activate
python server.py
```

- Alle Fehlermeldungen erscheinen direkt im Terminal.
- Mit `Strg + C` beendest du den Server.
- Danach:

  ```bash
  deactivate
  exit
  sudo systemctl start screeninvader2.service
  ```

---

## 10. Bekannte Einschränkungen (frühe Beta)

- **YouTube/yt-dlp:**  
  Plattformen wie YouTube ändern regelmäßig ihre internen Schnittstellen.
  Auch mit aktueller `yt-dlp`-Version kann es jederzeit zu:
  - fehlschlagenden Suchanfragen,
  - fehlenden Formaten,
  - oder Abbrüchen beim Abspielen kommen.

- **Performance / Auflösung:**  
  Der Banana Pi (erste Generation) ist recht schwach. In `config.py` wird eine
  bevorzugte Zielauflösung (z. B. bis 1080p) konfiguriert, mit Fallback auf
  niedrigere Auflösungen. Höhere Auflösungen können ruckeln oder gar nicht
  dekodierbar sein.

- **Kein Support / keine Garantie:**  
  Dies ist ein Hobby-/Community-Projekt ohne offiziellen Support. Nutze die
  Software auf eigene Verantwortung.

---

## 11. Updates

### Code aktualisieren

Auf dem Banana Pi:

```bash
sudo systemctl stop screeninvader2.service
sudo -u screeninvader -s
cd /opt/screeninvader2
git pull
source .venv/bin/activate
pip install --upgrade yt-dlp
deactivate
exit
sudo systemctl start screeninvader2.service
```

### Systempakete aktualisieren

```bash
sudo apt update
sudo apt upgrade -y
```

---

Damit sollte eine aktuelle Armbian-/Banana-Pi-Installation mit ScreenInvader 2.0,
venv-basiertem Python und aktueller yt-dlp-Version reproduzierbar sein.
