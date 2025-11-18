# Installation auf Banana Pi mit Armbian (Bookworm, Early Beta)

Diese Anleitung beschreibt die Installation von ScreenInvader 2.0 auf einem Banana Pi M1 (A20) 
mit Armbian (Debian/Ubuntu-basiert). Aktueller Stand ist eine **frühe, ungetestete Beta**.

## 0. Empfohlenes Armbian-Image

**Datei:** Armbian_23.08.0-trunk_Bananapi_bookworm_current_6.1.37.img.xz  
**Quelle:** Offizielles Banana-Pi-/Armbian-Community Google-Drive (über das BPI-M1-Wiki verlinkt)  
**Basis:** Debian 12 „Bookworm“, Kernel 6.1.37, „current“, kein Desktop

Hinweis: Community-Build → keine volle Stabilitätsgarantie.

## 1. Image unter Windows flashen (Balena Etcher)

1. Image herunterladen.
2. Balena Etcher installieren.
3. SD-Karte einlegen.
4. In Etcher:
   - „Flash from file“ → `.img.xz`
   - „Select target“ → SD-Karte
   - „Flash!“
5. SD-Karte in den Banana Pi einsetzen und booten.

## 2. Grundsystem vorbereiten

Einloggen per HDMI oder SSH (nach erstem Login Benutzer*in anlegen).

System aktualisieren:

```bash
sudo apt update
sudo apt upgrade -y
```

Benötigte Pakete installieren:

```bash
sudo apt install -y     python3     python3-pip     python3-flask     ffmpeg     mpv
```

### yt-dlp installieren (empfohlene stabile Methode via GitHub Binary)

```bash
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp      -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp
```

### Flask überprüfen

```bash
python3 -c "import flask" || echo "Flask fehlt!"
```

## 3. Benutzer*in für ScreenInvader anlegen

```bash
sudo useradd -r -s /usr/sbin/nologin screeninvader || true
```

## 4. Projekt installieren

```bash
sudo mkdir -p /opt/screeninvader2
sudo chown "$USER":"$USER" /opt/screeninvader2
cd /opt/screeninvader2
git clone https://github.com/Sonstwer/screeninvader2.git .
```

Rechte setzen:

```bash
sudo chown -R screeninvader:screeninvader /opt/screeninvader2
```

## 5. Manuell testen (wichtig!)

```bash
sudo -u screeninvader -s
cd /opt/screeninvader2
python3 server.py
```

Wenn der Server startet → OK.  
Mit `Strg+C` beenden.

Wenn ein Fehler erscheint (z. B. `ModuleNotFoundError`) → Paketinstallation prüfen.

## 6. systemd-Dienst aktivieren

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

Sollte „active (running)“ anzeigen.

## 7. Zugriff im Browser

IP herausfinden:

```bash
ip addr
```

Dann:

```
http://IP_DES_BANANAPI:5000/
```

## 8. Troubleshooting

### Kein Audio/Video
```bash
sudo -u screeninvader -s
mpv https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### yt-dlp Probleme
```bash
yt-dlp --force-ipv4 URL
```

Falls das funktioniert, im Code `--force-ipv4` ergänzen.

### Logs prüfen
```bash
sudo journalctl -u screeninvader2.service -f
```

### Beta-Hinweis
Dieses Setup ist experimentell. Funktion kann je nach Banana-Pi-Revision variieren.

