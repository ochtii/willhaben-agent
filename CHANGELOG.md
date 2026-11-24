# Versionsverlauf

Die Versionsnummer lautet `<VERSION>.<N>`: `VERSION` steht in der gleichnamigen Datei (z. B. `1.1`),
**N** zählt die Commits seit der letzten Änderung dieser Datei und steigt mit jedem Push automatisch.
Die App zeigt diesen Verlauf unter Hilfe → Über → „Neuigkeiten“.

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
