# Versionsverlauf

Die Versionsnummer lautet `<VERSION>.<N>`: `VERSION` steht in der gleichnamigen Datei (z. B. `1.1`),
**N** zählt die Commits seit der letzten Änderung dieser Datei und steigt mit jedem Push automatisch.
Die App zeigt diesen Verlauf im Über-Fenster (**?** rechts oben) unter „Neuigkeiten“.

## 1.2.8 – 2026-11-24
- Bezirke: statt eines Knopfs steht unter jedem gewählten Bundesland ein klickbarer Text – „Alle Bezirke“ oder „Bezirke … (Favoriten, Donaustadt)“
- Feld „Auswertung“ aufgeräumt: das Eingabefeld für eine Such-URL und der Schnellmodus sind entfallen (die Such-URL gibt es weiterhin in der Terminal-Version)
- Feld „KI & API-Keys“ neu gestaltet: Anbieter mit farbigem Status, darunter Modell, Ausweichmodell, Verbrauch heute und Websuche übersichtlich als Tabelle
- Behoben: Graue Hinweistexte und blaue Links wurden seit dem neuen Design in normaler Textfarbe angezeigt – die Farben stimmen jetzt wieder

## 1.2.7 – 2026-11-24
- Bezirksauswahl vereinfacht: „Alle Bezirke“ entfernt alle Häkchen und sucht damit im ganzen Bundesland; der Knopf „Keine“ ist entfallen

## 1.2.6 – 2026-11-24
- Neu: Gesamtfortschritt in Prozent über alle Phasen (Suche, Beschreibungen, KI-Bewertung, Endvergleich) – oben rechts und groß in der Lauf-Ansicht
- Der Gesamtfortschritt rückt auch während einer laufenden KI-Anfrage weiter und ist dabei animiert, damit es nicht nach Stillstand aussieht
- Darunter der aktuelle Schritt (z. B. „KI-Bewertung: 30 von 120“) mit Hinweis „warte auf KI-Antwort … 14 s“

## 1.2.5 – 2026-11-24
- Behoben: Die Laufzeit zählt während der Suche wieder sekündlich mit (oben rechts und in der Lauf-Ansicht); nach dem Ende bleibt die Gesamtdauer stehen, ab einer Stunde mit Stundenangabe

## 1.2.4 – 2026-11-24
- Neu: Fragezeichen rechts oben neben dem Zahnrad – öffnet direkt das Über-Fenster (auch mit F1)
- Die Menüleiste „Hilfe“ ist entfallen, dadurch mehr Platz im Fenster; Einstellungen weiterhin über das Zahnrad oder Strg+K

## 1.2.3 – 2026-11-24
- Neu: Reiter „Berichte“ mit allen früheren Suchläufen – neueste zuerst, formatiert lesbar mit klickbaren Links, auch löschbar
- Während der Suche werden die Sucheinstellungen ausgeblendet. Stattdessen zeigen eine Animation, die aktuelle Phase, ein moderner Fortschrittsbalken mit Prozent und der Suchauftrag, dass die Suche läuft
- Neuer Fortschrittsbalken mit Farbverlauf und wanderndem Lichtreflex
- Suchfeld: „✕“ zum Leeren des Suchbegriffs
- Kategorie: „↺ zurücksetzen“ stellt auf „Alle Kategorien“; die Unterkategorie erscheint nur, wenn eine Kategorie gewählt ist
- Hintergrundfarbe im hellen Design vereinheitlicht

## 1.2.2 – 2026-11-24
- Behoben: Im Über-Fenster waren die Knöpfe unten („Nach Updates suchen“, „GitHub öffnen“, „Schließen“) bei kleineren Bildschirmen oder größerer Schrift abgeschnitten – sie bleiben jetzt immer sichtbar
- Das Über-Fenster passt seine Höhe an den Bildschirm an; passt ein Reiter nicht hinein, erscheint eine Bildlaufleiste (auch mit dem Mausrad bedienbar)

## 1.2.1 – 2026-11-24
- Alle willhaben-Kategorien: 19 Hauptkategorien mit rund 190 Unterkategorien, Auswahl in zwei Stufen (Haupt- und Unterkategorie)
- Passender Beispieltext unter der Beschreibung für jede Kategorie (z. B. Wintersport, Fernseher, LEGO, Antiquitäten)
- Terminal-Version: „--kategorien“ listet alle Kurznamen; bisherige Kurznamen wie „laptops“ funktionieren weiter
- Neu in den Einstellungen: Knopf „Anleitung: …-Key holen“ mit Schritt-für-Schritt-Anleitung für den gewählten KI-Anbieter
- Menü „Hilfe“ aufgeräumt: die beiden API-Key-Einträge sind in die Einstellungen gewandert
- Behoben: Im Über-Fenster lässt sich der Reiter „Neuigkeiten“ jetzt mit dem Mausrad scrollen (Windows und Linux)

