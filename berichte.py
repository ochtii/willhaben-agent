"""Reiter „Berichte“: vergangene Suchläufe aus dem Ergebnis-Ordner auflisten und formatiert anzeigen.

Jeder Lauf speichert `<Zeit>-<Suche>-topN.md` (Bericht) sowie `…-anzeigen.json` und `…-bewertungen.json`.
Die Vorschau stellt den Markdown-Bericht mit Überschriften, Listen, Fettdruck und klickbaren Links dar.
"""

from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox

import plattform
import theme
from theme import P

_MUSTER = re.compile(r"^(?P<basis>.+)-top(?P<top>\d+)\.md$")


def _sicher(text: str) -> str:
    """Tk kann Zeichen außerhalb der BMP (Farb-Emojis) nicht darstellen."""
    return "".join(c for c in text if ord(c) <= 0xFFFF)


def berichte_finden(ordner: Path) -> list[dict]:
    """Alle Berichte im Ordner, neueste zuerst: {datei, basis, top, titel, datum, budget, region, wunsch, ki}."""
    out = []
    try:
        dateien = list(Path(ordner).glob("*-top*.md"))
    except OSError:
        return []
    for d in dateien:
        m = _MUSTER.match(d.name)
        if not m:
            continue
        info = {"datei": d, "basis": m.group("basis"), "top": int(m.group("top")), "titel": d.stem,
                "datum": datetime.fromtimestamp(d.stat().st_mtime), "budget": "", "region": "", "wunsch": "",
                "ki": ""}
        try:
            with d.open(encoding="utf-8") as f:
                kopf = [f.readline() for _ in range(4)]
        except OSError:
            kopf = []
        for z in kopf:
            if z.startswith("# "):
                info["titel"] = z[2:].strip().removeprefix("Willhaben-Auswertung:").strip() or info["titel"]
            elif z.startswith("*"):
                t = re.search(r"\*(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2})\*", z)
                if t:
                    try:
                        info["datum"] = datetime.strptime(t.group(1), "%d.%m.%Y %H:%M")
                    except ValueError:
                        pass
                for feld, muster in (("wunsch", r"Wunsch: \*\*(.*?)\*\*"), ("budget", r"Budget: ([^·]+)"),
                                     ("region", r"Region: ([^·]+)"), ("ki", r"KI: (.+)$")):
                    mm = re.search(muster, z.strip())
                    if mm:
                        info[feld] = mm.group(1).strip()
        out.append(info)
    return sorted(out, key=lambda i: i["datum"], reverse=True)


def zugehoerige_dateien(info: dict) -> list[Path]:
    """Bericht samt den JSON-Dateien desselben Laufs."""
    d: Path = info["datei"]
    return [p for p in (d, d.parent / f"{info['basis']}-anzeigen.json", d.parent / f"{info['basis']}-bewertungen.json")
            if p.exists()]


# --------------------------------------------------------------------------- Markdown-Darstellung

_INLINE = re.compile(r"\*\*(?P<fett>.+?)\*\*|\[(?P<ltext>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)"
                     r"|`(?P<code>[^`]+)`|(?<![\*\w])\*(?P<kursiv>[^*\s][^*]*?)\*(?!\*)")


def md_tags(t: tk.Text):
    t.tag_configure("h1", font=(theme.FONT, 16, "bold"), spacing1=4, spacing3=6)
    t.tag_configure("h2", font=(theme.FONT, 13, "bold"), spacing1=14, spacing3=4, foreground=P["accent"])
    t.tag_configure("h3", font=(theme.FONT, 11, "bold"), spacing1=12, spacing3=2)
    t.tag_configure("fett", font=(theme.FONT, 10, "bold"))
    t.tag_configure("kursiv", font=(theme.FONT, 10, "italic"), foreground=P["muted"])
    t.tag_configure("code", font=(plattform.MONO, 9), background=P["bg"])
    t.tag_configure("zitat", background=P["tipp_bg"], lmargin1=12, lmargin2=12, rmargin=12, spacing1=6, spacing3=6)
    for ebene in range(4):
        t.tag_configure(f"li{ebene}", lmargin1=8 + ebene * 18, lmargin2=22 + ebene * 18)
    t.tag_configure("link", foreground=P["accent"], underline=True)


