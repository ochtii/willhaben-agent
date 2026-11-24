# API-Key holen

Der Agent nutzt standardmäßig **Google Gemini** (kostenloser Einstieg, Anleitung unten). Alternativ gehen **OpenAI/ChatGPT,
Anthropic Claude, Perplexity, Mistral, DeepSeek, xAI Grok, Groq, OpenRouter, Together AI** oder eine eigene
OpenAI-kompatible Adresse (siehe „Andere KI-Anbieter“ weiter unten).

Den Key trägt man im Programm über das **Zahnrad rechts oben → „KI-Anbieter & Keys“** ein (auch: Hilfe → Einstellungen
oder Strg+K). Man kann beliebig viele Keys je Anbieter eintragen, der Agent verteilt die Anfragen dann automatisch.

---

# Gemini-Key erstellen

Dauer: ca. 3 Minuten. Du brauchst nur ein Google-Konto (z. B. dein Gmail-Konto).

## 1. Google AI Studio öffnen

Im Browser öffnen: **https://aistudio.google.com/apikey**

Im Agenten geht das auch direkt: Einstellungen (Zahnrad) → „KI-Anbieter & Keys“ → **„Anleitung: Google Gemini-Key holen …“** → „Seite öffnen ↗“.

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
2. Das **Zahnrad rechts oben** anklicken (oder Strg+K, Hilfe → Einstellungen, links der Knopf „KI-Anbieter & Keys …“).
3. Im Reiter **„KI-Anbieter & Keys“** ist **Google Gemini** schon gewählt. Im Bereich **„Keys für Google Gemini“** auf **„＋ Hinzufügen“** klicken.
4. Einen Namen vergeben (z. B. „Privat“), den Key einfügen (Strg+V) und auf **„Testen“** klicken. Bei Erfolg auf **„Speichern“** klicken.
   Gespeichert wird der Key in `~/.config/willhaben-agent/keys.json` (Windows: `%APPDATA%\willhaben-agent\keys.json`), nur für deinen Benutzer lesbar.
5. Oben unter **„KI-Modell“** stehen danach alle Modelle, die für deinen Key verfügbar sind. Wähle ein **Modell** und ein **Ausweichmodell**.
   - Voreingestellt sind `gemini-3.5-flash` (gut und günstig) und `gemini-3.6-flash`.
   - Das Ausweichmodell springt nur ein, wenn das gewählte Modell überlastet ist, nicht verfügbar ist oder sein Tageskontingent aufgebraucht hat. Andere Modelle verwendet der Agent nie von sich aus.

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

---

# Andere KI-Anbieter

Im Einstellungsfenster oben unter **„Anbieter“** wählen. Der Knopf daneben, **„Anleitung: …-Key holen“**, zeigt die
Schritte für genau diesen Anbieter und öffnet dessen Key-Seite. Danach wie oben Key hinzufügen. Die Modellliste lädt automatisch;
ist das voreingestellte Modell für deinen Key nicht verfügbar, wählt der Agent selbst ein passendes.

| Anbieter | Key erstellen | Umgebungsvariable | Hinweise |
|---|---|---|---|
| **Google Gemini** (Standard) | https://aistudio.google.com/apikey | `GEMINI_API_KEY` | Gratis-Tarif, Marktrecherche per Google-Suche |
| **OpenAI (ChatGPT)** | https://platform.openai.com/api-keys | `OPENAI_API_KEY` | nach Verbrauch (Guthaben aufladen), Websuche für die Marktrecherche |
| **Anthropic Claude** | https://console.anthropic.com/settings/keys | `ANTHROPIC_API_KEY` | nach Verbrauch, sehr gründlich, eigene Websuche |
| **Perplexity** | https://www.perplexity.ai/account/api/keys | `PERPLEXITY_API_KEY` | sucht bei jeder Anfrage im Web |
| **Mistral AI** | https://console.mistral.ai/api-keys | `MISTRAL_API_KEY` | europäischer Anbieter, Gratis-Testzugang |
| **DeepSeek** | https://platform.deepseek.com/api_keys | `DEEPSEEK_API_KEY` | sehr günstig, Server in China |
| **xAI Grok** | https://console.x.ai | `XAI_API_KEY` | nach Verbrauch |
| **Groq** | https://console.groq.com/keys | `GROQ_API_KEY` | Gratis-Tarif, kleine Limits (kleinere Pakete) |
| **OpenRouter** | https://openrouter.ai/settings/keys | `OPENROUTER_API_KEY` | ein Key für hunderte Modelle |
| **Together AI** | https://api.together.ai/settings/api-keys | `TOGETHER_API_KEY` | offene Modelle (Llama, Qwen, …) |
| **Eigener Anbieter** | – | – | Basis-URL einer OpenAI-kompatiblen Schnittstelle eintragen (z. B. Azure OpenAI, Fireworks, Cerebras) |

