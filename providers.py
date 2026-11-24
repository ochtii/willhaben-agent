"""KI-Anbieter: Google Gemini.

Schnittstelle:
    call(key, model, prompt, schema, heavy) -> Antwort(parsed, tokens, info)
und meldet Probleme als ProviderFehler mit einer `art`:
    minute       Limit pro Minute erreicht   -> kurz warten oder anderen Key nehmen
    kosten       Modell ist für diesen Key kostenpflichtig (kein Guthaben) -> Modell überspringen
    tag          Tageslimit erreicht         -> Key bis zum Reset sperren
    key          Key ungültig/gesperrt       -> Key für diesen Lauf überspringen
    modell       Modell gibt es nicht        -> anderes Modell wählen
    zu_gross     Anfrage zu groß             -> Paket verkleinern
    ausgabe      kaputte/leere Antwort       -> Paket verkleinern / wiederholen
    ueberlastet  Server überlastet           -> warten und wiederholen
    region       im Land/Konto nicht nutzbar -> Key überspringen
    sonstiges
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


class ProviderFehler(Exception):
    def __init__(self, art: str, meldung: str, retry_after: float | None = None,
                 reset_at: float | None = None, info: dict | None = None):
        super().__init__(meldung)
        self.art = art
        self.meldung = meldung
        self.retry_after = retry_after
        self.reset_at = reset_at
        self.info = info or {}


@dataclass
class Antwort:
    parsed: BaseModel | str
    tokens: int = 0
    info: dict = field(default_factory=dict)   # Limits/Restwerte vom Server (falls geliefert)


def _dauer(s: str | None) -> float | None:
    """'2m59.56s', '7.66s', '1h2m', '120ms', '30' -> Sekunden."""
    if not s:
        return None
    s = str(s).strip()
    try:
        return float(s)
    except ValueError:
        pass
    total, found = 0.0, False
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|h|m|s)", s):
        found = True
        total += float(num) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    return total if found else None


def naechste_mitternacht_pt() -> float:
    """Gemini-Tageskontingente werden um Mitternacht pazifischer Zeit zurückgesetzt."""
    if ZoneInfo is None:
        now = datetime.now(timezone.utc) - timedelta(hours=8)
        return (datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1, hours=8)).timestamp()
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime.now(tz)
    nxt = datetime(now.year, now.month, now.day, tzinfo=tz) + timedelta(days=1)
    return nxt.timestamp()


def _json_aus_text(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    a, b = text.find("{"), text.rfind("}")
    return text[a:b + 1] if a != -1 and b > a else text


def schema_hinweis(schema: type[BaseModel]) -> str:
    return ("\n\nAntworte ausschließlich mit einem JSON-Objekt, das exakt diesem JSON-Schema entspricht "
            "(keine Erklärungen, kein Markdown):\n" + json.dumps(schema.model_json_schema(), ensure_ascii=False))


# --------------------------------------------------------------------------- Gemini

class GeminiProvider:
    name = "gemini"
    titel = "Google Gemini"
    key_url = "https://aistudio.google.com/apikey"
    limits_url = "https://aistudio.google.com/usage"
    standard_modell = "gemini-3.5-flash"  # gutes Preis/Leistungs-Modell
    ausweich_modell = "gemini-3.6-flash"  # wenn das Hauptmodell überlastet ist / fehlt
    kann_recherche = True                 # Google-Suche (Grounding) für die aktuelle Marktlage
    # Free Tier (beobachtet Nov. 2026): nur ca. 20 Anfragen pro Tag und MODELL, jedes Modell hat ein eigenes
    # Kontingent. Das Tageslimit wird deshalb pro Modell verwaltet (keys.Verteiler), hier nur Minutenwerte.
    standard_limits = {"rpm": 5, "rpd": None, "tpm": 250_000, "tpd": None}
    paket = 30          # Anzeigen pro KI-Anfrage (große Pakete = wenige Anfragen = Kontingent sparen)
    text_zeichen = 1200
    final_zeichen = 2500
    final_max = 30
    tageswechsel = staticmethod(naechste_mitternacht_pt)

    def __init__(self):
        from google import genai
        from google.genai import errors, types
        self._genai, self._errors, self._types = genai, errors, types
        self._clients: dict[str, object] = {}

    def _client(self, key: str):
        if key not in self._clients:
            # Zeitlimit pro Anfrage: überlastete Modelle hängen sonst minutenlang
            self._clients[key] = self._genai.Client(
                api_key=key, http_options=self._types.HttpOptions(timeout=150_000))
        return self._clients[key]

    def modelle(self, key: str) -> list[str]:
        try:
            out = []
            for m in self._client(key).models.list():
                name = (m.name or "").removeprefix("models/")
                if "generateContent" in (m.supported_actions or []) and name.startswith("gemini") and not any(
                        x in name for x in ("tts", "image", "embedding", "audio", "live", "robotics", "computer",
                                         "banana", "omni")):
                    out.append(name)
            return sorted(set(out))
        except self._errors.APIError as e:
            raise self._fehler(e) from e

    def bestes_modell(self, namen: list[str]) -> str | None:
        def rank(n):
            ver = [int(x) for x in re.findall(r"\d+", n)[:2]] or [0]
            return ("flash" in n and "lite" not in n, "preview" not in n and "exp" not in n, ver)
        return max(namen, key=rank) if namen else None

    def testen(self, key: str, model: str) -> dict:
        """Prüft den Key ohne Kontingent zu verbrauchen (Modellliste)."""
        namen = self.modelle(key)
        return {"ok": True, "text": f"{len(namen)} Modelle verfügbar", "modelle": namen}

    def _fehler(self, e) -> ProviderFehler:
        errors = self._errors
        txt = str(e)
        code = getattr(e, "code", None)
        msg = getattr(e, "message", None) or txt
        if code == 429:
            if re.search(r"PerDay|per day|daily", txt, re.I):
                m = re.search(r"retry in ([\dhms.]+)s?", txt)
                wait = _dauer(m.group(1) + ("s" if m and not m.group(1).endswith("s") else "")) if m else None
                return ProviderFehler("tag", "Tageskontingent erreicht",
                                      reset_at=(time.time() + wait) if wait else naechste_mitternacht_pt())
            m = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", txt)
            return ProviderFehler("minute", "Limit pro Minute erreicht", retry_after=float(m.group(1)) if m else 30.0)
        if code == 402 or re.search(r"prepayment credits|billing", txt, re.I) and code in (402, 403):
            return ProviderFehler("kosten", "Modell wäre kostenpflichtig – Prepay-Guthaben des Projekts ist leer "
                                  "(Anfrage abgelehnt, nichts berechnet)")
        if code == 404 or (code == 400 and re.search(
                r"only supports|not supported for generateContent|Interactions API|no longer available", txt, re.I)):
            return ProviderFehler("modell", f"Modell für diese Nutzung nicht verfügbar: {msg}")
        if code in (400, 401, 403) and re.search(r"API.?key|API_KEY|UNAUTHENTICATED|PERMISSION_DENIED", txt, re.I):
            return ProviderFehler("key", "Key ungültig oder ohne Berechtigung")
        if code == 400 and re.search(r"location|region|not supported in your country", txt, re.I):
            return ProviderFehler("region", "In deiner Region/deinem Konto nicht nutzbar (evtl. Abrechnung nötig)")
        if code == 400 and re.search(r"token|too large|exceeds", txt, re.I):
            return ProviderFehler("zu_gross", "Anfrage zu groß")
        if isinstance(e, errors.ServerError) or (code and code >= 500):
            return ProviderFehler("ueberlastet", f"Server ausgelastet ({code})", retry_after=10.0)
        return ProviderFehler("sonstiges", f"Gemini-Fehler {code}: {msg}")

    def recherche(self, key: str, model: str, prompt: str) -> Antwort:
        """Freitext-Antwort mit Google-Suche. parsed = Text, info['quellen'] = [(titel, url), ...]."""
        types = self._types
        try:
            resp = self._client(key).models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=("Du bist Marktanalyst für Gebrauchtwaren in Österreich. Nutze die Google-Suche "
                                        "für aktuelle Preise und Fakten. Antworte auf Deutsch, knapp in Stichpunkten."),
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.2, max_output_tokens=8192))
        except self._errors.APIError as e:
            raise self._fehler(e) from e
        except Exception as e:
            if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower():
                raise ProviderFehler("ueberlastet", "keine Antwort innerhalb von 150 s", retry_after=5.0) from e
            raise
        text = (resp.text or "").strip()
        if not text:
            raise ProviderFehler("ausgabe", "Leere Antwort der Marktrecherche")
        quellen = []
        gm = resp.candidates[0].grounding_metadata if resp.candidates else None
        for ch in (getattr(gm, "grounding_chunks", None) or []):
            web = getattr(ch, "web", None)
            if web and web.uri and (web.title, web.uri) not in quellen:
                quellen.append((web.title or web.domain or "Quelle", web.uri))
        um = getattr(resp, "usage_metadata", None)
        return Antwort(text, getattr(um, "total_token_count", 0) or 0,
                       {"quellen": quellen, "suchen": list(getattr(gm, "web_search_queries", None) or [])})

    def call(self, key: str, model: str, prompt: str, schema: type[BaseModel], heavy: bool) -> Antwort:
        types = self._types
        try:
            resp = self._client(key).models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=_system(), response_mime_type="application/json",
                    response_schema=schema, temperature=0.3 if heavy else 0.1, max_output_tokens=32768))
        except self._errors.APIError as e:
            raise self._fehler(e) from e
        except Exception as e:                   # Zeitüberschreitung / Netzwerk (httpx2, requests, …)
            if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower():
                raise ProviderFehler("ueberlastet", "keine Antwort innerhalb von 150 s", retry_after=5.0) from e
            if "connect" in type(e).__name__.lower():
                raise ProviderFehler("ueberlastet", f"Netzwerkfehler: {e}", retry_after=5.0) from e
            raise
        tokens = getattr(getattr(resp, "usage_metadata", None), "total_token_count", None) or 0
        parsed = resp.parsed
        if parsed is None:
            text = resp.text or ""
            if not text.strip():
                reason = resp.candidates[0].finish_reason if resp.candidates else "unbekannt"
                raise ProviderFehler("ausgabe", f"Leere Antwort (Grund: {reason})", info={"tokens": tokens})
            try:
                parsed = schema.model_validate_json(_json_aus_text(text))
            except Exception as e:
                raise ProviderFehler("ausgabe", f"Antwort nicht lesbar ({type(e).__name__})", info={"tokens": tokens}) from e
        return Antwort(parsed, tokens, {})


def _system() -> str:
    from rating import SYSTEM
    return SYSTEM


PROVIDER_KLASSEN = {"gemini": GeminiProvider}
PROVIDER_TITEL = {"gemini": GeminiProvider.titel}
