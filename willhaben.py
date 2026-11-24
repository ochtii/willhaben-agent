"""Willhaben-Scraper: durchsucht ALLE Ergebnisseiten einer Suche und lädt die Beschreibungen.

Willhaben ist eine Next.js-Seite. Suchergebnisse und Anzeigendetails stecken als JSON im
<script id="__NEXT_DATA__"> der normalen HTML-Seite:
  Suche:  props.pageProps.searchResult  -> advertSummaryList.advertSummary, rowsFound, navigatorGroups
  Detail: props.pageProps.advertDetails -> attributes (DESCRIPTION, ...), attributeInformation (Marke, Zustand, ...)
(Stand Nov. 2026 live geprüft.)
"""

from __future__ import annotations

import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, parse_qsl, urlencode

import requests

BASE = "https://www.willhaben.at"
DEFAULT_PATH = "kaufen-und-verkaufen/marktplatz"

# Kategorien: alle willhaben-Kategorien mit Kurznamen stehen in kategorien.py. Für Sonderfilter
# die Such-URL aus dem Browser mit --url übergeben, das funktioniert immer.
import kategorien  # noqa: E402

CATEGORIES = kategorien.KURZ

# areaId der Bundesländer (live geprüft). Bezirke werden über --bezirk automatisch
# in willhaben-areaIds aufgelöst (siehe Willhaben.resolve_bezirke).
BUNDESLAENDER = {
    "burgenland": 1,
    "kaernten": 2, "kärnten": 2,
    "niederoesterreich": 3, "niederösterreich": 3, "noe": 3, "nö": 3,
    "oberoesterreich": 4, "oberösterreich": 4, "ooe": 4, "oö": 4,
    "salzburg": 5,
    "steiermark": 6,
    "tirol": 7,
    "vorarlberg": 8,
    "wien": 900,
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
    "Accept-Language": "de-AT,de;q=0.9",
}


@dataclass
class Listing:
    id: str
    title: str
    price: float | None
    price_text: str
    location: str
    district: str
    state: str
    postcode: str
    url: str
    published: str
    is_private: bool | None
    teaser: str                      # Kurzbeschreibung aus der Ergebnisliste
    description: str = ""            # volle Beschreibung von der Detailseite
    image: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- utils