- **Marktrecherche:** Gemini, Claude, ChatGPT und Perplexity können selbst im Web suchen. Bei den anderen Anbietern
  übernimmt die Recherche automatisch ein Anbieter mit Websuche, für den ein Key eingetragen ist – sonst wird ohne sie
  bewertet.
- **Kosten:** Bei bezahlten Anbietern im Konto des Anbieters ein Ausgabenlimit setzen. Ein Suchlauf mit ~100 Anzeigen
  braucht etwa 5–10 Anfragen.
- Bei „Kein Guthaben“ springt der Agent nicht still auf einen anderen Anbieter um – erst nach dem Aufladen oder einem
  Wechsel in den Einstellungen geht es weiter.

---

# Der Key- und Limit-Manager

| Spalte | Bedeutung |
|---|---|
| **Status** | bereit · Pause (Minutenlimit, zählt herunter) · Tageslimit bis HH:MM · ungültig · Guthaben leer · deaktiviert, dazu welche Modelle für heute aufgebraucht sind |
| **Anfragen heute / Token heute** | eigener Zähler pro Key, mit Tageslimit dahinter (`*` = Annahme) |
| **Pro Minute** | Anfragen- und Token-Limit pro Minute, nach diesen Werten bremst der Agent |
| **Gesamt** | alle Anfragen seit dem Eintragen |

- **KI-Modell:** Modell und Ausweichmodell aus der Liste der für deinen Key verfügbaren Modelle. Die Liste lädt beim Öffnen automatisch.
- **Keys nutzen:**
  - **gleichmäßig:** reihum, der am wenigsten genutzte Key kommt zuerst dran,
  - **nacheinander:** Key 1 wird aufgebraucht, dann Key 2, … Die Reihenfolge stellst du mit ▲/▼ ein.
- Erreicht ein Key sein Minutenlimit, nimmt der Agent **sofort einen anderen freien Key**. Sonst wartet er kurz.
- Hat ein Key das Tageskontingent eines Modells aufgebraucht, nimmt er für den Rest des Tages das Ausweichmodell. Sind bei einem Key beide Modelle aufgebraucht, wird er bis zum Reset übersprungen und die anderen Keys übernehmen.
- **Echte Gemini-Limits eintragen:** Google zeigt sie in AI Studio unter **„Rate limits“**. Über „Bearbeiten“ beim Key eintragen, dann rechnet der Agent damit statt mit Annahmen.

> ⚠ Keys von **verschiedenen eigenen Konten** nur zum Vervielfachen der Gratis-Limits verstoßen meist gegen die Nutzungsbedingungen der Anbieter. Das kann zur **Sperre aller beteiligten Konten** führen. Unproblematisch sind z. B. ein eigener Key plus der Key einer anderen Person, die ihn dir gibt.

## Häufige Probleme

| Meldung im Agenten | Lösung |
|---|---|
| „API-Key ungültig oder ohne Berechtigung“ | Key vollständig kopiert? Keine Leerzeichen am Anfang oder Ende? Wurde er in AI Studio gelöscht? Notfalls neuen Key erstellen. |
| „Modell … nicht gefunden“ / „überlastet“ | Der Agent weicht automatisch auf das Ausweichmodell aus. Sind beide nicht verfügbar, in den Einstellungen unter „KI-Modell“ andere Modelle aus der Liste wählen. |
| „Kein Guthaben/Kontingent mehr“ | Beim Anbieter Guthaben aufladen bzw. Abrechnung prüfen – oder in den Einstellungen einen anderen Anbieter wählen. |
| „Kein Key mehr verfügbar“ | Alle Keys sind für heute aufgebraucht. In den Einstellungen steht, ab wann sie wieder gehen. |
| „Minutenlimit erreicht – Pause …“ | Normal im Free Tier. Der Agent nimmt einen anderen Key oder wartet kurz. |
| „Tageslimit des Free Tiers erreicht“ | Morgen weitermachen, unter „Max. Anzeigen für KI“ weniger einstellen oder die Suche enger fassen (Bezirk, Suchbegriff, Preis). |
| „… aus deiner Region nicht nutzbar“ | Siehe oben „Wichtig für Österreich / EU“. |
