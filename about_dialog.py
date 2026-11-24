"""„Über“-Fenster: Was die App kann, wie sie funktioniert, Versionsverlauf, Entwickler & Links."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

import updater

ENTWICKLER = "ochtii"
ENTWICKLER_URL = "https://github.com/ochtii"
REPO_URL = updater.REPO_URL

# Farben
BLAU, GRUEN, DUNKEL, GRAU, HELL = "#0b6bcb", "#12a36b", "#1e1f24", "#6b6f76", "#f4f6f9"


def _mix(a: str, b: str, t: float) -> str:
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


class AboutDialog(tk.Toplevel):
    def __init__(self, master, version: str, on_update=None):
        super().__init__(master)
        self.title("Über Willhaben KI-Agent")
        self.transient(master)
        self.geometry("840x720")
        self.minsize(780, 680)
        self.configure(bg=HELL)
        self.on_update = on_update
        stand = updater.lokaler_stand()
        self._banner(version, stand)
        self._style()

        nb = ttk.Notebook(self, style="About.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        for titel, bau in (("Überblick", self._tab_ueberblick), ("Funktionen", self._tab_funktionen),
                           ("So funktioniert's", self._tab_ablauf), ("Neuigkeiten", self._tab_neuigkeiten),
                           ("Entwickler & Links", self._tab_entwickler)):
            f = tk.Frame(nb, bg="white", padx=22, pady=18)
            nb.add(f, text=f"  {titel}  ")
            bau(f)

        unten = tk.Frame(self, bg=HELL)
        unten.pack(fill="x", padx=16, pady=12)
        tk.Label(unten, text=f"© {ENTWICKLER} · Open Source auf GitHub", bg=HELL, fg=GRAU,
                 font=("TkDefaultFont", 9)).pack(side="left")
        ttk.Button(unten, text="Schließen", command=self.destroy).pack(side="right")
        ttk.Button(unten, text="GitHub öffnen", command=lambda: webbrowser.open(REPO_URL)).pack(side="right", padx=6)
        if on_update:
            ttk.Button(unten, text="Nach Updates suchen",
                       command=lambda: (self.destroy(), on_update())).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------ Kopf
    def _banner(self, version: str, stand):
        h = 158
        c = tk.Canvas(self, height=h, highlightthickness=0, bd=0)
        c.pack(fill="x")
        self._banner_canvas = c

        def zeichnen(event=None):
            c.delete("all")
            w = max(c.winfo_width(), 820)
            schritte = 60
            for i in range(schritte):                                   # Farbverlauf
                c.create_rectangle(i * w / schritte, 0, (i + 1) * w / schritte + 1, h,
                                   fill=_mix(BLAU, GRUEN, i / (schritte - 1)), outline="")
            for x, y, r, a in ((w - 90, 30, 90, 0.10), (w - 210, 140, 60, 0.08), (w - 30, 130, 45, 0.12)):
                c.create_oval(x - r, y - r, x + r, y + r, outline="", fill=_mix(GRUEN, "#ffffff", a + 0.15),
                              stipple="gray25")                          # dezente Kreise
            ix = 34
            if self._icon is not None:
                c.create_oval(ix - 6, 34, ix + 92, 132, fill="white", outline="")
                c.create_image(ix + 43, 83, image=self._icon)
                tx = ix + 118
            else:
                tx = ix
            c.create_text(tx, 52, anchor="w", text="Willhaben KI-Agent", fill="white",
                          font=("TkDefaultFont", 24, "bold"))
            c.create_text(tx, 86, anchor="w", fill="#e8f3ff", font=("TkDefaultFont", 11),
                          text="Durchsucht alle Anzeigen und findet mit KI die besten Angebote")
            badge = f"  v{version}  ·  {stand.kurz}  "
            bx, by = tx, 112
            tid = c.create_text(bx + 10, by + 13, anchor="w", text=badge, fill=BLAU, font=("TkDefaultFont", 10, "bold"))
            x1, y1, x2, y2 = c.bbox(tid)
            self._pille(c, x1 - 6, y1 - 4, x2 + 6, y2 + 4, "white")
            c.tag_raise(tid)
            c.create_text(x2 + 18, by + 13, anchor="w", fill="white", font=("TkDefaultFont", 10),
                          text=f"von {ENTWICKLER}")

        try:
            img = tk.PhotoImage(file=str(Path(__file__).resolve().parent / "icon.png"))
            self._icon = img.subsample(max(1, img.width() // 80))
        except Exception:
            self._icon = None
        c.bind("<Configure>", zeichnen)
        self.after(10, zeichnen)

    @staticmethod
    def _pille(c, x1, y1, x2, y2, farbe):
        r = (y2 - y1) / 2
        c.create_oval(x1, y1, x1 + 2 * r, y2, fill=farbe, outline="")
        c.create_oval(x2 - 2 * r, y1, x2, y2, fill=farbe, outline="")
        c.create_rectangle(x1 + r, y1, x2 - r, y2, fill=farbe, outline="")

    def _style(self):
        st = ttk.Style(self)
        st.configure("About.TNotebook", background=HELL, borderwidth=0)
        st.configure("About.TNotebook.Tab", padding=(10, 6), font=("TkDefaultFont", 10))
        st.map("About.TNotebook.Tab", foreground=[("selected", BLAU)])

    # ------------------------------------------------------------------ Bausteine
    def _h(self, parent, text, top=0):
        tk.Label(parent, text=text, bg="white", fg=DUNKEL, font=("TkDefaultFont", 13, "bold")).pack(
            anchor="w", pady=(top, 6))

    def _p(self, parent, text, fg=DUNKEL, size=10, pady=(0, 8)):
        lbl = tk.Label(parent, text=text, bg="white", fg=fg, font=("TkDefaultFont", size), justify="left",
                       anchor="w", wraplength=720)
        lbl.pack(anchor="w", fill="x", pady=pady)
        return lbl

    def _link(self, parent, text, url, size=10, bg="white"):
        l = tk.Label(parent, text=text, bg=bg, fg=BLAU, cursor="hand2", font=("TkDefaultFont", size, "underline"))
        l.bind("<Button-1>", lambda e: webbrowser.open(url))
        l.bind("<Enter>", lambda e: l.configure(fg=GRUEN))
        l.bind("<Leave>", lambda e: l.configure(fg=BLAU))
        return l

    def _karte(self, parent, symbol, titel, text, farbe):
        k = tk.Frame(parent, bg=HELL, padx=14, pady=12, highlightthickness=1, highlightbackground="#e2e6ec")
        tk.Label(k, text=symbol, bg=HELL, fg=farbe, font=("DejaVu Sans", 22, "bold")).pack(anchor="w")
        tk.Label(k, text=titel, bg=HELL, fg=DUNKEL, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(4, 2))
        tk.Label(k, text=text, bg=HELL, fg=GRAU, font=("TkDefaultFont", 9), justify="left", wraplength=200).pack(
            anchor="w")
        return k

    # ------------------------------------------------------------------ Reiter
    def _tab_ueberblick(self, f):
        self._h(f, "Gebraucht kaufen, ohne stundenlang zu suchen")
        self._p(f, "Der Willhaben KI-Agent durchsucht für dich alle passenden Anzeigen auf willhaben.at, liest "
                   "jede Beschreibung und lässt Google Gemini die Angebote wie ein erfahrener Einkaufsberater "
                   "bewerten. Am Ende bekommst du die besten Treffer nach Preis/Leistung, mit Vor- und Nachteilen, "
                   "einer Einordnung der aktuellen Marktlage und einer klaren Empfehlung.")
        reihe = tk.Frame(f, bg="white")
        reihe.pack(fill="x", pady=(8, 10))
        for i, (sym, t, txt, farbe) in enumerate((
                ("≡", "Alle Anzeigen", "Jede Ergebnisseite, jede Beschreibung – nicht nur die erste Seite.", BLAU),
                ("★", "KI-Bewertung", "Specs, Zustand, Warnsignale und Preis/Leistung für jede Anzeige.", "#e0a100"),
                ("↗", "Aktuelle Marktlage", "Live-Recherche per Google-Suche plus echte willhaben-Preise.", GRUEN))):
            self._karte(reihe, sym, t, txt, farbe).grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            reihe.columnconfigure(i, weight=1)
        self._p(f, "Für Laptops, PCs, Tablets, Handys, Konsolen, Kameras und jede andere willhaben-Kategorie. "
                   "Gefiltert nach Preis, Bundesland und Bezirk.", fg=GRAU)

    def _tab_funktionen(self, f):
        self._h(f, "Alles drin")
        punkte = [
            ("Vollständige Suche", "alle Ergebnisseiten, Detailbeschreibungen, Marke, Zustand, Display"),
            ("Regionen", "Bundesländer und Bezirke (auch per PLZ, z. B. 1100)"),
            ("KI-Bewertung", "Leistung, Preis/Leistung, Zustand, Warnsignale je Anzeige"),
            ("Endvergleich", "Top-N mit Vor-/Nachteilen, Fazit und Kauftipp"),
            ("Marktrecherche", "aktuelle Preise & Trends per Google-Suche, mit Quellen"),
            ("willhaben-Marktpreise", "Median je RAM-Klasse aus den echten Anzeigen"),
            ("Modellwahl", "Gemini-Modell + Ausweichmodell aus der Liste deines Keys"),
            ("Mehrere Keys", "automatisch verteilt – gleichmäßig oder nacheinander"),
            ("Limit-Manager", "Verbrauch, Minuten- & Tageslimits live, Pausen bei Überlastung"),
            ("Live-Ansicht", "Protokoll, Anzeigen-Tabelle und Ergebnis in Echtzeit"),
            ("Berichte", "Markdown-Bericht + JSON aller Anzeigen und Bewertungen"),
            ("Updates", "prüft GitHub beim Start, Update mit einem Klick"),
        ]
        grid = tk.Frame(f, bg="white")
        grid.pack(fill="both", expand=True)
        for i, (t, txt) in enumerate(punkte):
            zelle = tk.Frame(grid, bg="white")
            zelle.grid(row=i // 2, column=i % 2, sticky="nw", padx=(0, 24), pady=3)
            tk.Label(zelle, text="✔", bg="white", fg=GRUEN, font=("TkDefaultFont", 11, "bold")).pack(side="left", anchor="n")
            box = tk.Frame(zelle, bg="white")
            box.pack(side="left", padx=(6, 0))
            tk.Label(box, text=t, bg="white", fg=DUNKEL, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
            tk.Label(box, text=txt, bg="white", fg=GRAU, font=("TkDefaultFont", 9), wraplength=340,
                     justify="left").pack(anchor="w")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    def _tab_ablauf(self, f):
        self._h(f, "In fünf Schritten zur besten Wahl")
        schritte = [
            ("Suche", "Der Agent ruft alle Ergebnisseiten deiner willhaben-Suche ab (200 Anzeigen pro Seite) und "
                      "übersetzt Bezirke direkt in willhaben-Filter."),
            ("Details", "Jede Anzeige wird geöffnet: vollständige Beschreibung, Marke, Zustand, privat oder Händler. "
                        "Kontaktdaten der Verkäufer werden bewusst nicht gespeichert."),
            ("Marktrecherche", "Gemini sucht per Google nach aktuellen Gebraucht- und Neupreisen, Trends und "
                               "Kauftipps – damit die Bewertung nicht auf veraltetem Wissen beruht."),
            ("KI-Bewertung", "In Paketen zu 30 Anzeigen: technische Daten aus dem Freitext, Relevanz, Leistung, "
                             "Preis/Leistung und Warnsignale wie Defekte oder Betrugsverdacht."),
            ("Endvergleich", "Die besten Kandidaten werden direkt gegeneinander verglichen – heraus kommen deine "
                             "Top-Geräte mit Vor- und Nachteilen und einer klaren Empfehlung."),
        ]
        for i, (t, txt) in enumerate(schritte, 1):
            zeile = tk.Frame(f, bg="white")
            zeile.pack(fill="x", pady=5)
            kreis = tk.Canvas(zeile, width=34, height=34, bg="white", highlightthickness=0)
            kreis.pack(side="left", anchor="n")
            kreis.create_oval(2, 2, 32, 32, fill=_mix(BLAU, GRUEN, (i - 1) / 4), outline="")
            kreis.create_text(17, 17, text=str(i), fill="white", font=("TkDefaultFont", 12, "bold"))
            box = tk.Frame(zeile, bg="white")
            box.pack(side="left", fill="x", expand=True, padx=(12, 0))
            tk.Label(box, text=t, bg="white", fg=DUNKEL, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
            tk.Label(box, text=txt, bg="white", fg=GRAU, font=("TkDefaultFont", 9), wraplength=660,
                     justify="left").pack(anchor="w")

    def _tab_neuigkeiten(self, f):
        self._h(f, "Versionsverlauf")
        self._p(f, "Die Versionsnummer steigt mit jeder Änderung auf GitHub automatisch – v1.0.N, wobei N die "
                   "Anzahl der Änderungen ist.", fg=GRAU, size=9)
        liste = tk.Frame(f, bg="white")
        liste.pack(fill="both", expand=True)
        lade = self._p(liste, "Lade Versionsverlauf von GitHub …", fg=GRAU)
        installiert = updater.lokaler_stand().kurz

        def fertig(eintraege, fehler):
            if not self.winfo_exists():
                return
            lade.destroy()
            if fehler:
                self._p(liste, f"Versionsverlauf nicht abrufbar: {fehler}", fg="#b00020")
                return
            for i, v in enumerate(eintraege):
                zeile = tk.Frame(liste, bg=HELL if i % 2 == 0 else "white", padx=10, pady=6)
                zeile.pack(fill="x")
                aktuell = v["sha"] == installiert
                tk.Label(zeile, text=f"v{v['version']}", bg=zeile["bg"], fg=GRUEN if i == 0 else BLAU,
                         font=("TkDefaultFont", 10, "bold"), width=8, anchor="w").pack(side="left")
                tk.Label(zeile, text=v["datum"], bg=zeile["bg"], fg=GRAU, font=("TkDefaultFont", 9),
                         width=11, anchor="w").pack(side="left")
                text = "".join(ch for ch in v["nachricht"] if ord(ch) <= 0xFFFF)
                tk.Label(zeile, text=text, bg=zeile["bg"], fg=DUNKEL, font=("TkDefaultFont", 10),
                         anchor="w", justify="left", wraplength=470).pack(side="left", fill="x", expand=True)
                if aktuell:
                    tk.Label(zeile, text=" installiert ", bg=GRUEN, fg="white",
                             font=("TkDefaultFont", 8, "bold")).pack(side="right")
                elif i == 0:
                    tk.Label(zeile, text=" neu ", bg=BLAU, fg="white", font=("TkDefaultFont", 8, "bold")).pack(side="right")
            self._link(f, "Alle Änderungen auf GitHub ansehen ➜", f"{REPO_URL}/commits/{updater.BRANCH}").pack(
                anchor="w", pady=(10, 0))

        def work():
            try:
                daten, fehler = updater.verlauf(10), ""
            except updater.UpdateFehler as e:
                daten, fehler = [], str(e)
            except Exception as e:
                daten, fehler = [], type(e).__name__
            self.after(0, lambda: fertig(daten, fehler))
        threading.Thread(target=work, daemon=True).start()

    def _tab_entwickler(self, f):
        karte = tk.Frame(f, bg=HELL, padx=18, pady=16, highlightthickness=1, highlightbackground="#e2e6ec")
        karte.pack(fill="x")
        av = tk.Canvas(karte, width=64, height=64, bg=HELL, highlightthickness=0)
        av.pack(side="left")
        av.create_oval(2, 2, 62, 62, fill=_mix(BLAU, GRUEN, 0.5), outline="")
        av.create_text(32, 32, text=ENTWICKLER[:1].upper(), fill="white", font=("TkDefaultFont", 26, "bold"))
        info = tk.Frame(karte, bg=HELL)
        info.pack(side="left", padx=16)
        tk.Label(info, text="Entwickelt von", bg=HELL, fg=GRAU, font=("TkDefaultFont", 9)).pack(anchor="w")
        tk.Label(info, text=ENTWICKLER, bg=HELL, fg=DUNKEL, font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        self._link(info, ENTWICKLER_URL.replace("https://", ""), ENTWICKLER_URL, bg=HELL).pack(anchor="w")

        self._h(f, "Links", top=16)
        links = tk.Frame(f, bg="white")
        links.pack(fill="x")
        for i, (titel, url, txt) in enumerate((
                ("Repository", REPO_URL, "Quellcode, Anleitung und Installation"),
                ("Fehler melden / Idee vorschlagen", f"{REPO_URL}/issues/new", "Issue auf GitHub anlegen"),
                ("Versionsgeschichte", f"{REPO_URL}/commits/{updater.BRANCH}", "alle Änderungen im Detail"),
                ("API-Key-Anleitung", f"{REPO_URL}/blob/{updater.BRANCH}/ANLEITUNG-API-KEY.md",
                 "Google-Gemini-Key in 3 Minuten"))):
            zelle = tk.Frame(links, bg="white")
            zelle.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 30), pady=4)
            self._link(zelle, "➜ " + titel, url, size=10).pack(anchor="w")
            tk.Label(zelle, text=txt, bg="white", fg=GRAU, font=("TkDefaultFont", 9)).pack(anchor="w")

        self._h(f, "Gut zu wissen", top=14)
        for txt in ("Deine API-Keys bleiben auf deinem PC (~/.config/willhaben-agent, nur für dich lesbar).",
                    "An Google gehen nur öffentliche Anzeigentexte – keine Telefonnummern oder Adressen.",
                    "Nur für den privaten Gebrauch. Bitte die Nutzungsbedingungen von willhaben beachten.",
                    "Gebaut mit Python, Tkinter und Google Gemini."):
            zeile = tk.Frame(f, bg="white")
            zeile.pack(anchor="w", pady=1)
            tk.Label(zeile, text="●", bg="white", fg=GRUEN, font=("TkDefaultFont", 8)).pack(side="left")
            tk.Label(zeile, text=txt, bg="white", fg=DUNKEL, font=("TkDefaultFont", 9)).pack(side="left", padx=6)
