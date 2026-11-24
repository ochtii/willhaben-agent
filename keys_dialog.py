"""Einstellungsfenster: API-Keys & Limits (mehrere Keys pro Anbieter, Verbrauch live)."""

from __future__ import annotations

import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

from keys import KeyStore, ANBIETER, LIMIT_FELDER, maskiert, uhrzeit
from providers import PROVIDER_KLASSEN, PROVIDER_TITEL, ProviderFehler

REIHENFOLGEN = {
    "Gemini, bei Limit → Groq": ["gemini", "groq"],
    "Groq, bei Limit → Gemini": ["groq", "gemini"],
    "Nur Gemini": ["gemini"],
    "Nur Groq": ["groq"],
}
HINWEIS_KONTEN = ("Hinweis: Mehrere eigene Konten nur zum Vervielfachen der Gratis-Limits verstoßen meist gegen die "
                  "Nutzungsbedingungen von Google/Groq und können zur Sperre aller beteiligten Konten führen.")


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
        quelle = ("Die echten Werte stehen in AI Studio unter „Rate limits“." if provider == "gemini" else
                  "Groq meldet Anfragen/Tag und Token/Minute bei jeder Anfrage selbst – meist leer lassen.")
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
        ttk.Label(main, text="Mehrere Keys pro Anbieter möglich. Der Agent verteilt die Anfragen automatisch und "
                             "wechselt bei erreichtem Limit zum nächsten Key bzw. Anbieter.",
                  foreground="#666").pack(anchor="w", pady=(0, 8))

        top = ttk.LabelFrame(main, text="Strategie", padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Anbieter-Reihenfolge").grid(row=0, column=0, sticky="w")
        cur = store.optionen.get("reihenfolge", ["gemini", "groq"])
        self.var_reihe = tk.StringVar(value=next((k for k, v in REIHENFOLGEN.items() if v == cur), list(REIHENFOLGEN)[0]))
        cb = ttk.Combobox(top, textvariable=self.var_reihe, values=list(REIHENFOLGEN), state="readonly", width=28)
        cb.grid(row=0, column=1, padx=8, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._optionen_speichern())
        ttk.Label(top, text="Keys nutzen").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.var_vert = tk.StringVar(value=store.optionen.get("verteilung", "gleichmaessig"))
        ttk.Radiobutton(top, text="gleichmäßig verteilen", value="gleichmaessig", variable=self.var_vert,
                        command=self._optionen_speichern).grid(row=0, column=3, padx=6)
        ttk.Radiobutton(top, text="nacheinander (erst Key 1 aufbrauchen)", value="nacheinander",
                        variable=self.var_vert, command=self._optionen_speichern).grid(row=0, column=4)

        self.nb = ttk.Notebook(main)
        self.nb.pack(fill="both", expand=True, pady=(10, 0))
        self.trees, self.modell_vars, self.modell_cbs, self.summary = {}, {}, {}, {}
        self.ausweich_vars, self.ausweich_cbs = {}, {}
        for prov in ANBIETER:
            self._tab(prov)

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self._tick()

    # ---------------------------------------------------------------- Aufbau
    def _tab(self, prov: str):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text=f"  {PROVIDER_TITEL[prov]}  ")
        kl = PROVIDER_KLASSEN[prov]
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text="Modell").pack(side="left")
        v = tk.StringVar(value=self.store.optionen["modelle"].get(prov, kl.standard_modell))
        cb = ttk.Combobox(row, textvariable=v, width=34,
                          values=[kl.standard_modell])
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._optionen_speichern())
        cb.bind("<FocusOut>", lambda e: self._optionen_speichern())
        self.modell_vars[prov], self.modell_cbs[prov] = v, cb
        ttk.Button(row, text="Modelle laden", command=lambda: self._modelle_laden(prov)).pack(side="left")
        ttk.Label(row, text="Ausweichmodell").pack(side="left", padx=(14, 0))
        av = tk.StringVar(value=self.store.optionen.get("ausweich", {}).get(prov, kl.ausweich_modell))
        acb = ttk.Combobox(row, textvariable=av, width=26, values=[kl.ausweich_modell])
        acb.pack(side="left", padx=6)
        acb.bind("<<ComboboxSelected>>", lambda e: self._optionen_speichern())
        acb.bind("<FocusOut>", lambda e: self._optionen_speichern())
        self.ausweich_vars[prov], self.ausweich_cbs[prov] = av, acb
        links = [("Key erstellen ↗", kl.key_url), ("Limits online ↗", kl.limits_url)]
        if prov == "gemini":
            links.append(("Guthaben in AI Studio ↗", "https://ai.studio/projects"))
        for text, url in links:
            l = ttk.Label(row, text=text, foreground="#0b6bcb", cursor="hand2")
            l.pack(side="right", padx=6)
            l.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        cols = ("key", "status", "anfragen", "token", "minute", "server", "gesamt")
        tree = ttk.Treeview(tab, columns=cols, show="tree headings", height=6, selectmode="browse")
        tree.heading("#0", text="Name")
        tree.column("#0", width=130)
        for c, t, w in (("key", "Key", 90), ("status", "Status", 135), ("anfragen", "Anfragen heute", 110),
                        ("token", "Token heute", 105), ("minute", "Pro Minute (Anfr. · Token)", 165),
                        ("server", "Live vom Server", 255), ("gesamt", "Gesamt", 75)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("aus", foreground="#999")
        tree.tag_configure("problem", foreground="#b00020")
        tree.tag_configure("limit", foreground="#a0522d")
        tree.tag_configure("aktiv", background="#e9f7ec")
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
        legende = ("* = Annahme (Google veröffentlicht die Free-Tier-Limits nicht fest; echte Werte in AI Studio → "
                   "„Rate limits“, dann beim Key eintragen). Tageszähler wird um Mitternacht pazifischer Zeit "
                   "(9:00 Uhr bei uns) zurückgesetzt." if prov == "gemini" else
                   "Groq meldet Anfragen/Tag und Token/Minute live bei jeder Antwort („Live vom Server“). "
                   "* = Annahme bis zur ersten Antwort. Free Tier: wenige tausend Token pro Minute → kleine Pakete.")
        ttk.Label(tab, text=legende, foreground="#777", wraplength=1000, justify="left").pack(anchor="w")

    # ---------------------------------------------------------------- Anzeige
    def _zeile(self, e: dict) -> tuple:
        s = self.store
        u, lim = s.nutzung(e["id"]), s.limits(e)

        def lim_txt(f):
            v, q = lim[f]
            return (_zahl(v) + ("*" if q == "Annahme" else "")) if v else "?"

        def von(used, f):
            return f"{_zahl(used)} / {lim_txt(f)}" if lim[f][0] else _zahl(used)
        srv = u.get("server", {})
        live = ""
        if srv:
            alter = time.time() - srv.get("zeit", 0)
            teile = []
            if "rest_anfragen" in srv:
                teile.append(f"noch {_zahl(srv['rest_anfragen'])}/{_zahl(srv.get('rpd'))} Anfr.")
            if "rest_token" in srv:
                teile.append(f"{_zahl(srv['rest_token'])}/{_zahl(srv.get('tpm'))} Tok/min")
            if teile:
                live = " · ".join(teile) + (f" (vor {_sek(alter)})" if alter > 5 else "")
        if not live and u.get("fehler") and u.get("status") not in ("ok", ""):
            live = u["fehler"]
        return (maskiert(e["key"]), s.status_text(e),
                von(u.get("anfragen", 0), "rpd"),
                von(u.get("token", 0), "tpd"),
                f"{lim_txt('rpm')} · {lim_txt('tpm')}",
                live,
                f"{u.get('gesamt_anfragen', 0)} Anfr.")

    def refresh(self):
        for prov, tree in self.trees.items():
            sel = tree.selection()
            ids = []
            for e in self.store.eintraege(prov):
                ids.append(e["id"])
                vals = self._zeile(e)
                st = vals[1]
                tag = ("aus",) if st == "deaktiviert" else ("problem",) if st in ("ungültig", "Region/Abrechnung") else \
                      ("limit",) if st.startswith(("Tageslimit", "Pause")) else ()
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

    def _modelle_laden(self, prov):
        keys = [e for e in self.store.eintraege(prov) if e.get("aktiv", True)]
        if not keys:
            messagebox.showinfo("Modelle", "Bitte zuerst einen Key hinzufügen.", parent=self)
            return
        kl = PROVIDER_KLASSEN[prov]

        def work():
            try:
                p = kl()
                namen = p.modelle(keys[0]["key"])
                vorschlag = p.bestes_modell(namen)
                werte = [kl.standard_modell] + namen
                msg = f"{len(namen)} Modelle geladen. Empfehlung: {vorschlag}"
                self.after(0, lambda: (self.modell_cbs[prov].configure(values=werte),
                                       self.ausweich_cbs[prov].configure(values=namen),
                                       messagebox.showinfo("Modelle", msg, parent=self)))
            except ProviderFehler as f:
                self.after(0, lambda: messagebox.showerror("Modelle", f.meldung, parent=self))
        threading.Thread(target=work, daemon=True).start()

    def _optionen_speichern(self):
        with self.store.lock:
            self.store.optionen["reihenfolge"] = REIHENFOLGEN[self.var_reihe.get()]
            self.store.optionen["verteilung"] = self.var_vert.get()
            self.store.optionen["modelle"] = {p: (v.get().strip() or PROVIDER_KLASSEN[p].standard_modell)
                                              for p, v in self.modell_vars.items()}
            self.store.optionen["ausweich"] = {p: v.get().strip() for p, v in self.ausweich_vars.items()}
            self.store.save()
        self.on_change()

    def close(self):
        self._optionen_speichern()
        self.destroy()
