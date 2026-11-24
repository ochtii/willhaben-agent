# Kostenlose API-Keys holen (Gemini und Groq)

Der Agent nutzt **Google Gemini** und als Ausweich-Anbieter **Groq**. Beide sind kostenlos nutzbar, beide Keys trägt man im Programm unter **Einstellungen → API-Keys & Limits** ein (Strg+K). Man kann pro Anbieter beliebig viele Keys eintragen.

---

# Teil 1: Gemini-Key (Google)

Dauer: ca. 3 Minuten. Du brauchst nur ein Google-Konto (z. B. dein Gmail-Konto).

## 1. Google AI Studio öffnen

Im Browser öffnen: **https://aistudio.google.com/apikey**

Im Agenten geht das auch direkt: Klick auf **„→ Key holen (kostenlos)“** im Feld „KI“.

## 2. Mit dem Google-Konto anmelden

- Oben rechts auf **„Anmelden“** bzw. **„Sign in“** klicken und dein Google-Konto wählen.
- Beim ersten Besuch erscheint ein Fenster mit den Nutzungsbedingungen:
  - das Häkchen bei den **Nutzungsbedingungen** (Gemini API Additional Terms) setzen,
  - die E-Mail-Häkchen kannst du leer lassen,
  - dann **„Akzeptieren“** bzw. **„Continue“** klicken.
- Nutzen kannst du AI Studio nur mit einem Konto ab 18 Jahren. Bei manchen Firmen- oder Schulkonten (Google Workspace) ist AI Studio gesperrt. Dann ein privates Gmail-Konto verwenden.

## 3. API-Key erstellen

- Auf der Seite **„API Keys“** (links im Menü bzw. unter **„Get API key“**) auf **„API-Schlüssel erstellen“** bzw. **„Create API key“** klicken.
- Wird nach einem **Projekt** gefragt:
  - Gibt es schon ein Projekt (z. B. „Default Gemini Project“), dieses auswählen.
  - Sonst **„Create project“** bzw. **„Projekt erstellen“** klicken. Der Name ist egal, z. B. `willhaben-agent`.
- Der Key wird angezeigt. Er beginnt mit **`AIza…`** oder bei neuen Keys mit **`AQ.…`**. Beides funktioniert.
- Auf **„Kopieren“** bzw. das Kopier-Symbol klicken.

> 🔒 Den Key wie ein Passwort behandeln: nicht posten, nicht weitergeben.
> Wenn er doch einmal irgendwo landet, auf derselben Seite löschen und einen neuen erstellen.

## 4. Key im Agenten eintragen

1. Den Willhaben KI-Agenten starten.
2. **Einstellungen → API-Keys & Limits** öffnen (oder Strg+K, oder links der Knopf „API-Keys & Limits verwalten …“).
3. Reiter **„Google Gemini“** → **„＋ Hinzufügen“**.
4. Einen Namen vergeben (z. B. „Privat“), den Key einfügen (Strg+V) und auf **„Testen“** klicken. Bei Erfolg auf **„Speichern“** klicken.
   Gespeichert wird der Key in `~/.config/willhaben-agent/keys.json`, nur für deinen Benutzer lesbar.
5. Voreingestellt ist `gemini-3.5-flash`, ein gutes und günstiges Modell. Ist es überlastet, weicht der Agent automatisch auf `gemini-3.6-flash` aus. Beides lässt sich im Key-Manager ändern.

Alternativ für die Terminal-Version eine Umgebungsvariable setzen (mehrere Keys kommagetrennt in `GEMINI_API_KEYS`):

```bash
export GEMINI_API_KEY="AIza...dein-key..."
```

## 5. Gratis-Kontingent: Was ist kostenlos?

- Ohne hinterlegte Zahlungsmethode läuft dein Projekt im **Free Tier**: **0 €**, aber mit Limits pro Minute und pro Tag.
- Deine aktuellen Limits zeigt AI Studio im Bereich **„Usage“ / „Rate limits“** (je nach Version unter dem Dashboard oder neben „API Keys“). Die Limits gelten pro Projekt, nicht pro Key.
- Der Agent bremst sich automatisch: Zwischen zwei KI-Anfragen wartet er standardmäßig etwa 6,5 Sekunden. Meldet Google „zu viele Anfragen“, wartet er und macht langsamer weiter.
- Pro Lauf braucht der Agent etwa (Anzahl Anzeigen ÷ 20) + 1 Anfragen:
  - 168 Anzeigen ≈ 10 Anfragen, ca. 1–2 Minuten KI-Zeit,
  - 1.400 Anzeigen ≈ 72 Anfragen, ca. 8–10 Minuten.
- Ist das **Tageslimit** erreicht, sagt der Agent das klar. Dann am nächsten Tag weitermachen (das Limit wird um ca. 9:00 Uhr österreichischer Zeit zurückgesetzt) oder mit „Max. Anzeigen für KI“ weniger bewerten.
- Im Free Tier darf Google die gesendeten Texte zur Verbesserung seiner Dienste verwenden. Der Agent schickt nur öffentliche Anzeigentexte. Telefonnummern und Adressen der Verkäufer werden **nicht** übertragen.

## Österreich / EU

**Getestet (Nov. 2026):** Mit einem Key aus Österreich funktionierte der Gratis-Zugang ohne hinterlegte Zahlungsmethode.

