"""Reiter „KI-Anbieter & Keys“ im Einstellungsfenster: Anbieterwahl, Modell + Ausweichmodell, mehrere Keys je
Anbieter mit Limits und Verbrauch (live)."""

from __future__ import annotations

import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

import theme
from theme import P

from keys import KeyStore, LIMIT_FELDER, maskiert, uhrzeit
from providers import PROVIDER_KLASSEN, PROVIDER_TITEL, STANDARD_ANBIETER, ProviderFehler

KEIN_AUSWEICH = "(kein Ausweichmodell)"
HINWEIS_KONTEN = ("Hinweis: Mehrere eigene Konten nur zum Vervielfachen der Gratis-Limits verstoßen meist gegen die "
                  "Nutzungsbedingungen der Anbieter und können zur Sperre aller beteiligten Konten führen.")


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
        link = ttk.Label(f, text=f"→ Key bei {PROVIDER_TITEL[provider]} erstellen", foreground=P["accent"], cursor="hand2")
        link.grid(row=4, column=0, columnspan=4, sticky="w", pady=(2, 8))
        link.bind("<Button-1>", lambda e: webbrowser.open(PROVIDER_KLASSEN[provider].key_url))
        if not env and not eintrag:
            self.after(100, lambda: self.ent_key.focus_set())

        lf = ttk.LabelFrame(f, text="Limits dieses Keys (leer = automatisch)", padding=8)
        lf.grid(row=5, column=0, columnspan=4, sticky="ew")
        std = PROVIDER_KLASSEN[provider].standard_limits
        self.lim_vars = {}
        for i, (feld, text) in enumerate(LIMIT_FELDER):
            ttk.Label(lf, text=text).grid(row=i, column=0, sticky="w")
            v = tk.StringVar(value=str((eintrag or {}).get("limits", {}).get(feld) or ""))
            ttk.Entry(lf, textvariable=v, width=12).grid(row=i, column=1, padx=6, pady=1)
            hint = f"Annahme: {_zahl(std.get(feld))}" if std.get(feld) else "keine Annahme"
            ttk.Label(lf, text=hint, foreground=P["muted"]).grid(row=i, column=2, sticky="w")
            self.lim_vars[feld] = v
        quelle = ("Die echten Werte stehen in AI Studio unter „Rate limits“." if provider == "gemini" else
                  "Die echten Werte stehen in der Konsole des Anbieters (meist nur im Gratis-Tarif nötig).")
        ttk.Label(lf, text=quelle, foreground=P["muted"], wraplength=360).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self.lbl_test = ttk.Label(f, text="", wraplength=380)
        self.lbl_test.grid(row=6, column=0, columnspan=4, sticky="w", pady=(8, 0))
        if not eintrag and store.eintraege(provider):
            ttk.Label(f, text=HINWEIS_KONTEN, foreground=P["warn"], wraplength=380, justify="left").grid(
                row=8, column=0, columnspan=4, sticky="w", pady=(10, 0))
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
        self.lbl_test.configure(text="Teste …", foreground=P["muted"])
        modell = self.store.optionen["modelle"].get(self.provider, "")

        def work():
            try:
                r = PROVIDER_KLASSEN[self.provider]().testen(key, modell)
                txt, col = "✔ Key funktioniert – " + r["text"], P["ok"]
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
                txt, col = f"✖ {e.meldung}", P["danger"]
            except Exception as e:
                txt, col = f"✖ {type(e).__name__}: {e}", P["danger"]
            self.after(0, lambda: self.winfo_exists() and self.lbl_test.configure(text=txt, foreground=col))
        threading.Thread(target=work, daemon=True).start()




