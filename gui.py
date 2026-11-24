#!/usr/bin/env python3
"""Willhaben KI-Agent – grafische Oberfläche (Tkinter, läuft auf jedem Linux-Desktop).

Links: Suchauftrag. Rechts: Live-Protokoll, Anzeigen-Tabelle (füllt sich live), Ergebnis.
Alles, was im Fenster protokolliert wird, erscheint zusätzlich im Terminal (falls aus einem gestartet).
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ModuleNotFoundError:
    sys.exit("Tkinter fehlt. Installieren mit:  sudo apt install python3-tk   (Fedora: sudo dnf install python3-tkinter,"
             " Arch: sudo pacman -S tk)")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plattform  # noqa: E402
plattform.ausgabe_absichern()
try:                      # nach einem Update unter Windows: Python-Pakete vor dem Laden aktualisieren
    import updater as _upd  # noqa: E402
    _upd.ausstehende_pakete_installieren()
except Exception:
    pass

import settings  # noqa: E402
import theme  # noqa: E402
from theme import P  # noqa: E402
from pipeline import Auftrag, Ereignisse, run, region_text  # noqa: E402
from bezirk_dialog import BezirkDialog, kurzname  # noqa: E402
from keys import KeyStore, KIFehler, maskiert  # noqa: E402
from keys_dialog import KeyManager, _zahl  # noqa: E402
import updater  # noqa: E402
from update_dialog import UpdateDialog  # noqa: E402
from about_dialog import AboutDialog  # noqa: E402
from providers import PROVIDER_TITEL  # noqa: E402
from willhaben import CATEGORIES, Abgebrochen  # noqa: E402

APP_TITLE = "Willhaben KI-Agent"
BUNDESLAENDER = [("Wien", "wien"), ("Niederösterreich", "niederoesterreich"), ("Oberösterreich", "oberoesterreich"),
                 ("Steiermark", "steiermark"), ("Kärnten", "kaernten"), ("Salzburg", "salzburg"),
                 ("Tirol", "tirol"), ("Vorarlberg", "vorarlberg"), ("Burgenland", "burgenland")]
PHASES = ["Suche", "Details", "KI-Bewertung", "Endvergleich", "Fertig"]



_EMOJI_MAP = {"✅": "✔", "✔️": "✔", "⚠️": "⚠", "❌": "✖", "⏳": "…", "↻": "↻", "🔎": "»", "🤖": "»", "🏆": "»",
              "📄": "»", "💾": "»", "📍": "»", "💡": "★", "👁": "", "\ufe0f": ""}


def tk_safe(text: str) -> str:
    """Tk 8.6 kann Farb-Emojis/Zeichen außerhalb der BMP nicht sicher darstellen -> ersetzen."""
    for k, v in _EMOJI_MAP.items():
        text = text.replace(k, v)
    return "".join(c if ord(c) <= 0xFFFF else "•" for c in text)


def open_path(p: Path | str) -> None:
    plattform.oeffnen(p)


class GuiEreignisse(Ereignisse):
    """Leitet Ereignisse aus dem Arbeits-Thread thread-sicher an die Oberfläche (über eine Queue)."""

    def __init__(self, q: queue.Queue):
        self.q = q

    def log(self, msg):
        print(msg, flush=True)                      # Terminal
        self.q.put(("log", msg))

    def phase(self, name, done=0, total=0):
        self.q.put(("phase", (name, done, total)))

    def anzeigen(self, listings, total):
        self.q.put(("anzeigen", (list(listings), total)))

    def details(self, li):
        self.q.put(("detail", li))

    def bewertungen(self, bew):
        self.q.put(("bewertungen", list(bew)))

    def ergebnis(self, erg, md, md_file, by_id):
        self.q.put(("ergebnis", (erg, md, md_file, by_id)))

    def keys(self):
        self.q.put(("keys", None))

    def marktlage(self, text, quellen):
        self.q.put(("marktlage", (text, list(quellen))))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.worker: threading.Thread | None = None
        self.listings: dict[str, object] = {}
        self.bew: dict[str, object] = {}
        self.result_file: Path | None = None
        self.started_at: datetime | None = None
        self.cfg = settings.load()
        self.store = KeyStore()
        self.key_manager: KeyManager | None = None

        self.version = updater.version_text()
        root.title(f"{APP_TITLE}  v{self.version}")
        self.var_update_start = tk.BooleanVar(value=self.cfg.get("update_beim_start", True))
        self.var_update_start.trace_add("write", lambda *a: self._update_option_speichern())
        root.geometry(self.cfg.get("geometry", "1280x820"))
        root.minsize(1060, 680)
        theme.anwenden(root, self.cfg.get("design", "hell"))
        self._build()
        self._load_form()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self._poll)
        root.after(1000, self._ki_tick)
        root.after(300, self._installation_pruefen)
        root.bind("<<NeustartNachUpdate>>", lambda e: self._neustart())
        if self.var_update_start.get():
            root.after(1500, lambda: self.update_pruefen(manuell=False))
        self._log("Bereit. Suchauftrag links ausfüllen und auf ▶ Start klicken.", "info")
        if not self.store.eintraege():
            self._log("Hinweis: Noch kein Google-Gemini-Key eingetragen → „API-Keys & Limits …“ (Strg+K).", "warn")

    # ------------------------------------------------------------------ Layout
    def _build(self):
        menubar = tk.Menu(self.root)
        m = tk.Menu(menubar, tearoff=0)
        m.add_command(label="API-Keys & Limits …", command=self.open_keys, accelerator="Strg+K")
        m.add_command(label="Ergebnis-Ordner öffnen", command=lambda: open_path(self._outdir()))
        m.add_separator()
        m.add_command(label="Nach Updates suchen …", command=lambda: self.update_pruefen(manuell=True))
        m.add_checkbutton(label="Beim Start nach Updates suchen", variable=self.var_update_start)
        m.add_separator()
        self.var_design = tk.StringVar(value=self.cfg.get("design", "hell"))
        dm = tk.Menu(m, tearoff=0)
        dm.add_radiobutton(label="Hell", value="hell", variable=self.var_design, command=self._design_wechseln)
        dm.add_radiobutton(label="Dunkel", value="dunkel", variable=self.var_design, command=self._design_wechseln)
        m.add_cascade(label="Design", menu=dm)
        m.add_separator()
        m.add_command(label="Beenden", command=self.on_close)
        menubar.add_cascade(label="Einstellungen", menu=m)
        h = tk.Menu(menubar, tearoff=0)
        h.add_command(label="Anleitung: API-Key holen ↗", command=lambda: webbrowser.open(
            f"{updater.REPO_URL}/blob/{updater.BRANCH}/ANLEITUNG-API-KEY.md"))
        h.add_command(label="Gemini-Key erstellen ↗", command=lambda: webbrowser.open("https://aistudio.google.com/apikey"))
        h.add_separator()
        h.add_command(label="Über …", command=self._ueber)
        menubar.add_cascade(label="Hilfe", menu=h)
        self.root.configure(menu=menubar)
        self.root.bind_all("<Control-k>", lambda e: self.open_keys())
        try:
            img = tk.PhotoImage(file=str(Path(__file__).resolve().parent / "icon.png"))
            self._kopf_icon = img.subsample(max(1, img.width() // 40))
        except Exception:
            self._kopf_icon = None
        self.kopf = theme.Kopfleiste(self.root, APP_TITLE, "Durchsucht alle Anzeigen auf willhaben und bewertet sie mit KI",
                                     self.version, self._kopf_icon,
                                     [("API-Keys", self.open_keys), ("Updates", lambda: self.update_pruefen(manuell=True)),
                                      ("Über", self._ueber)])
        self.kopf.pack(fill="x")
        main = ttk.PanedWindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ---------------- linke Spalte: Formular (scrollbar)
        left_outer = ttk.Frame(main, padding=(14, 12, 6, 12))
        main.add(left_outer, weight=0)
        # Start/Stopp immer sichtbar unten
        bf = ttk.Frame(left_outer, padding=(0, 10, 0, 0))
        bf.pack(side="bottom", fill="x")
        self.btn_start = ttk.Button(bf, text="▶   Suche starten", style="Accent.TButton", command=self.start)
        self.btn_start.pack(side="left", fill="x", expand=True, ipady=4)
        self.btn_stop = ttk.Button(bf, text="■  Stopp", command=self.cancel, state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 0))
        canvas = tk.Canvas(left_outer, highlightthickness=0, width=380, bg=P["bg"])
        sb = ttk.Scrollbar(left_outer, orient="vertical", command=canvas.yview)
        form = ttk.Frame(canvas, padding=(0, 0, 10, 0))
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.bind_all("<Button-4>", lambda e: self._wheel(canvas, e, -1))
        canvas.bind_all("<Button-5>", lambda e: self._wheel(canvas, e, 1))
        canvas.bind_all("<MouseWheel>", lambda e: self._wheel(canvas, e, -1 if e.delta > 0 else 1))
        self._form_canvas = canvas

        ttk.Label(form, text="Neue Suche", style="Title.TLabel").pack(anchor="w")
        ttk.Label(form, text="Was, wie teuer, wo – den Rest erledigt der Agent.", style="Sub.TLabel").pack(
            anchor="w", pady=(0, 8))

        # Was?
        f = ttk.LabelFrame(form, text="Was suchst du?", style="Section.TLabelframe", padding=10)
        f.pack(fill="x", pady=5)
        ttk.Label(f, text="Suchbegriff (optional)").grid(row=0, column=0, sticky="w")
        self.var_suche = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_suche, width=10).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(f, text="Kategorie").grid(row=2, column=0, sticky="w")
        self.var_kat = tk.StringVar(value="laptops")
        ttk.Combobox(f, textvariable=self.var_kat, values=list(CATEGORIES), width=10).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(f, text="Kurze Beschreibung / Anforderungen").grid(row=4, column=0, sticky="w")
        self.txt_beschr = tk.Text(f, height=4, width=20, wrap="word", font=("TkDefaultFont", 10), padx=6, pady=4)
        theme.text_farben(self.txt_beschr)
        self.txt_beschr.grid(row=5, column=0, columnspan=2, sticky="ew")
        ttk.Label(f, text="z.B. „Für Uni & Office, leicht, guter Akku, mind. 16 GB RAM“",
                  style="Small.TLabel", wraplength=320, justify="left").grid(row=6, column=0, columnspan=2, sticky="w")
        f.columnconfigure(0, weight=1)

        # Preis
        f = ttk.LabelFrame(form, text="Preisspanne (€)", style="Section.TLabelframe", padding=10)
        f.pack(fill="x", pady=5)
        self.var_von, self.var_bis = tk.StringVar(), tk.StringVar()
        ttk.Label(f, text="von").pack(side="left")
        ttk.Spinbox(f, from_=0, to=100000, increment=50, textvariable=self.var_von, width=8).pack(side="left", padx=4)
        ttk.Label(f, text="bis").pack(side="left", padx=(8, 0))
        ttk.Spinbox(f, from_=0, to=100000, increment=50, textvariable=self.var_bis, width=8).pack(side="left", padx=4)

        # Region
        f = ttk.LabelFrame(form, text="Region", style="Section.TLabelframe", padding=10)
        f.pack(fill="x", pady=5)
        ttk.Label(f, text="Bundesland (keins = ganz Österreich)").grid(row=0, column=0, columnspan=3, sticky="w")
        self.bl_vars = {}
        self.bezirk_auswahl: dict[str, list[tuple[str, str]]] = {}    # Bundesland -> [(Name, areaId)]
        for i, (label, key) in enumerate(BUNDESLAENDER):
            v = tk.BooleanVar()
            self.bl_vars[key] = v
            v.trace_add("write", lambda *a: self._bezirk_zeilen())
            ttk.Checkbutton(f, text=label, variable=v).grid(row=1 + i // 2, column=i % 2, sticky="w", padx=(0, 6))
        # Bezirksauswahl je angehaktem Bundesland (erscheint direkt darunter)
        self.frm_bezirke = ttk.Frame(f)
        self.frm_bezirke.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self.frm_bezirke.columnconfigure(1, weight=1)
        ttk.Label(f, text="Weitere Orte / PLZ (optional, Textfilter)").grid(row=7, column=0, columnspan=3,
                                                                          sticky="w", pady=(6, 0))
        self.var_bezirk = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_bezirk, width=10).grid(row=8, column=0, columnspan=3, sticky="ew")
        ttk.Label(f, text="z.B. „1100“ oder ein Ortsname – meist nicht nötig", style="Sub.TLabel").grid(
            row=9, column=0, columnspan=3, sticky="w")

        # Ergebnis-Optionen
        f = ttk.LabelFrame(form, text="Auswertung", style="Section.TLabelframe", padding=10)
        f.pack(fill="x", pady=5)
        ttk.Label(f, text="Anzahl Top-Geräte").grid(row=0, column=0, sticky="w")
        self.var_top = tk.StringVar(value="10")
        ttk.Spinbox(f, from_=1, to=50, textvariable=self.var_top, width=6).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(f, text="Max. Anzeigen für KI (0 = alle)").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.var_max = tk.StringVar(value="0")
        ttk.Spinbox(f, from_=0, to=10000, increment=50, textvariable=self.var_max, width=6).grid(
            row=1, column=1, sticky="w", padx=6, pady=(4, 0))
        self.var_ohne_details = tk.BooleanVar()
        ttk.Checkbutton(f, text="Schnellmodus (nur Kurzbeschreibung laden)",
                        variable=self.var_ohne_details).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.var_markt = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Aktuelle Marktlage per Google-Suche einbeziehen",
                        variable=self.var_markt).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(f, text="Oder: Such-URL aus dem Browser (überschreibt Kategorie)").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.var_url = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_url, width=10).grid(row=4, column=0, columnspan=2, sticky="ew")

        # KI
        f = ttk.LabelFrame(form, text="KI & API-Keys", style="Section.TLabelframe", padding=10)
        f.pack(fill="x", pady=5)
        self.lbl_ki = ttk.Label(f, text="", justify="left", wraplength=320)
        self.lbl_ki.pack(anchor="w", fill="x")
        self.lbl_ki_live = ttk.Label(f, text="", style="Sub.TLabel", justify="left", wraplength=320)
        self.lbl_ki_live.pack(anchor="w", fill="x", pady=(4, 0))
        ttk.Button(f, text="API-Keys & Limits verwalten …", command=self.open_keys).pack(fill="x", pady=(8, 0))

        # ---------------- rechte Seite
        right = ttk.Frame(main, padding=(8, 12, 14, 12))
        main.add(right, weight=1)

        # Phasen als Stepper + Fortschritt
        self.stepper = theme.Stepper(right, PHASES)
        self.stepper.pack(fill="x")
        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.pack(fill="x", pady=(2, 4))
        zeile = ttk.Frame(right)
        zeile.pack(fill="x")
        self.lbl_status = ttk.Label(zeile, text="Bereit", style="Status.TLabel")
        self.lbl_status.pack(side="left")
        self.lbl_time = ttk.Label(zeile, text="", style="Status.TLabel")
        self.lbl_time.pack(side="right")

        # Zähler als Kacheln
        cnt = ttk.Frame(right)
        cnt.pack(fill="x", pady=(10, 10))
        self.counter = {}
        for i, (key, label, farbe) in enumerate((("gefunden", "Anzeigen gefunden", P["accent"]),
                                                 ("details", "Beschreibungen", "#7c5cff"),
                                                 ("bewertet", "KI-bewertet", P["gold"]),
                                                 ("relevant", "passend", P["accent2"]))):
            v = tk.StringVar(value="0")
            theme.Karte(cnt, label, v, farbe).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            cnt.columnconfigure(i, weight=1)
            self.counter[key] = v

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)

        # Tab 1: Live-Protokoll (Terminal-Look)
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Live-Protokoll  ")
        self.txt_log = tk.Text(tab, wrap="word", font=(plattform.MONO, 10), padx=12, pady=10, state="disabled")
        theme.text_farben(self.txt_log, terminal=True)
        sb = ttk.Scrollbar(tab, command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt_log.pack(fill="both", expand=True)
        for tag, color in (("info", "#8ab4f8"), ("warn", "#f9c74f"), ("err", "#ff6b6b"),
                           ("ok", "#7bd88f"), ("time", P["term_dim"]), ("dim", "#9a9a9a")):
            self.txt_log.tag_configure(tag, foreground=color)

        # Tab 2: Anzeigen
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Anzeigen  ")
        cols = ("preis", "ort", "zustand", "leistung", "pl", "status")
        self.tree = ttk.Treeview(tab, columns=cols, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Titel", command=lambda: self._sort("#0"))
        self.tree.column("#0", width=300, minwidth=180, stretch=True)
        for c, t, w in (("preis", "Preis", 75), ("ort", "Ort", 150), ("zustand", "Zustand", 105),
                        ("leistung", "Leistung", 65), ("pl", "P/L", 45), ("status", "KI-Status", 110)):
            self.tree.heading(c, text=t, command=lambda c=c: self._sort(c))
            self.tree.column(c, width=w, stretch=False, anchor="center" if c in ("preis", "leistung", "pl") else "w")
        self.tree.tag_configure("relevant", background=P["zeile_ok"])
        self.tree.tag_configure("irrelevant", foreground=P["zeile_aus"])
        self.tree.tag_configure("top", background=P["zeile_top"])
        sb = ttk.Scrollbar(tab, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.bind("<<TreeviewSelect>>", self._show_reason)
        self.lbl_reason = ttk.Label(tab, text="Doppelklick öffnet die Anzeige im Browser.", style="Sub.TLabel",
                                    wraplength=800, justify="left")
        self.lbl_reason.pack(fill="x", padx=4, pady=4)

        # Tab 3: Ergebnis
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Ergebnis  ")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(4, 0))
        self.btn_report = ttk.Button(bar, text="Bericht öffnen", state="disabled",
                                     command=lambda: self.result_file and open_path(self.result_file))
        self.btn_report.pack(side="left", padx=4)
        ttk.Button(bar, text="Ergebnis-Ordner öffnen", command=lambda: open_path(self._outdir())).pack(side="left")
        self.txt_res = tk.Text(tab, wrap="word", font=("TkDefaultFont", 11), padx=18, pady=14,
                               state="disabled", cursor="arrow")
        theme.text_farben(self.txt_res)
        sb = ttk.Scrollbar(tab, command=self.txt_res.yview)
        self.txt_res.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt_res.pack(fill="both", expand=True)
        t = self.txt_res
        t.tag_configure("h1", font=("TkDefaultFont", 16, "bold"), spacing3=6)
        t.tag_configure("h2", font=("TkDefaultFont", 13, "bold"), spacing1=12, spacing3=4)
        t.tag_configure("rank", font=("TkDefaultFont", 12, "bold"), foreground=P["accent"], spacing1=16)
        t.tag_configure("specs", foreground=P["muted"], font=(plattform.MONO, 10))
        t.tag_configure("pro", foreground=P["ok"])
        t.tag_configure("con", foreground=P["warn"])
        t.tag_configure("fazit", font=("TkDefaultFont", 10, "italic"))
        t.tag_configure("tipp", background=P["tipp_bg"], lmargin1=10, lmargin2=10, rmargin=10, spacing1=6, spacing3=6)
        t.tag_configure("dim", foreground=P["muted"])
        self._set_result_placeholder()

    def _bezirk_zeilen(self):
        """Zeigt unter den Bundesländern je angehaktem Bundesland die gewählten Bezirke + Knopf „Bezirke …“."""
        for w in self.frm_bezirke.winfo_children():
            w.destroy()
        r = 0
        for label, key in BUNDESLAENDER:
            if not self.bl_vars[key].get():
                continue
            auswahl = self.bezirk_auswahl.get(key, [])
            ttk.Label(self.frm_bezirke, text=f"{label}:", font=("TkDefaultFont", 9, "bold")).grid(
                row=r, column=0, sticky="nw", pady=2)
            if auswahl:
                namen = [kurzname(n) for n, _ in auswahl]
                text = ", ".join(namen[:4]) + (f" + {len(namen) - 4} weitere" if len(namen) > 4 else "")
            else:
                text = "alle Bezirke"
            ttk.Label(self.frm_bezirke, text=text, style="Sub.TLabel" if not auswahl else "TLabel",
                      wraplength=170, justify="left").grid(row=r, column=1, sticky="w", padx=6, pady=2)
            ttk.Button(self.frm_bezirke, text="Bezirke …", width=9,
                       command=lambda k=key, l=label: self._bezirke_waehlen(k, l)).grid(row=r, column=2, sticky="e", pady=2)
            r += 1

    def _bezirke_waehlen(self, key: str, label: str):
        def ok(liste):
            self.bezirk_auswahl[key] = liste
            self._bezirk_zeilen()
        BezirkDialog(self.root, key, label, self.bezirk_auswahl.get(key, []), ok)

    def _region(self) -> tuple[list[str], list[int], list[str]]:
        """(Bundesländer ohne Bezirksauswahl, areaIds der gewählten Bezirke, deren Namen)."""
        laender, ids, namen = [], [], []
        for _, key in BUNDESLAENDER:
            if not self.bl_vars[key].get():
                continue
            auswahl = self.bezirk_auswahl.get(key, [])
            if auswahl:
                ids += [int(aid) for _, aid in auswahl]
                namen += [kurzname(n) for n, _ in auswahl]
            else:
                laender.append(key)
        return laender, ids, namen

    def _wheel(self, canvas, event, direction):
        # nur scrollen, wenn die Maus über der linken Spalte ist
        w = self.root.winfo_containing(event.x_root, event.y_root)
        while w is not None:
            if w is canvas:
                canvas.yview_scroll(direction * 2, "units")
                return
            w = w.master

    # ------------------------------------------------------------------ Formular <-> Config
    def _load_form(self):
        c = self.cfg
        self.var_suche.set(c.get("suche", ""))
        self.var_kat.set(c.get("kategorie", "laptops"))
        self.txt_beschr.insert("1.0", c.get("beschreibung", ""))
        self.var_von.set(c.get("von", "200"))
        self.var_bis.set(c.get("bis", "600"))
        self.bezirk_auswahl = {k: [tuple(x) for x in v] for k, v in c.get("bezirke_auswahl", {}).items()}
        for k in c.get("bundeslaender", []):
            if k in self.bl_vars:
                self.bl_vars[k].set(True)
        self._bezirk_zeilen()
        self.var_bezirk.set(c.get("bezirke", ""))
        self.var_top.set(str(c.get("top", 10)))
        self.var_max.set(str(c.get("max_anzeigen", 0)))
        self.var_ohne_details.set(bool(c.get("ohne_details", False)))
        self.var_markt.set(bool(c.get("marktrecherche", True)))
        self._ki_refresh()

    def _save_form(self):
        c = self.cfg
        c.update({
            "suche": self.var_suche.get(), "kategorie": self.var_kat.get(),
            "beschreibung": self.txt_beschr.get("1.0", "end").strip(),
            "von": self.var_von.get(), "bis": self.var_bis.get(),
            "bundeslaender": [k for k, v in self.bl_vars.items() if v.get()],
            "bezirke": self.var_bezirk.get(), "top": self.var_top.get(),
            "bezirke_auswahl": {k: [list(x) for x in v] for k, v in self.bezirk_auswahl.items() if v},
            "max_anzeigen": self.var_max.get(), "ohne_details": self.var_ohne_details.get(),
            "marktrecherche": self.var_markt.get(),
            "geometry": self.root.geometry(),
        })
        try:
            settings.save(c)
        except Exception as e:
            self._log(f"Einstellungen konnten nicht gespeichert werden: {e}", "warn")

    def _outdir(self) -> Path:
        p = Path(self.cfg.get("ausgabe", settings.DEFAULT_OUTPUT)).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _int(s: str) -> int | None:
        s = (s or "").strip().replace("€", "").replace(".", "").replace(" ", "")
        return int(s) if s.isdigit() else None

    def _auftrag(self) -> Auftrag:
        laender, area_ids, bezirk_namen = self._region()
        return Auftrag(
            suche=self.var_suche.get().strip(),
            kategorie=self.var_kat.get().strip() or "laptops",
            url=self.var_url.get().strip(),
            von=self._int(self.var_von.get()),
            bis=self._int(self.var_bis.get()),
            bundeslaender=laender,
            area_ids=area_ids,
            bezirk_namen=bezirk_namen,
            bezirke=[b.strip() for b in self.var_bezirk.get().replace(";", ",").split(",") if b.strip()],
            beschreibung=self.txt_beschr.get("1.0", "end").strip(),
            top=self._int(self.var_top.get()) or 10,
            max_anzeigen=self._int(self.var_max.get()) or None,
            ohne_details=self.var_ohne_details.get(),
            marktrecherche=self.var_markt.get(),
            ausgabe=str(self._outdir()),
        )

    # ------------------------------------------------------------------ Aktionen
    def start(self):
        if self.worker and self.worker.is_alive():
            return
        a = self._auftrag()
        if not any(e.get("aktiv", True) for e in self.store.eintraege("gemini")):
            if messagebox.askyesno(APP_TITLE, "Es ist noch kein (aktiver) API-Key eingetragen.\n\n"
                                   "Jetzt die Key-Verwaltung öffnen?"):
                self.open_keys()
            return
        if a.kategorie not in CATEGORIES and "/" not in a.kategorie and not a.url:
            messagebox.showerror(APP_TITLE, f"Unbekannte Kategorie „{a.kategorie}“.\nBitte aus der Liste wählen.")
            return
        self._save_form()
        self._reset_run()
        self.stop.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.started_at = datetime.now()
        self._tick()
        self.nb.select(0)
        self._log(f"Start: {a.suche or a.kategorie} · {a.von or 0}–{a.bis or '∞'} € · "
                  f"{region_text(a)} · Top {a.top}", "info")
        ev = GuiEreignisse(self.q)

        def work():
            try:
                run(a, ev, self.stop, store=self.store)
                self.q.put(("done", None))
            except Abgebrochen:
                self.q.put(("cancelled", None))
            except KIFehler as e:
                self.q.put(("error", str(e)))
            except Exception as e:
                traceback.print_exc()
                self.q.put(("error", f"{type(e).__name__}: {e}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def cancel(self):
        if self.worker and self.worker.is_alive():
            self.stop.set()
            self.btn_stop.configure(state="disabled")
            self._log("Abbruch angefordert – wird nach dem aktuellen Schritt beendet …", "warn")

    def _installation_pruefen(self):
        """Entfernt nicht benötigte Dateien (z.B. nach einem Update durch eine ältere Version) und weist
        darauf hin, wenn die App noch direkt aus einem Quellordner/Git-Klon läuft."""
        try:
            plattform.windows_version_eintragen(self.version)
            updater.aufraeumen(log=lambda m: self._log(m, "info"))
            updater.alte_menueeintraege_entfernen(log=lambda m: self._log(m, "info"))
        except Exception as e:
            self._log(f"Aufräumen nicht möglich: {e}", "warn")
        if (updater.APP_DIR / ".git").exists() and (updater.APP_DIR / "install.sh").exists() \
                and not self.cfg.get("hinweis_installation"):
            self._log(plattform.installations_hinweis(), "warn")
            self.cfg["hinweis_installation"] = True

    # ------------------------------------------------------------------ Updates
    def update_pruefen(self, manuell: bool):
        """Prüft im Hintergrund auf GitHub. Beim Start still, außer es gibt eine neue (nicht übersprungene) Version."""
        if manuell:
            self._log("Suche nach Updates …", "info")

        def work():
            info = updater.pruefen()
            self.root.after(0, lambda: self._update_ergebnis(info, manuell))
        threading.Thread(target=work, daemon=True).start()

    def _update_ergebnis(self, info, manuell: bool):
        if info.fehler:
            self._log(f"Update-Prüfung: {info.fehler}", "warn")
            if not manuell:
                return
        elif info.neuer:
            self._log(f"Neue Version verfügbar: v{info.version_remote} (installiert: v{info.version_lokal})", "ok")
            if not manuell and self.cfg.get("update_uebersprungen") == info.version_remote:
                return
        else:
            if info.version_lokal != self.version:      # Nummer erst jetzt bekannt (z.B. ZIP-Installation)
                self.version = info.version_lokal
                self.root.title(f"{APP_TITLE}  v{self.version}")
                self.kopf.version_setzen(self.version)
            if manuell:
                self._log(f"Neueste Version installiert (v{info.version_lokal}).", "ok")
            else:
                return
        UpdateDialog(self.root, info, on_skip=self._update_ueberspringen,
                     darf_installieren=lambda: not (self.worker and self.worker.is_alive()),
                     beim_start_var=self.var_update_start)

    def _update_ueberspringen(self, version: str):
        self.cfg["update_uebersprungen"] = version
        self._save_form()
        self._log(f"Version v{version} wird übersprungen (manuell weiterhin installierbar).", "info")

    def _update_option_speichern(self):
        self.cfg["update_beim_start"] = bool(self.var_update_start.get())
        try:
            settings.save(self.cfg)
        except Exception:
            pass

    def _neustart(self):
        self._save_form()
        self.root.destroy()
        updater.neu_starten()

    def _design_wechseln(self):
        modus = self.var_design.get()
        if modus == self.cfg.get("design", "hell"):
            return
        self.cfg["design"] = modus
        self._save_form()
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_TITLE, "Das neue Design wird beim nächsten Start übernommen.")
        elif messagebox.askyesno(APP_TITLE, "Das neue Design wird nach einem Neustart vollständig übernommen.\n\n"
                                            "Jetzt neu starten?"):
            self._neustart()

    def _ueber(self):
        if getattr(self, "_about", None) is not None and self._about.winfo_exists():
            self._about.lift()
            return
        self._about = AboutDialog(self.root, self.version, on_update=lambda: self.update_pruefen(manuell=True))

    def open_keys(self):
        if self.key_manager is not None and self.key_manager.winfo_exists():
            self.key_manager.lift()
            self.key_manager.focus_force()
            return
        self.key_manager = KeyManager(self.root, self.store, on_change=self._ki_refresh)

    def _ki_refresh(self):
        """Kurzübersicht der Keys im Hauptfenster."""
        st = self.store
        alle = st.eintraege("gemini")
        aktiv = [e for e in alle if e.get("aktiv", True)]
        bereit = [e for e in aktiv if st.status_text(e).startswith(("bereit", "Pause"))]
        heute = sum(st.nutzung(e["id"]).get("anfragen", 0) for e in alle)
        modell = st.optionen.get("modelle", {}).get("gemini", "?")
        ausweich = st.optionen.get("ausweich", {}).get("gemini") or "–"
        vert = "gleichmäßig" if st.optionen.get("verteilung") == "gleichmaessig" else "nacheinander"
        keys_txt = (f"{len(bereit)}/{len(aktiv)} Keys bereit ({vert}) · heute {heute} Anfr." if alle else "kein Key")
        self.lbl_ki.configure(text=tk_safe(f"Google Gemini: {keys_txt}\nModell: {modell} · Ausweich: {ausweich}"))
        letzte = max(st.eintraege(), key=lambda e: st.nutzung(e["id"]).get("zuletzt", 0), default=None)
        if letzte and st.nutzung(letzte["id"]).get("zuletzt"):
            u, lim = st.nutzung(letzte["id"]), st.limits(letzte)
            srv = u.get("server", {})
            rest = f" · Server: noch {_zahl(srv['rest_anfragen'])} Anfr." if "rest_anfragen" in srv else ""
            rpd = lim["rpd"][0]
            self.lbl_ki_live.configure(text=tk_safe(
                f"Zuletzt: {PROVIDER_TITEL[letzte['provider']]} „{letzte['label']}“ – "
                f"{u.get('anfragen', 0)}/{_zahl(rpd) if rpd else '?'}{'*' if lim['rpd'][1] == 'Annahme' else ''} "
                f"heute, {st.status_text(letzte)}{rest}"))
        else:
            self.lbl_ki_live.configure(text="Noch keine KI-Anfrage." if st.eintraege() else
                                       "→ Unten auf „API-Keys & Limits verwalten“ klicken und einen Key hinzufügen.")

    def _ki_tick(self):
        if self.root.winfo_exists():
            self._ki_refresh()
            self.root.after(2000, self._ki_tick)

    def on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(APP_TITLE, "Der Agent läuft noch. Wirklich beenden?"):
                return
            self.stop.set()
        self._save_form()
        self.root.destroy()

    # ------------------------------------------------------------------ Anzeige-Updates
    def _reset_run(self):
        self.listings.clear()
        self.bew.clear()
        self.tree.delete(*self.tree.get_children())
        for v in self.counter.values():
            v.set("0")
        self.progress.configure(value=0, maximum=1)
        self.stepper.setzen(-1)
        self.result_file = None
        self._marktlage = ("", [])
        self.btn_report.configure(state="disabled")
        self._set_result_placeholder()

    def _tick(self):
        if self.started_at and self.worker and self.worker.is_alive():
            d = datetime.now() - self.started_at
            self.lbl_time.configure(text=f"⏱ {int(d.total_seconds()) // 60:02d}:{int(d.total_seconds()) % 60:02d}")
            self.root.after(1000, self._tick)

    def _log(self, msg: str, tag: str | None = None):
        if tag is None:
            m = msg.lstrip()
            tag = ("err" if m.startswith(("❌", "!")) else "ok" if m.startswith(("✅", "✔")) else
                   "warn" if m.startswith(("⚠", "⏳", "↻", "📍")) else "info" if m[:1] in "🔎🤖🏆📄💾" else None)
        t = self.txt_log
        t.configure(state="normal")
        t.insert("end", datetime.now().strftime("%H:%M:%S "), "time")
        t.insert("end", tk_safe(msg) + "\n", tag or ())
        t.see("end")
        t.configure(state="disabled")

    def _set_phase(self, name, done, total):
        if name in PHASES:
            self.stepper.setzen(PHASES.index(name), fertig=(name == "Fertig"))
        if total:
            if str(self.progress.cget("mode")) == "indeterminate":
                self.progress.stop()      # stop() setzt den Wert auf 0 -> nur im Lauf-Modus aufrufen
            self.progress.configure(mode="determinate", maximum=total, value=done)
            self.lbl_status.configure(text="Fertig" if name == "Fertig" else f"{name}: {done} / {total}")
        else:
            self.progress.configure(mode="indeterminate")
            self.progress.start(15)
            self.lbl_status.configure(text=f"{name} …")
            return
        if name == "Details":
            self.counter["details"].set(str(done))

    def _row_values(self, li):
        b = self.bew.get(li.id)
        price = li.price_text or ("–" if li.price is None else f"€ {li.price:.0f}")
        zustand = (b.zustand if b else (li.extra or {}).get("Zustand", ""))
        status = ("✔ relevant" if b.relevant else "✖ nicht passend") if b else (
            "Beschreibung ✓" if li.description else "gefunden")
        return (price, li.location, zustand, b.leistung if b else "", b.preis_leistung if b else "", status)

    def _upsert(self, li):
        self.listings[li.id] = li
        b = self.bew.get(li.id)
        tags = (("relevant",) if b.relevant else ("irrelevant",)) if b else ()
        if self.tree.exists(li.id):
            self.tree.item(li.id, values=[tk_safe(str(v)) for v in self._row_values(li)], tags=tags)
        else:
            self.tree.insert("", "end", iid=li.id, text=tk_safe(li.title), values=[tk_safe(str(v)) for v in self._row_values(li)], tags=tags)

    def _sort(self, col):
        items = list(self.tree.get_children(""))
        def key(iid):
            v = self.tree.item(iid, "text") if col == "#0" else self.tree.set(iid, col)
            if col == "preis":
                li = self.listings.get(iid)
                return (li.price if li and li.price is not None else 1e12)
            try:
                return float(v)
            except (TypeError, ValueError):
                return -1 if v == "" else str(v).lower()
        rev = getattr(self, "_sort_rev", {}).get(col, col in ("leistung", "pl"))
        try:
            items.sort(key=key, reverse=rev)
        except TypeError:
            items.sort(key=lambda i: str(key(i)), reverse=rev)
        for i, iid in enumerate(items):
            self.tree.move(iid, "", i)
        self._sort_rev = {col: not rev}

    def _open_selected(self, _e=None):
        sel = self.tree.selection()
        if sel and sel[0] in self.listings:
            webbrowser.open(self.listings[sel[0]].url)

    def _show_reason(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        li, b = self.listings.get(sel[0]), self.bew.get(sel[0])
        if b:
            warn = f"   ⚠ {', '.join(b.warnsignale)}" if b.warnsignale else ""
            self.lbl_reason.configure(text=tk_safe(f"{b.specs}  ·  {b.begruendung}{warn}"))
        elif li:
            self.lbl_reason.configure(text=tk_safe((li.description or li.teaser)[:300]))

    def _set_result_placeholder(self):
        t = self.txt_res
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", "Noch kein Ergebnis.\n\n", "h2")
        t.insert("end", "Nach dem Lauf erscheinen hier die besten Angebote mit Vor- und Nachteilen.", "dim")
        t.configure(state="disabled")

    def _show_result(self, erg, md_file, by_id):
        t = self.txt_res
        ins = lambda txt, *tags: t.insert("end", tk_safe(txt), *tags)
        t.configure(state="normal")
        t.delete("1.0", "end")
        ins(f"Top {len(erg.top)} – {self.var_suche.get() or self.var_kat.get()}\n", "h1")
        ins("Marktüberblick\n", "h2")
        ins(erg.zusammenfassung + "\n")
        markt, quellen = getattr(self, "_marktlage", ("", []))
        if markt:
            ins("\nAktuelle Marktlage (Google-Suche)\n", "h2")
            ins(markt + "\n", "dim")
            for i, (titel, url) in enumerate(quellen[:8]):
                tag = f"quelle-{i}"
                t.tag_configure(tag, foreground=P["accent"], underline=True)
                t.tag_bind(tag, "<Button-1>", lambda _e, u=url: webbrowser.open(u))
                ins(f"[{titel}]", tag)
                ins("  ")
            ins("\n")
        if erg.tipp:
            ins("\n★ Tipp: " + erg.tipp + "\n", "tipp")
        for e in erg.top:
            li = by_id.get(e.id)
            ins(f"\n{e.rang}. {e.titel}  —  {e.preis}\n", "rank")
            ins(e.specs + "\n", "specs")
            if li:
                ins(f"{li.postcode} {li.location}   ", "dim")
                tag = f"link-{e.id}"
                t.tag_configure(tag, foreground=P["accent"], underline=True)
                t.tag_bind(tag, "<Button-1>", lambda _e, u=li.url: webbrowser.open(u))
                t.tag_bind(tag, "<Enter>", lambda _e: t.configure(cursor="hand2"))
                t.tag_bind(tag, "<Leave>", lambda _e: t.configure(cursor="arrow"))
                ins("→ Anzeige öffnen", tag)
                ins("\n")
            for v in e.vorteile:
                ins(f"   ✔ {v}\n", "pro")
            for n in e.nachteile:
                ins(f"   ⚠ {n}\n", "con")
            ins(f"   {e.fazit}\n", "fazit")
        ins(f"\nBericht gespeichert: {md_file}\n", "dim")
        t.configure(state="disabled")
        for e in erg.top:
            if self.tree.exists(e.id):
                self.tree.item(e.id, tags=("top",), text=f"#{e.rang}  {self.tree.item(e.id, 'text')}")

    def _finish(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        if str(self.progress.cget("mode")) == "indeterminate":
            self.progress.stop()

    def _poll(self):
        try:
            for _ in range(500):
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._log(data)
                elif kind == "phase":
                    self._set_phase(*data)
                elif kind == "anzeigen":
                    listings, total = data
                    keep = {li.id for li in listings}
                    for iid in self.tree.get_children(""):
                        if iid not in keep:
                            self.tree.delete(iid)
                            self.listings.pop(iid, None)
                    for li in listings:
                        self._upsert(li)
                    self.counter["gefunden"].set(str(len(listings)))
                    self.nb.tab(1, text=f"  Anzeigen ({len(listings)})  ")
                elif kind == "detail":
                    if data.id in self.listings:
                        self._upsert(data)
                elif kind == "bewertungen":
                    for b in data:
                        self.bew[b.id] = b
                        if b.id in self.listings:
                            self._upsert(self.listings[b.id])
                    self.counter["bewertet"].set(str(len(self.bew)))
                    self.counter["relevant"].set(str(sum(1 for b in self.bew.values() if b.relevant)))
                elif kind == "ergebnis":
                    erg, md, md_file, by_id = data
                    self.result_file = md_file
                    self.btn_report.configure(state="normal")
                    self._show_result(erg, md_file, by_id)
                    self.nb.select(2)
                elif kind == "done":
                    self._finish()
                    self.lbl_status.configure(text="✔ Fertig")
                elif kind == "cancelled":
                    self._finish()
                    self._log("Abgebrochen.", "warn")
                    self.lbl_status.configure(text="Abgebrochen")
                elif kind == "error":
                    self._finish()
                    self._log("❌ " + data, "err")
                    self.lbl_status.configure(text="Fehler – siehe Protokoll")
                    messagebox.showerror(APP_TITLE, data)
                elif kind == "keys":
                    self._ki_refresh()
                elif kind == "marktlage":
                    self._marktlage = data
        except queue.Empty:
            pass
        self.root.after(80, self._poll)


def main():
    root = tk.Tk(className="willhaben-agent")
    icon = Path(__file__).resolve().parent / "icon.png"
    if icon.exists():
        try:
            root.iconphoto(True, tk.PhotoImage(file=str(icon)))
        except Exception:
            pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
