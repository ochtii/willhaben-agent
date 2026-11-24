#!/usr/bin/env bash
# Installiert den Willhaben KI-Agenten für den aktuellen Benutzer (kein root nötig, außer für fehlende Systempakete).
#
# Ins Installationsverzeichnis (Standard: ~/.local/share/willhaben-agent) kommen NUR die Dateien aus
# laufzeit-dateien.txt – alles andere (README, Anleitung, Installer, Git-Daten …) wird dort entfernt.
# Danach kann der heruntergeladene Quellordner gelöscht werden (der Installer fragt nach).
#
# Optionen:
#   --quelle-behalten   Quellordner nicht löschen und nicht danach fragen
#   --quelle-loeschen   Quellordner ohne Rückfrage löschen (außer bei ungesicherten Git-Änderungen)
#   Ziel ändern:        WILLHABEN_AGENT_HOME=/pfad ./install.sh
set -euo pipefail

QUELLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIEL="${WILLHABEN_AGENT_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/willhaben-agent}"
BIN="$HOME/.local/bin"
QUELLE_MODUS="fragen"
for arg in "$@"; do
  case "$arg" in
    --quelle-behalten) QUELLE_MODUS="behalten" ;;
    --quelle-loeschen) QUELLE_MODUS="loeschen" ;;
    *) echo "Unbekannte Option: $arg"; exit 1 ;;
  esac
done

echo "== Willhaben KI-Agent – Installation nach $ZIEL"
[ -f "$QUELLE/laufzeit-dateien.txt" ] || { echo "❌ laufzeit-dateien.txt fehlt in $QUELLE"; exit 1; }

# 1) Python mit Tkinter + venv finden (ggf. Systempakete nachinstallieren)
find_python() {
  for p in python3 python3.13 python3.12 python3.11 python3.10; do
    if command -v "$p" >/dev/null && "$p" -c "import tkinter, venv, ensurepip" 2>/dev/null; then
      echo "$p"; return 0
    fi
  done
  return 1
}
PY="$(find_python || true)"
if [ -z "$PY" ]; then
  echo "⚠ Python-Tkinter oder venv fehlt – installiere Systempakete (Passwort nötig) …"
  if command -v apt-get >/dev/null; then
    sudo apt-get install -y python3 python3-tk python3-venv
  elif command -v dnf >/dev/null; then
    sudo dnf install -y python3 python3-tkinter
  elif command -v pacman >/dev/null; then
    sudo pacman -S --noconfirm python tk
  elif command -v zypper >/dev/null; then
    sudo zypper install -y python3 python3-tk
  fi
  PY="$(find_python || true)"
fi
if [ -z "$PY" ]; then
  echo "❌ Kein Python mit Tkinter gefunden. Bitte 'python3-tk' und 'python3-venv' installieren."; exit 1
fi
echo "✔ Verwende $($PY --version) ($(command -v $PY))"

# 2) Nur die benötigten Dateien ins Installationsverzeichnis kopieren
mkdir -p "$ZIEL"
if [ "$QUELLE" != "$ZIEL" ]; then
  anzahl=0
  while IFS= read -r datei || [ -n "$datei" ]; do
    datei="${datei%%#*}"; datei="$(echo "$datei" | xargs)"
    [ -z "$datei" ] && continue
    [ -f "$QUELLE/$datei" ] || { echo "❌ $datei fehlt in $QUELLE"; exit 1; }
    mkdir -p "$ZIEL/$(dirname "$datei")"
    cp -p "$QUELLE/$datei" "$ZIEL/$datei"
    anzahl=$((anzahl + 1))
  done < "$QUELLE/laufzeit-dateien.txt"
  echo "✔ $anzahl Programmdateien nach $ZIEL kopiert"
fi

# 3) Virtuelle Umgebung + Pakete (im Installationsverzeichnis)
cd "$ZIEL"
if [ -x .venv/bin/python ] && ! .venv/bin/python -c "import tkinter" 2>/dev/null; then
  rm -rf .venv   # alte Umgebung ohne Tkinter ersetzen
fi
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
.venv/bin/python -c "import tkinter, requests, pydantic; from google import genai" \
  || { echo "❌ Installation unvollständig"; exit 1; }
echo "✔ Python-Pakete installiert"

# 4) Installierten Stand merken (für die Update-Prüfung) und Installationsverzeichnis aufräumen
if command -v git >/dev/null && git -C "$QUELLE" rev-parse HEAD >/dev/null 2>&1; then
  SHA="$(git -C "$QUELLE" rev-parse HEAD)"
  NUMMER="?"
  if [ "$(git -C "$QUELLE" rev-parse --is-shallow-repository)" = "false" ]; then
    # letzte Stelle der Version = Commits seit der letzten Änderung der VERSION-Datei
    V_COMMIT="$(git -C "$QUELLE" log -1 --format=%H -- VERSION)"
    if [ -n "$V_COMMIT" ]; then
      NUMMER="$(git -C "$QUELLE" rev-list --count "$V_COMMIT..HEAD")"
    else
      NUMMER="$(git -C "$QUELLE" rev-list --count HEAD)"
    fi
  fi
  .venv/bin/python updater.py --status "$SHA" "$NUMMER"
else
  # ZIP ohne Git: Stand von GitHub übernehmen, wenn die Dateien dem neuesten Stand entsprechen
  .venv/bin/python updater.py --status-vom-server || true
fi
.venv/bin/python updater.py --aufraeumen

