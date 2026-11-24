"""Gemeinsamer Ablauf für GUI und Kommandozeile: suchen -> Details laden -> KI bewerten -> Bericht."""

from __future__ import annotations

import json
import re
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from willhaben import Willhaben, Listing, build_query, filter_bezirk, debug_url
from rating import Bewerter, Bewertung, Ergebnis
from keys import KeyStore, Verteiler


@dataclass
class Auftrag:
    suche: str = ""
    kategorie: str = "laptops"
    url: str = ""
    von: int | None = None
    bis: int | None = None
    bundeslaender: list[str] = field(default_factory=list)
    bezirke: list[str] = field(default_factory=list)
    area_ids: list[int] = field(default_factory=list)
    bezirk_namen: list[str] = field(default_factory=list)   # Namen zu area_ids (nur für Anzeige/Bericht)
    beschreibung: str = ""
    top: int = 10
    max_seiten: int | None = None
    max_anzeigen: int | None = None
    ohne_details: bool = False
    nur_scrapen: bool = False
    marktrecherche: bool = True               # aktuelle Marktlage per Google-Suche (Gemini) einbeziehen
    modelle: dict | None = None               # {"gemini": "gemini-3.5-flash"}; None = aus den Einstellungen
    verteilung: str | None = None             # "gleichmaessig" | "nacheinander"
    ausweich: dict | None = None              # Ausweichmodelle bei Überlastung, z.B. {"gemini": "gemini-3.5-flash"}
    paketgroesse: int | None = None           # None = Standard (30 Anzeigen pro KI-Anfrage)
    ausgabe: str = "ergebnisse"


class Ereignisse:
    """Rückmeldungen an die Oberfläche. Die GUI überschreibt diese Methoden."""

    def log(self, msg: str) -> None:
        print(msg, flush=True)

    def phase(self, name: str, done: int = 0, total: int = 0) -> None:
        pass

    def anzeigen(self, listings: list[Listing], total: int) -> None:
        pass

    def details(self, li: Listing) -> None:
        pass

    def bewertungen(self, bew: list[Bewertung]) -> None:
        pass

    def ergebnis(self, erg: Ergebnis, md: str, md_file: Path, by_id: dict[str, Listing]) -> None:
        pass

    def keys(self) -> None:
        """Verbrauch/Status eines Keys hat sich geändert."""
        pass

    def marktlage(self, text: str, quellen: list[tuple[str, str]]) -> None:
        pass


def stats_of(listings) -> dict:
    prices = [li.price for li in listings if li.price and li.price > 0]
    if not prices:
        return {"anzahl": len(listings)}
    return {"anzahl": len(listings), "min": min(prices), "median": statistics.median(prices),
            "max": max(prices)}


def marktpreise(pairs) -> dict:
    """Echte willhaben-Marktpreise der passenden Anzeigen, gruppiert nach RAM und Zustand (Median, Anzahl)."""
    def gruppe(key_fn):
        g: dict[str, list[float]] = {}
        for li, b in pairs:
            k = key_fn(li, b)
            if k and li.price and li.price > 0:
                g.setdefault(k, []).append(li.price)
        return {k: {"median_eur": round(statistics.median(v)), "anzahl": len(v)}
                for k, v in sorted(g.items()) if len(v) >= 2}

    def ram(li, b):
        m = re.search(r"(\d{1,3})\s*GB\s*(?:DDR\d\s*)?RAM", f"{b.specs} {li.title}", re.I)
        return f"{m.group(1)} GB RAM" if m else None

    def zustand(li, b):
        z = (b.zustand or "").lower()
        for k in ("neu", "neuwertig", "generalüberholt", "gut", "gebrauchsspuren", "defekt"):
            if k in z:
                return k
        return None
    return {"nach_ram": gruppe(ram), "nach_zustand": gruppe(zustand)}


def region_text(a: "Auftrag") -> str:
    from willhaben import BUNDESLAENDER
    namen = {"wien": "Wien", "niederoesterreich": "Niederösterreich", "oberoesterreich": "Oberösterreich",
             "steiermark": "Steiermark", "kaernten": "Kärnten", "salzburg": "Salzburg", "tirol": "Tirol",
             "vorarlberg": "Vorarlberg", "burgenland": "Burgenland"}
    teile = [namen.get(b, b) for b in a.bundeslaender] + list(a.bezirk_namen) + list(a.bezirke)
    return ", ".join(teile) or "ganz Österreich"


