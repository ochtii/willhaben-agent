"""Modernes Erscheinungsbild: Sun-Valley-Theme (sv-ttk), Farbpaletten Hell/Dunkel und eigene Stile.

Alle Fenster holen sich ihre Farben aus `P` (aktuelle Palette), damit Hell- und Dunkelmodus
überall zusammenpassen. Ohne sv-ttk fällt die App auf das Standard-Theme „clam“ zurück.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTEN = {
    "hell": {
        "bg": "#fafafa", "fg": "#1b1d21", "muted": "#667085", "card": "#ffffff", "rand": "#e3e7ee",
        "accent": "#0b6bcb", "accent2": "#12a36b", "accent_hell": "#e7f1fc", "ok": "#15803d", "warn": "#b45309",
        "danger": "#c0262d", "gold": "#d29a00", "text_bg": "#ffffff", "feld": "#fdfdfd", "text_fg": "#1b1d21",
        "term_bg": "#11151c", "term_fg": "#d5dae3", "term_dim": "#6b7484",
        "zeile_ok": "#e8f6ee", "zeile_top": "#fff4cf", "zeile_aus": "#9aa1ad", "tipp_bg": "#fff4cf",
    },
    "dunkel": {
        "bg": "#1c1c1c", "fg": "#f2f2f2", "muted": "#a3a8b3", "card": "#262626", "rand": "#363a40",
        "accent": "#4ca2ff", "accent2": "#2fcf8e", "accent_hell": "#1f3550", "ok": "#4ade80", "warn": "#fbbf24",
        "danger": "#f87171", "gold": "#facc15", "text_bg": "#232323", "feld": "#292929", "text_fg": "#f2f2f2",
        "term_bg": "#0e1116", "term_fg": "#d5dae3", "term_dim": "#6b7484",
        "zeile_ok": "#1f3a2b", "zeile_top": "#4a3f12", "zeile_aus": "#7d838e", "tipp_bg": "#3d3511",
    },
}
P: dict[str, str] = dict(PALETTEN["hell"])
MODUS = "hell"
FONT = "TkDefaultFont"


def mix(a: str, b: str, t: float) -> str:
    a_, b_ = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a_, b_))


def anwenden(root: tk.Misc, modus: str = "hell") -> dict:
    """Theme setzen und eigene Stile anlegen. Gibt die Palette zurück."""
    global MODUS
    MODUS = modus if modus in PALETTEN else "hell"
    P.clear()
    P.update(PALETTEN[MODUS])
    st = ttk.Style(root)
    try:
        import sv_ttk
        sv_ttk.set_theme("dark" if MODUS == "dunkel" else "light", root)
    except Exception:
        if "clam" in st.theme_names():
            st.theme_use("clam")
        P["bg"] = st.lookup("TFrame", "background") or P["bg"]

    bg = st.lookup("TFrame", "background") or P["bg"]
    P["bg"] = bg
    root.configure(bg=bg) if isinstance(root, (tk.Tk, tk.Toplevel)) else None

    st.configure("Title.TLabel", font=(FONT, 15, "bold"))
    st.configure("H2.TLabel", font=(FONT, 11, "bold"))
    st.configure("Sub.TLabel", foreground=P["muted"])
    st.configure("Small.TLabel", foreground=P["muted"], font=(FONT, 9))
    st.configure("Section.TLabelframe.Label", font=(FONT, 10, "bold"), foreground=P["accent"])
    st.configure("Section.TLabelframe", padding=10)
    st.configure("Start.TButton", font=(FONT, 11, "bold"), padding=(10, 8))
    st.configure("Link.TLabel", foreground=P["accent"], font=(FONT, 10, "underline"))
    st.configure("Treeview", rowheight=28)
    st.configure("Treeview.Heading", font=(FONT, 9, "bold"))
    st.configure("Card.TFrame", background=P["card"])
    st.configure("Card.TLabel", background=P["card"])
    st.configure("CardBig.TLabel", background=P["card"], foreground=P["fg"], font=(FONT, 20, "bold"))
    st.configure("CardSub.TLabel", background=P["card"], foreground=P["muted"], font=(FONT, 9))
    st.configure("Status.TLabel", foreground=P["muted"], font=(FONT, 9))
    st.configure("Horizontal.TProgressbar", thickness=6)
    pad = st.lookup("TEntry", "padding") or ""
    try:                                 # Platz rechts im Suchfeld für den „✕“-Knopf
        werte = [int(float(x)) for x in str(pad).split()] or [8]
    except ValueError:
        werte = [8]
    werte = (werte * 4)[:4] if len(werte) < 4 else werte[:4]
    st.configure("Suche.TEntry", padding=(werte[0], werte[1], 28, werte[3]))
    return P


def text_farben(widget: tk.Text, terminal: bool = False):
    """tk.Text an die Palette anpassen."""
    if terminal:
        widget.configure(bg=P["term_bg"], fg=P["term_fg"], insertbackground=P["term_fg"],
                         selectbackground=P["accent"], highlightthickness=0, borderwidth=0)
    else:
        widget.configure(bg=P["text_bg"], fg=P["text_fg"], insertbackground=P["text_fg"],
                         selectbackground=P["accent"], selectforeground="#ffffff",
                         highlightthickness=1, highlightbackground=P["rand"], highlightcolor=P["accent"],
                         borderwidth=0, relief="flat")


class Karte(tk.Frame):
    """Kachel mit großer Zahl und Beschriftung (für die Zähler)."""

    def __init__(self, master, titel: str, variable: tk.StringVar, farbe: str | None = None):
        super().__init__(master, bg=P["card"], highlightthickness=1, highlightbackground=P["rand"], padx=14, pady=10)
        tk.Frame(self, bg=farbe or P["accent"], width=4).pack(side="left", fill="y", padx=(0, 12))
        box = tk.Frame(self, bg=P["card"])
        box.pack(side="left", fill="x", expand=True)
        tk.Label(box, textvariable=variable, bg=P["card"], fg=P["fg"], font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(box, text=titel, bg=P["card"], fg=P["muted"], font=(FONT, 9)).pack(anchor="w")


class Stepper(tk.Canvas):
    """Fortschrittsanzeige der Phasen: Kreise mit Verbindungslinie (erledigt/aktiv/offen)."""

    def __init__(self, master, schritte: list[str]):
        super().__init__(master, height=58, highlightthickness=0, bd=0, bg=P["bg"])
        self.schritte = schritte
        self.aktiv = -1
        self.fertig = False
        self.bind("<Configure>", lambda e: self.zeichnen())

    def setzen(self, aktiv: int, fertig: bool = False):
        self.aktiv, self.fertig = aktiv, fertig
        self.zeichnen()

    def zeichnen(self):
        self.delete("all")
        w = max(self.winfo_width(), 400)
        n = len(self.schritte)
        rand = 40
        abstand = (w - 2 * rand) / (n - 1)
        y, r = 18, 11
        for i in range(n - 1):
            x1, x2 = rand + i * abstand + r, rand + (i + 1) * abstand - r
            erledigt = self.fertig or i < self.aktiv
            self.create_line(x1, y, x2, y, width=3, fill=P["accent2"] if erledigt else P["rand"], capstyle="round")
        for i, name in enumerate(self.schritte):
            x = rand + i * abstand
            if self.fertig or i < self.aktiv:
                self.create_oval(x - r, y - r, x + r, y + r, fill=P["accent2"], outline="")
                self.create_text(x, y, text="✓", fill="#ffffff", font=(FONT, 10, "bold"))
                farbe, schrift = P["fg"], (FONT, 9)
            elif i == self.aktiv:
                self.create_oval(x - r - 4, y - r - 4, x + r + 4, y + r + 4, fill=P["accent_hell"], outline="")
                self.create_oval(x - r, y - r, x + r, y + r, fill=P["accent"], outline="")
                self.create_text(x, y, text=str(i + 1), fill="#ffffff", font=(FONT, 9, "bold"))
                farbe, schrift = P["accent"], (FONT, 9, "bold")
            else:
                self.create_oval(x - r, y - r, x + r, y + r, fill=P["card"], outline=P["rand"], width=2)
                self.create_text(x, y, text=str(i + 1), fill=P["muted"], font=(FONT, 9))
                farbe, schrift = P["muted"], (FONT, 9)
            self.create_text(x, y + r + 13, text=name, fill=farbe, font=schrift)


class Kopfleiste(tk.Canvas):
    """Farbverlauf-Kopfzeile mit Icon, Titel, Version und Zahnrad (Einstellungen) rechts."""

    def __init__(self, master, titel: str, untertitel: str, version: str, icon: tk.PhotoImage | None,
                 einstellungen=None):
        super().__init__(master, height=64, highlightthickness=0, bd=0)
        self.titel, self.untertitel, self.version, self.icon = titel, untertitel, version, icon
        self.einstellungen = einstellungen
        self.bind("<Configure>", lambda e: self.zeichnen())

    def version_setzen(self, v: str):
        self.version = v
        self.zeichnen()

    def zeichnen(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 600), 64
        a, b = P["accent"], P["accent2"]
        if MODUS == "dunkel":
            a, b = mix(a, "#000000", 0.35), mix(b, "#000000", 0.45)
        for i in range(48):
            self.create_rectangle(i * w / 48, 0, (i + 1) * w / 48 + 1, h, fill=mix(a, b, i / 47), outline="")
        x = 16
        if self.icon is not None:
            self.create_image(x + 20, h / 2, image=self.icon)
            x += 50
        tid = self.create_text(x, 22, anchor="w", text=self.titel, fill="#ffffff", font=(FONT, 15, "bold"))
        self.create_text(x, 44, anchor="w", text=self.untertitel, fill="#e6f0ff", font=(FONT, 9))
        x2 = self.bbox(tid)[2] + 12
        vid = self.create_text(x2 + 9, 22, anchor="w", text=f"v{self.version}", fill=P["accent"] if MODUS == "hell" else "#0b1220",
                               font=(FONT, 9, "bold"))
        bx = self.bbox(vid)
        self._pille(bx[0] - 8, bx[1] - 3, bx[2] + 8, bx[3] + 3, "#ffffff" if MODUS == "hell" else "#cfe4ff")
        self.tag_raise(vid)
        if self.einstellungen is not None:
            self._zahnrad(w - 36, h / 2, mix(a, b, 1.0))

    def _zahnrad(self, cx: float, cy: float, grund: str):
        """Zahnrad als Vektorgrafik (sieht auf jedem System gleich aus) mit runder Hover-Fläche."""
        import math
        hover = self.create_oval(cx - 22, cy - 22, cx + 22, cy + 22, fill=mix(grund, "#ffffff", 0.22), outline="",
                                 state="hidden")
        zaehne, r_aussen, r_innen = 8, 14.5, 10.5
        punkte = []
        for i in range(zaehne * 4):
            winkel = 2 * math.pi * i / (zaehne * 4) - math.pi / (zaehne * 4)
            r = r_aussen if i % 4 in (1, 2) else r_innen
            punkte += [cx + r * math.cos(winkel), cy + r * math.sin(winkel)]
        rad = self.create_polygon(punkte, fill="#ffffff", outline="#ffffff", joinstyle="round", width=1.5)
        loch = self.create_oval(cx - 4.6, cy - 4.6, cx + 4.6, cy + 4.6, fill=grund, outline="")
        teile = (hover, rad, loch)

        def rein(_e):
            self.itemconfigure(hover, state="normal")
            self.itemconfigure(loch, fill=mix(grund, "#ffffff", 0.22))
            self.configure(cursor="hand2")

        def raus(_e):
            self.itemconfigure(hover, state="hidden")
            self.itemconfigure(loch, fill=grund)
            self.configure(cursor="")
        for t in teile:
            self.tag_bind(t, "<Button-1>", lambda e: self.einstellungen())
            self.tag_bind(t, "<Enter>", rein)
            self.tag_bind(t, "<Leave>", raus)
        self.zahnrad_bbox = (cx - 22, cy - 22, cx + 22, cy + 22)

    def _pille(self, x1, y1, x2, y2, farbe):
        r = (y2 - y1) / 2
        self.create_oval(x1, y1, x1 + 2 * r, y2, fill=farbe, outline="")
        self.create_oval(x2 - 2 * r, y1, x2, y2, fill=farbe, outline="")
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=farbe, outline="")


def _runde_leiste(c: tk.Canvas, x1, y1, x2, y2, farbe, tag=""):
    """Waagrechter Balken mit runden Enden (Tk kennt keine abgerundeten Rechtecke)."""
    r = (y2 - y1) / 2
    if x2 - x1 < 2 * r:
        x2 = x1 + 2 * r
    c.create_oval(x1, y1, x1 + 2 * r, y2, fill=farbe, outline="", tags=tag)
    c.create_oval(x2 - 2 * r, y1, x2, y2, fill=farbe, outline="", tags=tag)
    c.create_rectangle(x1 + r, y1, x2 - r, y2, fill=farbe, outline="", tags=tag)


class Fortschritt(tk.Canvas):
    """Moderner Fortschrittsbalken: runde Enden, Farbverlauf und wandernder Lichtreflex.

    setzen(wert, maximum) -> bestimmter Fortschritt; unbestimmt() -> gleitendes Segment;
    anhalten() stoppt die Animation (der Balken bleibt stehen); leeren() setzt auf 0 zurück.
    """

    def __init__(self, master, hoehe: int = 10, hintergrund: str | None = None):
        super().__init__(master, height=hoehe, highlightthickness=0, bd=0, bg=hintergrund or P["bg"])
        self.hoehe = hoehe
        self.wert, self.maximum = 0.0, 1.0
        self.modus = "bestimmt"
        self.laeuft = False
        self._phase = 0.0
        self._job = None
        self.bind("<Configure>", lambda e: self.zeichnen())

    # -- Steuerung
    def setzen(self, wert: float, maximum: float):
        self.modus = "bestimmt"
        self.wert, self.maximum = float(wert), float(maximum or 1)
        self._starten()

    def unbestimmt(self):
        self.modus = "unbestimmt"
        self._starten()

    def anhalten(self, voll: bool = False):
        self.laeuft = False
        if voll:
            self.modus, self.wert, self.maximum = "bestimmt", 1.0, 1.0
        if self.modus == "unbestimmt":
            self.modus, self.wert = "bestimmt", 0.0
        self.zeichnen()

    def leeren(self):
        self.laeuft = False
        self.modus, self.wert, self.maximum = "bestimmt", 0.0, 1.0
        self.zeichnen()

    def _starten(self):
        self.laeuft = True
        if self._job is None:
            self._takt()
        else:
            self.zeichnen()

    def _takt(self):
        self._job = None
        if not self.winfo_exists():
            return
        self._phase = (self._phase + 0.012) % 1.0
        self.zeichnen()
        if self.laeuft:
            self._job = self.after(33, self._takt)

    # -- Zeichnen
    def zeichnen(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 50), self.hoehe
        _runde_leiste(self, 0, 0, w, h, P["rand"])
        a, b = P["accent"], P["accent2"]
        if self.modus == "unbestimmt":
            breite = w * 0.28
            t = self._phase * 2 if self._phase < 0.5 else 2 - self._phase * 2      # hin und her
            t = t * t * (3 - 2 * t)                                                  # weich
            x1 = (w - breite) * t
            self._verlauf(x1, x1 + breite, h, a, b, glanz=None)
            return
        anteil = max(0.0, min(1.0, self.wert / self.maximum)) if self.maximum else 0.0
        if anteil <= 0:
            return
        x2 = max(h, w * anteil)
        glanz = (self._phase * 1.6 - 0.3) * x2 if self.laeuft else None
        self._verlauf(0, x2, h, a, b, glanz=glanz)

    def _verlauf(self, x1, x2, h, a, b, glanz):
        r = h / 2
        schritt = 4
        n = max(1, int((x2 - x1 - 2 * r) / schritt))
        breite = (x2 - x1 - 2 * r) / n if x2 - x1 > 2 * r else 0

        def farbe(x):
            f = mix(a, b, max(0.0, min(1.0, x / max(1, self.winfo_width()))))
            if glanz is not None:
                naehe = max(0.0, 1 - abs(x - glanz) / 38)
                f = mix(f, "#ffffff", 0.45 * naehe * naehe)
            return f
        self.create_oval(x1, 0, x1 + h, h, fill=farbe(x1), outline="")
        self.create_oval(x2 - h, 0, x2, h, fill=farbe(x2), outline="")
        for i in range(n):
            sx = x1 + r + i * breite
            self.create_rectangle(sx, 0, sx + breite + 1, h, fill=farbe(sx + breite / 2), outline="")


class SuchAnimation(tk.Canvas):
    """Animation „Suche läuft“: Lupe in der Mitte, kreisende Bögen, pulsierende Ringe und Punkte."""

    def __init__(self, master, groesse: int = 170, hintergrund: str | None = None):
        super().__init__(master, width=groesse, height=groesse, highlightthickness=0, bd=0,
                         bg=hintergrund or P["bg"])
        self.groesse = groesse
        self._t = 0.0
        self._job = None
        self.zeichnen()

    def start(self):
        if self._job is None:
            self._takt()

    def stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self._t = 0.0
        self.zeichnen()

    def _takt(self):
        if not self.winfo_exists():
            return
        self._t += 1 / 30
        self.zeichnen()
        self._job = self.after(33, self._takt)

    def zeichnen(self):
        import math
        self.delete("all")
        g, t = self.groesse, self._t
        cx = cy = g / 2
        bg, a, b = self.cget("bg"), P["accent"], P["accent2"]
        # pulsierende Ringe (laufen nach außen und verblassen)
        for k in range(3):
            p = ((t * 0.55) + k / 3) % 1.0
            r = 34 + p * (g / 2 - 38)
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=mix(a, bg, p), width=2)
        # kreisende Bögen
        for r, tempo, farbe, laenge in ((g * 0.36, 140, a, 80), (g * 0.29, -200, b, 60)):
            start = (t * tempo) % 360
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=laenge, style="arc",
                            outline=farbe, width=4)
            self.create_arc(cx - r, cy - r, cx + r, cy + r, start=start + 180, extent=laenge * 0.5, style="arc",
                            outline=mix(farbe, bg, 0.45), width=4)
        # umlaufende Punkte
        for k in range(3):
            w = t * 1.6 + k * 2 * math.pi / 3
            r = g * 0.43
            x, y = cx + r * math.cos(w), cy + r * math.sin(w)
            d = 3.2 + 1.3 * math.sin(t * 4 + k)
            self.create_oval(x - d, y - d, x + d, y + d, fill=mix(a, b, k / 2), outline="")
        # Mitte: Kreis mit Lupe, leicht „atmend“
        s = 1 + 0.05 * math.sin(t * 3)
        r = 26 * s
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=mix(a, b, 0.5 + 0.5 * math.sin(t)), outline="")
        lr = 9 * s
        lx, ly = cx - 3 * s, cy - 3 * s
        self.create_oval(lx - lr, ly - lr, lx + lr, ly + lr, outline="#ffffff", width=3)
        self.create_line(lx + lr * 0.7, ly + lr * 0.7, lx + lr * 1.75, ly + lr * 1.75, fill="#ffffff", width=4,
                         capstyle="round")
