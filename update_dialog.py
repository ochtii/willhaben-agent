"""Fenster „Update verfügbar“ bzw. „Nach Updates suchen“."""

from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, messagebox

import theme
from theme import P

import updater


class UpdateDialog(tk.Toplevel):
    """Zeigt Versionen und Änderungen; installiert auf Wunsch und startet neu.

    on_skip(version)   -> „Diese Version überspringen“ merken
    darf_installieren() -> False, solange z.B. eine Suche läuft
    """

    def __init__(self, master, info: updater.UpdateInfo, on_skip=None, darf_installieren=None,
                 beim_start_var: tk.BooleanVar | None = None):
        super().__init__(master)
        self.info, self.on_skip = info, on_skip or (lambda v: None)
        self.darf_installieren = darf_installieren or (lambda: True)
        self.title("Update verfügbar" if info.neuer else "Updates")
        self.transient(master)
        self.resizable(True, True)
        self.minsize(520, 300)
        f = ttk.Frame(self, padding=16)
        f.pack(fill="both", expand=True)

        if info.fehler:
            kopf, farbe = "Update-Prüfung nicht möglich", P["danger"]
        elif info.neuer:
            kopf, farbe = "Eine neue Version ist verfügbar", P["accent"]
        else:
            kopf, farbe = "Du verwendest die neueste Version", P["ok"]
        ttk.Label(f, text=kopf, font=("TkDefaultFont", 13, "bold"), foreground=farbe).pack(anchor="w")

        zeilen = [f"Installiert:  v{info.version_lokal}   ({info.lokal.kurz})"]
        if info.remote:
            zeilen.append(f"Auf GitHub:  v{info.version_remote}   ({info.remote.kurz}, "
                          f"{info.remote.datum[:10]})")
        ttk.Label(f, text="\n".join(zeilen), font=("DejaVu Sans Mono", 10)).pack(anchor="w", pady=(8, 4))
        if info.fehler:
            ttk.Label(f, text=info.fehler, wraplength=480, justify="left").pack(anchor="w", pady=(4, 0))

        if info.neuer and info.aenderungen:
            ttk.Label(f, text=f"Änderungen ({len(info.aenderungen)}):", font=("TkDefaultFont", 10, "bold")).pack(
                anchor="w", pady=(8, 2))
            box = tk.Text(f, height=min(10, max(3, len(info.aenderungen) + 1)), wrap="word",
                          font=("TkDefaultFont", 10), padx=8, pady=6)
            theme.text_farben(box)
            for a in info.aenderungen[:40]:
                box.insert("end", "• " + "".join(c if ord(c) <= 0xFFFF else "" for c in a) + "\n")
            box.configure(state="disabled")
            box.pack(fill="both", expand=True)

        self.lbl_status = ttk.Label(f, text="", wraplength=480, justify="left")
        self.lbl_status.pack(anchor="w", pady=(8, 0))

        if beim_start_var is not None:
            ttk.Checkbutton(f, text="Beim Start nach Updates suchen", variable=beim_start_var).pack(anchor="w",
                                                                                                    pady=(8, 0))
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(12, 0))
        link = ttk.Label(bf, text="Auf GitHub ansehen ↗", foreground=P["accent"], cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(updater.REPO_URL + "/commits/" + updater.BRANCH))
        if info.neuer:
            self.btn_install = ttk.Button(bf, text="Jetzt aktualisieren", command=self.installieren)
            self.btn_install.pack(side="right")
            ttk.Button(bf, text="Diese Version überspringen", command=self.ueberspringen).pack(side="right", padx=6)
            ttk.Button(bf, text="Später", command=self.destroy).pack(side="right")
        else:
            ttk.Button(bf, text="Schließen", command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())

    def ueberspringen(self):
        self.on_skip(self.info.version_remote)
        self.destroy()

    def installieren(self):
        if not self.darf_installieren():
            messagebox.showinfo("Update", "Bitte zuerst die laufende Suche beenden oder abwarten.", parent=self)
            return
        self.btn_install.configure(state="disabled")
        meldungen: list[str] = []

        def log(m):
            print(m, flush=True)
            meldungen.append(m)
            self.after(0, lambda: self.winfo_exists() and self.lbl_status.configure(text="\n".join(meldungen[-4:])))

        def work():
            try:
                version = updater.installieren(self.info, log=log)
                self.after(0, lambda: self._fertig(version))
            except updater.UpdateFehler as e:
                self.after(0, lambda: self._fehler(str(e)))
            except Exception as e:
                self.after(0, lambda: self._fehler(f"{type(e).__name__}: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _fertig(self, version: str):
        if messagebox.askyesno("Update installiert", f"Version v{version} wurde installiert.\n\n"
                               "Jetzt neu starten, um sie zu verwenden?", parent=self):
            self.master.event_generate("<<NeustartNachUpdate>>")
        self.destroy()

    def _fehler(self, text: str):
        self.btn_install.configure(state="normal")
        self.lbl_status.configure(text="✖ " + text, foreground=P["danger"])
