# Willhaben KI-Agent

Durchsucht **alle** Anzeigen einer willhaben-Suche, lädt die vollständigen Beschreibungen und lässt
eine KI deiner Wahl die besten Angebote nach Preis/Leistung bzw. bestem Kompromiss auswählen – mit Vor-/Nachteilen,
Marktüberblick und Tipp. Mit grafischer Oberfläche für Windows und Linux, in der man live sieht, was der Agent gerade
macht.

**KI-Anbieter:** Google Gemini (Standard), OpenAI/ChatGPT, Anthropic Claude, Perplexity, Mistral, DeepSeek, xAI Grok,
Groq, OpenRouter, Together AI oder jede andere OpenAI-kompatible Schnittstelle – jeweils mit eigenem API-Key.

## Installation (einmalig)

Läuft unter **Windows 10/11** und **Linux**.

### Windows

1. Auf GitHub **Code → Download ZIP** wählen und das ZIP entpacken (oder `git clone https://github.com/ochtii/willhaben-agent.git`).
2. Im entpackten Ordner **`install-windows.cmd`** doppelklicken.

Der Windows-Installer
- sucht Python 3.10 oder neuer (mit Tkinter). Fehlt es, bietet er die Installation von Python 3.12 per `winget` an, sonst verweist er auf python.org,
- kopiert **nur die benötigten Dateien** nach `%LOCALAPPDATA%\willhaben-agent` und legt dort eine eigene Python-Umgebung an,
- erstellt eine Verknüpfung im **Startmenü** und auf dem **Desktop**,
- trägt die App unter **Einstellungen → Apps** ein (Deinstallation dort oder per `deinstallieren.cmd` im Programmordner; deine Ergebnisse bleiben erhalten, Einstellungen und Keys auf Wunsch auch),
- bietet am Ende an, den heruntergeladenen Ordner zu löschen.

Einstellungen und Keys liegen unter Windows in `%APPDATA%\willhaben-agent`.

### Linux

```bash
git clone https://github.com/ochtii/willhaben-agent.git
cd willhaben-agent && ./install.sh
```

(Oder das ZIP von GitHub herunterladen, entpacken und `./install.sh` ausführen.)

Der Installer
- sucht ein Python mit Tkinter (installiert `python3-tk` / `python3-venv` bei Bedarf per `sudo`, unterstützt apt/dnf/pacman/zypper),
- kopiert **nur die zum Betrieb und für Updates nötigen Dateien** (Liste: `laufzeit-dateien.txt`) nach `~/.local/share/willhaben-agent` und entfernt dort alles andere,
- legt dort eine eigene Python-Umgebung (`.venv/`) an, es wird nichts systemweit per pip installiert,
- erstellt die Startbefehle `willhaben-agent` / `willhaben-agent-cli` in `~/.local/bin`, den Startmenü-Eintrag **„Willhaben KI-Agent“** sowie ein Symbol auf dem Schreibtisch,
- bietet am Ende an, den **heruntergeladenen Quellordner zu löschen**, weil er nicht mehr gebraucht wird. Hat ein Git-Klon ungesicherte Änderungen, warnt er und fragt mit Standard „nein“. Optionen: `--quelle-behalten`, `--quelle-loeschen`.

Anderer Installationsort: `WILLHABEN_AGENT_HOME=/pfad ./install.sh`

Danach einen **API-Key** holen (am einfachsten und kostenlos: Google Gemini) und über das **Zahnrad rechts oben →
„KI-Anbieter & Keys“** eintragen: siehe **[ANLEITUNG-API-KEY.md](ANLEITUNG-API-KEY.md)**.

## Starten

- **Desktop:** Startmenü oder Schreibtisch → „Willhaben KI-Agent“
- **Mit Protokoll im Terminal:** im Terminal `willhaben-agent` starten – das Fenster erscheint, und im Terminal läuft dasselbe Protokoll mit
- **Aus dem Terminal:** `willhaben-agent`
- **Keys im Terminal:** `willhaben-agent-cli --keys` zeigt Anbieter, Keys, Limits und Verbrauch. `willhaben-agent-cli --key-hinzufuegen "Privat" AIza…` speichert einen Key (für einen anderen Anbieter mit `--anbieter openai`, `anthropic`, `perplexity`, …), `--modelle` listet die für deinen Key verfügbaren Modelle. `--anbieter` wählt den Anbieter auch für einen einzelnen Suchlauf.
- **Ohne Fenster (reine Terminal-Version):**
  ```bash
  willhaben-agent-cli --kategorie laptops --von 200 --bis 600 --bundesland wien --bezirk Favoriten \
      --beschreibung "Uni & Office, leicht, guter Akku, mind. 16 GB RAM" --top 10
  ```

