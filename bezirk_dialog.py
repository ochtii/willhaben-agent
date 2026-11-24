"""Auswahlfenster für die Bezirke eines Bundeslands (Liste live von willhaben, inkl. Anzeigenzahl)."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from willhaben import Willhaben, BUNDESLAENDER

# Bezirkslisten pro Bundesland (nur einmal pro Programmstart laden)
_CACHE: dict[str, list[tuple[str, str, int | None]]] = {}
_LOCK = threading.Lock()


def kurzname(label: str) -> str:
    """'Wien, 10. Bezirk, Favoriten' -> '10. Favoriten'; andere Bundesländer bleiben unverändert."""
    teile = [t.strip() for t in label.split(",")]
    if len(teile) == 3 and teile[1].endswith("Bezirk"):
        return f"{teile[1].split('.')[0]}. {teile[2]}"
    return label


def bezirke_laden(bl_key: str) -> list[tuple[str, str, int | None]]:
    """[(Name, areaId, Anzahl Anzeigen)] für ein Bundesland, live von willhaben."""
    with _LOCK:
        if bl_key in _CACHE:
            return _CACHE[bl_key]
    wh = Willhaben()
    sr = wh._search_page("kaufen-und-verkaufen/marktplatz",
                         [("areaId", str(BUNDESLAENDER[bl_key])), ("rows", "1")])
    out = []
    for g in sr.get("navigatorGroups") or []:
        for n in g.get("navigatorList") or []:
            if n.get("id") != "district":
                continue
            for gv in n.get("groupedPossibleValues") or []:
                for v in gv.get("possibleValues") or []:
                    prm = {u.get("urlParameterName"): u.get("value") for u in v.get("urlParamRepresentationForValue") or []}
                    if prm.get("areaId"):
                        out.append((v.get("label") or "", str(prm["areaId"]), v.get("hits")))
    with _LOCK:
        _CACHE[bl_key] = out
    return out


class BezirkDialog(tk.Toplevel):
    """Mehrfachauswahl der Bezirke eines Bundeslands. on_ok([(Name, areaId), ...]) – leere Liste = alle Bezirke."""

    def __init__(self, master, bl_key: str, bl_name: str, auswahl: list[tuple[str, str]], on_ok):
        super().__init__(master)
        self.title(f"Bezirke – {bl_name}")
        self.transient(master)
        self.geometry("540x600")
        self.minsize(500, 440)
        self.on_ok = on_ok
        self.bl_key = bl_key
        self.gewaehlt = {aid for _, aid in auswahl}
        self.vars: dict[str, tuple[tk.BooleanVar, str]] = {}
        self.zeilen: list[tuple[str, ttk.Checkbutton]] = []

        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"Bezirke in {bl_name}", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(f, text="Nichts angehakt = ganzes Bundesland. Zahl = aktuelle Anzeigen im Bezirk (alle Kategorien).",
                  foreground="#666", wraplength=500, justify="left").pack(anchor="w", pady=(0, 6))
        self.var_suche = tk.StringVar()
        suche = ttk.Entry(f, textvariable=self.var_suche)
        suche.pack(fill="x")
        suche.insert(0, "")
        self.var_suche.trace_add("write", lambda *a: self._filtern())
        ttk.Label(f, text="Suchen, z.B. „Baden“ oder „10.“", foreground="#888").pack(anchor="w")

        rahmen = ttk.Frame(f)
        rahmen.pack(fill="both", expand=True, pady=(6, 6))
        self.canvas = tk.Canvas(rahmen, highlightthickness=0)
        sb = ttk.Scrollbar(rahmen, orient="vertical", command=self.canvas.yview)
        self.liste = ttk.Frame(self.canvas)
        self.liste.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        win = self.canvas.create_window((0, 0), window=self.liste, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for seq, d in (("<Button-4>", -1), ("<Button-5>", 1)):
            self.canvas.bind_all(seq, lambda e, d=d: self._scroll(e, d), add="+")
        self.canvas.bind_all("<MouseWheel>", lambda e: self._scroll(e, -1 if e.delta > 0 else 1), add="+")
        self.lbl_status = ttk.Label(self.liste, text="Lade Bezirke von willhaben …", foreground="#666")
        self.lbl_status.pack(anchor="w", pady=10)

        self.lbl_anzahl = ttk.Label(f, text="", foreground="#444")
        self.lbl_anzahl.pack(anchor="w")
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(8, 0))
        ttk.Button(bf, text="Alle", command=lambda: self._alle(True)).pack(side="left")
        ttk.Button(bf, text="Keine", command=lambda: self._alle(False)).pack(side="left", padx=6)
        ttk.Button(bf, text="Übernehmen", command=self._ok).pack(side="right")
        ttk.Button(bf, text="Abbrechen", command=self.destroy).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        suche.focus_set()
        self.after(50, self.grab_set)
        threading.Thread(target=self._laden, daemon=True).start()

    def _scroll(self, event, richtung):
        w = self.winfo_containing(event.x_root, event.y_root)
        while w is not None:
            if w is self.canvas:
                self.canvas.yview_scroll(richtung * 2, "units")
                return
            w = getattr(w, "master", None)

    def _laden(self):
        try:
            daten, fehler = bezirke_laden(self.bl_key), ""
        except Exception as e:
            daten, fehler = [], str(e)
        self.after(0, lambda: self.winfo_exists() and self._anzeigen(daten, fehler))

    def _anzeigen(self, daten, fehler):
        self.lbl_status.destroy()
        if fehler or not daten:
            ttk.Label(self.liste, text=f"Bezirke konnten nicht geladen werden.\n{fehler}", foreground="#b00020",
                      wraplength=340).pack(anchor="w", pady=10)
            return
        for name, aid, hits in daten:
            v = tk.BooleanVar(value=aid in self.gewaehlt)
            v.trace_add("write", lambda *a: self._zaehlen())
            text = kurzname(name) + (f"   ({hits:,} Anz.)".replace(",", ".") if hits is not None else "")
            cb = ttk.Checkbutton(self.liste, text=text, variable=v)
            cb.pack(anchor="w", pady=1)
            self.vars[aid] = (v, name)
            self.zeilen.append((name.lower() + " " + kurzname(name).lower(), cb))
        self._zaehlen()

    def _filtern(self):
        q = self.var_suche.get().strip().lower()
        for text, cb in self.zeilen:
            cb.pack_forget()
        for text, cb in self.zeilen:
            if not q or q in text:
                cb.pack(anchor="w", pady=1)
        self.canvas.yview_moveto(0)

    def _alle(self, wert: bool):
        q = self.var_suche.get().strip().lower()
        for (aid, (v, name)), (text, _) in zip(self.vars.items(), self.zeilen):
            if not q or q in text:
                v.set(wert)

    def _zaehlen(self):
        n = sum(1 for v, _ in self.vars.values() if v.get())
        self.lbl_anzahl.configure(text=f"{n} von {len(self.vars)} Bezirken gewählt" if n else
                                  f"Keine Auswahl → ganzes Bundesland ({len(self.vars)} Bezirke)")

    def _ok(self):
        if self.vars:     # nur übernehmen, wenn die Liste geladen wurde
            self.on_ok([(name, aid) for aid, (v, name) in self.vars.items() if v.get()])
        self.destroy()
