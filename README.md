# FerrumC für Unraid

[![Container tests](https://github.com/gottschalkfelix4-source/ferrumc-unraid/actions/workflows/container.yml/badge.svg)](https://github.com/gottschalkfelix4-source/ferrumc-unraid/actions/workflows/container.yml)

Ein Docker-Paket für [FerrumC](https://github.com/ferrumc-rs/ferrumc) mit **vorhandenem FerrumC-Web-Dashboard**, dauerhafter Datenspeicherung und direkt verwendbarem Unraid-Template.

| Bestandteil | Version / Adresse |
| --- | --- |
| FerrumC | `v0.1.0-rc2`, experimentelle Alpha |
| Minecraft-Client | **Java Edition 1.21.8** (Protokoll 772) |
| Plattformen | `linux/amd64` (Unraid), `linux/arm64` |
| Container | `ghcr.io/gottschalkfelix4-source/ferrumc-unraid:latest` |
| Dashboard | `http://UNRAID-IP:9010/?ws_port=9010` |
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
4. Auf das Container-Symbol → **WebUI** klicken.
5. Minecraft **Java 1.21.8** öffnen und `UNRAID-IP:25565` als Server hinzufügen.

Das ist ein persönliches Template. Es muss nicht in Community Applications eingereicht werden, um es zu verwenden. Der Speicherort für Benutzertemplates entspricht der [Unraid-Dokumentation](https://docs.unraid.net/unraid-os/manual/applications/).

## Was die Weboberfläche kann

Das offizielle Dashboard ist bereits in der Release-Binärdatei eingebettet und wird mitgeliefert. Funktionierend geprüft: WebSocket-Verbindung, Laufzeit, CPU-/Speicherwerte, Spielerzahl und Weltgröße.

**Upstream-Grenzen dieser Version:** Konsole, Spielerverwaltung, Konfigurationseditor und Power-Buttons sind im Dashboard noch als „Coming soon“ deaktiviert. Der Bereich „Recent Console Activity“ enthält Beispieldaten; TPS/MSPT und Netzwerkstatistiken sind ebenfalls keine vollständig implementierten Live-Anzeigen. Neustart und echte Logs gibt es in Unraid über **Restart / Logs**, Einstellungen über das Template oder `configs/config.toml`. Das Paket ergänzt keine zweite Webanwendung.

Der Dashboard-WebSocket prüft in diesem Release **keine Authentifizierung**, obwohl die Konfiguration ein `dashboard.secret` enthält. Dashboard nur im vertrauenswürdigen LAN oder über VPN verwenden; Port `9010` nicht ungeschützt ins Internet weiterleiten. Der Unraid-WebUI-Link übergibt den tatsächlich gemappten Port über `ws_port`, damit auch geänderte Host-Ports funktionieren.

FerrumC ist kein vollständiger Vanilla-/Paper-Ersatz. Creative ist voreingestellt; vollständiges Survival, Java-Plugins und Vanilla-Parität werden hier nicht versprochen. Die Verpackung verwendet bewusst das veröffentlichte Release und keinen laufend wechselnden Entwicklungsbranch.

## Einstellungen

Die folgenden Variablen überschreiben beim Start die entsprechenden Werte in `configs/config.toml`. Ohne Variable oder mit leerem Wert bleiben manuelle Werte erhalten. Die Angaben unter „Template“ sind die Unraid-Vorgaben; die Binärdatei hat teilweise andere Standardwerte.

| Variable | Template | Bedeutung |
| --- | --- | --- |
| `PUID` / `PGID` | `99` / `100` | Unraid `nobody:users`; Server läuft mit diesen IDs |
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

Für manuelle Konfiguration den Container stoppen, `/mnt/user/appdata/ferrumc/configs/config.toml` bearbeiten und wieder starten. Entsprechende Template-Variablen entfernen/leeren, wenn sie die Handänderung nicht überschreiben sollen. Kommentare und unbekannte TOML-Einstellungen bleiben erhalten; die Konfiguration wird atomar geschrieben. Beim ersten Start erstellt FerrumC seine vollständige Konfiguration selbst.

## Daten, Updates und Backups

```text
/data/
├── ferrumc              # Kopie aus dem Image; wird beim Start aktualisiert
├── configs/config.toml  # Serverkonfiguration
├── whitelist.txt       # Upstream-Whitelist, kein Vanilla whitelist.json
├── world/              # Welt-Datenbank
├── import/             # Optionaler Import einer Vanilla-Welt
└── logs/               # FerrumC-Dateilogs
```

FerrumC ermittelt den Datenpfad anhand des **wirklichen Speicherorts seiner Programmdatei**. Deshalb liegt eine Kopie im Volume; ein Symlink oder lediglich `WORKDIR /data` würde nicht genügen. Beim Start stammt die Binärdatei immer aus dem Image, nicht aus einem Download zur Laufzeit. Die gespeicherten Welten und Einstellungen werden dabei nicht ersetzt.

- **Update:** Über Unraid „Check for Updates“ / „Update“; davor ein Backup anlegen. `latest` und `v0.1.0-rc2` erhalten getestete Verbesserungen an diesem Docker-Paket. Für exakt gleiche Builds den veröffentlichten `sha-<Git-Commit>`-Tag oder Image-Digest verwenden.
- **Backup:** Container stoppen und den gesamten Appdata-Ordner sichern. Der Stop sendet `SIGINT` an FerrumC und lässt bis zu 120 Sekunden zum Speichern. Kein Live-Kopieren der geöffneten Welt-Datenbank.
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

Bei Bedarf PUID/PGID in `compose.yaml` an den eigenen Linux-Benutzer anpassen. Das Dashboard ist unter `http://SERVER-IP:9010/?ws_port=9010` erreichbar.

```sh
docker build -t ferrumc-unraid:local .
python3 tests/container_smoke.py ferrumc-unraid:local
```

Der Build lädt offizielle Linux-Release-Artefakte und prüft sie gegen die im Repository festgeschriebenen SHA256-Werte in [`docker/upstream.json`](docker/upstream.json). Zum Upgrade der FerrumC-Version dort Version, Commit und beide Prüfsummen aktualisieren, außerdem das `VERSION`-Label im Dockerfile und die Protokolltests anpassen.

## Automatische Veröffentlichung und Tests

GitHub Actions prüft TOML-Verarbeitung und Template-Defaults, baut native amd64- und arm64-Images und startet auf **beiden Architekturen** den echten FerrumC-Server. Geprüft werden Minecraft-Statuspakete, Dashboard-HTML und JavaScript, WebSocket-Live-Metriken, nichtprivilegierter Serverprozess, Konfiguration, Persistenz nach Container-Neuanlage und sauberes Speichern/Beenden. Erst nach erfolgreichen Tests wird das gemeinsame GHCR-Image veröffentlicht. Es werden keine zusätzlichen Registry-Zugangsdaten benötigt: Actions nutzt `GITHUB_TOKEN`.

Das sind Container-/Protokolltests, kein vollständiger Gameplay-Test mit einem Minecraft-Client. Ein echter Unraid-Host ist für die abschließende Prüfung des Unraid-Dialogs erforderlich.

Lokale Konfigurationstests:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

## Herkunft und Lizenz

Unabhängiges Community-Paket, nicht das offizielle FerrumC-Repository. Docker-Integration: MIT, siehe [LICENSE](LICENSE). FerrumC und das aus seinem Repository übernommene Icon: MIT, Copyright © 2024 Saad Muhammad, siehe [LICENSE.ferrumc](LICENSE.ferrumc). Dashboard-Assets werden unverändert als Bestandteil der offiziellen Release-Binärdatei übernommen.

- [FerrumC-Projekt](https://ferrumc.com/)
- [Verwendetes Release v0.1.0-rc2](https://github.com/ferrumc-rs/ferrumc/releases/tag/v0.1.0-rc2)
- [Offizielles Dashboard](https://github.com/ferrumc-rs/dashboard)
