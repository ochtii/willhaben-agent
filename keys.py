"""API-Key- und Limit-Manager.

KeyStore  – speichert beliebig viele Google-Gemini-Keys samt Limits und Verbrauch
            (~/.config/willhaben-agent/keys.json, nur für den eigenen Benutzer lesbar).
Verteiler – wählt für jede KI-Anfrage Key und Modell: Keys gleichmäßig oder nacheinander,
            respektiert Minuten-/Tageslimits, wechselt bei Limit/Fehler automatisch zum nächsten
            Key bzw. vom gewählten Modell auf das Ausweichmodell.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Callable

from providers import PROVIDER_KLASSEN, PROVIDER_TITEL, ProviderFehler
import settings

KEYS_FILE = settings.CONFIG_DIR / "keys.json"
UEBERLAST_PAUSE = 180          # Sekunden Pause für ein Modell nach "503 überlastet"
ANBIETER = ["gemini"]
ENV_VARS = {"gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEYS"]}
LIMIT_FELDER = [("rpm", "Anfragen/Minute"), ("rpd", "Anfragen/Tag"), ("tpm", "Token/Minute"), ("tpd", "Token/Tag")]


class KIFehler(Exception):
    """Fehler mit verständlicher Meldung für die Oberfläche."""


class ZuGross(KIFehler):
    pass


class AusgabeFehler(KIFehler):
    pass


def maskiert(key: str) -> str:
    key = key or ""
    return f"{key[:4]}…{key[-4:]}" if len(key) > 10 else "•" * len(key)


def uhrzeit(ts: float) -> str:
    if not ts:
        return ""
    d = datetime.fromtimestamp(ts)
    return d.strftime("%H:%M") if d.date() == datetime.now().date() else d.strftime("%d.%m. %H:%M")


# --------------------------------------------------------------------------- Speicher

class KeyStore:
    def __init__(self, path=None):
        self.path = path or KEYS_FILE
        self.lock = threading.RLock()
        self.keys: list[dict] = []
        self.usage: dict[str, dict] = {}
        self.optionen: dict = {}
        self._laufzeit: dict[str, dict] = {}      # nicht gespeichert: Zeitfenster, letzte Anfrage
        self.load()

    # -- Laden/Speichern
    def load(self):
        with self.lock:
            try:
                data = json.loads(self.path.read_text())
            except Exception:
                data = {}
            # nur noch Google Gemini: Einträge anderer (früherer) Anbieter verwerfen
            self.keys = [k for k in data.get("keys", []) if k.get("provider") in PROVIDER_KLASSEN]
            ids = {k["id"] for k in self.keys}
            self.usage = {kid: u for kid, u in data.get("usage", {}).items() if kid in ids or kid.startswith("env-")}
            self.optionen = {"verteilung": "gleichmaessig", **data.get("optionen", {})}
            self.optionen.pop("reihenfolge", None)
            modelle = {p: m for p, m in self.optionen.get("modelle", {}).items() if p in PROVIDER_KLASSEN}
            ausweich = {p: m for p, m in self.optionen.get("ausweich", {}).items() if p in PROVIDER_KLASSEN}
            for p, k in PROVIDER_KLASSEN.items():
                if not modelle.get(p) or modelle[p] in ("auto", "gemini-flash-latest") \
                        or not self.optionen.get("v2_modelle"):
                    modelle[p] = k.standard_modell
                if not ausweich.get(p) or not self.optionen.get("v2_modelle"):
                    ausweich[p] = k.ausweich_modell
            self.optionen.update(modelle=modelle, ausweich=ausweich, v2_modelle=True)
            self._legacy_import()
            self._env_keys()

    def save(self):
        with self.lock:
            data = {"keys": [k for k in self.keys if k.get("quelle") != "umgebung"],
                    "usage": self.usage, "optionen": self.optionen}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
            os.chmod(tmp, 0o600)
            tmp.replace(self.path)

    def _legacy_import(self):
        """Früher gespeicherten Einzel-Key (config.json) übernehmen."""
        cfg = settings.load()
        old = cfg.pop("gemini_api_key", None)
        if old:
            if not any(k["key"] == old for k in self.keys):
                self.keys.append(self._neu("gemini", "Standard", old))
            settings.save(cfg)
            self.save()

    def _env_keys(self):
        self.keys = [k for k in self.keys if k.get("quelle") != "umgebung"]
        for prov, names in ENV_VARS.items():
            seen = set()
            for var in names:
                for i, val in enumerate(v.strip() for v in os.environ.get(var, "").split(",")):
                    if not val or val in seen or any(k["key"] == val for k in self.keys):
                        continue
                    seen.add(val)
                    e = self._neu(prov, f"${var}" + (f" #{i + 1}" if i else ""), val)
                    e["id"] = f"env-{var}-{i}"
                    e["quelle"] = "umgebung"
                    self.keys.append(e)

    @staticmethod
    def _neu(provider, label, key, limits=None) -> dict:
        return {"id": uuid.uuid4().hex[:10], "provider": provider, "label": label or "Key", "key": key.strip(),
                "aktiv": True, "limits": limits or {}, "quelle": "datei", "angelegt": time.time()}

    # -- Verwaltung
    def eintraege(self, provider: str | None = None) -> list[dict]:
        with self.lock:
            return [k for k in self.keys if provider is None or k["provider"] == provider]

    def get(self, kid: str) -> dict | None:
        with self.lock:
            return next((k for k in self.keys if k["id"] == kid), None)

    def add(self, provider, label, key, limits=None) -> dict:
        with self.lock:
            key = key.strip()
            if any(k["key"] == key for k in self.keys):
                raise ValueError("Dieser Key ist bereits eingetragen.")
            e = self._neu(provider, label, key, limits)
            self.keys.append(e)
            self.save()
            return e

    def update(self, kid, **felder):
        with self.lock:
            e = self.get(kid)
            if not e:
                return
            if "key" in felder and e.get("quelle") == "umgebung":
                felder.pop("key")
            e.update(felder)
            if "key" in felder:          # neuer Key -> alter Status ist hinfällig
                self.usage.pop(kid, None)
            self.save()

    def remove(self, kid):
        with self.lock:
            self.keys = [k for k in self.keys if k["id"] != kid or k.get("quelle") == "umgebung"]
            self.usage.pop(kid, None)
            self.save()

    def verschieben(self, kid, richtung: int):
        with self.lock:
            idx = next((i for i, k in enumerate(self.keys) if k["id"] == kid), None)
            if idx is None:
                return
            prov = self.keys[idx]["provider"]
            same = [i for i, k in enumerate(self.keys) if k["provider"] == prov]
            pos = same.index(idx) + richtung
            if 0 <= pos < len(same):
                j = same[pos]
                self.keys[idx], self.keys[j] = self.keys[j], self.keys[idx]
                self.save()

    # -- Verbrauch
    def nutzung(self, kid: str) -> dict:
        with self.lock:
            e = self.get(kid)
            u = self.usage.setdefault(kid, {"anfragen": 0, "token": 0, "gesamt_anfragen": 0, "gesamt_token": 0,
                                            "cooldown_bis": 0, "erschoepft_bis": 0, "status": "", "fehler": "",
                                            "server": {}, "zuletzt": 0, "tag": 0})
            if e:
                reset = PROVIDER_KLASSEN[e["provider"]].tageswechsel()
                if u.get("tag") != int(reset):       # neuer Tag -> Tageszähler zurücksetzen
                    u.update(anfragen=0, token=0, tag=int(reset))
                    if u.get("status") == "tageslimit" and u.get("erschoepft_bis", 0) <= time.time():
                        u["status"] = ""
            return u

    def laufzeit(self, kid: str) -> dict:
        return self._laufzeit.setdefault(kid, {"fenster": deque(), "letzte": 0.0})

    def limits(self, e: dict) -> dict:
        """Wirksame Limits: eigene Angabe > vom Server gemeldet > Annahme. Mit Quelle je Feld."""
        prov = PROVIDER_KLASSEN[e["provider"]]
        server = self.nutzung(e["id"]).get("server", {})
        out = {}
        for f, _ in LIMIT_FELDER:
            own = (e.get("limits") or {}).get(f)
            if own:
                out[f] = (own, "eigene")
            elif server.get(f):
                out[f] = (server[f], "Server")
            elif prov.standard_limits.get(f):
                out[f] = (prov.standard_limits[f], "Annahme")
            else:
                out[f] = (None, "")
        return out

    def erfolg(self, kid: str, tokens: int, info: dict):
        with self.lock:
            u = self.nutzung(kid)
            u["anfragen"] += 1
            u["token"] += tokens or 0
            u["gesamt_anfragen"] = u.get("gesamt_anfragen", 0) + 1
            u["gesamt_token"] = u.get("gesamt_token", 0) + (tokens or 0)
            u["zuletzt"] = time.time()
            u["status"], u["fehler"] = "ok", ""
            if info:
                u["server"] = {**u.get("server", {}), **info}
            self.laufzeit(kid)["fenster"].append((time.time(), tokens or 0))
            self.save()

    def fehler(self, kid: str, f: ProviderFehler):
        with self.lock:
            u = self.nutzung(kid)
            now = time.time()
            if f.info:
                u["server"] = {**u.get("server", {}), **{k: v for k, v in f.info.items() if k != "tokens"}}
            if f.info.get("tokens"):
                u["token"] += f.info["tokens"]
                self.laufzeit(kid)["fenster"].append((now, f.info["tokens"]))
            if f.art == "minute":
                u["cooldown_bis"] = now + (f.retry_after or 20) + 1
                u["status"] = "minutenlimit"
            elif f.art == "tag":
                u["erschoepft_bis"] = f.reset_at or PROVIDER_KLASSEN[self.get(kid)["provider"]].tageswechsel()
                u["status"] = "tageslimit"
            elif f.art in ("key", "region"):
                u["status"] = "ungueltig" if f.art == "key" else "region"
            u["fehler"] = f.meldung
            u["fehler_zeit"] = now
            self.save()

    def modell_sperren(self, kid: str, modell: str, bis: float, info: dict | None = None):
        """Tageskontingent eines Modells für diesen Key aufgebraucht."""
        with self.lock:
            u = self.nutzung(kid)
            u.setdefault("modell_gesperrt", {})[modell] = bis
            u["fehler"] = f"Tageskontingent „{modell}“ aufgebraucht"
            if info:
                u["server"] = {**u.get("server", {}), **{k: v for k, v in info.items() if k != "tokens"}}
            self.save()

    # -- überlastete Modelle merken (gilt für alle Keys eines Anbieters)
    def modell_pausieren(self, provider: str, modell: str, sekunden: float):
        with self.lock:
            self.optionen.setdefault("modell_pause", {})[f"{provider}:{modell}"] = time.time() + sekunden
            self.save()

    def modell_pausiert(self, provider: str, modell: str) -> bool:
        return self.optionen.get("modell_pause", {}).get(f"{provider}:{modell}", 0) > time.time()

    def pausierte_modelle(self, provider: str) -> list[tuple[str, float]]:
        now = time.time()
        return [(k.split(":", 1)[1], t) for k, t in self.optionen.get("modell_pause", {}).items()
                if k.startswith(provider + ":") and t > now]

    def zuruecksetzen(self, kid: str):
        with self.lock:
            self.usage.pop(kid, None)
            self._laufzeit.pop(kid, None)
            self.save()

    def status_text(self, e: dict) -> str:
        u = self.nutzung(e["id"])
        now = time.time()
        if not e.get("aktiv", True):
            return "deaktiviert"
        if u.get("erschoepft_bis", 0) > now:
            return f"Tageslimit bis {uhrzeit(u['erschoepft_bis'])}"
        if u.get("status") == "ungueltig":
            return "ungültig"
        if u.get("status") == "region":
            return "Region/Abrechnung"
        if u.get("guthaben_leer", 0) > now:
            return "Guthaben leer"
        if u.get("cooldown_bis", 0) > now:
            return f"Pause {int(u['cooldown_bis'] - now)} s"
        gesperrt = [m for m, t in u.get("modell_gesperrt", {}).items() if t > now]
        if u.get("status") in ("", "ok", "minutenlimit", "tageslimit"):
            return "bereit" + (f" ({len(gesperrt)} Modell{'e' if len(gesperrt) > 1 else ''} aufgebraucht)" if gesperrt else "")
        return u.get("status")


# --------------------------------------------------------------------------- Verteiler

def _sleep(seconds: float, stop: threading.Event | None):
    end = time.time() + seconds
    while time.time() < end:
        if stop is not None and stop.is_set():
            from willhaben import Abgebrochen
            raise Abgebrochen("Vom Benutzer abgebrochen")
        time.sleep(min(0.25, max(0.0, end - time.time())))


class Verteiler:
    """Wird von der Bewertung wie ein einzelnes Modell benutzt: generate(prompt, schema, heavy)."""

    def __init__(self, store: KeyStore, modelle: dict | None = None,
                 verteilung: str | None = None, log: Callable[[str], None] = print,
                 stop: threading.Event | None = None, on_update: Callable[[], None] | None = None,
                 ausweich: dict | None = None):
        self.store = store
        o = store.optionen
        self.reihenfolge = list(ANBIETER)            # nur Google Gemini
        self.modelle = {**o.get("modelle", {}), **(modelle or {})}
        self.ausweich = {**{p: getattr(k, "ausweich_modell", "") for p, k in PROVIDER_KLASSEN.items()},
                         **o.get("ausweich", {}), **(ausweich or {})}
        self._modellliste: dict[str, list] = {}
        self._kaputt: set[tuple[str, str]] = set()    # (anbieter, modell) gibt es nicht -> überspringen
        self.verteilung = verteilung or o.get("verteilung", "gleichmaessig")
        self.log, self.stop, self.on_update = log, stop, on_update or (lambda: None)
        self._prov: dict[str, object] = {}
        self._modell_je_key: dict[str, str] = {}      # key-id -> aktuell verwendetes Modell
        self.ausgeschlossen: set[str] = set()     # Keys, die in diesem Lauf nicht funktionieren
        self.requests = 0
        self.aktiv: tuple[str, dict] | None = None
        self._letzter_anbieter = None

    # -- Infos für Bewertung/Anzeige
    def provider(self, name):
        if name not in self._prov:
            self._prov[name] = PROVIDER_KLASSEN[name]()
        return self._prov[name]

    def keys_bereit(self, name: str) -> list[dict]:
        now = time.time()
        out = []
        for e in self.store.eintraege(name):
            u = self.store.nutzung(e["id"])
            if not e.get("aktiv", True) or e["id"] in self.ausgeschlossen or u.get("erschoepft_bis", 0) > now:
                continue
            rpd = self.store.limits(e)["rpd"][0]
            if rpd and u.get("anfragen", 0) >= rpd and self.store.limits(e)["rpd"][1] != "Annahme":
                continue
            srv = u.get("server", {})
            if srv.get("rest_anfragen") == 0 and srv.get("zeit", 0) + srv.get("reset_anfragen", 0) > now:
                continue
            out.append(e)
        return out

    def anbieter_jetzt(self) -> str | None:
        return next((n for n in self.reihenfolge if self.keys_bereit(n)), None)

    def _klasse(self):
        return PROVIDER_KLASSEN[self.anbieter_jetzt() or self.reihenfolge[0]]

    def paketgroesse(self) -> int:
        return self._klasse().paket

    def textlaenge(self) -> int:
        return self._klasse().text_zeichen

    def final_parameter(self) -> tuple[int, int]:
        k = self._klasse()
        return k.final_zeichen, k.final_max

    @property
    def name(self) -> str:
        n = self.aktiv[0] if self.aktiv else self.anbieter_jetzt() or self.reihenfolge[0]
        return PROVIDER_TITEL.get(n, n)

    @property
    def model(self) -> str:
        if self.aktiv:
            return self._modell_je_key.get(self.aktiv[1]["id"], "?")
        n = self.anbieter_jetzt() or self.reihenfolge[0]
        return self.modelle.get(n) or PROVIDER_KLASSEN[n].standard_modell

    def beschreibung(self) -> str:
        teile = []
        for n in self.reihenfolge:
            alle = [e for e in self.store.eintraege(n) if e.get("aktiv", True)]
            teile.append(f"{PROVIDER_TITEL[n]} ({len(self.keys_bereit(n))}/{len(alle)} Keys bereit)")
        return " → ".join(teile) + f" · Verteilung: {'gleichmäßig' if self.verteilung == 'gleichmaessig' else 'nacheinander'}"

    # -- Auswahl
    def _wartezeit(self, e: dict, est_tokens: float) -> float:
        now = time.time()
        u, lz, lim = self.store.nutzung(e["id"]), self.store.laufzeit(e["id"]), self.store.limits(e)
        w = max(0.0, u.get("cooldown_bis", 0) - now)
        rpm = lim["rpm"][0]
        if rpm:
            w = max(w, lz["letzte"] + 60.0 / rpm * 1.05 - now)
        tpm = lim["tpm"][0]
        f = lz["fenster"]
        while f and f[0][0] < now - 60:
            f.popleft()
        if tpm and est_tokens < tpm:
            used = sum(t for _, t in f)
            if used + est_tokens > tpm * 0.95:
                need = used + est_tokens - tpm * 0.95
                for ts, t in f:
                    need -= t
                    if need <= 0:
                        w = max(w, ts + 60 - now)
                        break
        srv = u.get("server", {})
        if srv.get("rest_token") is not None and srv.get("reset_token") is not None:
            frei_ab = srv.get("zeit", 0) + srv["reset_token"]
            if srv["rest_token"] < est_tokens and frei_ab > now and (not tpm or est_tokens < tpm):
                w = max(w, frei_ab - now)
        return w

    def _auslastung(self, e: dict) -> float:
        u, lim = self.store.nutzung(e["id"]), self.store.limits(e)
        werte = [u.get("anfragen", 0) / lim["rpd"][0] if lim["rpd"][0] else u.get("anfragen", 0) / 10_000,
                 u.get("token", 0) / lim["tpd"][0] if lim["tpd"][0] else 0]
        return max(werte)

    def _waehle(self, est: float, nur_recherche: bool = False):
        """-> (anbieter, key-eintrag, wartezeit) oder None."""
        kandidaten = []
        for rang, n in enumerate(self.reihenfolge):
            if nur_recherche and not getattr(PROVIDER_KLASSEN[n], "kann_recherche", False):
                continue
            keys = self.keys_bereit(n)
            for idx, e in enumerate(keys):
                kandidaten.append((rang, idx, self._wartezeit(e, est), self._auslastung(e), n, e))
        if not kandidaten:
            return None
        bester_rang = min(k[0] for k in kandidaten)
        eigene = [k for k in kandidaten if k[0] == bester_rang]
        if self.verteilung == "gleichmaessig":
            wahl = min(eigene, key=lambda k: (k[2] > 0.5, k[3], k[2]))
        else:
            wahl = min(eigene, key=lambda k: (k[2] > 0.5, k[1], k[2]))
        # Müsste lange gewartet werden und ein späterer Anbieter ist sofort frei -> den nehmen
        if wahl[2] > 20:
            sofort = [k for k in kandidaten if k[0] > bester_rang and k[2] <= 0.5]
            if sofort:
                wahl = min(sofort, key=lambda k: (k[0], k[3]))
        return wahl[4], wahl[5], wahl[2]

    def _kette(self, name: str, e: dict | None = None) -> list[str]:
        """Genau zwei Modelle: das gewählte und das Ausweichmodell (keine stillen weiteren Modelle)."""
        kette = [(self.modelle.get(name) or "").strip() or PROVIDER_KLASSEN[name].standard_modell,
                 (self.ausweich.get(name) or "").strip()]
        out = []
        for m in kette:
            if m and m not in out:
                out.append(m)
        return out

    def _nutzbar(self, name: str, e: dict, m: str) -> bool:
        if (name, m) in self._kaputt or self.store.modell_pausiert(name, m):
            return False
        return self.store.nutzung(e["id"]).get("modell_gesperrt", {}).get(m, 0) <= time.time()

    def _modell(self, name: str, e: dict) -> str:
        """Modell für diesen Key: das aktuelle, solange es nutzbar ist, sonst das nächste der Kette."""
        cur = self._modell_je_key.get(e["id"])
        if cur and self._nutzbar(name, e, cur):
            return cur
        for m in self._kette(name, e):
            if self._nutzbar(name, e, m):
                if cur:
                    self.log(f"  ↪ {PROVIDER_TITEL[name]} „{e['label']}“: wechsle von „{cur}“ auf „{m}“")
                else:
                    gesperrt = [x for x in self._kette(name, e) if not self._nutzbar(name, e, x)]
                    self.log(f"  {PROVIDER_TITEL[name]} „{e['label']}“: verwende Modell {m}"
                             + (f" (übersprungen: {', '.join(gesperrt)})" if gesperrt else ""))
                self._modell_je_key[e["id"]] = m
                return m
        # Kein Modell nutzbar. Nur wegen Überlastung pausiert -> kurz warten; Kontingente aufgebraucht -> Key sperren
        now = time.time()
        kette = self._kette(name, e)
        if all((name, m) in self._kaputt for m in kette):
            raise KIFehler(f"Weder „{kette[0]}“ noch das Ausweichmodell sind für deinen Key verfügbar. "
                           "Unter „API-Keys & Limits“ → „KI-Modell“ verfügbare Modelle wählen.")
        gesperrt = self.store.nutzung(e["id"]).get("modell_gesperrt", {})
        pausen = dict(self.store.pausierte_modelle(name))
        nur_pause = [pausen[m] for m in kette if m in pausen and gesperrt.get(m, 0) <= now and (name, m) not in self._kaputt]
        if nur_pause:
            warte = max(5.0, min(nur_pause) - now)
            raise ProviderFehler("minute", f"alle Modelle gerade überlastet – nächster Versuch in {warte:.0f} s",
                                 retry_after=warte)
        zeiten = [t for t in gesperrt.values() if t > now]
        bis = min(zeiten) if zeiten else now + 3600
        raise ProviderFehler("tag", "Tageskontingent aller Modelle dieses Keys aufgebraucht", reset_at=bis)

    def _zusammenfassung(self) -> str:
        teile = []
        for n in self.reihenfolge:
            for e in self.store.eintraege(n):
                teile.append(f"{PROVIDER_TITEL[n]} „{e['label']}“: {self.store.status_text(e)}")
        if not teile:
            return ("Kein API-Key eingetragen. Unter „API-Keys & Limits“ mindestens einen Google-Gemini-Key "
                    "hinzufügen (Anleitung: ANLEITUNG-API-KEY.md).")
        return "Kein Key mehr verfügbar – alle Limits erreicht oder Keys ungültig:\n  " + "\n  ".join(teile)

    # -- Anfrage
    def kann_recherche(self) -> bool:
        return any(getattr(PROVIDER_KLASSEN[n], "kann_recherche", False) and self.keys_bereit(n)
                   for n in self.reihenfolge)

    def recherche(self, prompt: str):
        """Websuche (nur Anbieter mit Suchfunktion, d.h. Gemini). -> Antwort(parsed=Text, info={'quellen': ...})"""
        return self.generate(prompt, None, heavy=True, recherche=True)

    def generate(self, prompt: str, schema, heavy: bool = False, recherche: bool = False):
        est = len(prompt) / 3.2 + (3000 if heavy else 1500)
        ueberlastet = 0
        for _ in range(60):
            if self.stop is not None and self.stop.is_set():
                from willhaben import Abgebrochen
                raise Abgebrochen("Vom Benutzer abgebrochen")
            wahl = self._waehle(est, nur_recherche=recherche)
            if wahl is None:
                raise KIFehler(self._zusammenfassung())
            name, e, warten = wahl
            titel = PROVIDER_TITEL[name]
            if name != self._letzter_anbieter:
                if self._letzter_anbieter:
                    self.log(f"↪ Wechsel zu {titel}")
                self._letzter_anbieter = name
            if warten > 0.5:
                if warten > 3:
                    self.log(f"  … warte {warten:.0f} s, bis {titel} „{e['label']}“ wieder frei ist")
                _sleep(warten, self.stop)
                continue                      # danach neu wählen (evtl. ist ein anderer Key frei geworden)
            prov = self.provider(name)
            modell = None
            try:
                modell = self._modell(name, e)
                self.store.laufzeit(e["id"])["letzte"] = time.time()
                antwort = (prov.recherche(e["key"], modell, prompt) if recherche
                           else prov.call(e["key"], modell, prompt, schema, heavy))
            except ProviderFehler as f:
                label = f"{titel} „{e['label']}“"
                if f.art == "tag" and modell:
                    # Tageskontingent gilt pro Modell -> nur dieses Modell für diesen Key sperren
                    bis = f.reset_at or PROVIDER_KLASSEN[name].tageswechsel()
                    self.store.modell_sperren(e["id"], modell, bis, f.info)
                    self.log(f"  ⚠ {label}: Tageskontingent für „{modell}“ aufgebraucht (bis {uhrzeit(bis)}) – nächstes Modell")
                    self.on_update()
                    continue
                self.store.fehler(e["id"], f)
                self.on_update()
                if f.art == "minute":
                    if "überlastet" in f.meldung:
                        self.log(f"  ⏳ {label}: {f.meldung}")
                    else:
                        self.log(f"  ⏳ {label}: Minutenlimit erreicht – Pause {f.retry_after or 20:.0f} s, nehme anderen Key falls frei")
                    continue
                if f.art == "tag":
                    self.log(f"  ⚠ {label}: {f.meldung} (bis {uhrzeit(self.store.nutzung(e['id'])['erschoepft_bis'])}) – wechsle")
                    continue
                if f.art in ("key", "region"):
                    self.ausgeschlossen.add(e["id"])
                    self.log(f"  ❌ {label}: {f.meldung} – wird übersprungen")
                    continue
                if f.art == "modell":
                    self._kaputt.add((name, modell))
                    self.store.modell_pausieren(name, modell, 7 * 86400)     # abgeschaltet -> eine Woche merken
                    self.log(f"  ⚠ {titel}: Modell „{modell}“ nicht verfügbar – nehme das nächste")
                    continue
                if f.art == "kosten":
                    with self.store.lock:      # Hinweis im Key-Manager für einen Tag (oder bis neu getestet)
                        self.store.nutzung(e["id"])["guthaben_leer"] = time.time() + 86400
                        self.store.save()
                    self.store.modell_sperren(e["id"], modell, time.time() + 86400)
                    self.log(f"  💶 {label}: „{modell}“ – {f.meldung}. Modell wird übersprungen.")
                    continue
                if f.art == "zu_gross":
                    raise ZuGross(f"{label}: {f.meldung}")
                if f.art == "ausgabe":
                    raise AusgabeFehler(f"{label}: {f.meldung}")
                if f.art == "ueberlastet":
                    ueberlastet += 1
                    self.store.modell_pausieren(name, modell, UEBERLAST_PAUSE)
                    self.log(f"  ↪ {titel}: Modell „{modell}“ ist überlastet – {UEBERLAST_PAUSE // 60} min Pause für dieses Modell")
                    if ueberlastet > 8:
                        raise KIFehler(f"{titel} ist dauerhaft überlastet. Später erneut versuchen "
                                       "oder in den Einstellungen ein anderes (Ausweich-)Modell wählen.")
                    continue
                raise KIFehler(f"{label}: {f.meldung}")
            self.store.erfolg(e["id"], antwort.tokens, antwort.info)
            self.requests += 1
            self.aktiv = (name, e)
            self.on_update()
            return antwort if recherche else antwort.parsed
        raise KIFehler("Zu viele Fehlversuche bei der KI-Anfrage.")