def render_md(a: Auftrag, erg: Ergebnis, by_id, total_found, scored, stats, kiname: str,
              marktlage: str = "", quellen: list | None = None) -> str:
    titel = a.suche or a.kategorie or "Suche"
    lines = [f"# Willhaben-Auswertung: {titel}", "",
             f"*{datetime.now():%d.%m.%Y %H:%M}* · Wunsch: **{a.beschreibung}** · "
             f"Budget: {a.von or 0}–{a.bis or '∞'} € · "
             f"Region: {region_text(a)} · KI: {kiname}", "",
             f"Durchsucht: **{total_found} Anzeigen**, davon {scored} KI-bewertet · "
             f"Preise: min {stats.get('min', '-')} € / Median {stats.get('median', '-')} € / max {stats.get('max', '-')} €",
             "", "## Marktüberblick", "", erg.zusammenfassung, ""]
    mp = stats.get("willhaben_marktpreise", {}).get("nach_ram", {})
    if mp:
        lines += ["**willhaben-Preise der passenden Angebote (Median):** "
                  + " · ".join(f"{k}: {v['median_eur']} € ({v['anzahl']}×)" for k, v in mp.items()), ""]
    if marktlage:
        lines += ["## Aktuelle Marktlage (Google-Suche)", "", marktlage, ""]
        if quellen:
            lines += ["Quellen: " + " · ".join(f"[{t}]({u})" for t, u in quellen), ""]
    if erg.tipp:
        lines += [f"> **Tipp:** {erg.tipp}", ""]
    lines += [f"## Top {len(erg.top)}", ""]
    for t in erg.top:
        li = by_id.get(t.id)
        ort = f"{li.postcode} {li.location}".strip() if li else ""
        link = f" · [Zur Anzeige]({li.url})" if li else ""
        lines += [f"### {t.rang}. {t.titel} — {t.preis}", "", f"{t.specs}  ", f"📍 {ort}{link}", "",
                  "**Vorteile**"] + [f"- ✅ {v}" for v in t.vorteile] + [
                  "", "**Nachteile**"] + [f"- ⚠️ {n}" for n in t.nachteile] + ["", f"*{t.fazit}*", ""]
    return "\n".join(lines)