class KIBereich(ttk.Frame):
    """Anbieter, Modell + Ausweichmodell und alle Keys des Anbieters mit Limits und Verbrauch
    (aktualisiert sich jede Sekunde)."""

    def __init__(self, master, store: KeyStore, on_change=None):
        super().__init__(master, padding=12)
        self.store, self.on_change = store, on_change or (lambda: None)
        self.prov = store.optionen.get("anbieter") or STANDARD_ANBIETER
        self._titel_zu_name = {t: n for n, t in PROVIDER_TITEL.items()}
        self._lade_nr = 0

        # --- Anbieter
        af = ttk.LabelFrame(self, text="KI-Anbieter", padding=8)
        af.pack(fill="x")
        ttk.Label(af, text="Anbieter").grid(row=0, column=0, sticky="w")
        self.var_prov = tk.StringVar(value=PROVIDER_TITEL[self.prov])
        self.cb_prov = ttk.Combobox(af, textvariable=self.var_prov, width=36, state="readonly",
                                    values=list(PROVIDER_TITEL.values()), height=12)
        self.cb_prov.grid(row=0, column=1, padx=(6, 16), sticky="w")
        self.cb_prov.bind("<<ComboboxSelected>>", lambda e: self._anbieter_wechseln())
        self.lbl_prov_keys = ttk.Label(af, text="", foreground=P["muted"])
        self.lbl_prov_keys.grid(row=0, column=2, sticky="w")
        af.columnconfigure(2, weight=1)
        self.lbl_hinweis = ttk.Label(af, text="", foreground=P["muted"], wraplength=980, justify="left")
        self.lbl_hinweis.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.frm_url = ttk.Frame(af)
        ttk.Label(self.frm_url, text="Adresse (Basis-URL)").pack(side="left")
        self.var_url = tk.StringVar(value=store.optionen.get("eigene_url", ""))
        ent = ttk.Entry(self.frm_url, textvariable=self.var_url, width=56)
        ent.pack(side="left", padx=6)
        ent.bind("<FocusOut>", lambda e: self._optionen_speichern())
        ent.bind("<Return>", lambda e: (self._optionen_speichern(), self._modelle_laden(still=True)))
        ttk.Label(self.frm_url, text="z.B. https://api.fireworks.ai/inference/v1", foreground=P["muted"]).pack(
            side="left")

        # --- Modellwahl
        self.mf = ttk.LabelFrame(self, text="KI-Modell", padding=8)
        self.mf.pack(fill="x", pady=(8, 0))
        mf = self.mf
        ttk.Label(mf, text="Modell").grid(row=0, column=0, sticky="w")
        self.var_modell = tk.StringVar()
        self.cb_modell = ttk.Combobox(mf, textvariable=self.var_modell, width=28, height=16)
        self.cb_modell.grid(row=0, column=1, padx=(6, 16), sticky="w")
        ttk.Label(mf, text="Ausweichmodell").grid(row=0, column=2, sticky="w")
        self.var_ausweich = tk.StringVar()
        self.cb_ausweich = ttk.Combobox(mf, textvariable=self.var_ausweich, width=28, height=16)
        self.cb_ausweich.grid(row=0, column=3, padx=(6, 16), sticky="w")
        for cb in (self.cb_modell, self.cb_ausweich):
            cb.bind("<<ComboboxSelected>>", lambda e: self._optionen_speichern())
            cb.bind("<FocusOut>", lambda e: self._optionen_speichern())
            cb.bind("<Return>", lambda e: self._optionen_speichern())
        ttk.Button(mf, text="Modellliste aktualisieren", command=self._modelle_laden).grid(row=0, column=4, sticky="w")
        self.lbl_modelle = ttk.Label(mf, text="", foreground=P["muted"], wraplength=980, justify="left")
        self.lbl_modelle.grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(mf, text="Das Ausweichmodell springt nur ein, wenn das gewählte Modell überlastet, nicht verfügbar "
                           "oder aufgebraucht ist – andere Modelle werden nie automatisch verwendet.",
                  foreground=P["muted"], wraplength=980, justify="left").grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(2, 0))

        # --- Keys
        self.kf = ttk.LabelFrame(self, text="Keys", padding=8)
        self.kf.pack(fill="both", expand=True, pady=(8, 0))
        self._keys_bereich(self.kf)

        self._anbieter_anzeigen()
        self._tick()

    # ---------------------------------------------------------------- Aufbau
    def _keys_bereich(self, tab):
        row = ttk.Frame(tab)
        row.pack(fill="x")
        self.links = []
        for text in ("Key erstellen ↗", "Limits & Guthaben online ↗"):
            l = ttk.Label(row, text=text, foreground=P["accent"], cursor="hand2")
            l.pack(side="left", padx=(0, 14))
            l.url = ""
            l.bind("<Button-1>", lambda e, w=l: w.url and webbrowser.open(w.url))
            self.links.append(l)
        # Strategie bei mehreren Keys
        self.var_vert = tk.StringVar(value=self.store.optionen.get("verteilung", "gleichmaessig"))
        ttk.Radiobutton(row, text="nacheinander (erst Key 1 aufbrauchen)", value="nacheinander",
                        variable=self.var_vert, command=self._optionen_speichern).pack(side="right")
        ttk.Radiobutton(row, text="gleichmäßig verteilen", value="gleichmaessig", variable=self.var_vert,
                        command=self._optionen_speichern).pack(side="right", padx=8)
        ttk.Label(row, text="Mehrere Keys:").pack(side="right")

        cols = ("key", "status", "anfragen", "token", "minute", "gesamt")
        tree = ttk.Treeview(tab, columns=cols, show="tree headings", height=3, selectmode="browse")
        tree.heading("#0", text="Name")
        tree.column("#0", width=150)
        for c, t, w in (("key", "Key", 100), ("status", "Status", 250), ("anfragen", "Anfragen heute", 110),
                        ("token", "Token heute", 100), ("minute", "Pro Minute (Anfr. · Token)", 170),
                        ("gesamt", "Gesamt", 80)):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("aus", foreground=P["zeile_aus"])
        tree.tag_configure("problem", foreground=P["danger"])
        tree.tag_configure("limit", foreground=P["warn"])
        tree.pack(fill="both", expand=True, pady=6)
        tree.column("#0", stretch=False)
        tree.bind("<Double-1>", lambda e: self._bearbeiten())
        self.tree = tree

        bf = ttk.Frame(tab)
        bf.pack(fill="x")
        for text, cmd in (("＋ Hinzufügen", self._hinzufuegen), ("Bearbeiten", self._bearbeiten),
                          ("Entfernen", self._entfernen), ("Ein/Aus", self._umschalten),
                          ("▲", lambda: self._schieben(-1)), ("▼", lambda: self._schieben(1)),
                          ("Testen", lambda: self._testen(alle=False)), ("Alle testen", lambda: self._testen(alle=True)),
                          ("Zähler zurücks.", self._reset)):
            ttk.Button(bf, text=text, command=cmd).pack(side="left", padx=(0, 4))
        self.summary = ttk.Label(tab, text="", foreground=P["muted"])
        self.summary.pack(anchor="w", pady=(6, 0))
        ttk.Label(tab, text="* = Annahme – echte Limits stehen in der Konsole des Anbieters und können beim Key "
                            "eingetragen werden.",
                  foreground=P["muted"], wraplength=980, justify="left").pack(anchor="w")

    # ---------------------------------------------------------------- Anbieter
    def _anbieter_wechseln(self):
        name = self._titel_zu_name.get(self.var_prov.get(), STANDARD_ANBIETER)
        if name == self.prov:
            return
        self._optionen_speichern()             # Modellwahl des bisherigen Anbieters sichern
        self.prov = name
        with self.store.lock:
            self.store.optionen["anbieter"] = name
            self.store.save()
        self._anbieter_anzeigen()
        self.on_change()

    def _anbieter_anzeigen(self):
        kl = PROVIDER_KLASSEN[self.prov]
        o = self.store.optionen
        self._lade_nr += 1                     # Antworten einer noch laufenden Modellabfrage verwerfen
        self.var_prov.set(PROVIDER_TITEL[self.prov])
        self.var_modell.set(o.get("modelle", {}).get(self.prov) or kl.standard_modell)
        aw = o.get("ausweich", {}).get(self.prov, kl.ausweich_modell)
        self.var_ausweich.set(aw or KEIN_AUSWEICH)
        self.cb_modell.configure(values=[self.var_modell.get()] if self.var_modell.get() else [])
        self.cb_ausweich.configure(values=[KEIN_AUSWEICH] + ([aw] if aw else []))
        self.mf.configure(text=f"KI-Modell ({kl.titel})")
        self.kf.configure(text=f"Keys für {kl.titel}")
        recherche = ("" if kl.kann_recherche else
                     "Ohne eigene Websuche – die Marktrecherche übernimmt ein anderer Anbieter, für den ein Key "
                     "eingetragen ist (Gemini, Claude, ChatGPT, Perplexity).")
        self.lbl_hinweis.configure(text=" ".join(x for x in (getattr(kl, "hinweis", ""), recherche) if x))
        if self.prov == "eigener":
            self.frm_url.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        else:
            self.frm_url.grid_remove()
        for lbl, url in zip(self.links, (kl.key_url, kl.limits_url)):
            lbl.url = url
            lbl.configure(foreground=P["accent"] if url else P["muted"])
        self.refresh()
        if any(e.get("aktiv", True) for e in self.store.eintraege(self.prov)):
            self.after(200, lambda: self._modelle_laden(still=True))
        else:
            self.lbl_modelle.configure(text="Erst einen Key hinzufügen – danach werden die für deinen Key "
                                            "verfügbaren Modelle hier zur Auswahl angezeigt.", foreground=P["muted"])

    # ---------------------------------------------------------------- Anzeige
    def _zeile(self, e: dict) -> tuple:
        s = self.store
        u, lim = s.nutzung(e["id"]), s.limits(e)

        def lim_txt(f):
            v, q = lim[f]
            return (_zahl(v) + ("*" if q == "Annahme" else "")) if v else "–"

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
        tree, prov = self.tree, self.prov
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
        self.summary.configure(
            text=f"{len(aktiv)} von {len(alle)} Keys aktiv · heute {heute} Anfragen"
                 + (f" von ca. {_zahl(kap)} möglichen" if kap else "")
                 + ("   ·   wegen Überlastung pausiert: " + ", ".join(
                     f"{m} (bis {uhrzeit(t)})" for m, t in pausen) if pausen else ""))
        mit_keys = sorted({PROVIDER_TITEL[e["provider"]] for e in self.store.eintraege() if e.get("aktiv", True)})
        self.lbl_prov_keys.configure(text=("Keys vorhanden für: " + ", ".join(mit_keys)) if mit_keys else
                                     "Noch keine Keys eingetragen.")
        self.on_change()

    def _tick(self):
        if self.winfo_exists():
            self.refresh()
            self.after(1000, self._tick)

    # ---------------------------------------------------------------- Aktionen
    def _sel(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("API-Keys", "Bitte zuerst einen Key in der Liste auswählen.", parent=self)
            return None
        return self.store.get(sel[0])

    def _nach_speichern(self):
        self.refresh()
        self._modelle_laden(still=True)

    def _hinzufuegen(self):
        self._optionen_speichern()
        KeyDialog(self.winfo_toplevel(), self.store, self.prov, None, on_save=self._nach_speichern)

    def _bearbeiten(self):
        e = self._sel()
        if e:
            KeyDialog(self.winfo_toplevel(), self.store, self.prov, e, on_save=self._nach_speichern)

    def _entfernen(self):
        e = self._sel()
        if not e:
            return
        if e.get("quelle") == "umgebung":
            messagebox.showinfo("API-Keys", "Dieser Key kommt aus einer Umgebungsvariable und kann hier nur "
                                "deaktiviert werden („Ein/Aus“).", parent=self)
            return
        if messagebox.askyesno("API-Keys", f"Key „{e['label']}“ ({maskiert(e['key'])}) wirklich entfernen?", parent=self):
            self.store.remove(e["id"])
            self.refresh()

    def _umschalten(self):
        e = self._sel()
        if e:
            self.store.update(e["id"], aktiv=not e.get("aktiv", True))
            self.refresh()

    def _schieben(self, r):
        e = self._sel()
        if e:
            self.store.verschieben(e["id"], r)
            self.refresh()

    def _reset(self):
        e = self._sel()
        if e and messagebox.askyesno("API-Keys", f"Zähler und Sperren von „{e['label']}“ zurücksetzen?\n"
                                     "(Die echten Limits beim Anbieter ändern sich dadurch nicht.)", parent=self):
            self.store.zuruecksetzen(e["id"])
            self.refresh()

    def _testen(self, alle: bool):
        prov = self.prov
        eintraege = self.store.eintraege(prov) if alle else [e for e in [self._sel()] if e]
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
        prov = self.prov
        keys = [e for e in self.store.eintraege(prov) if e.get("aktiv", True)]
        if not keys:
            if not still:
                messagebox.showinfo("Modelle", "Bitte zuerst einen Key hinzufügen.", parent=self)
            return
        self._lade_nr += 1
        nr = self._lade_nr
        self.lbl_modelle.configure(text="Lade die für deinen Key verfügbaren Modelle …", foreground=P["muted"])

        def fertig(f):
            if self.winfo_exists() and nr == self._lade_nr:
                f()

        def work():
            try:
                namen = PROVIDER_KLASSEN[prov]().modelle(keys[0]["key"])
                self.after(0, lambda: fertig(lambda: self._modelle_anzeigen(namen)))
            except ProviderFehler as f:
                text = f"Modellliste nicht abrufbar: {f.meldung}"
                self.after(0, lambda: fertig(lambda: self.lbl_modelle.configure(text=text, foreground=P["danger"])))
            except Exception as ex:
                text = f"Modellliste nicht abrufbar: {type(ex).__name__}: {ex}"
                self.after(0, lambda: fertig(lambda: self.lbl_modelle.configure(text=text, foreground=P["danger"])))
        threading.Thread(target=work, daemon=True).start()

    def _modelle_anzeigen(self, namen: list[str]):
        kl = PROVIDER_KLASSEN[self.prov]
        if not namen:
            self.lbl_modelle.configure(text="Der Anbieter hat keine Modelle gemeldet – Modellname bitte selbst "
                                            "eintragen.", foreground=P["warn"])
            return
        self.cb_modell.configure(values=namen)
        self.cb_ausweich.configure(values=[KEIN_AUSWEICH] + namen)
        angepasst = []
        if self.var_modell.get() not in namen:
            alt, neu = self.var_modell.get(), kl.bestes_modell(namen)
            self.var_modell.set(neu)
            angepasst.append(f"Modell „{alt or '–'}“ → „{neu}“")
        aw = self.var_ausweich.get()
        if aw != KEIN_AUSWEICH and aw not in namen:
            neu = kl.ausweich_modell if kl.ausweich_modell in namen and kl.ausweich_modell != self.var_modell.get() \
                else KEIN_AUSWEICH
            self.var_ausweich.set(neu)
            angepasst.append(f"Ausweichmodell „{aw}“ → „{neu}“")
        if angepasst:
            self._optionen_speichern()
            self.lbl_modelle.configure(text=f"⚠ Für deinen Key nicht verfügbar, automatisch angepasst: "
                                            f"{'; '.join(angepasst)}. ({len(namen)} Modelle verfügbar)",
                                       foreground=P["warn"])
        else:
            tipp = f" Empfehlung: {kl.standard_modell}" + (f", Ausweich: {kl.ausweich_modell}" if kl.ausweich_modell
                                                           else "") + "." if kl.standard_modell else ""
            self.lbl_modelle.configure(text=f"✔ {len(namen)} Modelle für deinen Key verfügbar.{tipp}",
                                       foreground=P["ok"])

    def _optionen_speichern(self):
        kl = PROVIDER_KLASSEN[self.prov]
        with self.store.lock:
            o = self.store.optionen
            o["verteilung"] = self.var_vert.get()
            o.setdefault("modelle", {})[self.prov] = self.var_modell.get().strip() or kl.standard_modell
            aw = self.var_ausweich.get().strip()
            o.setdefault("ausweich", {})[self.prov] = "" if aw == KEIN_AUSWEICH else aw
            url = self.var_url.get().strip()
            if url != o.get("eigene_url", ""):
                o["eigene_url"] = url
                import providers
                providers.EigenerProvider.basis_url = url
            self.store.save()
        self.on_change()

    def schliessen(self):
        self._optionen_speichern()
