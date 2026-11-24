"""Einstellungsfenster: API-Keys & Limits (mehrere Google-Gemini-Keys, Modellwahl, Verbrauch live)."""

from __future__ import annotations

import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

from keys import KeyStore, LIMIT_FELDER, maskiert, uhrzeit
from providers import PROVIDER_KLASSEN, PROVIDER_TITEL, ProviderFehler

PROV = "gemini"                       # einziger Anbieter
HINWEIS_KONTEN = ("Hinweis: Mehrere eigene Konten nur zum Vervielfachen der Gratis-Limits verstoßen meist gegen die "
                  "Nutzungsbedingungen von Google und können zur Sperre aller beteiligten Konten führen.")


def _zahl(n) -> str:
    if n is None:
        return "–"
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} Mio"
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return f"{n:.0f}"


def _sek(s) -> str:
    if s is None:
        return ""
    s = int(s)
    return f"{s // 3600} h {s % 3600 // 60} min" if s >= 3600 else f"{s // 60} min {s % 60} s" if s >= 60 else f"{s} s"


class KeyDialog(tk.Toplevel):
    """Hinzufügen/Bearbeiten eines Keys."""

    def __init__(self, master, store: KeyStore, provider: str, eintrag: dict | None = None, on_save=None):
        super().__init__(master)
        self.store, self.provider, self.eintrag, self.on_save = store, provider, eintrag, on_save
        self.title(("Key bearbeiten" if eintrag else "Key hinzufügen") + f" – {PROVIDER_TITEL[provider]}")
        self.transient(master)
        self.resizable(False, False)
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        env = eintrag is not None and eintrag.get("quelle") == "umgebung"

        ttk.Label(f, text="Name (z.B. „Privat“, „Konto Lisa“)").grid(row=0, column=0, columnspan=4, sticky="w")
        self.var_name = tk.StringVar(value=(eintrag or {}).get("label", f"Key {len(store.eintraege(provider)) + 1}"))
        ttk.Entry(f, textvariable=self.var_name, width=46).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 8))

        ttk.Label(f, text="API-Key" + ("  (aus Umgebungsvariable, hier nicht änderbar)" if env else "")).grid(
            row=2, column=0, columnspan=4, sticky="w")
        self.var_key = tk.StringVar(value=(eintrag or {}).get("key", ""))
        self.ent_key = ttk.Entry(f, textvariable=self.var_key, width=46, show="•",
                                 state="disabled" if env else "normal")
        self.ent_key.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.var_show = tk.BooleanVar()
        ttk.Checkbutton(f, text="zeigen", variable=self.var_show,
                        command=lambda: self.ent_key.configure(show="" if self.var_show.get() else "•")).grid(row=3, column=3)
        link = ttk.Label(f, text=f"→ Key bei {PROVIDER_TITEL[provider]} erstellen", foreground="#0b6bcb", cursor="hand2")
        link.grid(row=4, column=0, columnspan=4, sticky="w", pady=(2, 8))
        link.bind("<Button-1>", lambda e: webbrowser.open(PROVIDER_KLASSEN[provider].key_url))

        lf = ttk.LabelFrame(f, text="Limits dieses Keys (leer = automatisch)", padding=8)
        lf.grid(row=5, column=0, columnspan=4, sticky="ew")
        std = PROVIDER_KLASSEN[provider].standard_limits
        self.lim_vars = {}
        for i, (feld, text) in enumerate(LIMIT_FELDER):
            ttk.Label(lf, text=text).grid(row=i, column=0, sticky="w")
            v = tk.StringVar(value=str((eintrag or {}).get("limits", {}).get(feld) or ""))
            ttk.Entry(lf, textvariable=v, width=12).grid(row=i, column=1, padx=6, pady=1)
            hint = f"Annahme: {_zahl(std.get(feld))}" if std.get(feld) else "keine Annahme"
            ttk.Label(lf, text=hint, foreground="#777").grid(row=i, column=2, sticky="w")
            self.lim_vars[feld] = v
        quelle = "Die echten Werte stehen in AI Studio unter „Rate limits“."
        ttk.Label(lf, text=quelle, foreground="#777", wraplength=360).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self.lbl_test = ttk.Label(f, text="", wraplength=380)
        self.lbl_test.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
        bf = ttk.Frame(f)
        bf.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(bf, text="Testen", command=self.testen).pack(side="left")
        ttk.Button(bf, text="Abbrechen", command=self.destroy).pack(side="right")
        ttk.Button(bf, text="Speichern", command=self.speichern).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self.speichern())
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(50, self.grab_set)

    def _limits(self) -> dict:
        out = {}
        for f, v in self.lim_vars.items():
            s = v.get().strip().replace(".", "").replace("k", "000").replace(" ", "")
            if s:
                if not s.isdigit():
                    raise ValueError(f"Limit „{f}“ muss eine Zahl sein.")
                out[f] = int(s)
        return out

    def speichern(self):
        key, name = self.var_key.get().strip(), self.var_name.get().strip() or "Key"
        try:
            limits = self._limits()
            if not key:
                raise ValueError("Bitte einen API-Key eintragen.")
            if self.eintrag:
                self.store.update(self.eintrag["id"], label=name, key=key, limits=limits)
            else:
                self.store.add(self.provider, name, key, limits)
        except ValueError as e:
            messagebox.showerror("API-Key", str(e), parent=self)
            return
        if self.on_save:
            self.on_save()
        self.destroy()

    def testen(self):
        key = self.var_key.get().strip()
        if not key:
            return
        self.lbl_test.configure(text="Teste …", foreground="#444")
        modell = self.store.optionen["modelle"].get(self.provider, "")

        def work():
            try:
                r = PROVIDER_KLASSEN[self.provider]().testen(key, modell)
                txt, col = "✔ Key funktioniert – " + r["text"], "#1b7a2f"
                if r.get("info"):
                    i = r["info"]
                    txt += f"\nLimits laut Server: {_zahl(i.get('rpd'))} Anfragen/Tag (noch {_zahl(i.get('rest_anfragen'))}), " \
                           f"{_zahl(i.get('tpm'))} Token/Minute"
                    if self.eintrag:
                        with self.store.lock:
                            u = self.store.nutzung(self.eintrag["id"])
                            u["server"] = {**u.get("server", {}), **i}
                            self.store.save()
            except ProviderFehler as e:
                txt, col = f"✖ {e.meldung}", "#b00020"
            except Exception as e:
                txt, col = f"✖ {type(e).__name__}: {e}", "#b00020"
            self.after(0, lambda: self.winfo_exists() and self.lbl_test.configure(text=txt, foreground=col))
        threading.Thread(target=work, daemon=True).start()


