"""Alle Kategorien des willhaben-Marktplatzes (live ermittelt Nov. 2026) mit Beispieltext je Kategorie.

BAUM: [(Hauptkategorie, Pfad, Beispiel, [(Unterkategorie, Pfad, Beispiel), ...]), ...]
KURZ: Kurznamen für die Terminal-Version (z.B. "laptops", "fernseher", "wintersport" ...) -> Pfad
"""

from __future__ import annotations

import re

MARKTPLATZ = "kaufen-und-verkaufen/marktplatz"
ALLE_BEISPIEL = "Gutes Preis/Leistungs-Verhältnis, gepflegter Zustand, Abholung in meiner Nähe"

# fmt: off
BAUM: list[tuple[str, str, str, list[tuple[str, str, str]]]] = [
    ('Antiquitäten / Kunst', 'kaufen-und-verkaufen/marktplatz/antiquitaeten-kunst-6941',
     'Echte Antiquität in gutem Zustand, Herkunft/Alter belegt, keine Reproduktion', [
        ('Antike Bücher / Zeitschriften', 'kaufen-und-verkaufen/marktplatz/antike-buecher-zeitschriften-6942',
         'Erstausgabe oder alte Ausgabe, vollständig, kein Wasserschaden, Einband gut erhalten'),
        ('Antike Haushaltsgeräte', 'kaufen-und-verkaufen/marktplatz/antike-haushaltsgeraete-6959',
         'Funktionsfähig, original erhalten, dekorativ – z.B. alte Kaffeemühle oder Waage'),
        ('Antike Werkzeuge / Maschinen', 'kaufen-und-verkaufen/marktplatz/antike-werkzeuge-maschinen-6968',
         'Alte Hobel/Werkzeuge zum Benutzen, wenig Rost, Klingen intakt'),
        ('Antike Wohnaccessoires', 'kaufen-und-verkaufen/marktplatz/antike-wohnaccessoires-6969',
         'Vintage-Deko mit Patina, aber ohne Brüche oder Klebestellen'),
        ('Antikes Geschirr / Besteck', 'kaufen-und-verkaufen/marktplatz/antikes-geschirr-besteck-6980',
         'Vollständiges Service (6 Personen), ohne Chips/Sprünge, Marke z.B. Augarten'),
        ('Antike Möbel / Lampen', 'kaufen-und-verkaufen/marktplatz/antike-moebel-lampen-7003',
         'Antiker Kasten oder Kommode, Massivholz, restauriert, kein Wurmbefall'),
        ('Antikspielzeug', 'kaufen-und-verkaufen/marktplatz/antikspielzeug-7025',
         'Blechspielzeug vor 1970, original, mit Funktion, gerne mit Schachtel'),
        ('Banknoten / Wertpapiere', 'kaufen-und-verkaufen/marktplatz/banknoten-wertpapiere-7040',
         'Alte österreichische Banknoten, guter Erhaltungsgrad, keine Risse'),
        ('Gemälde / Bilder', 'kaufen-und-verkaufen/marktplatz/gemaelde-bilder-7043',
         'Ölgemälde mit Signatur, Landschaft, gerahmt, guter Zustand'),
        ('Medaillen / Pokale', 'kaufen-und-verkaufen/marktplatz/medaillen-pokale-7051',
         'Orden/Medaillen mit Band und Etui, echt, Herkunft nachvollziehbar'),
        ('Münzen', 'kaufen-und-verkaufen/marktplatz/muenzen-7055',
         'Silbermünzen Österreich, vorzüglich erhalten, keine Reinigungsspuren'),
        ('Sammelobjekte', 'kaufen-und-verkaufen/marktplatz/sammelobjekte-7059',
         'Sammlerstück komplett und gepflegt, fairer Preis im Vergleich'),
    ]),
    ('Baby / Kind', 'kaufen-und-verkaufen/marktplatz/baby-kind-3928',
     'Für Baby ab Geburt, gepflegt, rauchfreier Haushalt, gerne im Paket', [
        ('Kindermode', 'kaufen-und-verkaufen/marktplatz/kindermode-3929',
         'Paket Kleidung Gr. 86–92 für Bub, Markenware, ohne Flecken'),
        ('Kinderzimmer', 'kaufen-und-verkaufen/marktplatz/kinderzimmer-4168',
         'Gitterbett 70x140 mit Matratze, umbaubar, keine Schäden'),
        ('Pflege / Ernährung', 'kaufen-und-verkaufen/marktplatz/kinder-pflege-ernaehrung-4203',
         'Babyphone oder Fläschchenwärmer, voll funktionsfähig, mit Zubehör'),
        ('Schulsachen', 'kaufen-und-verkaufen/marktplatz/schulsachen-4240',
         'Ergonomische Schultasche für Volksschule, wenig benutzt'),
        ('Sicherheit', 'kaufen-und-verkaufen/marktplatz/kindersicherheit-4249',
         'Kindersitz i-Size 0–4 Jahre, unfallfrei, nicht älter als 6 Jahre'),
        ('Transport', 'kaufen-und-verkaufen/marktplatz/kindertransport-4257',
         'Kinderwagen mit Wanne und Sportsitz, leicht, gut zu falten'),
        ('Elternratgeber', 'kaufen-und-verkaufen/marktplatz/elternratgeber-4276',
         'Aktuelle Ratgeber zu Schlaf und Beikost, gut erhalten'),
        ('Feste / Feiern', 'kaufen-und-verkaufen/marktplatz/kinderfeste-kinderfeiern-4282',
         'Partydeko für Kindergeburtstag, vollständig, wiederverwendbar'),
        ('Tagesmutter / Babysitting', 'kaufen-und-verkaufen/marktplatz/tagesmutter-babysitting-4307',
         'Zuverlässige Betreuung, Erfahrung und Referenzen, flexible Zeiten'),
    ]),
    ('Beauty / Gesundheit / Wellness', 'kaufen-und-verkaufen/marktplatz/beauty-gesundheit-wellness-3076',
     'Originalverpackt oder kaum benutzt, nicht abgelaufen, keine Fälschung', [
        ('Esoterik', 'kaufen-und-verkaufen/marktplatz/esoterik-3077',
         'Echte Edelsteine/Kristalle, schön verarbeitet, fairer Preis'),
        ('Gesichtspflege', 'kaufen-und-verkaufen/marktplatz/gesichtspflege-3084',
         'Hochwertige Gesichtspflege, ungeöffnet, Haltbarkeit noch lang'),
        ('Gesundheit / Medizin', 'kaufen-und-verkaufen/marktplatz/gesundheit-medizin-3091',
         'Blutdruckmessgerät oder Rollator, geprüft, mit Anleitung'),
        ('Haarpflege', 'kaufen-und-verkaufen/marktplatz/haarpflege-3124',
         'Glätteisen/Föhn von Marke (z.B. Dyson, ghd), funktioniert einwandfrei'),
        ('Körperpflege', 'kaufen-und-verkaufen/marktplatz/koerperpflege-3139',
         'Elektrischer Rasierer oder Epilierer, wenig benutzt, mit Ladegerät'),
        ('Makeup / Schminken', 'kaufen-und-verkaufen/marktplatz/makeup-schminken-3148',
         'Make-up-Paket ungeöffnet, bekannte Marken, nicht abgelaufen'),
        ('Maniküre / Pediküre', 'kaufen-und-verkaufen/marktplatz/manikuere-pedikuere-3161',
         'UV-Lampe und Nagelset, vollständig, kaum benutzt'),
        ('Parfums', 'kaufen-und-verkaufen/marktplatz/parfums-3170',
         'Original-Parfum mit Rechnung/Batchcode, Füllstand mind. 80 %'),
        ('Vitamine / Nahrungsergänzung', 'kaufen-und-verkaufen/marktplatz/vitamine-nahrungsergaenzung-3185',
         'Ungeöffnet, Mindesthaltbarkeit noch über 6 Monate'),
        ('Wellness', 'kaufen-und-verkaufen/marktplatz/wellness-3171',
         'Massagesessel oder Sauna-Zubehör, gepflegt, voll funktionsfähig'),
        ('Wellness- / Gesundheitsgutscheine', 'kaufen-und-verkaufen/marktplatz/wellness-gesundheitsgutscheine-3184',
         'Gültiger Gutschein, mindestens 3 Monate Restlaufzeit, unter Nennwert'),
        ('Zahnpflege', 'kaufen-und-verkaufen/marktplatz/zahnpflege-3186',
         'Elektrische Zahnbürste, Akku hält, gerne neue Aufsteckbürsten dabei'),
        ('Dienstleistungen - Alten-/ Krankenpflege', 'kaufen-und-verkaufen/marktplatz/dienstleistungen-alten-krankenpflege-2682',
         'Erfahrene Pflegekraft, Referenzen, stundenweise in Wien'),
        ('Dienstleistungen - Beauty/ Gesundheit', 'kaufen-und-verkaufen/marktplatz/dienstleistungen-beauty-gesundheit-2683',
         'Mobile Kosmetik/Massage mit Ausbildung und guten Bewertungen'),
    ]),
    ('Boote / Yachten / Jetskis', 'kaufen-und-verkaufen/marktplatz/boote-yachten-jetskis-5007823',
     'Gepflegtes Boot mit Papieren, wenig Motorstunden, Liegeplatz in Österreich', [
        ('Boots- / Yachtzubehör', 'kaufen-und-verkaufen/marktplatz/boots-yachtzubehoer-5007824',
         'Bootszubehör in gutem Zustand, passend für Motorboot bis 6 m'),
        ('Jetskis', 'kaufen-und-verkaufen/marktplatz/jetskis-5007825',
         'Jetski mit wenig Betriebsstunden, Servicenachweis, Trailer dabei'),
        ('Motorboote / Motoryachten', 'kaufen-und-verkaufen/marktplatz/motorboote-motoryachten-5007826',
         'Motorboot mit Führerschein-freiem Motor oder Papieren, Trailer inklusive'),
        ('Motoren', 'kaufen-und-verkaufen/marktplatz/motoren-5007827',
         'Außenborder 5–15 PS, läuft gut, Wartung nachweisbar'),
        ('Schlauchboote / Kleinboote', 'kaufen-und-verkaufen/marktplatz/schlauchboote-kleinboote-5007828',
         'Schlauchboot dicht, mit Pumpe und Rudern, für 3 Personen'),
        ('Segelboote / Segelyachten', 'kaufen-und-verkaufen/marktplatz/segelboote-segelyachten-5007829',
         'Segelboot mit gutem Rigg und Segeln, Liegeplatz am See'),
    ]),
    ('Bücher / Filme / Musik', 'kaufen-und-verkaufen/marktplatz/buecher-filme-musik-387',
     'Gut erhalten, vollständig, gerne als Paket zum günstigen Preis', [
        ('Bücher', 'kaufen-und-verkaufen/marktplatz/buecher-2911',
         'Romane/Krimis im Paket, guter Zustand, keine Markierungen'),
        ('Hörbücher / Hörspiele', 'kaufen-und-verkaufen/marktplatz/hoerbuecher-hoerspiele-2948',
         'Hörbücher auf CD oder als Box, vollständig, CDs ohne Kratzer'),
        ('Kinder- / Jugendbücher', 'kaufen-und-verkaufen/marktplatz/kinder-jugendbuecher-2969',
         'Kinderbücher ab 6 Jahren im Paket, sauber, keine Kritzeleien'),
        ('Sachbücher', 'kaufen-und-verkaufen/marktplatz/sachbuecher-2999',
         'Aktuelle Ausgabe (nicht älter als 5 Jahre), kaum Gebrauchsspuren'),
        ('Schule / Studienliteratur / Ausbildung', 'kaufen-und-verkaufen/marktplatz/schule-studienliteratur-ausbildung-3024',
         'Lehrbuch in aktueller Auflage für Studium/Schule, wenig Markierungen'),
        ('Musik', 'kaufen-und-verkaufen/marktplatz/musik-2978',
         'Vinyl-LPs in gutem Zustand (VG+ oder besser), Rock/Jazz'),
        ('Filme', 'kaufen-und-verkaufen/marktplatz/filme-2933',
         'Blu-rays/DVDs im Paket, Deutsch, Discs ohne Kratzer'),
        ('Serien', 'kaufen-und-verkaufen/marktplatz/serien-3042',
         'Komplette Staffeln einer Serie, Deutsch, vollständig'),
        ('Zeitschriften', 'kaufen-und-verkaufen/marktplatz/zeitschriften-3053',
         'Vollständige Jahrgänge, gut erhalten, ohne fehlende Seiten'),
        ('Hüllen / Zubehör', 'kaufen-und-verkaufen/marktplatz/huellen-zubehoer-2968',
         'Hüllen/Zubehör für Platten oder CDs, sauber und unbeschädigt'),
        ('Reinigungs- / Pflegematerial', 'kaufen-und-verkaufen/marktplatz/reinigungs-pflegematerial-2998',
         'Plattenwaschmaschine oder Reinigungsset, funktionsfähig'),
    ]),
    ('Computer / Software', 'kaufen-und-verkaufen/marktplatz/computer-software-5824',
     'Für Uni & Office, zuverlässig, gerne mit Rechnung/Garantie', [
        ('Adapter / Kabel', 'kaufen-und-verkaufen/marktplatz/adapter-kabel-5825',
         'Kabel/Adapter passend für USB-C bzw. HDMI, funktioniert sicher'),
        ('Computer / Tablets', 'kaufen-und-verkaufen/marktplatz/computer-tablets-5828',
         'Für Uni & Office, leicht, guter Akku, mind. 16 GB RAM'),
        ('Computer / Tablets › Notebooks / Laptops', 'kaufen-und-verkaufen/marktplatz/computer-tablets/notebooks-5831',
         'Für Uni & Office, leicht, guter Akku, mind. 16 GB RAM'),
        ('Computer / Tablets › PCs', 'kaufen-und-verkaufen/marktplatz/computer-tablets/pcs-5833',
         'Gaming-PC für 1440p, aktuelle Grafikkarte, leise, mit SSD'),
        ('Computer / Tablets › Tablets', 'kaufen-und-verkaufen/marktplatz/computer-tablets/tablets-5834',
         'Tablet zum Lesen und Streamen, mind. 64 GB, Akku in Ordnung'),
        ('Computer / Tablets › E-Book-Reader', 'kaufen-und-verkaufen/marktplatz/computer-tablets/e-book-reader-7202',
         'E-Reader mit Beleuchtung, wasserdicht, ohne Displayschäden'),
        ('Computer / Tablets › Netbooks', 'kaufen-und-verkaufen/marktplatz/computer-tablets/netbooks-5829',
         'Kleines leichtes Gerät zum Surfen, Akku hält mehrere Stunden'),
        ('Computer / Tablets › Notebook-Taschen', 'kaufen-und-verkaufen/marktplatz/computer-tablets/notebook-taschen-5832',
         'Notebooktasche/Rucksack bis 15,6 Zoll, gepolstert, wie neu'),
        ('Computer / Tablets › Notebook-Hüllen / -Schutz', 'kaufen-und-verkaufen/marktplatz/computer-tablets/notebook-huellen-schutz-5830',
         'Hülle passend für 14-Zoll-Notebook, guter Schutz, sauber'),
        ('Computer / Tablets › Tablets Zubehör', 'kaufen-und-verkaufen/marktplatz/computer-tablets/tablets-zubehoer-5835',
         'Tablet-Tastatur oder Stift, kompatibel mit meinem Modell'),
        ('Drucker / Monitore / Lautsprecher', 'kaufen-und-verkaufen/marktplatz/drucker-monitore-lautsprecher-5836',
         'Monitor 27 Zoll 1440p, ohne Pixelfehler, höhenverstellbar'),
        ('Eingabe- / Lesegeräte', 'kaufen-und-verkaufen/marktplatz/eingabe-lesegeraete-5852',
         'Mechanische Tastatur und Maus, funktionieren einwandfrei'),
        ('Festplatten / Speicherkarten', 'kaufen-und-verkaufen/marktplatz/festplatten-speicherkarten-5867',
         'SSD 1–2 TB mit guten Health-Werten, keine Fehler'),
        ('Netzwerke', 'kaufen-und-verkaufen/marktplatz/netzwerke-5871',
         'WLAN-Router/Mesh mit Wi-Fi 6, aktuelle Firmware'),
        ('PC-Komponenten', 'kaufen-und-verkaufen/marktplatz/pc-komponenten-5878',
         'Grafikkarte für Gaming, nicht fürs Mining genutzt, mit Rechnung'),
        ('Software', 'kaufen-und-verkaufen/marktplatz/software-5891',
         'Original-Lizenz mit Key, übertragbar, aktuelle Version'),
        ('USB-Zubehör', 'kaufen-und-verkaufen/marktplatz/usb-zubehoer-5901',
         'USB-Hub/Dockingstation mit Netzteil, alle Anschlüsse funktionieren'),
    ]),
    ('Dienstleistungen', 'kaufen-und-verkaufen/marktplatz/dienstleistungen-537',
     'Zuverlässig, gute Bewertungen, fairer Stundensatz in meiner Nähe', [
        ('Alten- / Krankenbetreuung', 'kaufen-und-verkaufen/marktplatz/alten-krankenbetreuung-2699',
         'Erfahrene Betreuung mit Referenzen, deutschsprachig'),
        ('Ausbildung / Nachhilfe', 'kaufen-und-verkaufen/marktplatz/ausbildung-nachhilfe-2700',
         'Nachhilfe Mathe Oberstufe, Erfahrung, auch online'),
        ('Beauty / Gesundheit', 'kaufen-und-verkaufen/marktplatz/beauty-gesundheit-2701',
         'Ausgebildete Kosmetikerin/Masseur, Hausbesuche möglich'),
        ('Design / Druck / Merchandising', 'kaufen-und-verkaufen/marktplatz/design-druck-merchandising-2703',
         'Logo- und Flyergestaltung mit Portfolio, schnelle Lieferung'),
        ('Fotografie', 'kaufen-und-verkaufen/marktplatz/fotografie-2702',
         'Hochzeits- oder Porträtfotograf mit Portfolio, faire Pauschale'),
        ('Handwerker / Malerarbeiten', 'kaufen-und-verkaufen/marktplatz/handwerker-malerarbeiten-2704',
         'Maler für Wohnung 70 m², Erfahrung und Referenzen'),
        ('KFZ-Reparaturen / Services', 'kaufen-und-verkaufen/marktplatz/kfz-reparaturen-services-2705',
         'Service/Pickerl-Überprüfung zum fairen Preis, Werkstatt in der Nähe'),
        ('Lebensberatung / Coaching', 'kaufen-und-verkaufen/marktplatz/lebensberatung-coaching-2706',
         'Coach mit Ausbildung, Erstgespräch kostenlos'),
        ('PC / Konsolen', 'kaufen-und-verkaufen/marktplatz/pc-konsolen-2707',
         'PC-Reparatur/Aufrüstung, schnelle Abwicklung, faire Preise'),
        ('Reinigung / Gartenarbeit', 'kaufen-und-verkaufen/marktplatz/reinigung-gartenarbeit-2708',
         'Regelmäßige Reinigung oder Gartenpflege, zuverlässig, versichert'),
        ('Reitbeteiligungen', 'kaufen-und-verkaufen/marktplatz/reitbeteiligungen-5913',
         'Reitbeteiligung 2x pro Woche, braves Pferd, Stall in der Nähe'),
        ('Smartphone / Tablets', 'kaufen-und-verkaufen/marktplatz/smartphone-tablets-2709',
         'Displaytausch mit Garantie, Originalteile, am selben Tag'),
        ('Tagesmutter / Babysitting', 'kaufen-und-verkaufen/marktplatz/tagesmutter-babysitting-2712',
         'Liebevolle Betreuung mit Erfahrung, flexible Zeiten'),
        ('Tiersitter / Kurse', 'kaufen-und-verkaufen/marktplatz/tiersitter-kurse-2713',
         'Hundesitter mit Erfahrung, Referenzen, auch am Wochenende'),
        ('Umzug / Transport', 'kaufen-und-verkaufen/marktplatz/umzug-transport-2716',
         'Umzug 2-Zimmer-Wohnung mit Transporter und Helfern, Fixpreis'),
        ('Unterhaltung / Veranstaltung', 'kaufen-und-verkaufen/marktplatz/unterhaltung-veranstaltung-2717',
         'DJ oder Band für Feier, Referenzen, Technik inklusive'),
    ]),
    ('Freizeit / Instrumente / Kulinarik', 'kaufen-und-verkaufen/marktplatz/freizeit-instrumente-kulinarik-6462',
     'Gut erhalten und vollständig, fairer Preis', [
        ('Basteln / Handarbeit', 'kaufen-und-verkaufen/marktplatz/basteln-handarbeit-6463',
         'Nähmaschine oder Wolle/Stoffe im Paket, gut erhalten'),
        ('Geschenkartikel / Saisonales / Feste', 'kaufen-und-verkaufen/marktplatz/geschenkartikel-saisonales-feste-6478',
         'Weihnachtsdeko im Paket, vollständig, kaum benutzt'),
        ('Kulinarik', 'kaufen-und-verkaufen/marktplatz/kulinarik-6517',
         'Hochwertige Spezialitäten, ungeöffnet und nicht abgelaufen'),
        ('Musikinstrumente / Noten', 'kaufen-und-verkaufen/marktplatz/musikinstrumente-noten-6540',
         'Akustikgitarre für Einsteiger, gute Bespielbarkeit, ohne Risse'),
        ('Modellbau', 'kaufen-und-verkaufen/marktplatz/modellbau-6582',
         'Modelleisenbahn H0 mit Gleisen, digital, funktionsfähig'),
        ('Sammelobjekte', 'kaufen-und-verkaufen/marktplatz/sammelobjekte-6621',
         'Sammlung vollständig, gepflegt, fairer Preis im Vergleich'),
        ('Schreibwaren / Malen', 'kaufen-und-verkaufen/marktplatz/schreibwaren-malen-6677',
         'Künstlerbedarf (Farben, Pinsel), wenig benutzt, im Paket'),
        ('Tabakzubehör', 'kaufen-und-verkaufen/marktplatz/tabakzubehoer-6693',
         'Shisha oder Pfeife, sauber, vollständig'),
        ('Tickets / Gutscheine', 'kaufen-und-verkaufen/marktplatz/tickets-gutscheine-6700',
         'Echte Tickets zum Originalpreis, personalisierbar, kein Wucher'),
    ]),
    ('Games / Konsolen', 'kaufen-und-verkaufen/marktplatz/games-konsolen-2785',
     'Aktuelle Konsole mit Controller, funktioniert einwandfrei', [
        ('Controller / Eingabegeräte', 'kaufen-und-verkaufen/marktplatz/controller-eingabegeraete-2814',
         'Original-Controller ohne Stick-Drift, Akku hält'),
        ('Konsolen', 'kaufen-und-verkaufen/marktplatz/konsolen-2786',
         'PS5/Switch mit Controller und Rechnung, keine Defekte'),
        ('Konsolenzubehör', 'kaufen-und-verkaufen/marktplatz/konsolenzubehoer-2823',
         'Ladestation/Headset original, voll funktionsfähig'),
        ('Online Gaming', 'kaufen-und-verkaufen/marktplatz/online-gaming-2859',
         'Gutscheine/Accounts nur seriös, Originalpreis, übertragbar'),
        ('Spiele', 'kaufen-und-verkaufen/marktplatz/spiele-2830',
         'Spiele im Paket für PS5/Switch, Discs ohne Kratzer'),
    ]),
    ('Haus / Garten / Werkstatt', 'kaufen-und-verkaufen/marktplatz/haus-garten-werkstatt-3541',
     'Robust, funktionsfähig, gerne Markenqualität', [
        ('Haus / Bauen', 'kaufen-und-verkaufen/marktplatz/haus-bauen-3542',
         'Baumaterial/Fenster in passenden Maßen, unbeschädigt'),
        ('Garten', 'kaufen-und-verkaufen/marktplatz/garten-3631',
         'Rasenmäher-Roboter oder Gartenmöbel, gepflegt, wetterfest'),
        ('Maschinen', 'kaufen-und-verkaufen/marktplatz/maschinen-3761',
         'Maschine läuft einwandfrei, Wartung nachweisbar, mit Zubehör'),
        ('Werkstatt', 'kaufen-und-verkaufen/marktplatz/werkstatt-3778',
         'Akku-Werkzeug (Bosch/Makita), mit Akku und Ladegerät'),
    ]),
    ('Kameras / TV / Multimedia', 'kaufen-und-verkaufen/marktplatz/kameras-tv-multimedia-6808',
     'Funktioniert einwandfrei, gerne mit Rechnung und Zubehör', [
        ('Audio / Hifi', 'kaufen-und-verkaufen/marktplatz/audio-hifi-6809',
         'Verstärker/Lautsprecher mit gutem Klang, keine Kratzgeräusche'),
        ('Batterien / Akkus', 'kaufen-und-verkaufen/marktplatz/batterien-akkus-6845',
         'Original-Akkus mit guter Kapazität, nicht aufgebläht'),
        ('Beamer / Diaprojektoren', 'kaufen-und-verkaufen/marktplatz/beamer-diaprojektoren-6850',
         'Beamer Full HD, Lampenstunden gering, leise'),
        ('DVD / Blu-ray Player', 'kaufen-und-verkaufen/marktplatz/dvd-blu-ray-player-6857',
         'Blu-ray-Player mit Fernbedienung, liest alle Discs'),
        ('Eventtechnik', 'kaufen-und-verkaufen/marktplatz/eventtechnik-6863',
         'PA-Anlage/Lichteffekte für Partys, voll funktionsfähig'),
        ('Fernseher', 'kaufen-und-verkaufen/marktplatz/fernseher-6875',
         '4K-Fernseher 55 Zoll, kein Pixelfehler, mit Fernbedienung'),
        ('Funk', 'kaufen-und-verkaufen/marktplatz/funk-6892',
         'Funkgeräte mit Akkus, Reichweite gut, legal in Österreich'),
        ('Kameras / Camcorder', 'kaufen-und-verkaufen/marktplatz/kameras-camcorder-6895',
         'Systemkamera mit Objektiv, geringe Auslösungen, keine Kratzer'),
        ('Speichermedien', 'kaufen-und-verkaufen/marktplatz/speichermedien-6910',
         'Speicherkarten/USB-Sticks original, schnell, fehlerfrei'),
        ('Videorecorder', 'kaufen-und-verkaufen/marktplatz/videorecorder-6916',
         'Videorecorder zum Digitalisieren, Kopf sauber, funktioniert'),
    ]),
    ('KFZ-Zubehör / Motorradteile', 'kaufen-und-verkaufen/marktplatz/kfz-zubehoer-motorradteile-6142',
     'Passend für mein Fahrzeug, guter Zustand, mit Typenangabe', [
        ('PKW-Ersatzteile / Zubehör', 'kaufen-und-verkaufen/marktplatz/pkw-ersatzteile-zubehoer-6143',
         'Winterreifen 205/55 R16 auf Felgen, mind. 5 mm Profil'),
        ('Motorradteile / Rollerteile / Zubehör', 'kaufen-und-verkaufen/marktplatz/motorradteile-rollerteile-zubehoer-6302',
         'Motorradhelm Gr. M, unfallfrei, nicht älter als 5 Jahre'),
        ('Traktor- / Baggerzubehör', 'kaufen-und-verkaufen/marktplatz/traktor-baggerzubehoer-6380',
         'Ersatzteile passend für meinen Traktor, gebraucht aber funktionsfähig'),
        ('PKW-Anhänger', 'kaufen-und-verkaufen/marktplatz/pkw-anhaenger-6381',
         'PKW-Anhänger mit Papieren, Pickerl gültig, Plane dabei'),
        ('Navigationssysteme', 'kaufen-und-verkaufen/marktplatz/navigationssysteme-6390',
         'Navi mit aktuellen Karten Europa, Halterung dabei'),
        ('Fahrzeugpflege / Werkzeuge', 'kaufen-und-verkaufen/marktplatz/fahrzeugpflege-werkzeuge-6396',
         'Poliermaschine oder Drehmomentschlüssel, gepflegt'),
        ('Sicherheit / Pannenausstattung', 'kaufen-und-verkaufen/marktplatz/sicherheit-pannenausstattung-6416',
         'Vollständiges Pannenset (Warndreieck, Weste, Verbandskasten)'),
        ('Betriebsanleitungen / Typenscheine', 'kaufen-und-verkaufen/marktplatz/betriebsanleitungen-typenscheine-6420',
         'Originale Betriebsanleitung für mein Modell, vollständig'),
        ('Bücher / Fanartikel', 'kaufen-und-verkaufen/marktplatz/buecher-fanartikel-6424',
         'Fanartikel/Bücher zu Oldtimern, gut erhalten'),
    ]),
    ('Mode / Accessoires', 'kaufen-und-verkaufen/marktplatz/mode-accessoires-3275',
     'Markenware in meiner Größe, gepflegt, keine Flecken', [
        ('Damenmode', 'kaufen-und-verkaufen/marktplatz/damenmode-3276',
         'Winterjacke Damen Gr. M, warm, Markenqualität, wenig getragen'),
        ('Herrenmode', 'kaufen-und-verkaufen/marktplatz/herrenmode-3393',
         'Anzug Herren Gr. 50, wenig getragen, gereinigt'),
        ('Kleiderpflege / Zubehör', 'kaufen-und-verkaufen/marktplatz/kleiderpflege-zubehoer-3474',
         'Bügeleisen/Dampfglätter, funktioniert einwandfrei'),
        ('Taschen / Koffer', 'kaufen-und-verkaufen/marktplatz/taschen-koffer-3480',
         'Handgepäck-Trolley, leicht, Rollen und Griff intakt'),
        ('Verkleidungen', 'kaufen-und-verkaufen/marktplatz/verkleidungen-3493',
         'Faschingskostüm Gr. M, vollständig, sauber'),
    ]),
    ('Smartphones / Telefonie', 'kaufen-und-verkaufen/marktplatz/smartphones-telefonie-2691',
     'Funktioniert einwandfrei, Akku gut, ohne Displayschäden', [
        ('Handyservices', 'kaufen-und-verkaufen/marktplatz/handyservices-2692',
         'Reparatur mit Garantie und Originalteilen'),
        ('Organizer / PDAs', 'kaufen-und-verkaufen/marktplatz/organizer-pdas-2764',
         'Funktionsfähig, mit Ladegerät, für Sammler'),
        ('Smartphones / Handys', 'kaufen-und-verkaufen/marktplatz/smartphones-handys-2722',
         'Smartphone mit mind. 128 GB, Akku über 85 %, kein Displayschaden, ohne SIM-Lock'),
        ('Smartwatches', 'kaufen-und-verkaufen/marktplatz/smartwatches-2771',
         'Smartwatch mit gutem Akku, Display ohne Kratzer, mit Ladekabel'),
        ('Tablets', 'kaufen-und-verkaufen/marktplatz/tablets-2772',
         'Tablet zum Lesen und Streamen, mind. 64 GB, Akku in Ordnung'),
        ('Telefonie / Fax', 'kaufen-und-verkaufen/marktplatz/telefonie-fax-2765',
         'Schnurlostelefon mit 2 Mobilteilen, Akkus in Ordnung'),
        ('Zubehör Handy / Telefonie', 'kaufen-und-verkaufen/marktplatz/zubehoer-handy-telefonie-2750',
         'Original-Ladegerät/Hülle passend für mein Modell'),
    ]),
    ('Spielen / Spielzeug', 'kaufen-und-verkaufen/marktplatz/spielen-spielzeug-5136',
     'Vollständig, sauber, für Kinder ab 4 Jahren', [
        ('Babyspielzeug 0-2 J.', 'kaufen-und-verkaufen/marktplatz/babyspielzeug-5137',
         'Babyspielzeug ohne Kleinteile, sauber, gerne Holz'),
        ('Basteln / Baukästen', 'kaufen-und-verkaufen/marktplatz/basteln-baukaesten-5156',
         'Baukasten vollständig mit Anleitung'),
        ('Elektronisches Spielzeug', 'kaufen-und-verkaufen/marktplatz/elektronisches-spielzeug-5162',
         'Lernspielzeug mit Batterien/Akku, funktioniert'),
        ('Kinderfahrzeuge', 'kaufen-und-verkaufen/marktplatz/kinderfahrzeuge-5170',
         'Laufrad oder Roller für 3-Jährige, stabil, sicher'),
        ('Kinderinstrumente', 'kaufen-und-verkaufen/marktplatz/kinderinstrumente-5177',
         'Kinderkeyboard oder Xylophon, funktionsfähig'),
        ('Klemmbausteine/ Lego/ Playmobil', 'kaufen-und-verkaufen/marktplatz/klemmbausteine-lego-playmobil-5182',
         'LEGO-Set vollständig mit Anleitung, gerne OVP'),
        ('Puppen / Spielfiguren', 'kaufen-und-verkaufen/marktplatz/puppen-spielfiguren-5251',
         'Puppen/Figuren im Paket, sauber, vollständig'),
        ('Spiele / Puzzles', 'kaufen-und-verkaufen/marktplatz/spiele-puzzles-5277',
         'Brettspiele/Puzzles vollständig, alle Teile vorhanden'),
        ('Spieltische / Automaten', 'kaufen-und-verkaufen/marktplatz/spieltische-automaten-5293',
         'Tischfußball oder Flipper, funktionsfähig, guter Zustand'),
        ('Spielzeugfahrzeuge', 'kaufen-und-verkaufen/marktplatz/spielzeugfahrzeuge-5302',
         'Modellautos/Carrera-Bahn vollständig, funktioniert'),
        ('Spielzeug für Draußen', 'kaufen-und-verkaufen/marktplatz/spielzeug-fuer-draussen-5315',
         'Sandkiste/Rutsche/Trampolin, stabil und sicher'),
        ('Stofftiere', 'kaufen-und-verkaufen/marktplatz/stofftiere-5327',
         'Kuscheltiere sauber, aus Nichtraucherhaushalt'),
    ]),
    ('Sport / Sportgeräte', 'kaufen-und-verkaufen/marktplatz/sport-sportgeraete-4390',
     'Gut erhalten, passende Größe, sicher und funktionsfähig', [
        ('Angelsport / Jagdsport', 'kaufen-und-verkaufen/marktplatz/angelsport-jagdsport-4391',
         'Angelrute mit Rolle, guter Zustand, für Einsteiger'),
        ('Ballsportarten', 'kaufen-und-verkaufen/marktplatz/ballsportarten-4408',
         'Fußballschuhe Gr. 42 oder Ball, kaum getragen'),
        ('Bergsport / Outdoor', 'kaufen-und-verkaufen/marktplatz/bergsport-outdoor-4478',
         'Wanderschuhe/Rucksack, gute Qualität, wenig benutzt'),
        ('Fahrräder / Radsport', 'kaufen-und-verkaufen/marktplatz/fahrraeder-radsport-4525',
         'E-Bike/Fahrrad Rahmengröße M, gewartet, kein Sturzschaden'),
        ('Fitness / Laufen', 'kaufen-und-verkaufen/marktplatz/fitness-laufen-4566',
         'Laufband oder Hantelset, funktioniert, kompakt'),
        ('Freizeit- / Funsport', 'kaufen-und-verkaufen/marktplatz/freizeit-funsport-4598',
         'Stand-up-Paddle oder Skateboard, guter Zustand'),
        ('Reitsport', 'kaufen-und-verkaufen/marktplatz/reitsport-4626',
         'Sattel/Reitausrüstung passend, gepflegt'),
        ('Wassersport', 'kaufen-und-verkaufen/marktplatz/wassersport-4651',
         'Neoprenanzug oder Kajak, dicht und gepflegt'),
        ('Wintersport', 'kaufen-und-verkaufen/marktplatz/wintersport-4674',
         'Ski 160–170 cm mit Bindung, Kanten scharf, frisch gewachst'),
    ]),
    ('Tiere / Tierbedarf', 'kaufen-und-verkaufen/marktplatz/tiere-tierbedarf-4915',
     'Seriöser Abgabe- bzw. Tierbedarf in gutem Zustand, artgerecht', [
        ('Fische', 'kaufen-und-verkaufen/marktplatz/fische-4916',
         'Aquarium komplett mit Technik, dicht, gepflegt'),
        ('Hunde', 'kaufen-und-verkaufen/marktplatz/hunde-4943',
         'Hundebox/Zubehör passend für mittelgroßen Hund, sauber'),
        ('Katzen', 'kaufen-und-verkaufen/marktplatz/katzen-4968',
         'Kratzbaum stabil, sauber, aus Nichtraucherhaushalt'),
        ('Kleintiere / Nagetiere', 'kaufen-und-verkaufen/marktplatz/kleintiere-nagetiere-4983',
         'Gehege/Käfig für Kaninchen, artgerecht groß, sauber'),
        ('Nutztiere', 'kaufen-und-verkaufen/marktplatz/nutztiere-5007',
         'Gesunde Tiere mit Papieren, artgerechte Haltung'),
        ('Pferde', 'kaufen-und-verkaufen/marktplatz/pferde-5034',
         'Pferd mit AKU, brav, für Freizeitreiter'),
        ('Reptilien', 'kaufen-und-verkaufen/marktplatz/reptilien-5075',
         'Terrarium mit Technik, dicht, geeignet für meine Art'),
        ('Vögel', 'kaufen-und-verkaufen/marktplatz/voegel-5090',
         'Vogelvoliere/Käfig, artgerecht groß, sauber'),
        ('Stroh / Heu / Silage', 'kaufen-und-verkaufen/marktplatz/stroh-heu-silage-5104',
         'Heu/Stroh in guter Qualität, trocken gelagert, Lieferung möglich'),
    ]),
    ('Uhren / Schmuck', 'kaufen-und-verkaufen/marktplatz/uhren-schmuck-2409',
     'Echt (Gold/Silber), mit Punze oder Zertifikat, guter Zustand', [
        ('Uhren', 'kaufen-und-verkaufen/marktplatz/uhren-2650',
         'Automatikuhr mit Papieren/Box, echt, Service-Historie'),
        ('Anhänger / Charms', 'kaufen-und-verkaufen/marktplatz/anhaenger-charms-2663',
         'Echte Silber-Anhänger/Charms, passend zu Pandora'),
        ('Armschmuck', 'kaufen-und-verkaufen/marktplatz/armschmuck-2659',
         'Armband aus Silber oder Gold, echt, unbeschädigt'),
        ('Broschen / Stecker / Manschetten', 'kaufen-und-verkaufen/marktplatz/broschen-stecker-manschetten-2668',
         'Manschettenknöpfe/Brosche, echt, gut erhalten'),
        ('Halsketten', 'kaufen-und-verkaufen/marktplatz/halsketten-2664',
         'Goldkette 585, echt mit Punze, keine Schäden'),
        ('Ohrschmuck', 'kaufen-und-verkaufen/marktplatz/ohrschmuck-2669',
         'Ohrringe aus Silber/Gold, echt, Paar vollständig'),
        ('Piercings', 'kaufen-und-verkaufen/marktplatz/piercings-2673',
         'Piercings aus Titan/Chirurgenstahl, unbenutzt'),
        ('Ringe', 'kaufen-und-verkaufen/marktplatz/ringe-2504',
         'Ring Gr. 54 aus Gold, echt, mit Punze'),
        ('Schmucksets', 'kaufen-und-verkaufen/marktplatz/schmucksets-2680',
         'Schmuckset echt, vollständig, gerne mit Etui'),
        ('Zubehör / Aufbewahrung', 'kaufen-und-verkaufen/marktplatz/zubehoer-aufbewahrung-2681',
         'Schmuckkästchen/Uhrenbeweger, funktionsfähig, sauber'),
    ]),
    ('Wohnen / Haushalt / Gastronomie', 'kaufen-und-verkaufen/marktplatz/wohnen-haushalt-gastronomie-5387',
     'Gepflegt, aus Nichtraucherhaushalt, Abholung in meiner Nähe', [
        ('Badezimmer / WC', 'kaufen-und-verkaufen/marktplatz/badezimmer-wc-5388',
         'Waschtisch mit Unterschrank, unbeschädigt, Maße ca. 80 cm'),
        ('Büro / Geschäftseinrichtung', 'kaufen-und-verkaufen/marktplatz/buero-geschaeftseinrichtung-5418',
         'Ergonomischer Bürostuhl, höhenverstellbar, voll funktionsfähig'),
        ('Dekoration', 'kaufen-und-verkaufen/marktplatz/dekoration-5436',
         'Deko im skandinavischen Stil, unbeschädigt'),
        ('Garderobe / Vorzimmer', 'kaufen-und-verkaufen/marktplatz/garderobe-vorzimmer-5470',
         'Garderobe mit Schuhschrank, stabil, wenig Gebrauchsspuren'),
        ('Gastronomie', 'kaufen-und-verkaufen/marktplatz/gastronomie-5478',
         'Gastro-Kühlschrank/Kaffeemaschine, gewartet, funktioniert'),
        ('Geschirr / Gläser', 'kaufen-und-verkaufen/marktplatz/geschirr-glaeser-5507',
         'Geschirrset für 6 Personen, spülmaschinenfest, ohne Chips'),
        ('Haushaltsgeräte / Reinigung', 'kaufen-und-verkaufen/marktplatz/haushaltsgeraete-reinigung-5545',
         'Waschmaschine/Staubsauger von Marke, voll funktionsfähig'),
        ('Heimtextilien', 'kaufen-und-verkaufen/marktplatz/heimtextilien-5569',
         'Vorhänge/Teppich in passender Größe, sauber, Nichtraucher'),
        ('Kinderzimmer', 'kaufen-und-verkaufen/marktplatz/kinderzimmer-5595',
         'Kinderzimmermöbel stabil, unbeschädigt, gerne Hochbett'),
        ('Küchengeräte / -utensilien', 'kaufen-und-verkaufen/marktplatz/kuechengeraete-utensilien-5630',
         'Küchenmaschine (z.B. KitchenAid/Thermomix), voll funktionsfähig'),
        ('Küchenmöbel', 'kaufen-und-verkaufen/marktplatz/kuechenmoebel-5686',
         'Einbauküche mit Geräten, ca. 3 m, guter Zustand'),
        ('Lampen / Licht', 'kaufen-und-verkaufen/marktplatz/lampen-licht-5697',
         'Designerlampe, funktioniert, ohne Beschädigungen'),
        ('Regale / Kästen', 'kaufen-und-verkaufen/marktplatz/regale-kaesten-5714',
         'Regal/Kasten stabil, Maße passend, wenig Gebrauchsspuren'),
        ('Schlafzimmer', 'kaufen-und-verkaufen/marktplatz/schlafzimmer-5725',
         'Doppelbett 160x200 mit Lattenrost, stabil, ohne Matratze'),
        ('Sofas / Sessel', 'kaufen-und-verkaufen/marktplatz/sofas-sessel-5738',
         'Ecksofa ohne Flecken/Risse, Nichtraucher, haustierfrei'),
        ('Tische', 'kaufen-und-verkaufen/marktplatz/tische-5751',
         'Esstisch ausziehbar für 6 Personen, Massivholz'),
        ('Umzug / Reinigung', 'kaufen-und-verkaufen/marktplatz/umzug-reinigung-5759',
         'Umzugskartons/Hilfe, sauber, stabil'),
        ('Sicherheit', 'kaufen-und-verkaufen/marktplatz/sicherheit-5763',
         'Tresor oder Alarmanlage, funktionsfähig, mit Schlüssel/Code'),
    ]),
]
# fmt: on

