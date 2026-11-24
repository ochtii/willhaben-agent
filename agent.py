#!/usr/bin/env python3
"""Willhaben KI-Agent (Terminal-Version). Die grafische Version: gui.py

Beispiel:
  python agent.py --kategorie laptops --von 200 --bis 600 --bundesland wien \\
      --beschreibung "Laptop für Uni, leicht, guter Akku, 16GB RAM" --top 10

Google-Gemini-Keys werden aus den Einstellungen der GUI (~/.config/willhaben-agent/keys.json) und aus
den Umgebungsvariablen GEMINI_API_KEY (mehrere kommagetrennt in GEMINI_API_KEYS) gelesen.
  python agent.py --keys                       # Keys, Modelle, Limits und Verbrauch anzeigen
  python agent.py --key-hinzufuegen "Privat" AIza...
"""

from __future__ import annotations

import argparse
import sys

import settings
from keys import KeyStore, KIFehler, maskiert
from pipeline import Auftrag, run
from willhaben import CATEGORIES, Abgebrochen


def keys_anzeigen(store: KeyStore) -> None:
    o = store.optionen
    print(f"\nGoogle Gemini – Modell: {o['modelle'].get('gemini')} · Ausweichmodell: "
          f"{o.get('ausweich', {}).get('gemini') or '–'} · Verteilung: {o['verteilung']}")
    eintraege = store.eintraege("gemini")
    if not eintraege:
        print("  – keine Keys –")
    for e in eintraege:
        u, lim = store.nutzung(e["id"]), store.limits(e)
        def fmt(f):
            v, q = lim[f]
            return f"{v}" + ("*" if q == "Annahme" else "") if v else "?"
        print(f"  [{'x' if e.get('aktiv', True) else ' '}] {e['label']:<18} {maskiert(e['key']):<12} "
              f"{store.status_text(e):<26} heute {u.get('anfragen', 0)} Anfr., {u.get('token', 0)} Token "
              f"(Limit/Min: {fmt('rpm')} Anfr., {fmt('tpm')} Token)")
    print("(* = Annahme, echte Werte in AI Studio unter „Rate limits“)")


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
    p.add_argument("--verteilung", choices=["gleichmaessig", "nacheinander"], help="Keys gleichmäßig oder nacheinander nutzen")
    p.add_argument("--modell", default="", help="Gemini-Modell für diesen Lauf (Standard: Einstellungen, z.B. gemini-3.5-flash)")
    p.add_argument("--ausweichmodell", default="", help="Gemini-Ausweichmodell für diesen Lauf (Standard: Einstellungen)")
    p.add_argument("--modelle", action="store_true", help="Für den Key verfügbare Gemini-Modelle auflisten")
    p.add_argument("--ausgabe", default=settings.DEFAULT_OUTPUT, help="Ausgabeordner")
    p.add_argument("--keys", action="store_true", help="Keys, Limits und Verbrauch anzeigen und beenden")
    p.add_argument("--version", action="store_true", help="Installierte Version anzeigen")
    p.add_argument("--update", action="store_true", help="Auf GitHub nach einer neuen Version suchen und installieren")
    p.add_argument("--key-hinzufuegen", nargs=2, metavar=("NAME", "KEY"), help="Gemini-Key speichern und beenden")
    args = p.parse_args()

    try:                                     # nicht benötigte Dateien in Installationen entfernen
        import updater
        updater.aufraeumen(log=lambda m: print(m, file=sys.stderr))
    except Exception:
        pass

    if args.version or args.update:
        import updater
        info = updater.pruefen()
        print(f"Installiert: v{info.version_lokal} ({info.lokal.kurz})")
        if info.fehler:
            print(f"Update-Prüfung nicht möglich: {info.fehler}")
            return 1 if args.update else 0
        print(f"GitHub:      v{info.version_remote} ({info.remote.kurz})")
        if not info.neuer:
            print("✔ Neueste Version installiert.")
            return 0
        print("Neuere Version verfügbar. Änderungen:\n  - " + "\n  - ".join(info.aenderungen[:20]))
        if args.update:
            try:
                v = updater.installieren(info)
                print(f"✔ Update auf v{v} installiert.")
            except updater.UpdateFehler as e:
                print(f"❌ {e}")
                return 1
        else:
            print("Installieren mit:  --update")
        return 0

    store = KeyStore()
    if args.key_hinzufuegen:
        name, key = args.key_hinzufuegen
        store.add("gemini", name, key)
        print(f"✔ Gemini-Key „{name}“ gespeichert ({maskiert(key)})")
        return 0
    if args.keys:
        keys_anzeigen(store)
        return 0
    if args.modelle:
        from providers import GeminiProvider, ProviderFehler
        aktive = [e for e in store.eintraege("gemini") if e.get("aktiv", True)]
        if not aktive:
            print("Kein Gemini-Key eingetragen.")
            return 1
        try:
            for m in GeminiProvider().modelle(aktive[0]["key"]):
                print(" ", m)
        except ProviderFehler as e:
            print(f"❌ {e.meldung}")
            return 1
        return 0

    modelle = {"gemini": args.modell} if args.modell else None
    a = Auftrag(suche=args.suche, kategorie=args.kategorie, url=args.url, von=args.von, bis=args.bis,
                bundeslaender=args.bundesland, bezirke=args.bezirk, area_ids=args.area_id,
                beschreibung=args.beschreibung, top=args.top, max_seiten=args.max_seiten,
                max_anzeigen=args.max_anzeigen, ohne_details=args.ohne_details, nur_scrapen=args.nur_scrapen,
                marktrecherche=not args.ohne_marktrecherche,
                modelle=modelle, verteilung=args.verteilung, ausgabe=args.ausgabe,
                ausweich={"gemini": args.ausweichmodell} if args.ausweichmodell else None)
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
