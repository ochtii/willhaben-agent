"""Unterschiede zwischen Windows und Linux an einer Stelle."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

IST_WINDOWS = os.name == "nt"

# Schriften, die auf dem jeweiligen System sicher vorhanden sind
MONO = "Consolas" if IST_WINDOWS else "DejaVu Sans Mono"
SYMBOL = "Segoe UI Symbol" if IST_WINDOWS else "DejaVu Sans"

# Unter Windows bei Hintergrundprozessen kein Konsolenfenster aufblitzen lassen
OHNE_FENSTER = {"creationflags": 0x08000000} if IST_WINDOWS else {}   # CREATE_NO_WINDOW


def konfig_ordner() -> Path:
    """Ordner für Einstellungen und Keys: %APPDATA%\\willhaben-agent bzw. ~/.config/willhaben-agent."""
    if IST_WINDOWS:
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "willhaben-agent"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "willhaben-agent"


def oeffnen(pfad) -> None:
    """Datei/Ordner/URL mit dem Standardprogramm öffnen."""
    s = str(pfad)
    try:
        if IST_WINDOWS:
            os.startfile(s)                                    # noqa: S606 (nur Windows)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", s], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", s], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        import webbrowser
        webbrowser.open(s if s.startswith("http") else Path(s).resolve().as_uri())


def python_konsole() -> str:
    """Python-Programm mit Konsole (für pip) – auch wenn die App mit pythonw.exe läuft."""
    exe = Path(sys.executable)
    if IST_WINDOWS and exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return str(exe)


def neu_starten() -> None:
    """Das laufende Programm mit denselben Argumenten neu starten."""
    if IST_WINDOWS:
        subprocess.Popen([sys.executable] + sys.argv, close_fds=True,
                         creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        os._exit(0)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def ausgabe_absichern() -> None:
    """Emojis in der Konsolenausgabe dürfen nie zum Absturz führen (Windows-Codepages)."""
    for strom in (sys.stdout, sys.stderr):
        try:
            if strom is not None:
                strom.reconfigure(errors="replace")
        except Exception:
            pass


def installations_hinweis() -> str:
    if IST_WINDOWS:
        return ("Tipp: Diese App läuft direkt aus dem Quellordner. Einmal „install-windows.cmd“ ausführen – dann "
                "liegen nur noch die benötigten Dateien unter %LOCALAPPDATA%\\willhaben-agent und der Quellordner "
                "kann weg.")
    return ("Tipp: Diese App läuft direkt aus dem Quellordner. Einmal ./install.sh ausführen – dann liegen nur noch "
            "die benötigten Dateien unter ~/.local/share/willhaben-agent und der Quellordner kann weg.")


def windows_version_eintragen(version: str) -> None:
    """Windows: angezeigte Version unter „Apps & Features“ aktuell halten (falls per Installer eingetragen)."""
    if not IST_WINDOWS:
        return
    try:
        import winreg
        pfad = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\WillhabenKIAgent"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, pfad, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            if winreg.QueryValueEx(k, "DisplayVersion")[0] != version:
                winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, version)
    except OSError:
        pass