Google hat den Gratis-Zugang in der EU früher zeitweise eingeschränkt. Kommt beim Testen eine Fehlermeldung zu **Region, Abrechnung oder „billing“**:
1. In AI Studio bei deinem Projekt **„Set up billing“** wählen und eine Karte hinterlegen.
2. In der Google Cloud Console unter **Abrechnung → Budgets & Benachrichtigungen** ein Budget von z. B. **5 €** mit Warn-Mail setzen.
3. Flash-Modelle sind sehr günstig: Ein Lauf kostet grob wenige Cent. Das ist eine Schätzung, aktuelle Preise stehen unter https://ai.google.dev/pricing.

Oder einfach mit **Groq** weitermachen (siehe Teil 2).

---

# Teil 2: Groq-Key (Ausweich-Anbieter)

Groq ist ein zweiter kostenloser Anbieter. Er übernimmt automatisch, wenn Gemini überlastet oder aufgebraucht ist. Groq ist sehr schnell, hat im Free Tier aber kleine Limits pro Minute. Der Agent schickt ihm deshalb kleinere Pakete.

1. **https://console.groq.com/keys** öffnen (im Programm: Hilfe → „Groq-Key erstellen“).
2. **Anmelden:** mit Google-Konto, GitHub oder E-Mail. Keine Kreditkarte nötig.
3. Auf **„Create API Key“** klicken, einen Namen vergeben (z. B. `willhaben-agent`) und auf **„Submit“** klicken.
4. Den Key **sofort kopieren**. Er beginnt mit `gsk_…` und wird nur einmal angezeigt.
5. Im Agenten: **API-Keys & Limits → Reiter „Groq“ → „＋ Hinzufügen“** → einfügen, **„Testen“** klicken, **„Speichern“** klicken.
   Beim Testen fragt der Agent Groq nach den echten Limits. Die stehen dann in der Spalte **„Live vom Server“**: Anfragen pro Tag (Rest) und Token pro Minute.

Für die Terminal-Version: `export GROQ_API_KEY="gsk_..."`

---

# Der Key- und Limit-Manager

| Spalte | Bedeutung |
|---|---|
| **Status** | bereit · Pause (Minutenlimit, zählt herunter) · Tageslimit bis HH:MM · ungültig · deaktiviert |
| **Anfragen heute / Token heute** | eigener Zähler pro Key, mit Tageslimit dahinter (`*` = Annahme) |
| **Pro Minute** | Anfragen- und Token-Limit pro Minute, nach diesen Werten bremst der Agent |
| **Live vom Server** | bei Groq die echten Restwerte, die Groq mit jeder Antwort meldet |
| **Gesamt** | alle Anfragen seit dem Eintragen |

- **Anbieter-Reihenfolge:** z. B. „Gemini, bei Limit → Groq“.
- **Keys nutzen:**
  - **gleichmäßig:** reihum, der am wenigsten genutzte Key kommt zuerst dran,
  - **nacheinander:** Key 1 wird aufgebraucht, dann Key 2, … Die Reihenfolge stellst du mit ▲/▼ ein.
- Erreicht ein Key sein Minutenlimit, nimmt der Agent **sofort einen anderen freien Key**. Sonst wartet er kurz.
- Ist ein Key für heute aufgebraucht, wird er bis zum Reset übersprungen. Sind alle Keys eines Anbieters aufgebraucht, geht es beim nächsten Anbieter weiter.
- **Echte Gemini-Limits eintragen:** Google zeigt sie in AI Studio unter **„Rate limits“**. Über „Bearbeiten“ beim Key eintragen, dann rechnet der Agent damit statt mit Annahmen.

> ⚠ Keys von **verschiedenen eigenen Konten** nur zum Vervielfachen der Gratis-Limits verstoßen meist gegen die Nutzungsbedingungen von Google und Groq. Das kann zur **Sperre aller beteiligten Konten** führen. Unproblematisch sind z. B. ein eigener Key plus der Key einer anderen Person, die ihn dir gibt.

## Häufige Probleme

| Meldung im Agenten | Lösung |
|---|---|
| „API-Key ungültig oder ohne Berechtigung“ | Key vollständig kopiert? Keine Leerzeichen am Anfang oder Ende? Wurde er in AI Studio gelöscht? Notfalls neuen Key erstellen. |
| „Modell … nicht gefunden“ / „überlastet“ | Der Agent weicht automatisch auf das Ausweichmodell aus (Gemini: `gemini-3.6-flash`). In den Einstellungen über „Modelle laden“ ein anderes wählen. |
| „Kein Key mehr verfügbar“ | Alle Keys sind für heute aufgebraucht. Im Key-Manager steht, ab wann sie wieder gehen. Oder einen Groq-Key ergänzen. |
| „Minutenlimit erreicht – Pause …“ | Normal im Free Tier. Der Agent nimmt einen anderen Key oder wartet kurz. |
| „Tageslimit des Free Tiers erreicht“ | Morgen weitermachen, unter „Max. Anzeigen für KI“ weniger einstellen oder die Suche enger fassen (Bezirk, Suchbegriff, Preis). |
| „… aus deiner Region nicht nutzbar“ | Siehe oben „Wichtig für Österreich / EU“. |
