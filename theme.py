"""Modernes Erscheinungsbild: Sun-Valley-Theme (sv-ttk), Farbpaletten Hell/Dunkel und eigene Stile.

Alle Fenster holen sich ihre Farben aus `P` (aktuelle Palette), damit Hell- und Dunkelmodus
überall zusammenpassen. Ohne sv-ttk fällt die App auf das Standard-Theme „clam“ zurück.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTEN = {
    "hell": {
        "bg": "#f3f5f8", "fg": "#1b1d21", "muted": "#667085", "card": "#ffffff", "rand": "#e3e7ee",
        "accent": "#0b6bcb", "accent2": "#12a36b", "accent_hell": "#e7f1fc", "ok": "#15803d", "warn": "#b45309",
        "danger": "#c0262d", "gold": "#d29a00", "text_bg": "#ffffff", "text_fg": "#1b1d21",
        "term_bg": "#11151c", "term_fg": "#d5dae3", "term_dim": "#6b7484",
        "zeile_ok": "#e8f6ee", "zeile_top": "#fff4cf", "zeile_aus": "#9aa1ad", "tipp_bg": "#fff4cf",
    },
    "dunkel": {
        "bg": "#1c1c1c", "fg": "#f2f2f2", "muted": "#a3a8b3", "card": "#262626", "rand": "#363a40",
        "accent": "#4ca2ff", "accent2": "#2fcf8e", "accent_hell": "#1f3550", "ok": "#4ade80", "warn": "#fbbf24",
        "danger": "#f87171", "gold": "#facc15", "text_bg": "#232323", "text_fg": "#f2f2f2",
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
    """Farbverlauf-Kopfzeile mit Icon, Titel, Version und Schnellzugriffen rechts."""

    def __init__(self, master, titel: str, untertitel: str, version: str, icon: tk.PhotoImage | None,
                 aktionen: list[tuple[str, callable]]):
        super().__init__(master, height=64, highlightthickness=0, bd=0)
        self.titel, self.untertitel, self.version, self.icon = titel, untertitel, version, icon
        self.aktionen = aktionen
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
        rx = w - 16
        for text, cmd in reversed(self.aktionen):
            t = self.create_text(rx, h / 2, anchor="e", text=text, fill="#ffffff", font=(FONT, 10, "bold"))
            x1, y1, x2_, y2 = self.bbox(t)
            r = self.create_rectangle(x1 - 10, y1 - 6, x2_ + 10, y2 + 6, outline="#ffffff", width=1,
                                      fill="")
            for item in (t, r):
                self.tag_bind(item, "<Button-1>", lambda e, c=cmd: c())
                self.tag_bind(item, "<Enter>", lambda e, rr=r: (self.itemconfigure(rr, width=2), self.configure(cursor="hand2")))
                self.tag_bind(item, "<Leave>", lambda e, rr=r: (self.itemconfigure(rr, width=1), self.configure(cursor="")))
            rx = x1 - 22

    def _pille(self, x1, y1, x2, y2, farbe):
        r = (y2 - y1) / 2
        self.create_oval(x1, y1, x1 + 2 * r, y2, fill=farbe, outline="")
        self.create_oval(x2 - 2 * r, y1, x2, y2, fill=farbe, outline="")
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=farbe, outline="")
