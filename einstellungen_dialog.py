"""Einstellungsfenster (Zahnrad rechts oben): KI-Anbieter & Keys, Darstellung, Allgemein & Updates."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog

import theme
from theme import P

import plattform
import settings
from keys_dialog import KIBereich

REITER = ("ki", "darstellung", "allgemein")


class EinstellungenDialog(tk.Toplevel):
    """Alle Einstellungen an einem Ort. `app` ist das Hauptfenster (gui.App)."""

    def __init__(self, master, app, reiter: str = "ki"):
        super().__init__(master)
        self.app = app
        self.title("Einstellungen")
        self.geometry("1080x740")
        self.minsize(940, 640)
        self.transient(master)
        self.configure(bg=P["bg"])

        kopf = ttk.Frame(self, padding=(16, 14, 16, 4))
        kopf.pack(fill="x")
        ttk.Label(kopf, text="Einstellungen", font=(theme.FONT, 15, "bold")).pack(anchor="w")
        ttk.Label(kopf, text="KI-Anbieter, API-Keys, Darstellung und Updates – Änderungen gelten sofort.",
                  foreground=P["muted"]).pack(anchor="w")

        unten = ttk.Frame(self, padding=(16, 8, 16, 14))
        unten.pack(side="bottom", fill="x")
        ttk.Button(unten, text="Schließen", style="Accent.TButton", command=self.schliessen).pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16)
        self.ki = KIBereich(self.nb, app.store, on_change=app._ki_refresh)
        self.nb.add(self.ki, text="  KI-Anbieter & Keys  ")
        self.nb.add(self._darstellung(), text="  Darstellung  ")
        self.nb.add(self._allgemein(), text="  Allgemein & Updates  ")
        self.zeigen(reiter)

        self.protocol("WM_DELETE_WINDOW", self.schliessen)
        self.bind("<Escape>", lambda e: self.schliessen())

    def zeigen(self, reiter: str):
        self.nb.select(REITER.index(reiter) if reiter in REITER else 0)

    # ---------------------------------------------------------------- Reiter
    def _darstellung(self):
        f = ttk.Frame(self.nb, padding=16)
        lf = ttk.LabelFrame(f, text="Design", padding=12)
        lf.pack(fill="x")
        for wert, titel, text in (("hell", "Hell", "Helle Flächen, blauer Akzent – gut bei Tageslicht."),
                                  ("dunkel", "Dunkel", "Dunkle Flächen, schont die Augen am Abend.")):
            zeile = ttk.Frame(lf)
            zeile.pack(fill="x", pady=4)
            vorschau = tk.Canvas(zeile, width=86, height=48, highlightthickness=0, bd=0, bg=P["bg"])
            vorschau.pack(side="left", padx=(0, 12))
            pal = theme.PALETTEN[wert]
            vorschau.create_rectangle(1, 1, 85, 47, fill=pal["bg"], outline=pal["rand"])
            vorschau.create_rectangle(1, 1, 85, 13, fill=pal["accent"], outline="")
            vorschau.create_rectangle(8, 20, 50, 40, fill=pal["card"], outline=pal["rand"])
            vorschau.create_rectangle(56, 20, 78, 28, fill=pal["accent"], outline="")
            vorschau.create_line(12, 26, 44, 26, fill=pal["fg"])
            vorschau.create_line(12, 33, 36, 33, fill=pal["muted"])
            sp = ttk.Frame(zeile)
            sp.pack(side="left", fill="x")
            ttk.Radiobutton(sp, text=titel, value=wert, variable=self.app.var_design,
                            command=self.app._design_wechseln).pack(anchor="w")
            ttk.Label(sp, text=text, foreground=P["muted"]).pack(anchor="w", padx=(26, 0))
            vorschau.bind("<Button-1>", lambda e, w=wert: (self.app.var_design.set(w), self.app._design_wechseln()))
        ttk.Label(lf, text="Das neue Design wird nach einem Neustart der App vollständig übernommen.",
                  foreground=P["muted"]).pack(anchor="w", pady=(8, 0))
        return f

    def _allgemein(self):
        f = ttk.Frame(self.nb, padding=16)

        of = ttk.LabelFrame(f, text="Ergebnisse", padding=12)
        of.pack(fill="x")
        ttk.Label(of, text="Ergebnis-Ordner (Berichte als Markdown/JSON)").grid(row=0, column=0, columnspan=3, sticky="w")
        self.var_ordner = tk.StringVar(value=str(self.app._outdir()))
        ttk.Entry(of, textvariable=self.var_ordner, width=70, state="readonly").grid(row=1, column=0, sticky="ew",
                                                                                     pady=(4, 0))
        ttk.Button(of, text="Ändern …", command=self._ordner_waehlen).grid(row=1, column=1, padx=6, pady=(4, 0))
        ttk.Button(of, text="Öffnen", command=lambda: plattform.oeffnen(self.app._outdir())).grid(row=1, column=2,
                                                                                                 pady=(4, 0))
        of.columnconfigure(0, weight=1)

        uf = ttk.LabelFrame(f, text="Updates", padding=12)
        uf.pack(fill="x", pady=(12, 0))
        ttk.Label(uf, text=f"Installierte Version: v{self.app.version}", font=(theme.FONT, 10, "bold")).pack(anchor="w")
        ttk.Checkbutton(uf, text="Beim Start nach Updates suchen", variable=self.app.var_update_start).pack(
            anchor="w", pady=(8, 0))
        ttk.Button(uf, text="Jetzt nach Updates suchen …",
                   command=lambda: self.app.update_pruefen(manuell=True)).pack(anchor="w", pady=(8, 0))
        ttk.Label(uf, text="Updates kommen direkt von GitHub. Eine angebotene Version kann übersprungen werden – "
                           "die bisherige Version bleibt dann installiert.", foreground=P["muted"], wraplength=900,
                  justify="left").pack(anchor="w", pady=(6, 0))

        kf = ttk.LabelFrame(f, text="Speicherort", padding=12)
        kf.pack(fill="x", pady=(12, 0))
        zeile = ttk.Frame(kf)
        zeile.pack(fill="x")
        ttk.Label(zeile, text=f"Einstellungen und API-Keys: {settings.CONFIG_DIR}").pack(side="left")
        ttk.Button(zeile, text="Öffnen", command=self._konfig_oeffnen).pack(side="right")
        ttk.Label(kf, text="Die Keys liegen nur auf diesem Computer (Datei nur für deinen Benutzer lesbar) und "
                           "werden ausschließlich an den jeweiligen KI-Anbieter gesendet.",
                  foreground=P["muted"], wraplength=900, justify="left").pack(anchor="w", pady=(6, 0))
        return f

    # ---------------------------------------------------------------- Aktionen
    def _ordner_waehlen(self):
        neu = filedialog.askdirectory(parent=self, initialdir=self.var_ordner.get(), title="Ergebnis-Ordner wählen")
        if neu:
            self.app.cfg["ausgabe"] = str(Path(neu))
            self.var_ordner.set(str(self.app._outdir()))
            try:
                settings.save(self.app.cfg)
            except Exception:
                pass

    @staticmethod
    def _konfig_oeffnen():
        settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        plattform.oeffnen(settings.CONFIG_DIR)

    def schliessen(self):
        try:
            self.ki.schliessen()
        finally:
            self.destroy()
