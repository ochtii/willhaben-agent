# Willhaben KI-Agent

Durchsucht **alle** Anzeigen einer willhaben-Suche, lädt die vollständigen Beschreibungen und lässt
**Google Gemini** die besten Angebote nach Preis/Leistung bzw.
bestem Kompromiss auswählen – mit Vor-/Nachteilen, Marktüberblick und Tipp. Mit grafischer Oberfläche für Linux, in der
man live sieht, was der Agent gerade macht.

## Installation (einmalig)

```bash
cd willhaben-agent
./install.sh
```

Der Installer
- sucht ein Python mit Tkinter (installiert `python3-tk` / `python3-venv` bei Bedarf per `sudo`, unterstützt apt/dnf/pacman/zypper),
- legt eine eigene Python-Umgebung in `.venv/` an (nichts wird systemweit per pip installiert),
- erstellt die Startmenü-Einträge **„Willhaben KI-Agent“** und **„Willhaben KI-Agent (mit Terminal)“** sowie ein Symbol auf dem Schreibtisch.

Danach einen **Google-Gemini-API-Key** holen und unter **Einstellungen → API-Keys & Limits**
eintragen: siehe **[ANLEITUNG-API-KEY.md](ANLEITUNG-API-KEY.md)**.

## Starten

- **Desktop:** Startmenü oder Schreibtisch → „Willhaben KI-Agent“
- **Mit Terminal-Fenster:** „Willhaben KI-Agent (mit Terminal)“ – das Fenster erscheint, und im Terminal läuft dasselbe Protokoll mit
- **Aus dem Terminal:** `./willhaben-agent`
- **Keys im Terminal:** `./willhaben-agent-cli --keys` zeigt Keys, Limits und Verbrauch. `./willhaben-agent-cli --key-hinzufuegen "Privat" AIza…` speichert einen Key, `--modelle` listet die für deinen Key verfügbaren Modelle.
- **Ohne Fenster (reine Terminal-Version):**
  ```bash
  ./willhaben-agent-cli --kategorie laptops --von 200 --bis 600 --bundesland wien --bezirk Favoriten \
      --beschreibung "Uni & Office, leicht, guter Akku, mind. 16 GB RAM" --top 10
  ```

## Updates

- **Beim Start** prüft die App im Hintergrund auf GitHub, ob es eine neuere Version gibt. Wenn ja, zeigt sie Versionsnummern und Änderungen an: **Jetzt aktualisieren · Später · Diese Version überspringen**.
- **Von Hand:** Einstellungen → **Nach Updates suchen …** Dort lässt sich auch die Prüfung beim Start abschalten.
- **Terminal:** `./willhaben-agent-cli --version` bzw. `./willhaben-agent-cli --update`
- **Versionsnummer** `1.0.N`: `1.0` steht in der Datei `VERSION` (für größere Sprünge von Hand ändern), **N ist die Anzahl der Commits auf `main`** und steigt bei jedem Push automatisch.
- **So wird installiert:**
  - Bei einem Git-Klon per `git pull`. Lokal geänderte Programmdateien werden nie überschrieben, das Update bricht dann mit Hinweis ab.
  - Bei einer ZIP-Installation per Download von GitHub.
  - Danach werden die Python-Pakete aktualisiert, und ein Neustart wird angeboten.
  - Keys, Einstellungen und Ergebnisse bleiben erhalten.

## Das Fenster

| Bereich | Inhalt |
|---|---|
| **Links: Suchauftrag** | Suchbegriff, Kategorie, Beschreibung, Preisspanne, Bundesländer (Häkchen), Bezirke, Anzahl Top-Geräte. Die Eingaben werden fürs nächste Mal gemerkt. Darunter eine Kurzübersicht der Keys (bereit, heute verbraucht, zuletzt genutzt). |
| **Einstellungen → API-Keys & Limits** (Strg+K) | **Modell** und **Ausweichmodell** aus der Liste der für deinen Key verfügbaren Gemini-Modelle wählen. Dazu beliebig viele Gemini-Keys: hinzufügen, ändern, testen, ein- und ausschalten, Reihenfolge festlegen, Verteilung gleichmäßig oder nacheinander. Verbrauch und Limits werden live angezeigt. |
| **Oben: Phasen** | 1. Suche → 2. Details → 3. KI-Bewertung → 4. Endvergleich → 5. Fertig, mit Fortschrittsbalken, Zählern und Laufzeit |
| **Live-Protokoll** | Terminal-Ansicht: jede Seite, jede Wartezeit, jede KI-Anfrage |
| **Anzeigen** | Tabelle, die sich live füllt: Preis, Ort, Zustand, KI-Werte für Leistung und Preis/Leistung. Grün = passend, grau = aussortiert, gelb = Top-Liste. Klick auf eine Spalte sortiert, Klick auf eine Zeile zeigt die KI-Begründung, Doppelklick öffnet die Anzeige im Browser. |
| **Ergebnis** | Top-N mit Vor-/Nachteilen, Fazit, Tipp und Links zu den Anzeigen. Wird zusätzlich als Markdown-Bericht gespeichert. |
| **Stopp** | bricht jederzeit sauber ab |