def run(a: Auftrag, ev: Ereignisse | None = None, stop: threading.Event | None = None,
        store: KeyStore | None = None) -> Path | None:
    """Führt den kompletten Auftrag aus. Gibt den Pfad zum Bericht (oder zur JSON-Datei) zurück."""
    ev = ev or Ereignisse()
    stop = stop or threading.Event()
    log = ev.log
    if not a.beschreibung:
        a.beschreibung = a.suche or "gutes Preis/Leistungs-Verhältnis"

    # KI zuerst vorbereiten -> fehlender/ungültiger Key fällt sofort auf, nicht erst nach dem Scrapen
    bewerter = None
    if not a.nur_scrapen:
        store = store or KeyStore()
        backend = Verteiler(store, a.modelle, a.verteilung, log=log, stop=stop, on_update=ev.keys,
                            ausweich=a.ausweich)
        if not backend.anbieter_jetzt():
            from keys import KIFehler
            raise KIFehler(backend._zusammenfassung())
        bewerter = Bewerter(backend, log=log, stop=stop)
        log(f"🤖 KI: {backend.beschreibung()}")

    path, params = build_query(a.suche or None, a.von, a.bis, a.bundeslaender,
                               a.area_ids, a.kategorie, a.url or None)
    wh = Willhaben()
    wh.stop = stop
    wh.on_bremse = lambda m: log("  ⏳ " + m)

    ev.phase("Suche", 0, 0)
    text_bezirke = list(a.bezirke)
    if a.bezirke:
        ids, labels, missing = wh.resolve_bezirke(path, params, a.bezirke)
        if ids and not missing:
            # getippte Bezirke ersetzen die Bundesland-Filter; per Auswahl gewählte Bezirke bleiben erhalten
            params = ([kv for kv in params if kv[0] != "areaId"] + [("areaId", str(i)) for i in a.area_ids]
                      + [("areaId", i) for i in ids])
            text_bezirke = []
            log(f"📍 Bezirke erkannt: {'; '.join(labels)}")
        else:
            hint = "" if a.bundeslaender else " (Tipp: Bundesland wählen, dann werden Bezirke exakt aufgelöst)"
            log(f"📍 Bezirk(e) {missing or a.bezirke} nicht als willhaben-Bezirk erkannt → Textfilter auf Ort/PLZ{hint}")

    log(f"🔎 Suche: {debug_url(path, params)}")

    def on_page(found, total):
        ev.phase("Suche", len(found), total)
        ev.anzeigen(found, total)

    listings = wh.search(path, params, max_pages=a.max_seiten, progress=log, on_page=on_page)
    total_found = len(listings)
    if text_bezirke:
        listings = filter_bezirk(listings, text_bezirke)
        log(f"📍 Textfilter {text_bezirke}: {len(listings)} von {total_found} übrig")
    if a.von is not None:
        listings = [li for li in listings if li.price is None or li.price >= a.von]
    if a.bis is not None:
        listings = [li for li in listings if li.price is None or li.price <= a.bis]
    ev.anzeigen(listings, len(listings))
    if not listings:
        log("❌ Keine Anzeigen gefunden.")
        return None
    log(f"✔ {len(listings)} Anzeigen gefunden")

    if not a.ohne_details:
        log(f"📄 Lade {len(listings)} Detailbeschreibungen …")
        ev.phase("Details", 0, len(listings))
        wh.fetch_descriptions(listings, progress=log,
                              on_progress=lambda d, t, li: (ev.phase("Details", d, t), ev.details(li)))

    out = Path(a.ausgabe).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", (a.suche or a.kategorie or "suche").lower()).strip("-")[:40] or "suche"
    raw_file = out / f"{stamp}-{slug}-anzeigen.json"
    raw_file.write_text(json.dumps([li.to_dict() for li in listings], ensure_ascii=False, indent=1))
    log(f"💾 Anzeigen gespeichert: {raw_file}")
    if a.nur_scrapen:
        ev.phase("Fertig", 1, 1)
        return raw_file

    to_score = listings
    if a.max_anzeigen and len(listings) > a.max_anzeigen:
        to_score = sorted(listings, key=lambda li: li.price or 0)[: a.max_anzeigen]
        log(f"⚠ Limit: bewerte nur {len(to_score)} von {len(listings)} Anzeigen")

    if a.marktrecherche:
        log("🌐 Marktrecherche: aktuelle Preise & Trends per Google-Suche …")
        ev.phase("KI-Bewertung", 0, len(to_score))
        text = bewerter.marktrecherche(a.suche, a.kategorie if not a.url else "", a.beschreibung, a.von, a.bis)
        if text:
            log("🌐 Aktuelle Marktlage:\n" + "\n".join("   " + z for z in text.splitlines() if z.strip()))
            if bewerter.quellen:
                log("   Quellen: " + ", ".join(t for t, _ in bewerter.quellen[:6]))
            ev.marktlage(text, bewerter.quellen)

    size = a.paketgroesse or bewerter.backend.paketgroesse()
    log(f"🤖 Stufe 1: bewerte {len(to_score)} Anzeigen in ca. {-(-len(to_score) // size)} Paketen …")
    ev.phase("KI-Bewertung", 0, len(to_score))
    bew = bewerter.score(to_score, a.beschreibung, a.von, a.bis, batch_size=a.paketgroesse,
                         on_batch=lambda n, t, res: (ev.phase("KI-Bewertung", n, t), ev.bewertungen(res)))

    by_id = {li.id: li for li in listings}
    pairs = [(by_id[i], b) for i, b in bew.items() if i in by_id and b.relevant]
    log(f"✔ {len(pairs)} von {len(bew)} bewerteten Anzeigen sind relevant")
    if not pairs:
        log("❌ Keine relevanten Anzeigen nach KI-Bewertung.")
        return None

    def key(pb):
        b = pb[1]
        return 0.65 * b.preis_leistung + 0.35 * b.leistung - 6 * len(b.warnsignale)
    pairs.sort(key=key, reverse=True)
    n_cand = min(len(pairs), max(a.top * 3, 25))
    candidates = pairs[:n_cand]

    log(f"🏆 Stufe 2: Endvergleich der besten {n_cand} Kandidaten …")
    ev.phase("Endvergleich", 0, 1)
    stats = stats_of([li for li, _ in pairs])
    stats["willhaben_marktpreise"] = marktpreise(pairs)
    if stats["willhaben_marktpreise"]["nach_ram"]:
        log("📊 willhaben-Marktpreise (Median): " + " · ".join(
            f"{k}: {v['median_eur']} €" for k, v in stats["willhaben_marktpreise"]["nach_ram"].items()))
    erg = bewerter.final(candidates, a.beschreibung, a.von, a.bis, min(a.top, n_cand), stats)
    ev.phase("Endvergleich", 1, 1)

    md = render_md(a, erg, by_id, total_found, len(bew), stats,
                   f"{bewerter.backend.name} ({bewerter.backend.model})", bewerter.marktlage, bewerter.quellen)
    md_file = out / f"{stamp}-{slug}-top{a.top}.md"
    md_file.write_text(md)
    (out / f"{stamp}-{slug}-bewertungen.json").write_text(json.dumps(
        {"ergebnis": erg.model_dump(), "vorbewertung": {k: v.model_dump() for k, v in bew.items()}},
        ensure_ascii=False, indent=1))
    log(f"✅ Fertig! Bericht: {md_file}  ({bewerter.backend.requests} KI-Anfragen)")
    ev.phase("Fertig", 1, 1)
    ev.ergebnis(erg, md, md_file, by_id)
    return md_file
