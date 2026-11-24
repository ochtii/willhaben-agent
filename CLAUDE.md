# Willhaben KI-Agent – Regeln für die Entwicklung

## Bei JEDEM Push (Pflicht)
1. **README.md** an alle Änderungen anpassen (Funktionen, Bedienung, Dateiliste).
2. **Über-Fenster** (`about_dialog.py`) aktualisieren: Reiter „Überblick“, „Funktionen“ und
   „So funktioniert's“ müssen den aktuellen Funktionsumfang zeigen.
3. **Versionsverlauf** (`CHANGELOG.md`) um einen Eintrag für die neue Version ergänzen
   (verständliche Stichpunkte für Nutzer, keine Commit-Texte). Format:
   `## 1.1.3 – JJJJ-MM-TT` gefolgt von `- …`-Zeilen. Die App liest genau dieses Format.

## Versionsnummer
- `<VERSION>.<N>`: `VERSION` enthält z. B. `1.1`; **N = Anzahl der Commits seit der letzten Änderung
  der Datei `VERSION`** (der Commit, der `VERSION` ändert, ist `.0`).
- Nächste Version bestimmen: `git log -1 --format=%H -- VERSION` → `git rev-list --count <sha>..HEAD`,
  das Ergebnis **+1** ist die Nummer des nächsten Commits (bei geändertem `VERSION` → `.0`).
- Größere Sprünge (z. B. 1.2.0) = `VERSION` ändern.
- Ein Push soll möglichst **ein** Commit sein, damit Changelog-Eintrag und Versionsnummer übereinstimmen.

## Dateien
- Neue Programmdateien in **`laufzeit-dateien.txt`** eintragen – Installer und Updater kopieren nur
  diese Dateien und löschen im Installationsordner alles andere.
- Neue Python-Pakete in `requirements.txt` eintragen (der Updater installiert sie nach).

## Design
- Farben nie fest eintragen, sondern aus `theme.P` (Hell/Dunkel-Palette) nehmen.
- Oberfläche: Tkinter + sv-ttk; keine Farb-Emojis in Tk-Widgets (siehe `tk_safe` in `gui.py`).

## Prüfen vor dem Push
- `python -c "import gui, agent, keys, keys_dialog, pipeline, rating, providers, updater, about_dialog, bezirk_dialog, theme"`
- GUI in Hell und Dunkel unter `xvfb-run` ansehen, wenn sich die Oberfläche ändert.