Ergebnisse landen in `~/willhaben-ergebnisse/`:
- `…-topN.md` – der Bericht
- `…-anzeigen.json` – alle Anzeigen
- `…-bewertungen.json` – alle KI-Bewertungen

## Ablauf

1. **Suche:** alle Ergebnisseiten (200 Anzeigen pro Seite), Bezirke werden in willhaben-Filter übersetzt
2. **Details:** jede Anzeigenseite → vollständige Beschreibung, Marke, Zustand, Display, privat/Händler (keine Kontaktdaten)
3. **Marktrecherche** (abschaltbar): Gemini sucht per Google-Suche die *aktuelle* Marktlage. Gefragt sind typische Gebrauchtpreise in Österreich, Neupreise zur Einordnung, Trends und worauf man achten sollte. Das Ergebnis samt Quellen fließt in die Bewertung ein, steht im Bericht und kostet eine zusätzliche Anfrage.
4. **KI-Bewertung:** Pakete mit 30 Anzeigen an Gemini → Specs, Zustand, Relevanz, Leistung, Preis/Leistung, Warnsignale. Der Verteiler wählt für jede Anfrage den passenden Key. Bei einem Limit oder einem ungültigen Key wechselt er zum nächsten Key, bei Überlastung oder aufgebrauchtem Kontingent vom gewählten Modell auf das Ausweichmodell.
5. **Endvergleich:** die besten ~3×N Kandidaten werden gegeneinander verglichen → Top-N mit Vor-/Nachteilen

## Kategorien

`laptops`, `pcs`, `tablets`, `ebook-reader`, `pc-komponenten`, `computer`, `handys`, `konsolen`, `kameras`, `alle`.

Für jede andere Kategorie oder spezielle Filter: Suche im Browser auf willhaben einstellen und die Adresse ins Feld **„Such-URL aus dem Browser“** kopieren.

## Hinweise

- **Modell:** Standard ist `gemini-3.5-flash`, bei Überlastung weicht der Agent auf `gemini-3.6-flash` aus. Außerdem berechnet der Agent aus den gefundenen Anzeigen die willhaben-Marktpreise je RAM-Klasse (Median) und gibt sie der KI als Vergleich mit.
- **Free Tier:** Der Agent hält die Limits pro Key ein (Anfragen und Token pro Minute bzw. Tag) und verteilt auf alle Keys. Details: [ANLEITUNG-API-KEY.md](ANLEITUNG-API-KEY.md)
- **Mehrere Konten:** Keys verschiedener eigener Konten nur zum Umgehen der Gratis-Limits verstoßen meist gegen die Nutzungsbedingungen. Es drohen Kontosperren.
- **Dauer:** Die Listenseiten sind schnell. Die Detailseiten dauern ca. 1 s je 4 Anzeigen. Die KI braucht ca. 7 s je 20 Anzeigen.
- **Rücksicht:** Zwischen den willhaben-Abrufen wird gewartet. Nur für den privaten Gebrauch, willhaben-AGB beachten.
- Kategorien, Bundesland- und Bezirks-IDs sind live geprüft (Nov. 2026).

## Dateien

| Datei | Zweck |
|---|---|
| `gui.py` | grafische Oberfläche (Tkinter) |
| `agent.py` | Terminal-Version |
| `pipeline.py` | gemeinsamer Ablauf |
| `willhaben.py` | Scraper |
| `rating.py` | KI-Bewertung (Prompts, Pakete, Endvergleich) |
| `providers.py` | Anbindung an Google Gemini, Fehler- und Limit-Erkennung |
| `keys.py` | Key-Speicher, Verbrauchszähler, automatischer Verteiler |
| `keys_dialog.py` | Fenster „API-Keys & Limits“ |
| `updater.py`, `update_dialog.py` | Update-Prüfung und -Installation über GitHub |
| `VERSION` | Haupt-/Nebenversion (die letzte Stelle zählt automatisch die Commits) |
| `settings.py` | gespeicherte Eingaben |
| `install.sh` | Installer |