# Frühere Kurznamen (Terminal-Version, gespeicherte Eingaben) bleiben gültig
_CT = f"{MARKTPLATZ}/computer-tablets"
ALIASE = {
    "alle": MARKTPLATZ,
    "laptops": f"{_CT}/notebooks-5831",
    "notebooks": f"{_CT}/notebooks-5831",
    "pcs": f"{_CT}/pcs-5833",
    "tablets": f"{_CT}/tablets-5834",
    "ebook-reader": f"{_CT}/e-book-reader-7202",
    "computer": f"{MARKTPLATZ}/computer-software-5824",
    "pc-komponenten": f"{MARKTPLATZ}/pc-komponenten-5878",
    "handys": f"{MARKTPLATZ}/smartphones-handys-2722",
    "smartphones": f"{MARKTPLATZ}/smartphones-handys-2722",
    "konsolen": f"{MARKTPLATZ}/konsolen-2786",
    "kameras": f"{MARKTPLATZ}/kameras-camcorder-6895",
}
# alte Pfade aus gespeicherten Einstellungen -> heutige willhaben-Pfade
_ALTE_PFADE = {
    f"{MARKTPLATZ}/computer-tablets/notebooks-5831": ALIASE["laptops"],
    f"{MARKTPLATZ}/computer-software/pc-komponenten-5878": ALIASE["pc-komponenten"],
}


