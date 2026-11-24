"""Speichert die letzten Eingaben und (optional) den API-Key in ~/.config/willhaben-agent/config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "willhaben-agent"
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
    os.chmod(tmp, 0o600)          # Key nur für den eigenen Benutzer lesbar
    tmp.replace(CONFIG_FILE)


def api_key(anbieter: str = "gemini") -> str:
    """Key aus Umgebungsvariable oder gespeicherter Konfiguration."""
    if anbieter.startswith("claude"):
        return os.environ.get("ANTHROPIC_API_KEY", "") or load().get("claude_api_key", "")
    return (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            or load().get("gemini_api_key", ""))