## Updates

- **Beim Start** prüft die App im Hintergrund auf GitHub, ob es eine neuere Version gibt. Wenn ja, zeigt sie Versionsnummern und Änderungen an: **Jetzt aktualisieren · Später · Diese Version überspringen**.
- **Von Hand:** Zahnrad → Einstellungen → **Allgemein & Updates** → „Jetzt nach Updates suchen …“. Dort lässt sich auch die Prüfung beim Start abschalten.
- **Terminal:** `willhaben-agent-cli --version` bzw. `willhaben-agent-cli --update`
- **Versionsnummer** `1.2.N`: `1.2` steht in der Datei `VERSION` (für größere Sprünge von Hand ändern). **N zählt die Commits seit der letzten Änderung von `VERSION`** und steigt bei jedem Push automatisch. Der Commit, der `VERSION` ändert, ist `.0`.
- **Versionsverlauf:** `CHANGELOG.md`, in der App über das **?** rechts oben → „Neuigkeiten“.
- **Aufräumen:** Ein Update übernimmt nur die Dateien, die laut `laufzeit-dateien.txt` der neuen Version gebraucht werden, und löscht im Installationsordner alles andere. Neue Programmdateien müssen deshalb in `laufzeit-dateien.txt` eingetragen werden.
- **So wird installiert:**
  - Bei einem Git-Klon per `git pull`. Lokal geänderte Programmdateien werden nie überschrieben, das Update bricht dann mit Hinweis ab.
  - Bei einer ZIP-Installation per Download von GitHub.
  - Danach werden die Python-Pakete aktualisiert, und ein Neustart wird angeboten.
  - Keys, Einstellungen und Ergebnisse bleiben erhalten.

## Das Fenster

Modernes Erscheinungsbild (Sun-Valley-Theme), wahlweise **hell oder dunkel**: Einstellungen → Darstellung.