def kurzname(pfad: str) -> str:
    return re.sub(r"-\d+$", "", pfad.rstrip("/").rsplit("/", 1)[-1])


def _kurz() -> dict[str, str]:
    out: dict[str, str] = {}
    doppelt: set[str] = set()
    for _, p, _, unter in BAUM:
        for pfad in [p] + [u[1] for u in unter]:
            k = kurzname(pfad)
            if k in out and out[k] != pfad:
                doppelt.add(k)
            out.setdefault(k, pfad)
            out[pfad.rsplit("/", 1)[-1]] = pfad          # eindeutig: z.B. "tablets-2772"
    for k in doppelt:
        out.pop(k, None)
    out.update(ALIASE)
    return out


KURZ = _kurz()


def pfad(wert: str) -> str:
    """Kurzname oder Pfad -> willhaben-Pfad (unbekannte Pfade werden unverändert übernommen)."""
    w = (wert or "").strip()
    if w.lower() in KURZ:
        return KURZ[w.lower()]
    w = w.strip("/")
    if w.startswith("iad/"):
        w = w[4:]
    return _ALTE_PFADE.get(w, w) if "/" in w else w


def finden(p: str) -> tuple[int | None, int | None]:
    """Pfad -> (Index Hauptkategorie, Index Unterkategorie) im BAUM; (None, None) = alle Kategorien."""
    p = pfad(p)
    for i, (_, hp, _, unter) in enumerate(BAUM):
        if hp == p:
            return i, None
        for j, u in enumerate(unter):
            if u[1] == p:
                return i, j
    return None, None


def name(p: str) -> str:
    i, j = finden(p)
    if i is None:
        return "Alle Kategorien" if pfad(p) == MARKTPLATZ else p
    return BAUM[i][0] + (f" › {BAUM[i][3][j][0]}" if j is not None else "")


def beispiel(p: str) -> str:
    i, j = finden(p)
    if i is None:
        return ALLE_BEISPIEL
    return (BAUM[i][3][j][2] if j is not None else "") or BAUM[i][2] or ALLE_BEISPIEL


def ist_bekannt(wert: str) -> bool:
    return (wert or "").strip().lower() in KURZ or finden(wert)[0] is not None or pfad(wert) == MARKTPLATZ
