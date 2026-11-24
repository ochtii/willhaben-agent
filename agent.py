#!/usr/bin/env python3
"""Willhaben KI-Agent (Terminal-Version). Die grafische Version: gui.py

Beispiel:
  python agent.py --kategorie laptops --von 200 --bis 600 --bundesland wien \\
      --beschreibung "Laptop für Uni, leicht, guter Akku, 16GB RAM" --top 10

Keys: werden aus den Einstellungen der GUI (~/.config/willhaben-agent/keys.json) und aus den
Umgebungsvariablen GEMINI_API_KEY / GROQ_API_KEY (mehrere kommagetrennt in *_API_KEYS) gelesen.
  python agent.py --keys                       # Keys, Limits und Verbrauch anzeigen
  python agent.py --key-hinzufuegen groq "Privat" gsk_...
"""

from __future__ import annotations

import argparse
import sys

import settings
from keys import KeyStore, KIFehler, ANBIETER, maskiert
from pipeline import Auftrag, run
from providers import PROVIDER_TITEL
from willhaben import CATEGORIES, Abgebrochen


def keys_anzeigen(store: KeyStore) -> None:
    for prov in ANBIETER:
        print(f"\n{PROVIDER_TITEL[prov]}  (Modell: {store.optionen['modelle'].get(prov)})")
        eintraege = store.eintraege(prov)
        if not eintraege:
            print("  – keine Keys –")
        for e in eintraege:
            u, lim = store.nutzung(e["id"]), store.limits(e)
            def fmt(f):
                v, q = lim[f]
                return f"{v}" + ("*" if q == "Annahme" else "") if v else "?"
            srv = u.get("server", {})
            rest = f" · Server: noch {srv['rest_anfragen']} Anfr." if "rest_anfragen" in srv else ""
            print(f"  [{'x' if e.get('aktiv', True) else ' '}] {e['label']:<18} {maskiert(e['key']):<12} "
                  f"{store.status_text(e):<22} heute {u.get('anfragen', 0)}/{fmt('rpd')} Anfr., "
                  f"{u.get('token', 0)}/{fmt('tpd')} Token{rest}")
    print(f"\nReihenfolge: {' → '.join(store.optionen['reihenfolge'])} · Verteilung: {store.optionen['verteilung']}"
          "\n(* = Annahme, echte Werte in AI Studio bzw. der Groq-Konsole)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--suche", default="", help="Suchbegriff, z.B. 'thinkpad'")
    p.add_argument("--kategorie", default="laptops", help=f"{', '.join(CATEGORIES)} oder willhaben-Pfad")
    p.add_argument("--url", default="", help="Alternativ: Such-URL aus dem Browser")
    p.add_argument("--von", type=int, help="Mindestpreis in €")
    p.add_argument("--bis", type=int, help="Höchstpreis in €")
    p.add_argument("--bundesland", action="append", default=[], help="wien, niederoesterreich, ... (mehrfach)")
    p.add_argument("--bezirk", action="append", default=[], help="z.B. Mödling, Favoriten, 1100 (mehrfach)")
    p.add_argument("--area-id", type=int, action="append", default=[], help="willhaben areaId direkt")
    p.add_argument("--beschreibung", default="", help="Was suchst du? Anforderungen, Einsatzzweck")
    p.add_argument("--top", type=int, default=10, help="Anzahl Top-Geräte (Standard 10)")
    p.add_argument("--max-seiten", type=int, help="Seitenlimit (Standard: alle)")
    p.add_argument("--max-anzeigen", type=int, help="Höchstens so viele Anzeigen KI-bewerten")
    p.add_argument("--ohne-details", action="store_true", help="Detailseiten nicht laden")
    p.add_argument("--nur-scrapen", action="store_true", help="Nur Anzeigen sammeln, keine KI")
    p.add_argument("--ohne-marktrecherche", action="store_true",
                   help="Aktuelle Marktlage NICHT per Google-Suche recherchieren (spart eine Anfrage)")
    p.add_argument("--anbieter", default="", help="Reihenfolge, z.B. 'gemini,groq' oder 'groq' (Standard: Einstellungen)")
    p.add_argument("--verteilung", choices=["gleichmaessig", "nacheinander"], help="Keys gleichmäßig oder nacheinander nutzen")
    p.add_argument("--modell-gemini", default="", help="Gemini-Modell (Standard: auto = bestes Flash-Modell)")
    p.add_argument("--modell-groq", default="", help="Groq-Modell (Standard: auto)")
    p.add_argument("--ausweich-gemini", default="", help="Gemini-Ausweichmodell bei Überlastung (Standard: gemini-3.5-flash)")
    p.add_argument("--ausgabe", default=settings.DEFAULT_OUTPUT, help="Ausgabeordner")
    p.add_argument("--keys", action="store_true", help="Keys, Limits und Verbrauch anzeigen und beenden")
    p.add_argument("--key-hinzufuegen", nargs=3, metavar=("ANBIETER", "NAME", "KEY"), help="Key speichern und beenden")
    args = p.parse_args()

    store = KeyStore()
    if args.key_hinzufuegen:
        prov, name, key = args.key_hinzufuegen
        if prov not in ANBIETER:
            p.error(f"Anbieter muss {' oder '.join(ANBIETER)} sein")
        store.add(prov, name, key)
        print(f"✔ {PROVIDER_TITEL[prov]}-Key „{name}“ gespeichert ({maskiert(key)})")
        return 0
    if args.keys:
        keys_anzeigen(store)
        return 0

    modelle = {k: v for k, v in (("gemini", args.modell_gemini), ("groq", args.modell_groq)) if v}
    a = Auftrag(suche=args.suche, kategorie=args.kategorie, url=args.url, von=args.von, bis=args.bis,
                bundeslaender=args.bundesland, bezirke=args.bezirk, area_ids=args.area_id,
                beschreibung=args.beschreibung, top=args.top, max_seiten=args.max_seiten,
                max_anzeigen=args.max_anzeigen, ohne_details=args.ohne_details, nur_scrapen=args.nur_scrapen,
                marktrecherche=not args.ohne_marktrecherche,
                reihenfolge=[x.strip() for x in args.anbieter.split(",") if x.strip()] or None,
                modelle=modelle or None, verteilung=args.verteilung, ausgabe=args.ausgabe,
                ausweich={"gemini": args.ausweich_gemini} if args.ausweich_gemini else None)
    try:
        result = run(a, store=store)
    except KIFehler as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, Abgebrochen):
        print("Abgebrochen.", file=sys.stderr)
        return 130
    if result and result.suffix == ".md":
        print("\n" + result.read_text())
        keys_anzeigen(store)
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
