#!/usr/bin/env bash
# Installiert den Willhaben KI-Agenten für den aktuellen Benutzer (kein root nötig, außer für fehlende Systempakete).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
echo "== Willhaben KI-Agent – Installation in $DIR"

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

# 2) Virtuelle Umgebung + Pakete
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

# 3) Startskripte
cat > willhaben-agent <<EOS
#!/usr/bin/env bash
# Startet die grafische Oberfläche. Im Terminal gestartet, erscheint das Protokoll zusätzlich hier.
exec "$DIR/.venv/bin/python" "$DIR/gui.py" "\$@"
EOS
cat > willhaben-agent-cli <<EOS
#!/usr/bin/env bash
# Terminal-Version ohne Fenster, z.B.:  ./willhaben-agent-cli --kategorie laptops --von 200 --bis 600 --bundesland wien
exec "$DIR/.venv/bin/python" "$DIR/agent.py" "\$@"
EOS
chmod +x willhaben-agent willhaben-agent-cli

# 4) Startmenü- und Desktop-Einträge
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS"
write_desktop() {  # $1=Datei $2=Name $3=Terminal(true/false)
cat > "$1" <<EOD
[Desktop Entry]
Type=Application
Name=$2
Comment=Durchsucht willhaben.at und bewertet Angebote mit KI
Exec=$DIR/willhaben-agent
Icon=$DIR/icon.png
Terminal=$3
Categories=Utility;Network;
StartupWMClass=willhaben-agent
EOD
chmod +x "$1"
}
write_desktop "$APPS/willhaben-agent.desktop" "Willhaben KI-Agent" false
write_desktop "$APPS/willhaben-agent-terminal.desktop" "Willhaben KI-Agent (mit Terminal)" true
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "✔ Startmenü-Einträge angelegt"

DESKTOP="$(command -v xdg-user-dir >/dev/null && xdg-user-dir DESKTOP || echo "$HOME/Desktop")"
if [ -d "$DESKTOP" ]; then
  cp "$APPS/willhaben-agent.desktop" "$DESKTOP/"
  chmod +x "$DESKTOP/willhaben-agent.desktop"
  command -v gio >/dev/null && gio set "$DESKTOP/willhaben-agent.desktop" metadata::trusted true 2>/dev/null || true
  echo "✔ Symbol auf dem Schreibtisch: $DESKTOP/willhaben-agent.desktop"
fi

echo
.venv/bin/python agent.py --version 2>/dev/null || true
echo
echo "Fertig! Starten über:"
echo "  • Startmenü / Schreibtisch: „Willhaben KI-Agent“"
echo "  • Terminal:  $DIR/willhaben-agent"
echo "Updates: beim Start automatisch, oder Einstellungen → „Nach Updates suchen …“ (Terminal: ./willhaben-agent-cli --update)"