# 5) Startskripte
cat > willhaben-agent <<EOS
#!/usr/bin/env bash
# Startet die grafische Oberfläche. Im Terminal gestartet, erscheint das Protokoll zusätzlich hier.
exec "$ZIEL/.venv/bin/python" "$ZIEL/gui.py" "\$@"
EOS
cat > willhaben-agent-cli <<EOS
#!/usr/bin/env bash
# Terminal-Version ohne Fenster, z.B.:  willhaben-agent-cli --kategorie laptops --von 200 --bis 600 --bundesland wien
exec "$ZIEL/.venv/bin/python" "$ZIEL/agent.py" "\$@"
EOS
chmod +x willhaben-agent willhaben-agent-cli
mkdir -p "$BIN"
ln -sf "$ZIEL/willhaben-agent" "$BIN/willhaben-agent"
ln -sf "$ZIEL/willhaben-agent-cli" "$BIN/willhaben-agent-cli"
echo "✔ Startbefehle: $BIN/willhaben-agent, $BIN/willhaben-agent-cli"

# 6) Startmenü- und Desktop-Einträge
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
write_desktop() {  # $1=Datei $2=Name $3=Terminal(true/false)
cat > "$1" <<EOD
[Desktop Entry]
Type=Application
Name=$2
Comment=Durchsucht willhaben.at und bewertet Angebote mit KI
Exec=$ZIEL/willhaben-agent
Icon=$ZIEL/icon.png
Terminal=$3
Categories=Utility;Network;
StartupWMClass=willhaben-agent
EOD
chmod +x "$1"
}
write_desktop "$APPS/willhaben-agent.desktop" "Willhaben KI-Agent" false
rm -f "$APPS/willhaben-agent-terminal.desktop"      # früherer zweiter Eintrag (mit Terminal) – nicht mehr nötig
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "✔ Startmenü-Eintrag angelegt"

DESKTOP="$(command -v xdg-user-dir >/dev/null && xdg-user-dir DESKTOP || echo "$HOME/Desktop")"
if [ -d "$DESKTOP" ]; then
  cp "$APPS/willhaben-agent.desktop" "$DESKTOP/"
  chmod +x "$DESKTOP/willhaben-agent.desktop"
  command -v gio >/dev/null && gio set "$DESKTOP/willhaben-agent.desktop" metadata::trusted true 2>/dev/null || true
  echo "✔ Symbol auf dem Schreibtisch: $DESKTOP/willhaben-agent.desktop"
fi

echo
.venv/bin/python agent.py --version 2>/dev/null || true

# 7) Heruntergeladenen Quellordner entfernen (wird nicht mehr benötigt)
if [ "$QUELLE" != "$ZIEL" ]; then
  # Reste einer älteren Installation direkt im Quellordner (vor v1.0.6) entfernen
  rm -rf "$QUELLE/.venv" "$QUELLE/willhaben-agent" "$QUELLE/willhaben-agent-cli" "$QUELLE/.installed_version.json"

  sicher=true      # nur löschen, was eindeutig ein Quellordner dieses Projekts ist
  case "$QUELLE" in "/"|"$HOME"|"$HOME/"|"$ZIEL"|"$ZIEL"/*) sicher=false ;; esac
  case "$ZIEL" in "$QUELLE"/*) sicher=false ;; esac
  [ -f "$QUELLE/install.sh" ] && [ -f "$QUELLE/laufzeit-dateien.txt" ] || sicher=false

  standard="j"
  if [ -d "$QUELLE/.git" ] && command -v git >/dev/null; then
    if [ -n "$(git -C "$QUELLE" status --porcelain 2>/dev/null)" ] || \
       [ -n "$(git -C "$QUELLE" log --branches --not --remotes --oneline 2>/dev/null | head -1)" ]; then
      echo "⚠ $QUELLE enthält ungespeicherte oder nicht gepushte Git-Änderungen."
      standard="n"
      [ "$QUELLE_MODUS" = "loeschen" ] && QUELLE_MODUS="fragen"
    fi
  fi

  if [ "$sicher" = true ] && [ "$QUELLE_MODUS" != "behalten" ]; then
    antwort="$standard"
    if [ "$QUELLE_MODUS" = "fragen" ]; then
      if [ -t 0 ]; then
        hinweis="[J/n]"; [ "$standard" = "n" ] && hinweis="[j/N]"
        read -r -p "Der Quellordner $QUELLE wird nicht mehr benötigt. Löschen? $hinweis " antwort || antwort=""
        antwort="${antwort:-$standard}"
      else
        antwort="n"   # ohne Terminal nie ungefragt löschen
      fi
    fi
    case "$antwort" in
      j|J|ja|Ja|y|Y)
        cd "$HOME"
        rm -rf -- "$QUELLE"
        echo "✔ Quellordner entfernt: $QUELLE" ;;
      *)
        echo "ℹ Quellordner behalten: $QUELLE (kann jederzeit gelöscht werden)" ;;
    esac
  fi
fi

echo
echo "Fertig! Starten über:"
echo "  • Startmenü / Schreibtisch: „Willhaben KI-Agent“"
echo "  • Terminal:  willhaben-agent   (bzw. $ZIEL/willhaben-agent)"
echo "Updates: beim Start automatisch, oder Einstellungen → „Nach Updates suchen …“ (Terminal: willhaben-agent-cli --update)"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Hinweis: $BIN ist nicht im PATH – ggf. neu anmelden oder den vollen Pfad nutzen." ;; esac