class KeyManager(tk.Toplevel):
    """Übersicht aller Keys mit Limits und Verbrauch (aktualisiert sich jede Sekunde)."""

    def __init__(self, master, store: KeyStore, on_change=None):
        super().__init__(master)
        self.store, self.on_change = store, on_change or (lambda: None)
        self.title("API-Keys & Limits")
        self.geometry("1180x640")
        self.minsize(940, 520)
        self.transient(master)
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        unten = ttk.Frame(main)
        unten.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(unten, text="Schließen", command=self.close).pack(side="right")
        ttk.Label(unten, text=HINWEIS_KONTEN, foreground="#8a6d00", wraplength=900, justify="left").pack(side="left")
        ttk.Label(main, text="API-Keys & Limits", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        ttk.Label(main, text="Google Gemini – mehrere Keys möglich. Der Agent verteilt die Anfragen automatisch auf die "
                             "Keys und wechselt bei erreichtem Limit zum nächsten Key.",
                  foreground="#666").pack(anchor="w", pady=(0, 8))
        kl = PROVIDER_KLASSEN[PROV]
        self.trees, self.summary = {}, {}

        # --- Modellwahl
        mf = ttk.LabelFrame(main, text="KI-Modell (Google Gemini)", padding=8)
        mf.pack(fill="x")
        ttk.Label(mf, text="Modell").grid(row=0, column=0, sticky="w")
        self.var_modell = tk.StringVar(value=store.optionen["modelle"].get(PROV, kl.standard_modell))
        self.cb_modell = ttk.Combobox(mf, textvariable=self.var_modell, width=30, state="readonly",
                                      values=[self.var_modell.get()])
        self.cb_modell.grid(row=0, column=1, padx=(6, 16), sticky="w")
        ttk.Label(mf, text="Ausweichmodell").grid(row=0, column=2, sticky="w")
        self.var_ausweich = tk.StringVar(value=store.optionen.get("ausweich", {}).get(PROV, kl.ausweich_modell))
        self.cb_ausweich = ttk.Combobox(mf, textvariable=self.var_ausweich, width=30, state="readonly",
                                        values=[self.var_ausweich.get()])
        self.cb_ausweich.grid(row=0, column=3, padx=(6, 16), sticky="w")
        for cb in (self.cb_modell, self.cb_ausweich):
            cb.bind("<<ComboboxSelected>>", lambda e: self._optionen_speichern())
        ttk.Button(mf, text="Modellliste aktualisieren", command=self._modelle_laden).grid(row=0, column=4, sticky="w")
        self.lbl_modelle = ttk.Label(mf, text="", foreground="#666", wraplength=1050, justify="left")
        self.lbl_modelle.grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(mf, text="Das Ausweichmodell wird nur verwendet, wenn das gewählte Modell überlastet ist, nicht "
                           "verfügbar ist oder sein Tageskontingent aufgebraucht hat. Andere Modelle werden nie "
                           "automatisch verwendet.", foreground="#777", wraplength=1050, justify="left").grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(2, 0))

        # --- Strategie
        top = ttk.LabelFrame(main, text="Mehrere Keys", padding=8)
        top.pack(fill="x", pady=(8, 0))
        ttk.Label(top, text="Keys nutzen").grid(row=0, column=0, sticky="w")
        self.var_vert = tk.StringVar(value=store.optionen.get("verteilung", "gleichmaessig"))
        ttk.Radiobutton(top, text="gleichmäßig verteilen", value="gleichmaessig", variable=self.var_vert,
                        command=self._optionen_speichern).grid(row=0, column=1, padx=6)
        ttk.Radiobutton(top, text="nacheinander (erst Key 1 aufbrauchen)", value="nacheinander",
                        variable=self.var_vert, command=self._optionen_speichern).grid(row=0, column=2)

        # --- Keys
        kf = ttk.LabelFrame(main, text="Keys", padding=8)
        kf.pack(fill="both", expand=True, pady=(8, 0))
        self._keys_bereich(kf)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self._tick()
        if any(e.get("aktiv", True) for e in store.eintraege(PROV)):
            self.after(200, lambda: self._modelle_laden(still=True))
        else:
            self.lbl_modelle.configure(text="Erst einen Key hinzufügen – danach werden die für deinen Key "
                                            "verfügbaren Modelle hier zur Auswahl angezeigt.")

    # ---------------------------------------------------------------- Aufbau
    def _keys_bereich(self, tab):
        prov = PROV
        kl = PROVIDER_KLASSEN[prov]
        row = ttk.Frame(tab)
        row.pack(fill="x")
        for text, url in (("Key erstellen ↗", kl.key_url), ("Limits online ↗", kl.limits_url),
                          ("Guthaben in AI Studio ↗", "https://ai.studio/projects")):
            l = ttk.Label(row, text=text, foreground="#0b6bcb", cursor="hand2")
            l.pack(side="right", padx=6)
            l.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        cols = ("key", "status", "anfragen", "token", "minute", "gesamt")
        tree = ttk.Treeview(tab, columns=cols, show="tree headings", height=6, selectmode="browse")
        tree.heading("#0", text="Name")
        tree.column("#0", width=150)
        for c, t, w in (("key", "Key", 100), ("status", "Status", 300), ("anfragen", "Anfragen heute", 120),
                        ("token", "Token heute", 120), ("minute", "Pro Minute (Anfr. · Token)", 170),
                        ("gesamt", "Gesamt", 90)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("aus", foreground="#999")
        tree.tag_configure("problem", foreground="#b00020")
        tree.tag_configure("limit", foreground="#a0522d")
        tree.pack(fill="both", expand=True, pady=6)
        tree.bind("<Double-1>", lambda e: self._bearbeiten(prov))
        self.trees[prov] = tree

        bf = ttk.Frame(tab)
        bf.pack(fill="x")
        for text, cmd in (("＋ Hinzufügen", lambda: self._hinzufuegen(prov)), ("Bearbeiten", lambda: self._bearbeiten(prov)),
                          ("Entfernen", lambda: self._entfernen(prov)), ("Ein/Aus", lambda: self._umschalten(prov)),
                          ("▲", lambda: self._schieben(prov, -1)), ("▼", lambda: self._schieben(prov, 1)),
                          ("Testen", lambda: self._testen(prov, alle=False)), ("Alle testen", lambda: self._testen(prov, alle=True)),
                          ("Zähler zurücks.", lambda: self._reset(prov))):
            ttk.Button(bf, text=text, command=cmd).pack(side="left", padx=(0, 4))
        self.summary[prov] = ttk.Label(tab, text="", foreground="#444")
        self.summary[prov].pack(anchor="w", pady=(6, 0))
        ttk.Label(tab, text="* = Annahme (Google veröffentlicht die Limits nicht fest; echte Werte in AI Studio → "
                            "„Rate limits“, dann beim Key eintragen). Der Tageszähler wird um Mitternacht pazifischer "
                            "Zeit (9:00 Uhr bei uns) zurückgesetzt.",
                  foreground="#777", wraplength=1050, justify="left").pack(anchor="w")

    # ---------------------------------------------------------------- Anzeige
    def _zeile(self, e: dict) -> tuple:
        s = self.store
        u, lim = s.nutzung(e["id"]), s.limits(e)

        def lim_txt(f):
            v, q = lim[f]
            return (_zahl(v) + ("*" if q == "Annahme" else "")) if v else "?"

        def von(used, f):
            return f"{_zahl(used)} / {lim_txt(f)}" if lim[f][0] else _zahl(used)
        status = s.status_text(e)
        gesperrt = [m for m, t in u.get("modell_gesperrt", {}).items() if t > time.time()]
        if gesperrt:
            status += " – aufgebraucht: " + ", ".join(gesperrt)
        elif u.get("fehler") and u.get("status") not in ("ok", "") and status != "bereit":
            status += f" – {u['fehler']}"
        return (maskiert(e["key"]), status,
                von(u.get("anfragen", 0), "rpd"),
                von(u.get("token", 0), "tpd"),
                f"{lim_txt('rpm')} · {lim_txt('tpm')}",
                f"{u.get('gesamt_anfragen', 0)} Anfr.")

    def refresh(self):
        for prov, tree in self.trees.items():
            sel = tree.selection()
            ids = []
            for e in self.store.eintraege(prov):
                ids.append(e["id"])
                vals = self._zeile(e)
                st = vals[1]
                tag = ("aus",) if st == "deaktiviert" else \
                      ("problem",) if st.startswith(("ungültig", "Region/Abrechnung", "Guthaben leer")) else \
                      ("limit",) if st.startswith(("Tageslimit", "Pause")) or "aufgebraucht" in st else ()
                label = e["label"] + ("  (Umgebung)" if e.get("quelle") == "umgebung" else "")
                if tree.exists(e["id"]):
                    tree.item(e["id"], text=label, values=vals, tags=tag)
                else:
                    tree.insert("", "end", iid=e["id"], text=label, values=vals, tags=tag)
            for iid in tree.get_children():
                if iid not in ids:
                    tree.delete(iid)
            for i, iid in enumerate(ids):
                tree.move(iid, "", i)
            if sel and tree.exists(sel[0]):
                tree.selection_set(sel)
            alle = self.store.eintraege(prov)
            aktiv = [e for e in alle if e.get("aktiv", True)]
            heute = sum(self.store.nutzung(e["id"]).get("anfragen", 0) for e in alle)
            rpd = [self.store.limits(e)["rpd"][0] for e in aktiv]
            kap = sum(r for r in rpd if r) if rpd and all(rpd) else None
            pausen = self.store.pausierte_modelle(prov)
            self.summary[prov].configure(
                text=f"{len(aktiv)} von {len(alle)} Keys aktiv · heute {heute} Anfragen"
                     + (f" von ca. {_zahl(kap)} möglichen" if kap else "")
                     + ("   ·   wegen Überlastung pausiert: " + ", ".join(
                         f"{m} (bis {uhrzeit(t)})" for m, t in pausen) if pausen else ""))
        self.on_change()

    def _tick(self):
        if self.winfo_exists():
            self.refresh()
            self.after(1000, self._tick)

    # ---------------------------------------------------------------- Aktionen
    def _sel(self, prov) -> dict | None:
        sel = self.trees[prov].selection()
        if not sel:
            messagebox.showinfo("API-Keys", "Bitte zuerst einen Key in der Liste auswählen.", parent=self)
            return None
        return self.store.get(sel[0])

    def _hinzufuegen(self, prov):
        KeyDialog(self, self.store, prov, None, on_save=self.refresh)

    def _bearbeiten(self, prov):
        e = self._sel(prov)
        if e:
            KeyDialog(self, self.store, prov, e, on_save=self.refresh)

    def _entfernen(self, prov):
        e = self._sel(prov)
        if not e:
            return
        if e.get("quelle") == "umgebung":
            messagebox.showinfo("API-Keys", "Dieser Key kommt aus einer Umgebungsvariable und kann hier nur "
                                "deaktiviert werden („Ein/Aus“).", parent=self)
            return
        if messagebox.askyesno("API-Keys", f"Key „{e['label']}“ ({maskiert(e['key'])}) wirklich entfernen?", parent=self):
            self.store.remove(e["id"])
            self.refresh()

    def _umschalten(self, prov):
        e = self._sel(prov)
        if e:
            self.store.update(e["id"], aktiv=not e.get("aktiv", True))
            self.refresh()

    def _schieben(self, prov, r):
        e = self._sel(prov)
        if e:
            self.store.verschieben(e["id"], r)
            self.refresh()

    def _reset(self, prov):
        e = self._sel(prov)
        if e and messagebox.askyesno("API-Keys", f"Zähler und Sperren von „{e['label']}“ zurücksetzen?\n"
                                     "(Die echten Limits beim Anbieter ändern sich dadurch nicht.)", parent=self):
            self.store.zuruecksetzen(e["id"])
            self.refresh()

    def _testen(self, prov, alle: bool):
        eintraege = self.store.eintraege(prov) if alle else [e for e in [self._sel(prov)] if e]
        if not eintraege:
            return
        modell = self.store.optionen["modelle"].get(prov, "")

        def work():
            ergebnisse = []
            for e in eintraege:
                try:
                    r = PROVIDER_KLASSEN[prov]().testen(e["key"], modell)
                    with self.store.lock:
                        u = self.store.nutzung(e["id"])
                        if r.get("info"):
                            u["server"] = {**u.get("server", {}), **r["info"]}
                        if u.get("status") in ("ungueltig", "region"):
                            u["status"], u["fehler"] = "", ""
                        u.pop("guthaben_leer", None)
                        self.store.save()
                    ergebnisse.append(f"✔ {e['label']}: {r['text']}")
                except ProviderFehler as f:
                    if f.art in ("key", "region"):
                        self.store.fehler(e["id"], f)
                    ergebnisse.append(f"✖ {e['label']}: {f.meldung}")
                except Exception as ex:
                    ergebnisse.append(f"✖ {e['label']}: {type(ex).__name__}: {ex}")
            self.after(0, lambda: self.winfo_exists() and messagebox.showinfo(
                "Key-Test", "\n".join(ergebnisse), parent=self))
        threading.Thread(target=work, daemon=True).start()

    def _modelle_laden(self, still: bool = False):
        keys = [e for e in self.store.eintraege(PROV) if e.get("aktiv", True)]
        if not keys:
            if not still:
                messagebox.showinfo("Modelle", "Bitte zuerst einen Key hinzufügen.", parent=self)
            return
        self.lbl_modelle.configure(text="Lade die für deinen Key verfügbaren Modelle …", foreground="#666")

        def work():
            try:
                namen = PROVIDER_KLASSEN[PROV]().modelle(keys[0]["key"])
                self.after(0, lambda: self.winfo_exists() and self._modelle_anzeigen(namen))
            except ProviderFehler as f:
                self.after(0, lambda: self.winfo_exists() and self.lbl_modelle.configure(
                    text=f"Modellliste nicht abrufbar: {f.meldung}", foreground="#b00020"))
        threading.Thread(target=work, daemon=True).start()

    def _modelle_anzeigen(self, namen: list[str]):
        self.cb_modell.configure(values=namen)
        self.cb_ausweich.configure(values=["(kein Ausweichmodell)"] + namen)
        warn = [f"„{v.get()}“" for v in (self.var_modell, self.var_ausweich)
                if v.get() and v.get() not in namen and v.get() != "(kein Ausweichmodell)"]
        if warn:
            self.lbl_modelle.configure(text=f"⚠ {' und '.join(warn)} ist für deinen Key nicht verfügbar – bitte "
                                            f"ein Modell aus der Liste wählen ({len(namen)} verfügbar).",
                                       foreground="#b00020")
        else:
            self.lbl_modelle.configure(text=f"✔ {len(namen)} Modelle für deinen Key verfügbar. Empfehlung: "
                                            "gemini-3.5-flash (gut & günstig), Ausweich: gemini-3.6-flash.",
                                       foreground="#1b7a2f")

    def _optionen_speichern(self):
        with self.store.lock:
            self.store.optionen["verteilung"] = self.var_vert.get()
            self.store.optionen["modelle"] = {PROV: self.var_modell.get().strip() or PROVIDER_KLASSEN[PROV].standard_modell}
            aw = self.var_ausweich.get().strip()
            self.store.optionen["ausweich"] = {PROV: "" if aw == "(kein Ausweichmodell)" else aw}
            if self.lbl_modelle.cget("foreground") == "#b00020" and self.cb_modell.cget("values"):
                self._modelle_anzeigen(list(self.cb_modell.cget("values")))
            self.store.save()
        self.on_change()

    def close(self):
        self._optionen_speichern()
        self.destroy()
