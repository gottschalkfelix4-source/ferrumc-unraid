# FerrumC für Unraid

[![Container tests](https://github.com/gottschalkfelix4-source/ferrumc-unraid/actions/workflows/container.yml/badge.svg)](https://github.com/gottschalkfelix4-source/ferrumc-unraid/actions/workflows/container.yml)

Ein Docker-Paket für [FerrumC](https://github.com/ferrumc-rs/ferrumc) mit **weiterentwickeltem FerrumC-Web-Dashboard im ursprünglichen Design**, dauerhafter Datenspeicherung und direkt verwendbarem Unraid-Template.

| Bestandteil | Version / Adresse |
| --- | --- |
| FerrumC | `v0.1.0-rc2` mit Dashboard-Erweiterungen, experimentelle Alpha |
| Minecraft-Client | **Java Edition 1.21.8** (Protokoll 772) |
| Plattformen | `linux/amd64` (Unraid), `linux/arm64` |
| Container | `ghcr.io/gottschalkfelix4-source/ferrumc-unraid:latest` |
| Dashboard | `http://UNRAID-IP:9010/` |
| Minecraft | `UNRAID-IP:25565` |
| Appdata | `/mnt/user/appdata/ferrumc` → `/data` |

## Installation auf Unraid

Im **Unraid-Terminal** ausführen:

```sh
mkdir -p /boot/config/plugins/dockerMan/templates-user
curl -fL https://raw.githubusercontent.com/gottschalkfelix4-source/ferrumc-unraid/main/unraid/ferrumc.xml \
  -o /boot/config/plugins/dockerMan/templates-user/my-ferrumc.xml
```

1. **Docker → Add Container → Template → ferrumc** auswählen; ggf. die Seite neu laden.
2. Appdata-Pfad, Minecraft-Port und Dashboard-Port prüfen. Standard: `25565` und `9010`.
3. Server-Nachricht, Spielerlimit und Sichtweite nach Wunsch setzen. **Apply** startet den Container.
4. **Dashboard password** festlegen (mindestens 12 Zeichen). Ohne Vorgabe wird ein Passwort in `/mnt/user/appdata/ferrumc/dashboard-password.txt` erzeugt.
5. Auf das Container-Symbol → **WebUI** klicken und anmelden.
6. Minecraft **Java 1.21.8** öffnen und `UNRAID-IP:25565` als Server hinzufügen.

Das ist ein persönliches Template. Es muss nicht in Community Applications eingereicht werden, um es zu verwenden. Der Speicherort für Benutzertemplates entspricht der [Unraid-Dokumentation](https://docs.unraid.net/unraid-os/manual/applications/).

## Was die Weboberfläche kann

Das originale Svelte-Dashboard wurde im bestehenden dunklen Design mit orangefarbenen Akzenten ausgebaut. Die bisher deaktivierten Seiten und Schaltflächen sind mit dem echten Server verbunden:

- **Overview:** CPU, RAM, Spieler, Weltgröße, Container-Netzwerk, gemessene TPS/MSPT und Verlauf für 1, 6 oder 24 Stunden. Keine Demo-Messwerte.
- **Console:** echte Prozessausgabe, Filter, Download, Scrollpause und Befehle mit Eingabeverlauf. `help`, `list` und `save` sowie registrierte FerrumC-Befehle; derzeit ASCII-Eingaben bis 1024 Zeichen wegen des nativen Parsers.
- **Players:** tatsächliche Online-Spieler, Kick, persistente UUID-Banns und Whitelist. Banns blockieren erneute Anmeldungen, Whitelist-Änderungen wirken auf neue Verbindungen. Bereits verbundene Spieler bei Bedarf zusätzlich kicken.
- **Config:** Servernachricht, Spielerlimit, Sichtweite, Spielmodus, Authentifizierung, Verschlüsselung, Whitelist, Tickrate und Komprimierung. Validierung, Konflikterkennung und Sicherung vor dem Speichern.
- **Power Options:** Start, geordnetes Stoppen und Neustart mit Bestätigung. Das Dashboard bleibt bei gestopptem Minecraft-Server erreichbar.
- **Anmeldung:** passwortgeschützte API und WebSocket-Verbindung, begrenzte Loginversuche, HttpOnly-Sitzung und Schutz gegen fremde Webseiten.

Das Passwort wird niemals an FerrumCs Kindprozess weitergegeben. Der native Verwaltungsport `9001` ist ausschließlich im Container auf Loopback erreichbar und wird nicht veröffentlicht. `dashboard.secret` aus der alten FerrumC-Konfiguration wird nicht verwendet. Für Zugriff über das Internet HTTPS über einen Reverse Proxy oder ein VPN verwenden; HTTP überträgt das Passwort unverschlüsselt. WebSocket und UI nutzen denselben externen Port, ohne `ws_port`-Parameter.

FerrumC selbst bleibt experimentell und ist kein vollständiger Vanilla-/Paper-Ersatz. Creative ist voreingestellt; vollständiges Survival, Java-Plugins und Vanilla-Parität sind nicht Bestandteil dieser Dashboard-Erweiterung. Es wird ein festgeschriebener Release-Quellstand mit nachvollziehbaren lokalen Patches gebaut.

## Einstellungen

**Bis zum ersten Speichern im Dashboard** überschreiben die folgenden Variablen beim Containerstart die entsprechenden Werte in `configs/config.toml`. **Danach haben Dashboard-Einstellungen Vorrang**, auch bei Container-Updates. Die Datei `/data/.dashboard-config-managed` markiert diesen Zustand. Um wieder Template-Werte zu verwenden, den Container stoppen und diese Markierungsdatei entfernen. Ohne Variable oder mit leerem Wert bleiben manuelle Werte erhalten. Die Angaben unter „Template“ sind die Unraid-Vorgaben; die Binärdatei hat teilweise andere Standardwerte.

| Variable | Template | Bedeutung |
| --- | --- | --- |
| `PUID` / `PGID` | `99` / `100` | Unraid `nobody:users`; Server läuft mit diesen IDs |
| `DASHBOARD_PASSWORD` | leer | Mindestens 12 Zeichen; leer erzeugt ein dauerhaftes Passwort in `dashboard-password.txt` |
| `TZ` | `Europe/Berlin` | Zeitzone; FerrumC kann Logs weiterhin in UTC schreiben |
| `UMASK` | `002` | Dateirechte als Oktalzahl |
| `MOTD` | `FerrumC auf Unraid` | Nachricht in der Serverliste |
| `MAX_PLAYERS` | `20` | Spielerlimit, 1–10000 |
| `VIEW_DISTANCE` | `8` | Sichtweite, 2–32 Chunks |
| `ONLINE_MODE` | `true` | Minecraft-Konten durch Mojang authentifizieren |
| `GAMEMODE` | `creative` | creative, survival, adventure oder spectator |
| `WHITELIST` | `false` | Vor Aktivierung `/data/whitelist.txt` befüllen |
| `TPS` | nicht gesetzt | Tickrate, 1–100; Upstream-Standard 20 |
| `LOG_LEVEL` | `info` | trace, debug, info, warn oder error |

Host-Bindung und **interne** Ports werden für Docker auf `0.0.0.0`, `25565` und `9000` gesetzt. Andere externe Ports werden ausschließlich im Unraid-Template bzw. Compose-Mapping geändert.

Für manuelle Konfiguration den Container stoppen, `/mnt/user/appdata/ferrumc/configs/config.toml` bearbeiten und wieder starten. Solange noch keine Dashboard-Einstellungen gespeichert wurden, entsprechende Template-Variablen entfernen/leeren, wenn sie die Handänderung nicht überschreiben sollen. Kommentare und unbekannte TOML-Einstellungen bleiben erhalten; die Konfiguration wird atomar geschrieben. Beim ersten Start erstellt FerrumC seine vollständige Konfiguration selbst.

## Daten, Updates und Backups

```text
/data/
├── ferrumc              # Kopie aus dem Image; wird beim Start aktualisiert
├── configs/config.toml  # Serverkonfiguration
├── whitelist.txt       # Eine Spieler-UUID pro Zeile
├── banned-players.json  # Persistente gesperrte UUIDs
├── dashboard-password.txt # Generiertes Passwort, wenn keine Variable gesetzt ist
├── dashboard-metrics.sqlite3 # Messverlauf, maximal 24 Stunden
├── .dashboard-config-managed # Dashboard-Einstellungen haben Vorrang
├── world/              # Welt-Datenbank
├── import/             # Optionaler Import einer Vanilla-Welt
└── logs/               # FerrumC-Dateilogs
```

FerrumC ermittelt den Datenpfad anhand des **wirklichen Speicherorts seiner Programmdatei**. Deshalb liegt eine Kopie im Volume; ein Symlink oder lediglich `WORKDIR /data` würde nicht genügen. Beim Start stammt die Binärdatei immer aus dem Image, nicht aus einem Download zur Laufzeit. Die gespeicherten Welten und Einstellungen werden dabei nicht ersetzt.

- **Update:** Über Unraid „Check for Updates“ / „Update“; davor ein Backup anlegen. `latest` und `v0.1.0-rc2-dashboard.1` erhalten getestete Verbesserungen an diesem Docker-Paket. Für exakt gleiche Builds den veröffentlichten `sha-<Git-Commit>`-Tag oder Image-Digest verwenden.
- **Backup:** Container stoppen und den gesamten Appdata-Ordner sichern. Der Supervisor leitet beim Stop `SIGINT` an FerrumC weiter und lässt bis zu 120 Sekunden zum Speichern. Kein Live-Kopieren der geöffneten Welt-Datenbank.
- **Wiederherstellung:** Gestoppten Container, gesicherten Appdata-Ordner und die dazugehörige Image-Version verwenden.
- **Dateirechte:** Neue Daten erhalten `99:100`. Bei vorhandenen Daten oder einem Wechsel von PUID/PGID den Container stoppen und die Besitzrechte des gewählten Appdata-Verzeichnisses passend setzen, z. B. `chown -R 99:100 /mnt/user/appdata/ferrumc`. Das Image ändert nicht bei jedem Start rekursiv die ganze Welt.
- **Speicher:** FerrumCs großes virtuelles Datenbank-Mapping ist nicht gleich physischer RAM-Verbrauch. Sichtweite und Spielerzahl beeinflussen den Bedarf. Docker-Logs werden auf 3 × 10 MB rotiert; Dateilogs unter `/data/logs` separat im Blick behalten.

## Vanilla-Welt importieren

Vorher sichern und den normalen Container stoppen. Den entpackten Weltordner (mit `region/`, nicht nur dessen Inhalt) unter `/mnt/user/appdata/ferrumc/import/my-world` ablegen. Dann im Unraid-Terminal:

```sh
docker run --rm --name ferrumc-import \
  -e PUID=99 -e PGID=100 \
  -v /mnt/user/appdata/ferrumc:/data \
  ghcr.io/gottschalkfelix4-source/ferrumc-unraid:latest \
  import --import-path /data/import/my-world --max-concurrent-tasks 32
```

Anschließend Import-Logs auf Fehler prüfen, erst danach den normalen Container starten. Der Upstream-Importer kann Fehler loggen, ohne einen ungleich null Exit-Code zurückzugeben. Server und Import nie gleichzeitig auf derselben Datenbank betreiben.

## Docker Compose und eigener Build

```sh
git clone https://github.com/gottschalkfelix4-source/ferrumc-unraid.git
cd ferrumc-unraid
docker compose up -d
```

Bei Bedarf PUID/PGID in `compose.yaml` an den eigenen Linux-Benutzer anpassen. Das Dashboard ist unter `http://SERVER-IP:9010/` erreichbar.

```sh
docker build -t ferrumc-unraid:local .
python3 tests/container_smoke.py ferrumc-unraid:local
```

Der Build prüft das festgeschriebene FerrumC-Quellarchiv gegen SHA256, wendet [`patches/ferrumc.patch`](patches/ferrumc.patch) an und kompiliert mit dem dokumentierten Rust-Nightly und Cargo-Lockfile. Das Dashboard wird aus [`dashboard/`](dashboard/) mit einem festen pnpm-Lockfile gebaut. Versionen und Herkunft stehen in [`docker/upstream.json`](docker/upstream.json). Native API/Tick-Anbindung und Bannprüfung sind als separate Rust-Dateien unter `patches/` enthalten; die Verwaltung läuft ohne Docker-Socket als nichtprivilegierter Python-Supervisor.

Für den Container-Test wird zusätzlich Node.js benötigt: `npm ci --prefix tests/client`. Den lokalen Testclient nur gegen eigene Testwelten ausführen: Er schaltet vorübergehend auf Offline-Modus und stellt anschließend die Konfiguration wieder her.

## Automatische Veröffentlichung und Tests

GitHub Actions prüft TOML-Verarbeitung und Template-Defaults, baut native amd64- und arm64-Images und startet auf **beiden Architekturen** den echten FerrumC-Server. Geprüft werden Anmeldung, CSRF-/WebSocket-Schutz, echte Konsolenbefehle, Konfigurationsänderungen, Start/Stop/Neustart, Kick/Bann/Whitelist mit einem Minecraft-Protokollclient, Minecraft-Statuspakete, Dashboard-HTML und JavaScript, WebSocket-Live-Metriken, nichtprivilegierter Serverprozess, Konfiguration, Persistenz nach Container-Neuanlage und sauberes Speichern/Beenden. Erst nach erfolgreichen Tests wird das gemeinsame GHCR-Image veröffentlicht. Es werden keine zusätzlichen Registry-Zugangsdaten benötigt: Actions nutzt `GITHUB_TOKEN`.

Der automatisierte Minecraft-Testclient prüft Verwaltung und Login, kein vollständiges Gameplay. Ein echter Unraid-Host ist für die abschließende Prüfung des Unraid-Dialogs erforderlich.

Lokale Konfigurationstests:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

## Herkunft und Lizenz

Unabhängiges Community-Paket, nicht das offizielle FerrumC-Repository. Docker-Integration: MIT, siehe [LICENSE](LICENSE). FerrumC und das aus seinem Repository übernommene Icon: MIT, Copyright © 2024 Saad Muhammad, siehe [LICENSE.ferrumc](LICENSE.ferrumc). Das Dashboard basiert auf [ferrumc-rs/dashboard](https://github.com/ferrumc-rs/dashboard) und wurde für dieses Community-Paket erweitert. Originale Gestaltung und vorhandene UI-Komponenten bleiben erhalten.

- [FerrumC-Projekt](https://ferrumc.com/)
- [Verwendetes Release v0.1.0-rc2](https://github.com/ferrumc-rs/ferrumc/releases/tag/v0.1.0-rc2)
- [Offizielles Dashboard](https://github.com/ferrumc-rs/dashboard)