def md_anzeigen(t: tk.Text, md: str):
    """Markdown (Untermenge: Überschriften, Listen, Zitate, fett/kursiv, Code, Links) in ein Text-Widget."""
    md_tags(t)
    t.configure(state="normal")
    t.delete("1.0", "end")
    links = 0

    def inline(text: str, *basis):
        nonlocal links
        pos = 0
        for m in _INLINE.finditer(text):
            if m.start() > pos:
                t.insert("end", _sicher(text[pos:m.start()]), basis)
            if m.group("fett") is not None:
                t.insert("end", _sicher(m.group("fett")), basis + ("fett",))
            elif m.group("url") is not None:
                tag = f"link-{links}"
                links += 1
                t.tag_bind(tag, "<Button-1>", lambda _e, u=m.group("url"): webbrowser.open(u))
                t.tag_bind(tag, "<Enter>", lambda _e: t.configure(cursor="hand2"))
                t.tag_bind(tag, "<Leave>", lambda _e: t.configure(cursor="arrow"))
                t.insert("end", _sicher(m.group("ltext")), basis + ("link", tag))
            elif m.group("code") is not None:
                t.insert("end", _sicher(m.group("code")), basis + ("code",))
            else:
                t.insert("end", _sicher(m.group("kursiv")), basis + ("kursiv",))
            pos = m.end()
        t.insert("end", _sicher(text[pos:]) + "\n", basis)

    for zeile in md.splitlines():
        roh = zeile.rstrip()
        s = roh.lstrip()
        einzug = len(roh) - len(s)
        if not s:
            t.insert("end", "\n")
        elif s.startswith("### "):
            inline(s[4:], "h3")
        elif s.startswith("## "):
            inline(s[3:], "h2")
        elif s.startswith("# "):
            inline(s[2:], "h1")
        elif s.startswith(">"):
            inline(s.lstrip("> ").strip(), "zitat")
        else:
            m = re.match(r"([-*+]|\d+\.)\s+(.*)", s)
            if m:
                ebene = min(3, einzug // 2)
                zeichen = "•" if m.group(1) in "-*+" else m.group(1)
                t.insert("end", f"{zeichen} ", (f"li{ebene}",))
                inline(m.group(2), f"li{ebene}")
            else:
                inline(s)
    t.configure(state="disabled")


# --------------------------------------------------------------------------- Reiter

class BerichteTab(ttk.Frame):
    """Liste aller gespeicherten Berichte (links) mit formatierter Vorschau (rechts)."""

    def __init__(self, master, ordner_holen):
        super().__init__(master)
        self.ordner_holen = ordner_holen
        self.berichte: dict[str, dict] = {}

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(4, 6))
        ttk.Button(bar, text="↻ Aktualisieren", command=self.aktualisieren).pack(side="left", padx=(4, 4))
        self.btn_oeffnen = ttk.Button(bar, text="Datei öffnen", command=self._oeffnen, state="disabled")
        self.btn_oeffnen.pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Ordner öffnen", command=lambda: plattform.oeffnen(self.ordner_holen())).pack(
            side="left", padx=(0, 4))
        self.btn_loeschen = ttk.Button(bar, text="Löschen", command=self._loeschen, state="disabled")
        self.btn_loeschen.pack(side="left")
        self.lbl_info = ttk.Label(bar, text="", style="Status.TLabel")
        self.lbl_info.pack(side="right", padx=4)

        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)
        links = ttk.Frame(pw)
        pw.add(links, weight=0)
        self.tree = ttk.Treeview(links, columns=("datum", "budget", "top"), show="tree headings",
                                 selectmode="extended")
        self.tree.heading("#0", text="Suche")
        self.tree.column("#0", width=170, minwidth=120)
        for c, text, w in (("datum", "Datum", 112), ("budget", "Budget", 86), ("top", "Top", 40)):
            self.tree.heading(c, text=text)
            self.tree.column(c, width=w, minwidth=40, stretch=False, anchor="center" if c == "top" else "w")
        sb = ttk.Scrollbar(links, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._anzeigen())
        self.tree.bind("<Double-1>", lambda e: self._oeffnen())
        self.tree.bind("<Delete>", lambda e: self._loeschen())

        rechts = ttk.Frame(pw)
        pw.add(rechts, weight=1)
        self.txt = tk.Text(rechts, wrap="word", font=(theme.FONT, 10), padx=18, pady=14, state="disabled",
                           cursor="arrow")
        theme.text_farben(self.txt)
        sb2 = ttk.Scrollbar(rechts, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True)
        self._leer("Noch keine Berichte.", "Nach jeder Suche wird der Bericht im Ergebnis-Ordner gespeichert und "
                                           "erscheint hier.")

    def _leer(self, titel: str, text: str):
        md_anzeigen(self.txt, f"## {titel}\n\n*{text}*")

    def aktualisieren(self):
        ordner = self.ordner_holen()
        auswahl = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        self.berichte = {}
        liste = berichte_finden(ordner)
        for i, b in enumerate(liste):
            iid = str(b["datei"])
            self.berichte[iid] = b
            self.tree.insert("", "end", iid=iid, text=_sicher(b["titel"]),
                             values=(b["datum"].strftime("%d.%m.%y %H:%M"), b["budget"], b["top"]))
        self.lbl_info.configure(text=f"{len(liste)} Bericht{'e' if len(liste) != 1 else ''} in {ordner}")
        noch = [i for i in auswahl if self.tree.exists(i)]
        if noch:
            self.tree.selection_set(noch)
        elif liste:
            self.tree.selection_set(str(liste[0]["datei"]))
        else:
            self._leer("Noch keine Berichte.", f"Nach jeder Suche wird der Bericht in {ordner} gespeichert und "
                                               "erscheint hier.")
            self._knoepfe()

    def auswaehlen(self, datei: Path):
        """Nach einem Lauf: Liste neu laden und den neuen Bericht markieren."""
        self.aktualisieren()
        if self.tree.exists(str(datei)):
            self.tree.selection_set(str(datei))
            self.tree.see(str(datei))

    def _knoepfe(self):
        zustand = "normal" if self.tree.selection() else "disabled"
        self.btn_oeffnen.configure(state=zustand)
        self.btn_loeschen.configure(state=zustand)

    def _anzeigen(self):
        self._knoepfe()
        sel = self.tree.selection()
        if not sel:
            return
        b = self.berichte.get(sel[0])
        if not b:
            return
        try:
            md_anzeigen(self.txt, b["datei"].read_text(encoding="utf-8"))
        except OSError as e:
            self._leer("Bericht nicht lesbar", str(e))

    def _oeffnen(self):
        for iid in self.tree.selection()[:1]:
            plattform.oeffnen(iid)

    def _loeschen(self):
        sel = [self.berichte[i] for i in self.tree.selection() if i in self.berichte]
        if not sel:
            return
        dateien = [d for b in sel for d in zugehoerige_dateien(b)]
        text = (f"Bericht „{sel[0]['titel']}“ vom {sel[0]['datum']:%d.%m.%Y %H:%M}" if len(sel) == 1
                else f"{len(sel)} Berichte")
        if not messagebox.askyesno("Berichte", f"{text} wirklich löschen?\n\nEs werden {len(dateien)} Dateien "
                                   "(Bericht und gespeicherte Anzeigen/Bewertungen) entfernt.",
                                   parent=self.winfo_toplevel()):
            return
        for d in dateien:
            try:
                d.unlink()
            except OSError:
                pass
        self.aktualisieren()
