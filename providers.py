"""KI-Anbieter: Google Gemini (Standard), OpenAI/ChatGPT, Anthropic Claude, Perplexity, Mistral, DeepSeek,
xAI Grok, Groq, OpenRouter, Together AI und eigene OpenAI-kompatible Schnittstellen.

Schnittstelle jedes Anbieters:
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


def naechste_mitternacht() -> float:
    """Tageszähler der übrigen Anbieter: Mitternacht Ortszeit."""
    jetzt = datetime.now()
    return (datetime(jetzt.year, jetzt.month, jetzt.day) + timedelta(days=1)).timestamp()


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

    @classmethod
    def bestes_modell(cls, namen: list[str]) -> str | None:
        if cls.standard_modell in namen:
            return cls.standard_modell

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


# --------------------------------------------------------------------------- OpenAI-kompatible Anbieter

class OpenAIKompatibel:
    """Alle Anbieter mit OpenAI-kompatibler Chat-Schnittstelle (/chat/completions, /models)."""
    name = "openai"
    titel = "OpenAI (ChatGPT)"
    basis_url = "https://api.openai.com/v1"
    key_url = "https://platform.openai.com/api-keys"
    limits_url = "https://platform.openai.com/settings/organization/limits"
    env_vars: list[str] = ["OPENAI_API_KEY"]
    standard_modell = "gpt-5-mini"
    ausweich_modell = "gpt-5"
    kann_recherche = False
    standard_limits = {"rpm": None, "rpd": None, "tpm": None, "tpd": None}
    paket = 30
    text_zeichen = 1200
    final_zeichen = 2500
    final_max = 30
    json_modus = "objekt"              # "objekt" = response_format json_object, "schema" = json_schema, "" = nur Prompt
    token_parameter = "max_tokens"
    mit_temperatur = True
    feste_modelle: list[str] = []      # falls der Anbieter keine Modellliste liefert
    modell_filter = ()                 # Teilstrings, die nicht in der Auswahl erscheinen sollen
    hinweis = ""
    tageswechsel = staticmethod(naechste_mitternacht)

    def __init__(self):
        import requests
        self._requests = requests
        self._session = requests.Session()

    # -- Hilfen
    def _url(self) -> str:
        return (self.basis_url or "").rstrip("/")

    def _kopf(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _anfrage(self, methode: str, pfad: str, key: str, json_daten: dict | None = None, timeout: float = 150):
        if not self._url():
            raise ProviderFehler("key", "Keine Adresse (Basis-URL) eingetragen – in den Einstellungen ergänzen")
        try:
            r = self._session.request(methode, self._url() + pfad, headers=self._kopf(key), json=json_daten,
                                      timeout=timeout)
        except self._requests.Timeout as e:
            raise ProviderFehler("ueberlastet", f"keine Antwort innerhalb von {timeout:.0f} s", retry_after=5.0) from e
        except self._requests.RequestException as e:
            raise ProviderFehler("ueberlastet", f"Netzwerkfehler: {e}", retry_after=5.0) from e
        if r.status_code >= 400:
            raise self._fehler(r)
        try:
            return r, r.json()
        except ValueError as e:
            raise ProviderFehler("ausgabe", "Antwort des Servers nicht lesbar") from e

    def _server_info(self, r) -> dict:
        h = r.headers
        info = {}
        for feld, kopf in (("rest_anfragen", "x-ratelimit-remaining-requests"),
                           ("rest_token", "x-ratelimit-remaining-tokens")):
            try:
                if h.get(kopf) is not None:
                    info[feld] = int(float(h[kopf]))
            except ValueError:
                pass
        for feld, kopf in (("reset_anfragen", "x-ratelimit-reset-requests"),
                           ("reset_token", "x-ratelimit-reset-tokens")):
            d = _dauer(h.get(kopf))
            if d is not None:
                info[feld] = d
        if info:
            info["zeit"] = time.time()
        return info

    def _fehler(self, r) -> ProviderFehler:
        code = r.status_code
        try:
            daten = r.json()
            err = daten.get("error", daten) if isinstance(daten, dict) else {}
            msg = (err.get("message") if isinstance(err, dict) else str(err)) or r.text
        except ValueError:
            msg = r.text
        msg = str(msg)[:300]
        txt = (msg + " " + r.text[:500]).lower()
        warte = _dauer(r.headers.get("retry-after"))
        if code in (401, 403) and not re.search(r"region|country|location", txt):
            return ProviderFehler("key", "Key ungültig oder ohne Berechtigung")
        if code == 402 or re.search(r"insufficient_quota|insufficient balance|credit|billing|payment", txt):
            return ProviderFehler("kosten", "Kein Guthaben/Kontingent mehr beim Anbieter (Abrechnung prüfen)")
        if code == 403:
            return ProviderFehler("region", "In deiner Region/deinem Konto nicht nutzbar")
        if code == 429:
            if re.search(r"per day|daily|requests per day|tokens per day|\brpd\b|\btpd\b", txt):
                return ProviderFehler("tag", "Tageslimit erreicht",
                                      reset_at=time.time() + warte if warte else self.tageswechsel())
            return ProviderFehler("minute", "Limit pro Minute erreicht", retry_after=warte or 20.0,
                                  info=self._server_info(r))
        if code == 404 or (code == 400 and re.search(r"model.*(not found|does not exist|invalid|not available)|"
                                                     r"(unknown|invalid) model", txt)):
            return ProviderFehler("modell", f"Modell nicht verfügbar: {msg}")
        if code in (400, 413) and re.search(r"context|too long|too large|maximum.*tokens|exceed", txt):
            return ProviderFehler("zu_gross", "Anfrage zu groß")
        if code >= 500 or code == 529:
            return ProviderFehler("ueberlastet", f"Server ausgelastet ({code})", retry_after=warte or 10.0)
        return ProviderFehler("sonstiges", f"{self.titel}-Fehler {code}: {msg}")

    # -- Schnittstelle
    def modelle(self, key: str) -> list[str]:
        if self.feste_modelle:
            return list(self.feste_modelle)
        _, daten = self._anfrage("GET", "/models", key, timeout=30)
        liste = daten.get("data", daten) if isinstance(daten, dict) else daten
        namen = [m.get("id") for m in liste or [] if isinstance(m, dict) and m.get("id")]
        return sorted({n for n in namen if not any(x in n.lower() for x in self.modell_filter)})

    @classmethod
    def bestes_modell(cls, namen: list[str]) -> str | None:
        if not namen:
            return None
        for m in (cls.standard_modell, cls.ausweich_modell):
            if m in namen:
                return m
        return namen[0]

    def testen(self, key: str, model: str) -> dict:
        if self.feste_modelle:
            # keine Modellliste beim Anbieter -> Mini-Anfrage (kostet nur wenige Token)
            r, _ = self._anfrage("POST", "/chat/completions", key, self._koerper(
                model or self.standard_modell, [{"role": "user", "content": "Antworte nur mit OK."}], 5, False),
                timeout=60)
            return {"ok": True, "text": "Antwort erhalten", "modelle": list(self.feste_modelle),
                    "info": self._server_info(r)}
        namen = self.modelle(key)
        return {"ok": True, "text": f"{len(namen)} Modelle verfügbar", "modelle": namen}

    def _koerper(self, model: str, nachrichten: list, max_token: int, json_antwort: bool,
                 schema: type[BaseModel] | None = None, temperatur: float = 0.2) -> dict:
        k = {"model": model, "messages": nachrichten, self.token_parameter: max_token}
        if self.mit_temperatur:
            k["temperature"] = temperatur
        if json_antwort and self.json_modus == "objekt":
            k["response_format"] = {"type": "json_object"}
        elif json_antwort and self.json_modus == "schema" and schema is not None:
            k["response_format"] = {"type": "json_schema",
                                    "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}
        return k

    def _chat(self, key: str, koerper: dict):
        try:
            return self._anfrage("POST", "/chat/completions", key, koerper)
        except ProviderFehler as f:
            # Manche Modelle (z.B. Reasoning-Modelle) lehnen einzelne Parameter ab -> einmal ohne versuchen
            if f.art != "sonstiges" or not re.search(r"temperature|max_tokens|response_format|unsupported", f.meldung, re.I):
                raise
            k = dict(koerper)
            k.pop("temperature", None)
            if "max_tokens" in k and re.search(r"max_tokens", f.meldung, re.I):
                k["max_completion_tokens"] = k.pop("max_tokens")
            if re.search(r"response_format", f.meldung, re.I):
                k.pop("response_format", None)
            return self._anfrage("POST", "/chat/completions", key, k)

    def call(self, key: str, model: str, prompt: str, schema: type[BaseModel], heavy: bool) -> Antwort:
        nachrichten = [{"role": "system", "content": _system()},
                       {"role": "user", "content": prompt + schema_hinweis(schema)}]
        r, daten = self._chat(key, self._koerper(model, nachrichten, 16000, True, schema, 0.3 if heavy else 0.1))
        tokens = int((daten.get("usage") or {}).get("total_tokens") or 0)
        try:
            wahl = daten["choices"][0]
            text = wahl["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            raise ProviderFehler("ausgabe", "Leere Antwort", info={"tokens": tokens})
        if isinstance(text, list):                   # manche Anbieter liefern Inhalts-Blöcke
            text = "".join(t.get("text", "") for t in text if isinstance(t, dict))
        if not text.strip():
            raise ProviderFehler("ausgabe", f"Leere Antwort (Grund: {wahl.get('finish_reason')})", info={"tokens": tokens})
        try:
            parsed = schema.model_validate_json(_json_aus_text(text))
        except Exception as e:
            raise ProviderFehler("ausgabe", f"Antwort nicht lesbar ({type(e).__name__})", info={"tokens": tokens}) from e
        return Antwort(parsed, tokens, self._server_info(r))

    def recherche(self, key: str, model: str, prompt: str) -> Antwort:
        raise ProviderFehler("sonstiges", f"{self.titel} bietet hier keine Websuche")


RECHERCHE_SYSTEM = ("Du bist Marktanalyst für Gebrauchtwaren in Österreich. Nutze die Websuche für aktuelle Preise "
                    "und Fakten. Antworte auf Deutsch, knapp in Stichpunkten.")


class OpenAIProvider(OpenAIKompatibel):
    """ChatGPT-Modelle über die OpenAI-API; Marktrecherche über die Responses-API mit Websuche."""
    hinweis = "ChatGPT-Modelle über die OpenAI-API (Abrechnung nach Verbrauch), Marktrecherche per Websuche."
    token_parameter = "max_completion_tokens"
    mit_temperatur = False             # aktuelle GPT-Modelle akzeptieren nur die Standard-Temperatur
    kann_recherche = True
    modell_filter = ("audio", "realtime", "tts", "transcribe", "whisper", "embedding", "dall-e", "image",
                     "moderation", "davinci", "babbage", "search", "codex", "sora", "computer")

    def modelle(self, key: str) -> list[str]:
        return [m for m in super().modelle(key) if m.startswith(("gpt", "o1", "o3", "o4", "o5", "chatgpt"))]

    def recherche(self, key: str, model: str, prompt: str) -> Antwort:
        r, daten = self._anfrage("POST", "/responses", key, {
            "model": model, "instructions": RECHERCHE_SYSTEM, "input": prompt,
            "tools": [{"type": "web_search"}], "max_output_tokens": 8000})
        texte, quellen = [], []
        for item in daten.get("output") or []:
            if item.get("type") != "message":
                continue
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    texte.append(c.get("text", ""))
                    for a in c.get("annotations") or []:
                        if a.get("url") and (a.get("title") or "Quelle", a["url"]) not in quellen:
                            quellen.append((a.get("title") or "Quelle", a["url"]))
        text = "\n".join(t for t in texte if t).strip()
        if not text:
            raise ProviderFehler("ausgabe", "Leere Antwort der Marktrecherche")
        tokens = int((daten.get("usage") or {}).get("total_tokens") or 0)
        return Antwort(text, tokens, {"quellen": quellen, "suchen": []})


class PerplexityProvider(OpenAIKompatibel):
    name = "perplexity"
    titel = "Perplexity"
    basis_url = "https://api.perplexity.ai"
    key_url = "https://www.perplexity.ai/account/api/keys"
    limits_url = "https://docs.perplexity.ai/guides/usage-tiers"
    env_vars = ["PERPLEXITY_API_KEY", "PPLX_API_KEY"]
    standard_modell = "sonar-pro"
    ausweich_modell = "sonar"
    kann_recherche = True              # jede Antwort basiert auf einer Websuche
    json_modus = "schema"
    feste_modelle = ["sonar", "sonar-pro", "sonar-reasoning-pro", "sonar-deep-research"]
    paket = 20
    hinweis = "Perplexity sucht bei jeder Anfrage im Web – ideal für die Marktrecherche, aber etwas teurer."

    def recherche(self, key: str, model: str, prompt: str) -> Antwort:
        r, daten = self._anfrage("POST", "/chat/completions", key, self._koerper(
            model, [{"role": "system", "content": RECHERCHE_SYSTEM}, {"role": "user", "content": prompt}],
            4000, False))
        try:
            text = daten["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            text = ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        if not text:
            raise ProviderFehler("ausgabe", "Leere Antwort der Marktrecherche")
        quellen = []
        for q in daten.get("search_results") or []:
            if q.get("url"):
                quellen.append((q.get("title") or q["url"], q["url"]))
        if not quellen:
            quellen = [(u, u) for u in daten.get("citations") or [] if isinstance(u, str)]
        tokens = int((daten.get("usage") or {}).get("total_tokens") or 0)
        return Antwort(text, tokens, {"quellen": quellen, "suchen": []})


class MistralProvider(OpenAIKompatibel):
    name = "mistral"
    titel = "Mistral AI"
    basis_url = "https://api.mistral.ai/v1"
    key_url = "https://console.mistral.ai/api-keys"
    limits_url = "https://admin.mistral.ai/plateforme/limits"
    env_vars = ["MISTRAL_API_KEY"]
    standard_modell = "mistral-medium-latest"
    ausweich_modell = "mistral-small-latest"
    modell_filter = ("embed", "moderation", "ocr", "codestral", "devstral", "voxtral", "transcribe")
    hinweis = "Europäischer Anbieter (Frankreich), kostenloser Testzugang „Experiment“ verfügbar."


class DeepSeekProvider(OpenAIKompatibel):
    name = "deepseek"
    titel = "DeepSeek"
    basis_url = "https://api.deepseek.com"
    key_url = "https://platform.deepseek.com/api_keys"
    limits_url = "https://platform.deepseek.com/usage"
    env_vars = ["DEEPSEEK_API_KEY"]
    standard_modell = "deepseek-chat"
    ausweich_modell = "deepseek-reasoner"
    hinweis = "Sehr günstig. Server in China – Datenschutz beachten."


class XAIProvider(OpenAIKompatibel):
    name = "xai"
    titel = "xAI Grok"
    basis_url = "https://api.x.ai/v1"
    key_url = "https://console.x.ai"
    limits_url = "https://console.x.ai"
    env_vars = ["XAI_API_KEY"]
    standard_modell = "grok-4"
    ausweich_modell = "grok-3-mini"
    modell_filter = ("image", "vision", "imagine")


class GroqProvider(OpenAIKompatibel):
    name = "groq"
    titel = "Groq"
    basis_url = "https://api.groq.com/openai/v1"
    key_url = "https://console.groq.com/keys"
    limits_url = "https://console.groq.com/settings/limits"
    env_vars = ["GROQ_API_KEY"]
    standard_modell = "llama-3.3-70b-versatile"
    ausweich_modell = "llama-3.1-8b-instant"
    standard_limits = {"rpm": 30, "rpd": 1000, "tpm": 12_000, "tpd": 100_000}
    paket = 8                          # kleine Token-Limits im Gratis-Tarif
    text_zeichen = 700
    final_zeichen = 1200
    final_max = 20
    modell_filter = ("whisper", "tts", "guard", "playai", "orpheus", "prompt-guard")
    hinweis = "Sehr schnell und mit Gratis-Tarif, aber kleine Token-Limits (kleinere Pakete)."


class OpenRouterProvider(OpenAIKompatibel):
    name = "openrouter"
    titel = "OpenRouter"
    basis_url = "https://openrouter.ai/api/v1"
    key_url = "https://openrouter.ai/settings/keys"
    limits_url = "https://openrouter.ai/settings/credits"
    env_vars = ["OPENROUTER_API_KEY"]
    standard_modell = "openrouter/auto"
    ausweich_modell = ""
    hinweis = "Ein Key für hunderte Modelle vieler Anbieter (auch einige kostenlose „:free“-Modelle)."

    def modelle(self, key: str) -> list[str]:
        namen = super().modelle(key)
        return (["openrouter/auto"] if "openrouter/auto" not in namen else []) + namen


class TogetherProvider(OpenAIKompatibel):
    name = "together"
    titel = "Together AI"
    basis_url = "https://api.together.xyz/v1"
    key_url = "https://api.together.ai/settings/api-keys"
    limits_url = "https://api.together.ai/settings/billing"
    env_vars = ["TOGETHER_API_KEY"]
    standard_modell = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    ausweich_modell = ""

    def modelle(self, key: str) -> list[str]:
        _, daten = self._anfrage("GET", "/models", key, timeout=30)
        liste = daten if isinstance(daten, list) else daten.get("data", [])
        return sorted(m["id"] for m in liste if isinstance(m, dict) and m.get("id") and m.get("type", "chat") == "chat")


class EigenerProvider(OpenAIKompatibel):
    """Beliebige OpenAI-kompatible Schnittstelle (z.B. Azure OpenAI, Fireworks, Cerebras, eigener Server)."""
    name = "eigener"
    titel = "Eigener Anbieter (OpenAI-kompatibel)"
    basis_url = ""                     # wird aus den Einstellungen gesetzt (KeyStore)
    key_url = "https://platform.openai.com/docs/api-reference/chat"
    limits_url = ""
    env_vars = []
    standard_modell = ""
    ausweich_modell = ""
    json_modus = ""
    hinweis = "Jeder Dienst mit OpenAI-kompatibler Schnittstelle (z.B. Azure OpenAI, Fireworks, Cerebras)."


# --------------------------------------------------------------------------- Anthropic Claude

class AnthropicProvider:
    """Claude über das offizielle anthropic-SDK: strukturierte Ausgabe und Websuche (Server-Werkzeug)."""
    name = "anthropic"
    titel = "Anthropic Claude"
    key_url = "https://console.anthropic.com/settings/keys"
    limits_url = "https://console.anthropic.com/settings/limits"
    env_vars = ["ANTHROPIC_API_KEY"]
    standard_modell = "claude-opus-5-5"
    ausweich_modell = "claude-sonnet-5-5"
    kann_recherche = True
    standard_limits = {"rpm": None, "rpd": None, "tpm": None, "tpd": None}
    paket = 30
    text_zeichen = 1200
    final_zeichen = 2500
    final_max = 30
    hinweis = ("Claude bewertet sehr gründlich und sucht für die Marktrecherche selbst im Web. Opus ist das "
               "stärkste, Sonnet das günstigere Modell.")
    tageswechsel = staticmethod(naechste_mitternacht)
    _FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

    def __init__(self):
        try:
            import anthropic
        except ImportError as e:
            raise ProviderFehler("sonstiges", "Python-Paket „anthropic“ fehlt – bitte die App aktualisieren "
                                 "oder „pip install anthropic“ ausführen") from e
        self._a = anthropic
        self._clients: dict[str, object] = {}
        self._mit_fallback = True

    def _client(self, key: str):
        if key not in self._clients:
            self._clients[key] = self._a.Anthropic(api_key=key, timeout=300.0, max_retries=1)
        return self._clients[key]

    def _fehler(self, e) -> ProviderFehler:
        a = self._a
        txt = str(e)
        if isinstance(e, a.AuthenticationError):
            return ProviderFehler("key", "Key ungültig")
        if isinstance(e, a.PermissionDeniedError):
            return ProviderFehler("region", "Kein Zugriff mit diesem Key (Berechtigung/Region)")
        if re.search(r"credit balance|billing|purchase credits", txt, re.I):
            return ProviderFehler("kosten", "Kein Guthaben mehr im Anthropic-Konto (Plans & Billing)")
        if isinstance(e, a.RateLimitError):
            warte = None
            try:
                warte = _dauer(e.response.headers.get("retry-after"))
            except Exception:
                pass
            return ProviderFehler("minute", "Limit pro Minute erreicht", retry_after=warte or 20.0)
        if isinstance(e, a.NotFoundError):
            return ProviderFehler("modell", "Modell nicht verfügbar")
        if isinstance(e, a.BadRequestError) and re.search(r"too long|too large|context|max_tokens", txt, re.I):
            return ProviderFehler("zu_gross", "Anfrage zu groß")
        if isinstance(e, (a.APITimeoutError, a.APIConnectionError)):
            return ProviderFehler("ueberlastet", f"keine Verbindung/Antwort ({type(e).__name__})", retry_after=5.0)
        if isinstance(e, a.InternalServerError) or getattr(e, "status_code", 0) in (500, 502, 503, 529):
            return ProviderFehler("ueberlastet", f"Server ausgelastet ({getattr(e, 'status_code', '?')})",
                                  retry_after=10.0)
        return ProviderFehler("sonstiges", f"Claude-Fehler: {txt[:300]}")

    def modelle(self, key: str) -> list[str]:
        try:
            return sorted({m.id for m in self._client(key).models.list(limit=100) if m.id.startswith("claude")})
        except self._a.APIError as e:
            raise self._fehler(e) from e

    @classmethod
    def bestes_modell(cls, namen: list[str]) -> str | None:
        for m in (cls.standard_modell, cls.ausweich_modell):
            if m in namen:
                return m
        return namen[0] if namen else None

    def testen(self, key: str, model: str) -> dict:
        namen = self.modelle(key)
        return {"ok": True, "text": f"{len(namen)} Modelle verfügbar", "modelle": namen}

    def _senden(self, funktion, **kw):
        """Mit serverseitigem Ausweichen bei Überlastung; falls der Key/das Modell das nicht kennt, ohne."""
        if self._mit_fallback:
            try:
                return funktion(**kw, **self._FALLBACK)
            except self._a.BadRequestError as e:
                if not re.search(r"fallback|beta", str(e), re.I):
                    raise
                self._mit_fallback = False
        return funktion(**kw)

    def call(self, key: str, model: str, prompt: str, schema: type[BaseModel], heavy: bool) -> Antwort:
        try:
            resp = self._senden(self._client(key).beta.messages.parse, model=model, max_tokens=16000,
                                system=_system(), messages=[{"role": "user", "content": prompt}],
                                output_format=schema, output_config={"effort": "high" if heavy else "low"})
        except self._a.APIError as e:
            raise self._fehler(e) from e
        tokens = (resp.usage.input_tokens or 0) + (resp.usage.output_tokens or 0)
        if resp.stop_reason == "refusal":
            raise ProviderFehler("ausgabe", "Claude hat die Anfrage abgelehnt", info={"tokens": tokens})
        parsed = getattr(resp, "parsed_output", None)
        if parsed is None:
            text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
            try:
                parsed = schema.model_validate_json(_json_aus_text(text))
            except Exception as e:
                grund = "Antwort abgeschnitten" if resp.stop_reason == "max_tokens" else "Antwort nicht lesbar"
                raise ProviderFehler("ausgabe", grund, info={"tokens": tokens}) from e
        return Antwort(parsed, tokens, {})

    def recherche(self, key: str, model: str, prompt: str) -> Antwort:
        client = self._client(key)
        nachrichten = [{"role": "user", "content": prompt}]
        tokens = 0
        suchen: list[str] = []
        try:
            for _ in range(5):
                resp = self._senden(client.beta.messages.create, model=model, max_tokens=8000,
                                    system=RECHERCHE_SYSTEM, messages=nachrichten,
                                    tools=[{"type": "web_search_20260209", "name": "web_search"}])
                tokens += (resp.usage.input_tokens or 0) + (resp.usage.output_tokens or 0)
                for b in resp.content:
                    q = (getattr(b, "input", None) or {}).get("query") if getattr(b, "type", "") == "server_tool_use" else None
                    if q and q not in suchen:
                        suchen.append(q)
                if resp.stop_reason != "pause_turn":
                    break
                # Server-Werkzeug hat pausiert: Verlauf unverändert erneut senden, damit Claude weitermacht
                nachrichten = [nachrichten[0], {"role": "assistant", "content": resp.content}]
        except self._a.APIError as e:
            raise self._fehler(e) from e
        if resp.stop_reason == "refusal":
            raise ProviderFehler("ausgabe", "Claude hat die Recherche abgelehnt")
        texte, quellen = [], []
        for b in resp.content:
            typ = getattr(b, "type", "")
            if typ == "text":
                texte.append(b.text)
                for c in getattr(b, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url and (getattr(c, "title", None) or url, url) not in quellen:
                        quellen.append((getattr(c, "title", None) or url, url))
            elif typ == "web_search_tool_result" and isinstance(getattr(b, "content", None), list):
                for r in b.content:
                    url = getattr(r, "url", None)
                    if url and len(quellen) < 12 and not any(u == url for _, u in quellen):
                        quellen.append((getattr(r, "title", None) or url, url))
        text = "".join(texte).strip()
        if not text:
            raise ProviderFehler("ausgabe", "Leere Antwort der Marktrecherche")
        return Antwort(text, tokens, {"quellen": quellen, "suchen": suchen})


# --------------------------------------------------------------------------- Liste

def _system() -> str:
    from rating import SYSTEM
    return SYSTEM


GeminiProvider.env_vars = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEYS"]
GeminiProvider.hinweis = ("Standard. Großzügiger Gratis-Tarif in Google AI Studio, Marktrecherche per "
                          "Google-Suche.")

# Schritt-für-Schritt-Anleitungen „API-Key holen“ (Einstellungen → KI-Anbieter → „Anleitung: API-Key holen“)
_HINZU = "Hier im Einstellungsfenster bei „Keys für …“ auf „＋ Hinzufügen“ klicken, Key einfügen, „Testen“, „Speichern“."
GeminiProvider.anleitung = [
    "aistudio.google.com/apikey öffnen und mit deinem Google-Konto (z.B. Gmail) anmelden.",
    "Beim ersten Besuch die Nutzungsbedingungen bestätigen (die E-Mail-Häkchen können leer bleiben).",
    "„API-Schlüssel erstellen“ bzw. „Create API key“ klicken; nach einem Projekt gefragt: vorhandenes wählen oder "
    "neues erstellen (Name egal).",
    "Den Key kopieren – er beginnt mit „AIza…“ oder „AQ.…“.",
    _HINZU,
    "Kosten: Ohne hinterlegte Zahlungsmethode gilt der kostenlose Tarif (mit Tageslimits pro Modell).",
]
OpenAIProvider.anleitung = [
    "platform.openai.com öffnen und registrieren bzw. anmelden. Achtung: Ein ChatGPT-Abo (Plus/Pro) gilt NICHT "
    "für die API.",
    "Unter Settings → Billing eine Zahlungsmethode hinterlegen und Guthaben aufladen (ab 5 $).",
    "Unter API keys auf „Create new secret key“ klicken, einen Namen vergeben (z.B. willhaben-agent).",
    "Den Key sofort kopieren (beginnt mit „sk-…“) – er wird nur einmal angezeigt.",
    _HINZU,
    "Tipp: Unter Settings → Limits ein monatliches Ausgabenlimit setzen.",
]
AnthropicProvider.anleitung = [
    "console.anthropic.com öffnen und registrieren bzw. anmelden. Achtung: Ein Claude-Abo (Pro/Max) gilt NICHT "
    "für die API.",
    "Unter Settings → Billing (Plans & Billing) Guthaben kaufen (ab 5 $).",
    "Unter Settings → API Keys auf „Create Key“ klicken und einen Namen vergeben.",
    "Den Key kopieren (beginnt mit „sk-ant-…“) – er wird nur einmal angezeigt.",
    _HINZU,
    "Tipp: Unter Settings → Limits ein Ausgabenlimit setzen. Sonnet ist deutlich günstiger als Opus.",
]
PerplexityProvider.anleitung = [
    "perplexity.ai öffnen und anmelden.",
    "Unter Einstellungen → API (perplexity.ai/account/api) eine Zahlungsmethode hinterlegen und Guthaben laden.",
    "„Create Key“ bzw. „API-Schlüssel generieren“ klicken.",
    "Den Key kopieren (beginnt mit „pplx-…“).",
    _HINZU,
]
MistralProvider.anleitung = [
    "console.mistral.ai öffnen und registrieren bzw. anmelden.",
    "Einen Tarif wählen: „Experiment“ ist kostenlos (Telefonnummer bestätigen), „Scale“ wird nach Verbrauch "
    "abgerechnet.",
    "Unter API Keys auf „Create new key“ klicken.",
    "Den Key kopieren – er wird nur einmal angezeigt. Neue Keys sind oft erst nach ein paar Minuten aktiv.",
    _HINZU,
]
DeepSeekProvider.anleitung = [
    "platform.deepseek.com öffnen und registrieren bzw. anmelden.",
    "Unter Top up Guthaben aufladen (ohne Guthaben antwortet die API nicht).",
    "Unter API keys auf „Create new API key“ klicken.",
    "Den Key kopieren (beginnt mit „sk-…“) – er wird nur einmal angezeigt.",
    _HINZU,
]
XAIProvider.anleitung = [
    "console.x.ai öffnen und anmelden (mit X-Konto, Google oder E-Mail).",
    "Unter Billing bzw. Credits Guthaben kaufen.",
    "Unter API Keys auf „Create API Key“ klicken.",
    "Den Key kopieren (beginnt mit „xai-…“).",
    _HINZU,
]
GroqProvider.anleitung = [
    "console.groq.com öffnen und anmelden (Google, GitHub oder E-Mail).",
    "Unter API Keys auf „Create API Key“ klicken – ein Zahlungsmittel ist für den Gratis-Tarif nicht nötig.",
    "Den Key kopieren (beginnt mit „gsk_…“) – er wird nur einmal angezeigt.",
    _HINZU,
    "Hinweis: Der Gratis-Tarif hat kleine Limits pro Minute; der Agent nimmt dafür kleinere Pakete.",
]
OpenRouterProvider.anleitung = [
    "openrouter.ai öffnen und anmelden.",
    "Unter Credits Guthaben kaufen – für die kostenlosen Modelle (Endung „:free“) nicht nötig.",
    "Unter Keys auf „Create Key“ klicken, optional ein Ausgabenlimit für den Key setzen.",
    "Den Key kopieren (beginnt mit „sk-or-…“).",
    _HINZU,
]
TogetherProvider.anleitung = [
    "api.together.ai öffnen und registrieren bzw. anmelden.",
    "Unter Billing Guthaben aufladen.",
    "Unter Settings → API Keys den Key kopieren bzw. einen neuen erstellen.",
    _HINZU,
]
EigenerProvider.anleitung = [
    "Beim Dienst deiner Wahl (z.B. Azure OpenAI, Fireworks, Cerebras) einen API-Key erstellen.",
    "Die Basis-Adresse der OpenAI-kompatiblen Schnittstelle heraussuchen – sie endet meist auf „/v1“.",
    "Hier oben bei „Adresse (Basis-URL)“ eintragen und Enter drücken.",
    _HINZU,
    "Kann der Dienst keine Modellliste liefern, den Modellnamen bei „Modell“ selbst eintippen.",
]

# Reihenfolge = Anzeige in den Einstellungen
PROVIDER_KLASSEN = {k.name: k for k in (
    GeminiProvider, OpenAIProvider, AnthropicProvider, PerplexityProvider, MistralProvider, DeepSeekProvider,
    XAIProvider, GroqProvider, OpenRouterProvider, TogetherProvider, EigenerProvider)}
PROVIDER_TITEL = {n: k.titel for n, k in PROVIDER_KLASSEN.items()}
STANDARD_ANBIETER = "gemini"
