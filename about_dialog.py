"""„Über“-Fenster: Was die App kann, wie sie funktioniert, Versionsverlauf, Entwickler & Links."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

import plattform
import settings
import updater

ENTWICKLER = "ochtii"
ENTWICKLER_URL = "https://github.com/ochtii"
REPO_URL = updater.REPO_URL

# Farben (werden beim Öffnen aus der aktuellen Palette übernommen -> Hell/Dunkel)
BLAU, GRUEN, DUNKEL, GRAU, HELL, WEISS = "#0b6bcb", "#12a36b", "#1e1f24", "#6b6f76", "#f4f6f9", "#ffffff"


def _farben_uebernehmen():
    global BLAU, GRUEN, DUNKEL, GRAU, HELL, WEISS
    from theme import P
    BLAU, GRUEN, DUNKEL, GRAU = P["accent"], P["accent2"], P["fg"], P["muted"]
    HELL, WEISS = P["bg"], P["card"]


def P_DANGER() -> str:
    from theme import P
    return P["danger"]


def _rand() -> str:
    from theme import P
    return P["rand"]


def _mix(a: str, b: str, t: float) -> str:
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _mausrad(widget, canvas) -> None:
    """Mausrad über `widget` und allen Unterelementen scrollt `canvas` (Linux: Button-4/5, Windows/macOS:
    MouseWheel). "break" verhindert, dass zusätzlich das Hauptfenster mitscrollt."""
    def rollen(schritte):
        if canvas.yview() != (0.0, 1.0):
            canvas.yview_scroll(schritte, "units")
        return "break"
    widget.bind("<Button-4>", lambda e: rollen(-2))
    widget.bind("<Button-5>", lambda e: rollen(2))
    widget.bind("<MouseWheel>", lambda e: rollen(-2 if e.delta > 0 else 2))
    for kind in widget.winfo_children():
        _mausrad(kind, canvas)


class AboutDialog(tk.Toplevel):
    def __init__(self, master, version: str, on_update=None):
        super().__init__(master)
        _farben_uebernehmen()
        self._version = version
        self.title("Über Willhaben KI-Agent")
        self.transient(master)
        # passt auch auf Bildschirme mit 768 Pixel Höhe; Inhalte scrollen, die Knöpfe unten bleiben sichtbar
        hoehe = max(520, min(780, self.winfo_screenheight() - 90))
        self.geometry(f"860x{hoehe}")
        self.minsize(760, 480)
        self.configure(bg=HELL)
        self.on_update = on_update
        stand = updater.lokaler_stand()
        self._banner(version, stand)
        self._style()

        unten = tk.Frame(self, bg=HELL)
        unten.pack(side="bottom", fill="x", padx=16, pady=12)      # zuerst packen: bleibt immer sichtbar
        tk.Label(unten, text=f"© {ENTWICKLER} · Open Source auf GitHub", bg=HELL, fg=GRAU,
                 font=("TkDefaultFont", 9)).pack(side="left")
        ttk.Button(unten, text="Schließen", command=self.destroy).pack(side="right")
        ttk.Button(unten, text="GitHub öffnen", command=lambda: webbrowser.open(REPO_URL)).pack(side="right", padx=6)
        if on_update:
            ttk.Button(unten, text="Nach Updates suchen",
                       command=lambda: (self.destroy(), on_update())).pack(side="right")

        nb = ttk.Notebook(self, style="About.TNotebook")
        nb.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        for titel, bau, scrollen in (("Überblick", self._tab_ueberblick, True),
                                     ("Funktionen", self._tab_funktionen, True),
                                     ("So funktioniert's", self._tab_ablauf, True),
                                     ("Neuigkeiten", self._tab_neuigkeiten, False),   # scrollt selbst
                                     ("Entwickler & Links", self._tab_entwickler, True)):
            if scrollen:
                aussen, f = self._scrollbereich(nb)
            else:
                aussen = f = tk.Frame(nb, bg=WEISS, padx=22, pady=18)
            nb.add(aussen, text=f"  {titel}  ")
            bau(f)
            if scrollen:
                _mausrad(aussen, aussen.canvas)

        self.bind("<Escape>", lambda e: self.destroy())

    @staticmethod
    def _scrollbereich(nb):
        """Reiter mit senkrechter Bildlaufleiste, die nur erscheint, wenn der Inhalt nicht hineinpasst."""
        aussen = tk.Frame(nb, bg=WEISS)
        canvas = tk.Canvas(aussen, bg=WEISS, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(aussen, orient="vertical", command=canvas.yview)
        innen = tk.Frame(canvas, bg=WEISS, padx=22, pady=18)
        fenster = canvas.create_window((0, 0), window=innen, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)

        def anpassen(_e=None):
            canvas.configure(scrollregion=(0, 0, innen.winfo_reqwidth(), innen.winfo_reqheight()))
            if innen.winfo_reqheight() > canvas.winfo_height() > 1:
                if not sb.winfo_ismapped():
                    sb.pack(side="right", fill="y", before=canvas)
            elif sb.winfo_ismapped():
                sb.pack_forget()
                canvas.yview_moveto(0)
        innen.bind("<Configure>", anpassen)
        canvas.bind("<Configure>", lambda e: (canvas.itemconfigure(fenster, width=e.width), anpassen()))
        aussen.canvas = canvas
        return aussen, innen

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
        tk.Label(parent, text=text, bg=WEISS, fg=DUNKEL, font=("TkDefaultFont", 13, "bold")).pack(
            anchor="w", pady=(top, 6))

    def _p(self, parent, text, fg=None, size=10, pady=(0, 8)):
        lbl = tk.Label(parent, text=text, bg=WEISS, fg=fg or DUNKEL, font=("TkDefaultFont", size), justify="left",
                       anchor="w", wraplength=720)
        lbl.pack(anchor="w", fill="x", pady=pady)
        return lbl

    def _link(self, parent, text, url, size=10, bg=None):
        bg = bg or WEISS
        l = tk.Label(parent, text=text, bg=bg, fg=BLAU, cursor="hand2", font=("TkDefaultFont", size, "underline"))
        l.bind("<Button-1>", lambda e: webbrowser.open(url))
        l.bind("<Enter>", lambda e: l.configure(fg=GRUEN))
        l.bind("<Leave>", lambda e: l.configure(fg=BLAU))
        return l

    def _karte(self, parent, symbol, titel, text, farbe):
        k = tk.Frame(parent, bg=HELL, padx=14, pady=12, highlightthickness=1, highlightbackground=_rand())
        tk.Label(k, text=symbol, bg=HELL, fg=farbe, font=(plattform.SYMBOL, 22, "bold")).pack(anchor="w")
        tk.Label(k, text=titel, bg=HELL, fg=DUNKEL, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", pady=(4, 2))
        tk.Label(k, text=text, bg=HELL, fg=GRAU, font=("TkDefaultFont", 9), justify="left", wraplength=200).pack(
            anchor="w")
        return k

    # ------------------------------------------------------------------ Reiter
    def _tab_ueberblick(self, f):
        self._h(f, "Gebraucht kaufen, ohne stundenlang zu suchen")
        self._p(f, "Der Willhaben KI-Agent durchsucht für dich alle passenden Anzeigen auf willhaben.at, liest "
                   "jede Beschreibung und lässt eine KI deiner Wahl – Google Gemini, ChatGPT, Claude, Perplexity und viele "
                   "mehr – die Angebote wie ein erfahrener Einkaufsberater "
                   "bewerten. Am Ende bekommst du die besten Treffer nach Preis/Leistung, mit Vor- und Nachteilen, "
                   "einer Einordnung der aktuellen Marktlage und einer klaren Empfehlung.")
        reihe = tk.Frame(f, bg=WEISS)
        reihe.pack(fill="x", pady=(8, 10))
        for i, (sym, t, txt, farbe) in enumerate((
                ("≡", "Alle Anzeigen", "Jede Ergebnisseite, jede Beschreibung – nicht nur die erste Seite.", BLAU),
                ("★", "KI-Bewertung", "Specs, Zustand, Warnsignale und Preis/Leistung für jede Anzeige.", "#e0a100"),
                ("↗", "Aktuelle Marktlage", "Live-Recherche im Web plus echte willhaben-Preise.", GRUEN))):
            self._karte(reihe, sym, t, txt, farbe).grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 10, 0))
            reihe.columnconfigure(i, weight=1)
        self._p(f, "Für alle willhaben-Kategorien – 19 Hauptkategorien mit rund 190 Unterkategorien, von Laptops "
                   "über Ski bis Antiquitäten. Gefiltert nach Preis, Bundesland und Bezirk.", fg=GRAU)

    def _tab_funktionen(self, f):
        self._h(f, "Alles drin")
        punkte = [
            ("Vollständige Suche", "alle willhaben-Kategorien (mit Beispieltext je Kategorie), alle Ergebnisseiten "
                                   "und Detailbeschreibungen"),
            ("Regionen", "Bundesländer + Bezirksauswahl (live von willhaben), frei kombinierbar"),
            ("KI-Bewertung", "Leistung, Preis/Leistung, Zustand, Warnsignale je Anzeige"),
            ("Endvergleich", "Top-N mit Vor-/Nachteilen, Fazit und Kauftipp"),
            ("Marktrecherche", "aktuelle Preise & Trends per Websuche (Gemini, Claude, ChatGPT, Perplexity), mit Quellen"),
            ("willhaben-Marktpreise", "Median je RAM-Klasse aus den echten Anzeigen"),
            ("Viele KI-Anbieter", "Gemini (Standard), ChatGPT, Claude, Perplexity, Mistral, DeepSeek, Grok, Groq, "
                                  "OpenRouter, Together, eigene Adresse – mit Modell + Ausweichmodell"),
            ("Mehrere Keys", "je Anbieter, automatisch verteilt; Verbrauch und Limits live, Pausen bei Überlastung"),
            ("Live-Ansicht", "Animation, Fortschritt, Protokoll, Anzeigen-Tabelle und Ergebnis in Echtzeit"),
            ("Berichte", "jeder Lauf als Bericht gespeichert; frühere Berichte im Reiter „Berichte“ ansehen"),
            ("Updates", "prüft GitHub beim Start, Update mit einem Klick, räumt selbst auf"),
            ("Einstellungen", "alles in einem Fenster (Zahnrad oder Strg+K), mit Key-Anleitung je Anbieter"),
            ("Modernes Design", "helles oder dunkles Erscheinungsbild (Einstellungen → Darstellung)"),
            ("Windows & Linux", "eigene Installer, Startmenü, Updates und Deinstallation"),
        ]
        grid = tk.Frame(f, bg=WEISS)
        grid.pack(fill="both", expand=True)
        for i, (t, txt) in enumerate(punkte):
            zelle = tk.Frame(grid, bg=WEISS)
            zelle.grid(row=i // 2, column=i % 2, sticky="nw", padx=(0, 24), pady=3)
            tk.Label(zelle, text="✔", bg=WEISS, fg=GRUEN, font=("TkDefaultFont", 11, "bold")).pack(side="left", anchor="n")
            box = tk.Frame(zelle, bg=WEISS)
            box.pack(side="left", padx=(6, 0))
            tk.Label(box, text=t, bg=WEISS, fg=DUNKEL, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
            tk.Label(box, text=txt, bg=WEISS, fg=GRAU, font=("TkDefaultFont", 9), wraplength=340,
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
            ("Marktrecherche", "Die KI sucht im Web nach aktuellen Gebraucht- und Neupreisen, Trends und "
                               "Kauftipps – damit die Bewertung nicht auf veraltetem Wissen beruht. Hat der gewählte "
                               "Anbieter keine Websuche, springt ein anderer mit Key ein."),
            ("KI-Bewertung", "Mit dem gewählten Anbieter und Modell, in Paketen zu bis zu 30 Anzeigen: technische Daten aus dem Freitext, Relevanz, Leistung, "
                             "Preis/Leistung und Warnsignale wie Defekte oder Betrugsverdacht."),
            ("Endvergleich", "Die besten Kandidaten werden direkt gegeneinander verglichen – heraus kommen deine "
                             "Top-Geräte mit Vor- und Nachteilen und einer klaren Empfehlung."),
        ]
        for i, (t, txt) in enumerate(schritte, 1):
            zeile = tk.Frame(f, bg=WEISS)
            zeile.pack(fill="x", pady=5)
            kreis = tk.Canvas(zeile, width=34, height=34, bg=WEISS, highlightthickness=0)
            kreis.pack(side="left", anchor="n")
            kreis.create_oval(2, 2, 32, 32, fill=_mix(BLAU, GRUEN, (i - 1) / 4), outline="")
            kreis.create_text(17, 17, text=str(i), fill="white", font=("TkDefaultFont", 12, "bold"))
            box = tk.Frame(zeile, bg=WEISS)
            box.pack(side="left", fill="x", expand=True, padx=(12, 0))
            tk.Label(box, text=t, bg=WEISS, fg=DUNKEL, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
            tk.Label(box, text=txt, bg=WEISS, fg=GRAU, font=("TkDefaultFont", 9), wraplength=660,
                     justify="left").pack(anchor="w")

    def _tab_neuigkeiten(self, f):
        self._h(f, "Versionsverlauf")
        self._p(f, "Die letzte Stelle der Versionsnummer steigt mit jeder Änderung automatisch. Größere Schritte "
                   "(z. B. 1.1 → 1.2) markieren neue Funktionsblöcke.", fg=GRAU, size=9)
        aussen = tk.Frame(f, bg=WEISS)
        aussen.pack(fill="both", expand=True)
        canvas = tk.Canvas(aussen, bg=WEISS, highlightthickness=0)
        sb = ttk.Scrollbar(aussen, orient="vertical", command=canvas.yview)
        liste = tk.Frame(canvas, bg=WEISS)
        liste.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=liste, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        _mausrad(canvas, canvas)
        lade = self._p(liste, "Lade Versionsverlauf von GitHub …", fg=GRAU)
        installiert = self._version

        def fertig(eintraege, fehler):
            if not self.winfo_exists():
                return
            lade.destroy()
            if fehler:
                self._p(liste, f"Versionsverlauf nicht abrufbar: {fehler}", fg=P_DANGER())
                return
            for i, v in enumerate(eintraege):
                karte = tk.Frame(liste, bg=HELL if i % 2 == 0 else WEISS, padx=12, pady=8)
                karte.pack(fill="x", pady=(0, 2))
                kopf = tk.Frame(karte, bg=karte["bg"])
                kopf.pack(fill="x")
                tk.Label(kopf, text=f"v{v['version']}", bg=karte["bg"], fg=GRUEN if i == 0 else BLAU,
                         font=("TkDefaultFont", 11, "bold")).pack(side="left")
                tk.Label(kopf, text=v["datum"], bg=karte["bg"], fg=GRAU, font=("TkDefaultFont", 9)).pack(
                    side="left", padx=10)
                if v["version"] == installiert:
                    tk.Label(kopf, text=" installiert ", bg=GRUEN, fg="white",
                             font=("TkDefaultFont", 8, "bold")).pack(side="right")
                elif i == 0:
                    tk.Label(kopf, text=" neu ", bg=BLAU, fg="white", font=("TkDefaultFont", 8, "bold")).pack(side="right")
                for punkt in v["punkte"]:
                    zeile = tk.Frame(karte, bg=karte["bg"])
                    zeile.pack(fill="x", anchor="w")
                    tk.Label(zeile, text="•", bg=karte["bg"], fg=GRUEN, font=("TkDefaultFont", 10, "bold")).pack(
                        side="left", anchor="n")
                    tk.Label(zeile, text="".join(ch for ch in punkt if ord(ch) <= 0xFFFF), bg=karte["bg"],
                             fg=DUNKEL, font=("TkDefaultFont", 9), justify="left", anchor="w",
                             wraplength=700).pack(side="left", padx=(6, 0), fill="x")
            _mausrad(liste, canvas)            # auch über den Einträgen (Labels) scrollen
            self._link(f, "Kompletter Verlauf auf GitHub ➜", f"{REPO_URL}/blob/{updater.BRANCH}/CHANGELOG.md").pack(
                anchor="w", pady=(10, 0))

        def work():
            try:
                daten, fehler = updater.verlauf(15), ""
            except updater.UpdateFehler as e:
                daten, fehler = [], str(e)
            except Exception as e:
                daten, fehler = [], type(e).__name__
            self.after(0, lambda: fertig(daten, fehler))
        threading.Thread(target=work, daemon=True).start()

    def _tab_entwickler(self, f):
        karte = tk.Frame(f, bg=HELL, padx=18, pady=16, highlightthickness=1, highlightbackground=_rand())
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
        links = tk.Frame(f, bg=WEISS)
        links.pack(fill="x")
        for i, (titel, url, txt) in enumerate((
                ("Repository", REPO_URL, "Quellcode, Anleitung und Installation"),
                ("Fehler melden / Idee vorschlagen", f"{REPO_URL}/issues/new", "Issue auf GitHub anlegen"),
                ("Versionsgeschichte", f"{REPO_URL}/commits/{updater.BRANCH}", "alle Änderungen im Detail"),
                ("API-Key-Anleitung", f"{REPO_URL}/blob/{updater.BRANCH}/ANLEITUNG-API-KEY.md",
                 "Key für Gemini & Co. in 3 Minuten"))):
            zelle = tk.Frame(links, bg=WEISS)
            zelle.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 30), pady=4)
            self._link(zelle, "➜ " + titel, url, size=10).pack(anchor="w")
            tk.Label(zelle, text=txt, bg=WEISS, fg=GRAU, font=("TkDefaultFont", 9)).pack(anchor="w")

        self._h(f, "Gut zu wissen", top=14)
        for txt in (f"Deine API-Keys bleiben auf deinem PC ({settings.CONFIG_DIR}, nur für dich lesbar).",
                    "An den KI-Anbieter gehen nur öffentliche Anzeigentexte – keine Telefonnummern oder Adressen.",
                    "Nur für den privaten Gebrauch. Bitte die Nutzungsbedingungen von willhaben beachten.",
                    "Läuft unter Windows 10/11 und Linux. Gebaut mit Python und Tkinter."):
            zeile = tk.Frame(f, bg=WEISS)
            zeile.pack(anchor="w", pady=1)
            tk.Label(zeile, text="●", bg=WEISS, fg=GRUEN, font=("TkDefaultFont", 8)).pack(side="left")
            tk.Label(zeile, text=txt, bg=WEISS, fg=DUNKEL, font=("TkDefaultFont", 9)).pack(side="left", padx=6)