| Bereich | Inhalt |
|---|---|
| **Links: Suchauftrag** | Suchbegriff, Haupt- und Unterkategorie (alle willhaben-Kategorien, mit passendem Beispieltext), Beschreibung, Preisspanne, Bundesländer (Häkchen). Unter jedem angehakten Bundesland öffnet **„Bezirke …“** eine Auswahl aller Bezirke (live von willhaben, mit Suche und Anzeigenzahl). Nichts gewählt – oder der Knopf **„Alle Bezirke“**, der alle Häkchen entfernt – bedeutet das ganze Bundesland. Dazu Anzahl Top-Geräte. Die Eingaben werden fürs nächste Mal gemerkt. Darunter eine Kurzübersicht der Keys (bereit, heute verbraucht, zuletzt genutzt). |
| **Kopfleiste** | Farbverlauf mit Version, rechts das **?** (Über-Fenster mit Funktionen, Anleitung, Neuigkeiten, F1) und das **Zahnrad** (Einstellungen, Strg+K). Eine Menüleiste gibt es nicht mehr. |
| **Einstellungen → KI-Anbieter & Keys** | **Anbieter** wählen (Gemini, ChatGPT, Claude, Perplexity, Mistral, DeepSeek, Grok, Groq, OpenRouter, Together, eigene Adresse). Daneben **„Anleitung: …-Key holen“**: Schritt-für-Schritt-Anleitung für genau diesen Anbieter mit Link zur Key-Seite. **Modell** und **Ausweichmodell** aus der Liste der für deinen Key verfügbaren Modelle (passt sich automatisch an, wenn ein Modell fehlt). Beliebig viele Keys je Anbieter: hinzufügen, ändern, testen, ein- und ausschalten, Reihenfolge festlegen, Verteilung gleichmäßig oder nacheinander. Verbrauch und Limits werden live angezeigt. |
| **Einstellungen → Darstellung** | Hell oder Dunkel (mit Vorschau) |
| **Einstellungen → Allgemein & Updates** | Ergebnis-Ordner ändern/öffnen, Update-Prüfung beim Start, „Jetzt nach Updates suchen“, Speicherort der Einstellungen und Keys |
| **Während der Suche** | Das Formular wird ausgeblendet. Stattdessen zeigt die linke Spalte eine Animation, die aktuelle Phase, den **Gesamtfortschritt** in Prozent über alle Phasen, darunter den aktuellen Schritt (z. B. „KI-Bewertung: 30 von 120“), die Laufzeit und den Suchauftrag. Während einer KI-Anfrage rückt der Gesamtfortschritt langsam weiter (nie über den nächsten Zwischenstand hinaus) und es steht dabei, wie lange schon auf die Antwort gewartet wird – so sieht man, dass nichts hängt. Danach erscheint das Formular wieder. |
| **Fortschritt** | Stepper Suche → Details → KI-Bewertung → Endvergleich → Fertig, darunter ein Fortschrittsbalken mit Farbverlauf und Laufzeit, dazu vier Kacheln (gefunden, Beschreibungen, KI-bewertet, passend) |
| **Live-Protokoll** | Terminal-Ansicht: jede Seite, jede Wartezeit, jede KI-Anfrage |
| **Anzeigen** | Tabelle, die sich live füllt: Preis, Ort, Zustand, KI-Werte für Leistung und Preis/Leistung. Grün = passend, grau = aussortiert, gelb = Top-Liste. Klick auf eine Spalte sortiert, Klick auf eine Zeile zeigt die KI-Begründung, Doppelklick öffnet die Anzeige im Browser. |
| **Ergebnis** | Top-N mit Vor-/Nachteilen, Fazit, Tipp und Links zu den Anzeigen. Wird zusätzlich als Markdown-Bericht gespeichert. |
| **Berichte** | Alle früheren Berichte aus dem Ergebnis-Ordner, neueste zuerst (Suche, Datum, Budget, Top-N). Ein Klick zeigt den Bericht formatiert mit klickbaren Links an. Dazu „Datei öffnen“, „Ordner öffnen“ und „Löschen“ (entfernt Bericht und zugehörige JSON-Dateien, nach Rückfrage). |
| **Stopp** | bricht jederzeit sauber ab |
| **Suchfeld / Kategorie** | „✕“ im Suchfeld leert den Suchbegriff. „↺ zurücksetzen“ neben „Kategorie“ stellt auf „Alle Kategorien“. Das zweite Auswahlfeld (Unterkategorie) erscheint nur, wenn eine Kategorie gewählt ist. |

Ergebnisse landen in `~/willhaben-ergebnisse/`:
- `…-topN.md` – der Bericht
- `…-anzeigen.json` – alle Anzeigen
- `…-bewertungen.json` – alle KI-Bewertungen

## Ablauf

1. **Suche:** alle Ergebnisseiten (200 Anzeigen pro Seite), Bezirke werden in willhaben-Filter übersetzt
2. **Details:** jede Anzeigenseite → vollständige Beschreibung, Marke, Zustand, Display, privat/Händler (keine Kontaktdaten)
3. **Marktrecherche** (abschaltbar): Die KI sucht im Web die *aktuelle* Marktlage (Gemini per Google-Suche, Claude und ChatGPT mit eigener Websuche, Perplexity sowieso). Hat der gewählte Anbieter keine Websuche (z. B. Mistral, DeepSeek), übernimmt ein anderer Anbieter, für den ein Key eingetragen ist. Gefragt sind typische Gebrauchtpreise in Österreich, Neupreise zur Einordnung, Trends und worauf man achten sollte. Das Ergebnis samt Quellen fließt in die Bewertung ein, steht im Bericht und kostet eine zusätzliche Anfrage.
4. **KI-Bewertung:** Pakete mit bis zu 30 Anzeigen an den gewählten Anbieter → Specs, Zustand, Relevanz, Leistung, Preis/Leistung, Warnsignale. Der Verteiler wählt für jede Anfrage den passenden Key. Bei einem Limit oder einem ungültigen Key wechselt er zum nächsten Key, bei Überlastung oder aufgebrauchtem Kontingent vom gewählten Modell auf das Ausweichmodell.
5. **Endvergleich:** die besten ~3×N Kandidaten werden gegeneinander verglichen → Top-N mit Vor-/Nachteilen

## Kategorien

