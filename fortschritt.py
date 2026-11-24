"""Gesamtfortschritt eines Suchlaufs über alle Phasen – auch während langer KI-Anfragen.

Die Phasen melden Fortschritt nur in Schritten (z.B. „30 von 120 bewertet“ nach jedem KI-Paket). Eine einzelne
KI-Anfrage kann aber eine Minute dauern. Damit die Anzeige dabei nicht stehen bleibt, rückt der Wert zwischen zwei
Meldungen zeitabhängig langsam weiter – höchstens bis kurz vor den nächsten erwarteten Schritt, nie darüber.
"""

from __future__ import annotations

import math
import time

PHASEN = ["Suche", "Details", "KI-Bewertung", "Endvergleich"]
GEWICHTE = {"Suche": 0.10, "Details": 0.30, "KI-Bewertung": 0.45, "Endvergleich": 0.15}
KI_PHASEN = ("KI-Bewertung", "Endvergleich")
# erwartete Schrittweite, solange noch kein echter Schritt gemessen wurde
STANDARD_SCHRITT = {"Suche": 200, "KI-Bewertung": 30, "Endvergleich": 1, "Details": 4}


class Gesamtschaetzung:
    def __init__(self, ohne_details: bool = False, jetzt=time.monotonic):
        g = dict(GEWICHTE)
        if ohne_details:
            g["Details"] = 0.0
        summe = sum(g.values())
        self.gewicht = {k: v / summe for k, v in g.items()}
        self.jetzt = jetzt
        self.phase: str | None = None
        self.done = self.total = 0
        self.schritt = 0
        self.seit = jetzt()
        self.wert = 0.0
        self.fertig = False

    def melden(self, name: str, done: int, total: int):
        """Fortschrittsmeldung einer Phase übernehmen."""
        if name == "Fertig":
            self.fertig = True
            return
        if name not in self.gewicht:
            return
        if name != self.phase:
            self.phase, self.schritt = name, 0
            self.seit = self.jetzt()
        elif done != self.done or total != self.total:
            if done > self.done:
                self.schritt = done - self.done               # tatsächliche Paketgröße merken
            self.seit = self.jetzt()
        self.done, self.total = done, total

    def wartet(self) -> float:
        """Sekunden seit der letzten Meldung."""
        return self.jetzt() - self.seit

    def phasen_anteil(self) -> float:
        """Anteil der aktuellen Phase (0..1) inklusive zeitabhängigem Weiterrücken."""
        if self.phase is None:
            return 0.0
        if self.total:
            basis = min(1.0, self.done / self.total)
            schritt = self.schritt or STANDARD_SCHRITT.get(self.phase, 1)
            naechst = min(1.0, (self.done + schritt) / self.total)
        else:
            basis, naechst = 0.0, 0.5                         # Gesamtzahl noch unbekannt
        tau = 25.0 if self.phase in KI_PHASEN else 6.0        # KI antwortet langsamer
        kriechen = (naechst - basis) * 0.9 * (1 - math.exp(-self.wartet() / tau))
        return min(1.0, basis + kriechen)

    def gesamt(self) -> float:
        """Gesamtfortschritt 0..1; steigt nur, fällt nie zurück."""
        if self.fertig:
            self.wert = 1.0
            return 1.0
        if self.phase is None:
            return self.wert
        vorher = sum(self.gewicht[p] for p in PHASEN[:PHASEN.index(self.phase)])
        w = vorher + self.gewicht[self.phase] * self.phasen_anteil()
        self.wert = max(self.wert, min(w, 0.995))
        return self.wert