def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</li>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _attrs(obj: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for a in ((obj.get("attributes") or {}).get("attribute") or []):
        name = a.get("name")
        if name:
            out[name] = [str(v) for v in (a.get("values") or [])]
    return out


def _first(attrs: dict, *names: str, default: str = "") -> str:
    for n in names:
        if attrs.get(n):
            return attrs[n][0]
    return default


def _parse_price(attrs: dict) -> tuple[float | None, str]:
    raw = _first(attrs, "PRICE", "PRICE/AMOUNT")
    text = _first(attrs, "PRICE_FOR_DISPLAY", default=raw)
    try:
        return (float(raw) if raw else None), text
    except ValueError:
        return None, text


def _next_data(html_text: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.S)
    if not m:
        raise ValueError("__NEXT_DATA__ nicht gefunden (Seitenlayout geändert oder Bot-Sperre?)")
    return json.loads(m.group(1))


def parse_summary(ad: dict) -> Listing:
    a = _attrs(ad)
    price, price_text = _parse_price(a)
    seo = _first(a, "SEO_URL")
    url = f"{BASE}/iad/{seo.lstrip('/')}" if seo else f"{BASE}/iad/object?adId={ad.get('id')}"
    priv = _first(a, "ISPRIVATE")
    return Listing(
        id=str(ad.get("id")),
        title=_first(a, "HEADING", default=ad.get("description") or ""),
        price=price,
        price_text=price_text or ("" if price is None else f"€ {price:,.0f}"),
        location=_first(a, "LOCATION"),
        district=_first(a, "DISTRICT"),
        state=_first(a, "STATE"),
        postcode=_first(a, "POSTCODE"),
        url=url,
        published=_first(a, "PUBLISHED_String", "PUBLISHED"),
        is_private=None if priv == "" else priv == "1",
        teaser=_strip_html(_first(a, "BODY_DYN", "DESCRIPTION")),
        image=(_first(a, "MMO", "ALL_IMAGE_URLS").split(";")[0]),
    )


# --------------------------------------------------------------------------- client

class Abgebrochen(Exception):
    pass


class Willhaben:
    def __init__(self, delay: float = 0.6, timeout: float = 20.0):
        self.s = requests.Session()
        self.s.headers.update(HEADERS)
        self.delay = delay
        self.timeout = timeout
        self.stop = threading.Event()   # von der GUI gesetzt -> Abbruch
        self.gebremst = False
        self.on_bremse = None             # Callback für Meldungen, wenn willhaben bremst

    def _check(self):
        if self.stop.is_set():
            raise Abgebrochen("Vom Benutzer abgebrochen")

    def _get(self, url: str, params=None, headers=None, tries: int = 4) -> requests.Response:
        """GET mit Wiederholung. Bei HTTP 429 (willhaben bremst) wird länger gewartet, ggf. laut Retry-After."""
        last = None
        bremsungen = 0
        i = 0
        while i < tries:
            self._check()
            try:
                r = self.s.get(url, params=params, headers=headers, timeout=self.timeout)
                if r.status_code == 429:
                    bremsungen += 1
                    if bremsungen > 6:
                        raise RuntimeError("willhaben bremst dauerhaft (HTTP 429) – bitte später erneut versuchen")
                    try:
                        wait = float(r.headers.get("Retry-After", ""))
                    except ValueError:
                        wait = 15.0 * bremsungen
                    self.gebremst = True
                    if self.on_bremse:
                        self.on_bremse(f"willhaben bremst (zu viele Anfragen) – warte {wait:.0f} s …")
                    self._schlafen(min(wait, 120))
                    continue                       # zählt nicht als normaler Fehlversuch
                if r.status_code in (500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last = e
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (403, 404, 410):   # sinnlos zu wiederholen
                    break
                self._schlafen(1.5 * (2 ** i))
                i += 1
        raise RuntimeError(f"Abruf fehlgeschlagen: {url} ({last})")

    def _schlafen(self, sekunden: float):
        end = time.time() + sekunden
        while time.time() < end:
            self._check()
            time.sleep(min(0.25, max(0.0, end - time.time())))

    def _search_page(self, path: str, params: list[tuple[str, str]]) -> dict:
        r = self._get(f"{BASE}/iad/{path}", params=params)
        nd = _next_data(r.text)
        sr = nd.get("props", {}).get("pageProps", {}).get("searchResult")
        if not sr:
            raise ValueError("Kein searchResult in der Seite gefunden.")
        return sr

    def navigator_values(self, path: str, params: list[tuple[str, str]]) -> dict[str, list[tuple[str, dict]]]:
        """Filterwerte, die willhaben für diese Suche anbietet: {navigator_id: [(label, {param: wert})]}."""
        p = [kv for kv in params if kv[0] not in ("page", "rows")] + [("rows", "1")]
        sr = self._search_page(path, p)
        out: dict[str, list] = {}
        for g in sr.get("navigatorGroups") or []:
            for n in g.get("navigatorList") or []:
                for gv in n.get("groupedPossibleValues") or []:
                    for v in gv.get("possibleValues") or []:
                        prm = {u.get("urlParameterName"): u.get("value")
                               for u in v.get("urlParamRepresentationForValue") or []}
                        out.setdefault(n.get("id"), []).append((v.get("label") or "", prm))
        return out

    def resolve_bezirke(self, path: str, params: list[tuple[str, str]], names: list[str]
                        ) -> tuple[list[str], list[str], list[str]]:
        """Bezirksnamen/PLZ-Bereiche -> willhaben-areaIds. Funktioniert, wenn ein Bundesland gewählt ist.
        Rückgabe: (areaIds, gefundene Labels, nicht gefundene Namen)."""
        try:
            districts = self.navigator_values(path, params).get("district", [])
        except Exception:
            districts = []
        ids, labels, missing = [], [], []
        for name in names:
            key = name.strip().lower()
            hits = [(lab, prm) for lab, prm in districts
                    if key in lab.lower() and prm.get("areaId")]
            if not hits and key.isdigit() and len(key) == 4 and key.startswith("1"):
                # Wiener PLZ 1100 -> "10. Bezirk"
                hits = [(lab, prm) for lab, prm in districts
                        if f"{int(key[1:3]):02d}. bezirk" in lab.lower()]
            if not hits:
                missing.append(name)
            for lab, prm in hits:
                ids.append(prm["areaId"])
                labels.append(lab)
        return ids, labels, missing

    def search(self, path: str, params: list[tuple[str, str]], rows: int = 200,
               max_pages: int | None = None, progress=print, on_page=None) -> list[Listing]:
        """Holt ALLE Seiten der Suche (bis rowsFound erreicht ist)."""
        results: dict[str, Listing] = {}
        page, total = 1, None
        while True:
            self._check()
            p = [kv for kv in params if kv[0] not in ("page", "rows")]
            p += [("rows", str(rows)), ("page", str(page))]
            sr = self._search_page(path, p)
            total = int(sr.get("rowsFound") or 0)
            ads = (sr.get("advertSummaryList") or {}).get("advertSummary") or []
            for ad in ads:
                try:
                    li = parse_summary(ad)
                    results.setdefault(li.id, li)
                except Exception:
                    continue
            progress(f"  Seite {page}: {len(ads)} Anzeigen  (gesamt {len(results)}/{total})")
            if on_page:
                on_page(list(results.values()), total)
            if not ads or len(results) >= total or len(ads) < rows:
                break
            if max_pages and page >= max_pages:
                break
            page += 1
            time.sleep(self.delay)
        return list(results.values())

    def fetch_description(self, li: Listing) -> Listing:
        if self.stop.is_set():
            return li
        try:
            r = self._get(li.url, tries=2)
            nd = _next_data(r.text)
            det = nd.get("props", {}).get("pageProps", {}).get("advertDetails") or {}
            a = _attrs(det)
            desc = _first(a, "DESCRIPTION", "BODY_DYN") or det.get("description") or ""
            li.description = _strip_html(desc)
            # strukturierte Kategorie-Felder (Marke, Display, Zustand, Übergabe, ...).
            # Bewusst KEINE Kontakt-/Adressdaten des Verkäufers übernehmen.
            extra = {}
            for info in det.get("attributeInformation") or []:
                lab = (info.get("treeAttributeElement") or {}).get("label")
                vals = [v.get("label") for v in info.get("values") or [] if v.get("label")]
                if lab and vals:
                    extra[lab] = ", ".join(vals)
            if _first(a, "ISPRIVATE"):
                extra["Anbieter"] = "privat" if _first(a, "ISPRIVATE") == "1" else "Händler"
                li.is_private = _first(a, "ISPRIVATE") == "1"
            li.extra = extra
        except Exception as e:
            li.description = li.teaser
            li.extra = {"_fehler": str(e)[:100]}
        time.sleep(self.delay)
        return li

    def fetch_descriptions(self, listings: list[Listing], workers: int = 3, progress=print,
                           on_progress=None) -> None:
        done = 0
        ex = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [ex.submit(self.fetch_description, li) for li in listings]
            for fut in as_completed(futures):
                if self.stop.is_set():
                    break
                li = fut.result()
                done += 1
                if on_progress:
                    on_progress(done, len(listings), li)
                if done % 20 == 0 or done == len(listings):
                    progress(f"  Beschreibungen: {done}/{len(listings)}")
        finally:
            ex.shutdown(wait=True, cancel_futures=True)
        self._check()


# --------------------------------------------------------------------------- params

def build_query(keyword: str | None, price_from: int | None, price_to: int | None,
                bundesland: list[str] | None, area_ids: list[int] | None,
                category: str | None, url: str | None) -> tuple[str, list[tuple[str, str]]]:
    """Liefert (pfad, params). Eine Browser-URL (--url) hat Vorrang, Optionen werden ergänzt."""
    params: list[tuple[str, str]] = []
    if url:
        u = urlparse(url)
        path = u.path.split("/iad/", 1)[-1].strip("/") or DEFAULT_PATH
        params = parse_qsl(u.query)
    else:
        cat = (category or "alle").strip()
        path = kategorien.pfad(cat)

    def setp(k, v):
        nonlocal params
        params = [kv for kv in params if kv[0] != k] + [(k, str(v))]

    if keyword:
        setp("keyword", keyword)
    if price_from is not None:
        setp("PRICE_FROM", price_from)
    if price_to is not None:
        setp("PRICE_TO", price_to)
    for bl in bundesland or []:
        key = bl.strip().lower()
        if key not in BUNDESLAENDER:
            raise SystemExit(f"Unbekanntes Bundesland '{bl}'. Erlaubt: {', '.join(sorted(set(BUNDESLAENDER)))}")
        params.append(("areaId", str(BUNDESLAENDER[key])))
    for aid in area_ids or []:
        params.append(("areaId", str(aid)))
    return path, params


def filter_bezirk(listings: list[Listing], bezirke: list[str]) -> list[Listing]:
    keys = [b.lower() for b in bezirke]
    return [li for li in listings
            if any(k in f"{li.district} {li.location} {li.postcode}".lower() for k in keys)]


def debug_url(path: str, params) -> str:
    return f"{BASE}/iad/{path}?{urlencode(params)}"