## 1.2.0 – 2026-11-24
- Neu: Freie Wahl des KI-Anbieters – Google Gemini (Standard), OpenAI/ChatGPT, Anthropic Claude, Perplexity, Mistral, DeepSeek, xAI Grok, Groq, OpenRouter, Together AI oder eine eigene OpenAI-kompatible Adresse
- Je Anbieter mehrere Keys, Modell und Ausweichmodell aus der Liste deines Keys (passt sich automatisch an, wenn ein Modell fehlt)
- Marktrecherche im Web jetzt auch mit Claude, ChatGPT und Perplexity; Anbieter ohne Websuche lassen die Recherche automatisch von einem anderen Anbieter mit Key erledigen
- Neues Einstellungsfenster: Zahnrad rechts oben (oder Hilfe → Einstellungen, Strg+K) mit den Reitern „KI-Anbieter & Keys“, „Darstellung“ und „Allgemein & Updates“
- Das Menü „Einstellungen“ und die drei Knöpfe in der Kopfleiste sind dafür entfallen
- Ergebnis-Ordner kann jetzt in den Einstellungen geändert werden
- Keys aus Umgebungsvariablen für alle Anbieter (z. B. OPENAI_API_KEY, ANTHROPIC_API_KEY, PERPLEXITY_API_KEY)
- Behoben: Schlägt ein Update fehl, wird die Fehlermeldung jetzt richtig angezeigt

## 1.1.1 – 2026-11-24
- Neu: Windows-Installer – Doppelklick auf „install-windows.cmd“ installiert die App unter Windows 10/11 (Startmenü, Desktop, „Apps & Features“ mit Deinstallation)
- Fehlt Python, bietet der Installer die automatische Installation per winget an
- Updates unter Windows: Python-Pakete werden beim nächsten Start aktualisiert (Windows sperrt geladene Dateien)
- Einstellungen und Keys liegen unter Windows in %APPDATA%\willhaben-agent

## 1.1.0 – 2026-11-24
- Komplett modernisiertes Design (Sun-Valley-Theme): Kopfleiste mit Farbverlauf und Schnellzugriffen, Fortschritts-Stepper, Kacheln für die Zähler, Akzent-Knopf zum Starten
- Neuer Dunkelmodus: Einstellungen → Design → Hell / Dunkel – alle Fenster passen sich an
- Neues Versionsschema: Ab jetzt 1.1.x, die letzte Stelle zählt die Änderungen seit 1.1.0
- Versionsverlauf im Über-Fenster kommt jetzt aus diesem Changelog (verständliche Einträge statt Commit-Texten)

## 1.0.9 – 2026-11-24
- Bezirksauswahl direkt unter dem Bundesland: „Bezirke …“ öffnet eine Liste aller Bezirke (live von willhaben, mit Suche und Anzeigenzahl)
- Bundesländer und einzelne Bezirke frei kombinierbar (z. B. ganz Niederösterreich + Favoriten)

## 1.0.8 – 2026-11-24
- Nur noch ein Startmenü-Eintrag; der doppelte Eintrag „… (mit Terminal)“ wird automatisch entfernt

## 1.0.7 – 2026-11-24
- Beim Start werden nicht benötigte Dateien aus der Installation entfernt (auch nach Updates von älteren Versionen)

## 1.0.6 – 2026-11-24
- Installer installiert nach ~/.local/share/willhaben-agent und behält nur die Dateien, die zum Betrieb nötig sind
- Der heruntergeladene Quellordner kann nach der Installation automatisch gelöscht werden
- Updates räumen den Installationsordner auf

## 1.0.5 – 2026-11-24
- Neues „Über“-Fenster mit Überblick, Funktionen, Ablauf, Versionsverlauf und Entwickler-Infos

## 1.0.4 – 2026-11-24
- Nur noch Google Gemini: Modell und Ausweichmodell aus der Liste der für den Key verfügbaren Modelle wählbar
- Mehrere Gemini-Keys mit automatischer Verteilung

## 1.0.3 – 2026-11-24
- Update-Prüfung robuster direkt nach einer neuen Veröffentlichung

## 1.0.2 – 2026-11-24
- Update-Funktion: Prüfung beim Start, Installation mit einem Klick, automatische Versionsnummer

## 1.0.1 – 2026-11-24
- Erste Version: vollständige willhaben-Suche, KI-Bewertung mit Google Gemini, Marktrecherche, Linux-Oberfläche
