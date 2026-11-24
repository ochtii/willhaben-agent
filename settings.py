"""Speichert die letzten Eingaben in config.json im Konfigurationsordner
(Linux: ~/.config/willhaben-agent, Windows: %APPDATA%\\willhaben-agent)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from plattform import konfig_ordner

CONFIG_DIR = konfig_ordner()
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_OUTPUT = str(Path.home() / "willhaben-ergebnisse")


def load() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    try:
        os.chmod(tmp, 0o600)      # nur für den eigenen Benutzer lesbar (unter Windows ohne Wirkung)
    except OSError:
        pass
    tmp.replace(CONFIG_FILE)
