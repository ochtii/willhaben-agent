"""KI-Anbieter: Google Gemini und Groq.

Jeder Anbieter hat eine einheitliche Schnittstelle:
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

import requests
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
    standard_modell = "gemini-3.5-flash"  # gutes Preis/Leistungs-Modell; "auto" = neuestes Flash-Modell
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
                        x in name for x in ("tts", "image", "embedding", "audio", "live", "robotics", "computer")):
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


# --------------------------------------------------------------------------- Groq

class GroqProvider:
    name = "groq"
    titel = "Groq"
    key_url = "https://console.groq.com/keys"
    limits_url = "https://console.groq.com/settings/limits"
    standard_modell = "auto"
    ausweich_modell = "llama-3.3-70b-versatile"
    kann_recherche = False      # keine Websuche -> Marktlage nur aus den willhaben-Daten
    # Annahmen bis der Server echte Werte liefert (Header x-ratelimit-*)
    standard_limits = {"rpm": 30, "rpd": 1000, "tpm": 6000, "tpd": 100_000}
    # Groq-Free-Tier hat kleine Token-pro-Minute-Limits -> kleinere Pakete
    paket = 6
    text_zeichen = 700
    final_zeichen = 450
    final_max = 16
    URL = "https://api.groq.com/openai/v1"
    BEVORZUGT = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "moonshotai/kimi-k2-instruct-0905",
                 "moonshotai/kimi-k2-instruct", "qwen/qwen3-32b", "meta-llama/llama-4-maverick-17b-128e-instruct",
                 "openai/gpt-oss-20b", "llama-3.1-8b-instant"]

    @staticmethod
    def tageswechsel() -> float:
        """Für die lokale Tageszählung: Mitternacht UTC (Groq selbst rechnet rollierend, siehe Header)."""
        now = datetime.now(timezone.utc)
        return (datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)).timestamp()

    def __init__(self):
        self.s = requests.Session()

    def _headers(self, key):
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def modelle(self, key: str) -> list[str]:
        try:
            r = self.s.get(f"{self.URL}/models", headers=self._headers(key), timeout=20)
        except requests.RequestException as e:
            raise ProviderFehler("ueberlastet", f"Netzwerkfehler: {e}", retry_after=5.0) from e
        if r.status_code != 200:
            raise self._fehler(r)
        namen = [m.get("id") for m in r.json().get("data", []) if m.get("active", True)]
        return sorted(n for n in namen if n and not re.search(r"whisper|guard|tts|playai|orpheus|compound|prompt", n))

    def bestes_modell(self, namen: list[str]) -> str | None:
        for n in self.BEVORZUGT:
            if n in namen:
                return n
        big = [n for n in namen if re.search(r"70b|120b|maverick|kimi|32b", n)]
        return (big or namen or [None])[0]

    @staticmethod
    def _info(r: requests.Response) -> dict:
        h = r.headers
        def num(k):
            try:
                return int(float(h.get(k)))
            except (TypeError, ValueError):
                return None
        info = {
            "rpd": num("x-ratelimit-limit-requests"),
            "rest_anfragen": num("x-ratelimit-remaining-requests"),
            "reset_anfragen": _dauer(h.get("x-ratelimit-reset-requests")),
            "tpm": num("x-ratelimit-limit-tokens"),
            "rest_token": num("x-ratelimit-remaining-tokens"),
            "reset_token": _dauer(h.get("x-ratelimit-reset-tokens")),
            "zeit": time.time(),
        }
        return {k: v for k, v in info.items() if v is not None}

    def _fehler(self, r: requests.Response) -> ProviderFehler:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        msg = err.get("message") or r.text[:300]
        code = err.get("code") or ""
        info = self._info(r)
        retry = _dauer(r.headers.get("retry-after"))
        s = r.status_code
        if s in (401,) or code == "invalid_api_key":
            return ProviderFehler("key", "Key ungültig", info=info)
        if s == 403:
            if re.search(r"region|country|location", msg, re.I):
                return ProviderFehler("region", "In deiner Region nicht nutzbar", info=info)
            return ProviderFehler("key", f"Zugriff verweigert: {msg}", info=info)
        if s == 404 or code == "model_not_found" or "model_decommissioned" in str(code):
            return ProviderFehler("modell", f"Modell nicht verfügbar: {msg}", info=info)
        if s == 413 or code in ("request_too_large", "context_length_exceeded") or "too large" in msg.lower():
            return ProviderFehler("zu_gross", "Anfrage zu groß für das Limit", info=info)
        if s == 429:
            if re.search(r"per day|\(TPD\)|\(RPD\)", msg, re.I):
                wait = retry or _dauer((re.search(r"try again in ([\dhms.]+)", msg) or [None, None])[1]) or 3600
                return ProviderFehler("tag", "Tageslimit erreicht", reset_at=time.time() + wait, info=info)
            wait = retry or _dauer((re.search(r"try again in ([\dhms.]+)", msg) or [None, None])[1]) or 20
            return ProviderFehler("minute", "Limit pro Minute erreicht", retry_after=wait, info=info)
        if s == 400 and ("json_validate_failed" in str(code) or "json" in msg.lower()):
            return ProviderFehler("ausgabe", "Antwort war kein gültiges JSON", info=info)
        if s in (498, 500, 502, 503, 504):
            return ProviderFehler("ueberlastet", f"Server ausgelastet ({s})", retry_after=retry or 10, info=info)
        return ProviderFehler("sonstiges", f"Groq-Fehler {s}: {msg}", info=info)

    def _post(self, key, body) -> requests.Response:
        try:
            return self.s.post(f"{self.URL}/chat/completions", headers=self._headers(key), json=body, timeout=180)
        except requests.RequestException as e:
            raise ProviderFehler("ueberlastet", f"Netzwerkfehler: {e}", retry_after=5.0) from e

    def testen(self, key: str, model: str) -> dict:
        """Mini-Anfrage (1 Token), damit Groq die aktuellen Limits/Restwerte mitschickt."""
        namen = self.modelle(key)
        m = model if model and model != "auto" and model in namen else self.bestes_modell(namen)
        r = self._post(key, {"model": m, "messages": [{"role": "user", "content": "ok"}], "max_completion_tokens": 1})
        info = self._info(r)
        if r.status_code not in (200, 429):
            raise self._fehler(r)
        return {"ok": True, "text": f"{len(namen)} Modelle, Test mit {m}", "modelle": namen, "info": info}

    def call(self, key: str, model: str, prompt: str, schema: type[BaseModel], heavy: bool) -> Antwort:
        body = {
            "model": model,
            "messages": [{"role": "system", "content": _system()},
                         {"role": "user", "content": prompt + schema_hinweis(schema)}],
            "temperature": 0.3 if heavy else 0.1,
            "max_completion_tokens": 6000 if heavy else 3500,
            "response_format": {"type": "json_object"},
        }
        r = self._post(key, body)
        if r.status_code != 200:
            raise self._fehler(r)
        info = self._info(r)
        data = r.json()
        tokens = (data.get("usage") or {}).get("total_tokens", 0)
        try:
            content = data["choices"][0]["message"]["content"] or ""
            parsed = schema.model_validate_json(_json_aus_text(content))
        except Exception as e:
            raise ProviderFehler("ausgabe", f"Antwort nicht lesbar ({type(e).__name__})",
                                 info={**info, "tokens": tokens}) from e
        return Antwort(parsed, tokens, info)


def _system() -> str:
    from rating import SYSTEM
    return SYSTEM


PROVIDER_KLASSEN = {"gemini": GeminiProvider, "groq": GroqProvider}
PROVIDER_TITEL = {"gemini": GeminiProvider.titel, "groq": GroqProvider.titel}