Alle **19 Hauptkategorien** des willhaben-Marktplatzes mit rund **190 Unterkategorien** (live ermittelt, Nov. 2026) – von
Antiquitäten über Mode, Sport und Wohnen bis Tiere. Im Fenster wählt man oben die Hauptkategorie und darunter die
Unterkategorie (oder „alle Unterkategorien“). Für jede Kategorie erscheint unter der Beschreibung ein **passender
Beispieltext** (z. B. Wintersport: „Ski 160–170 cm mit Bindung, Kanten scharf, frisch gewachst“).

Terminal: `willhaben-agent-cli --kategorien` listet alle Kurznamen (z. B. `fernseher`, `wintersport`,
`klemmbausteine-lego-playmobil`). Die bisherigen Kurznamen `laptops`, `pcs`, `tablets`, `ebook-reader`, `pc-komponenten`,
`computer`, `handys`, `konsolen`, `kameras`, `alle` funktionieren weiterhin.

Für spezielle Filter (z. B. Marke, Unter-Unterkategorie): Suche im Browser auf willhaben einstellen und die Adresse ins Feld **„Such-URL aus dem Browser“** kopieren.

## Hinweise

- **Modell:** Standard ist Google Gemini mit `gemini-3.5-flash`, bei Überlastung weicht der Agent auf `gemini-3.6-flash` aus. Vorschläge der anderen Anbieter: ChatGPT `gpt-5-mini`/`gpt-5`, Claude `claude-opus-5-5`/`claude-sonnet-5-5`, Perplexity `sonar-pro`/`sonar`, Mistral `mistral-medium-latest`/`mistral-small-latest`.
- **Kosten:** Nur Gemini (und Groq) haben einen brauchbaren Gratis-Tarif. Bei den anderen Anbietern wird nach Verbrauch abgerechnet – ein Suchlauf mit ~100 Anzeigen braucht etwa 5–10 Anfragen. Außerdem berechnet der Agent aus den gefundenen Anzeigen die willhaben-Marktpreise je RAM-Klasse (Median) und gibt sie der KI als Vergleich mit.
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
| `fortschritt.py` | Schätzung des Gesamtfortschritts über alle Phasen (auch während KI-Anfragen) |
| `berichte.py` | Reiter „Berichte“: frühere Berichte auflisten, formatiert anzeigen, löschen |
| `kategorien.py` | alle willhaben-Kategorien mit Pfad, Kurzname und Beispieltext |
| `rating.py` | KI-Bewertung (Prompts, Pakete, Endvergleich) |
| `providers.py` | Anbindung an alle KI-Anbieter (Gemini, Claude per `anthropic`-SDK, OpenAI-kompatible), Fehler- und Limit-Erkennung |
| `keys.py` | Key-Speicher, Verbrauchszähler, automatischer Verteiler |
| `einstellungen_dialog.py` | Einstellungsfenster (Zahnrad): KI-Anbieter & Keys, Darstellung, Allgemein & Updates |
| `keys_dialog.py` | Reiter „KI-Anbieter & Keys“ und Fenster „Key hinzufügen/bearbeiten“ |
| `updater.py`, `update_dialog.py` | Update-Prüfung und -Installation über GitHub |
| `about_dialog.py` | Fenster „Über“: Funktionen, Ablauf, Versionsverlauf, Entwickler & Links |
| `bezirk_dialog.py` | Auswahlfenster für die Bezirke eines Bundeslands |
| `theme.py` | Design: Sun-Valley-Theme, Hell-/Dunkel-Palette, Kopfleiste, Stepper, Kacheln |
| `plattform.py` | Unterschiede Windows/Linux (Ordner, Schriften, Dateien öffnen, Neustart) |
| `install-windows.cmd`, `install.ps1` | Installer für Windows |
| `install.sh` | Installer für Linux |
| `icon.ico` | Programmsymbol für Windows-Verknüpfungen |
| `CHANGELOG.md` | Versionsverlauf (wird im Über-Fenster angezeigt) |
| `CLAUDE.md` | Entwicklungsregeln (README, Über-Fenster und Changelog bei jedem Push aktualisieren) |
| `VERSION` | Haupt-/Nebenversion (die letzte Stelle zählt automatisch die Commits) |
| `laufzeit-dateien.txt` | Liste der Dateien, die eine Installation braucht (alles andere wird entfernt) |
| `settings.py` | gespeicherte Eingaben |
| `install.sh` | Installer |
