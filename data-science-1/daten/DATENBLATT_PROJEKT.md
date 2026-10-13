# Datenblatt: Datenpakete für das Abschlussprojekt

**Herkunft:** synthetisch, für das Abschlussprojekt des Kurses Data Science 1 von linkit courses. Jedes Paket ist eine
eigene Simulation mit eigenem Seed. Die Nordwerk GmbH und die Datenfabrik Karlsruhe e.V. sind erfunden, alle Personen
auch. Ähnlichkeiten mit echten Werken und Vereinen sind gewollt, echte Messwerte oder Personen stecken nicht darin.

**Pakete:** `projekt/A-NN.zip` für Track A (Campus) und `projekt/B-NN.zip` für Track B (Nordwerk), jeweils mit den
Nummern 00 bis 20. Paket 00 ist das **Übungspaket** für alle; die Lerneinheiten und das Projekthandbuch rechnen damit.
Jedes Paar bekommt vom Kursteam eine eigene Paketnummer und arbeitet nur mit diesem Paket. Jedes Paket enthält eine
`LIESMICH.md` mit dem Auftrag, den Spalten und den Annahmen.

**Datenfehler:** Jedes Paket enthält Datenfehler, wie sie in echten Daten vorkommen, und zwar in jedem Paket andere.
Welche es sind, steht nirgends: Sie zu finden und begründet zu behandeln, gehört zum Projekt.

## Track A · Datenfabrik Karlsruhe e.V. (Campus)

Eine Hochschulgruppe lädt vom Wintersemester 2024/25 bis zum Sommersemester 2026 zu Vorträgen, Workshops, Stammtischen,
Exkursionen und Hackathons ein. Im Sommersemester 2026 (ab 20. April) bekam jede Anmeldung per Münzwurf am Vorabend
eine Erinnerung oder nicht.

### personen.csv (eine Zeile je Person)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `person` | Text | Kennung `P-0001` ff. |
| `studiengang` | Text | Studiengang |
| `fachsemester_start` | Ganzzahl | Fachsemester bei der ersten Anmeldung |
| `mitglied` | 0 oder 1 | 1, wenn die Person Mitglied im Verein ist |

### veranstaltungen.csv (eine Zeile je Veranstaltung)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `veranstaltung` | Text | Kennung `V-001` ff. |
| `datum` | Datum (Text `JJJJ-MM-TT`) | Tag der Veranstaltung |
| `beginn` | Text `HH:MM` | Uhrzeit des Beginns |
| `typ` | Text | Vortrag, Workshop, Stammtisch, Exkursion oder Hackathon |
| `thema` | Text | Thema |
| `plaetze` | Ganzzahl | Plätze im Raum (bei Exkursionen im Bus) |
| `catering` | 0 oder 1 | 1, wenn es Essen gab |

### anmeldungen.csv (eine Zeile je Anmeldung)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `anmeldung` | Text | Kennung `A-00001` ff. |
| `veranstaltung` | Text | passt zu `veranstaltungen.csv` |
| `person` | Text | passt zu `personen.csv` |
| `angemeldet_am` | Datum (Text) | Tag der Anmeldung |
| `erinnerung` | 0 oder 1, leer | 1 mit Erinnerung am Vorabend, 0 ohne; leer, wenn es keine Erinnerungen gab |
| `erschienen` | 0 oder 1 | 1, wenn die Person gekommen ist |

Bisher nimmt der Verein höchstens so viele Anmeldungen an, wie Plätze da sind. Vorlesungszeiten: Wintersemester 2024/25
vom 14. Oktober 2024 bis 14. Februar 2025, Sommersemester 2025 vom 22. April bis 25. Juli 2025, Wintersemester 2025/26
vom 20. Oktober 2025 bis 13. Februar 2026, Sommersemester 2026 vom 20. April bis 24. Juli 2026. In den Prüfungsphasen
dazwischen gibt es nur Stammtische.

**Annahmen des Vorstands:** Eine Erinnerung kostet 0,10 Euro und etwas Arbeit; der Vorstand führt sie ein, wenn sie die
Teilnahme um mindestens 3 Prozentpunkte erhöht. Mehr Personen als Plätze darf es höchstens bei einer von 20
Veranstaltungen geben (5 %), bei Exkursionen mit dem Bus (25 Plätze) höchstens bei einer von 100 (1 %).

## Track B · Nordwerk GmbH (zustandsbasierte Wartung)

Die 20 Maschinen aus `maschinen.csv` der Kursdaten, je Produktionstag vom 1. Oktober 2024 bis 29. September 2026. Seit
dem 12. Januar 2026 läuft an acht Maschinen ein Pilot mit einem Warnsystem: Liegt die mittlere Schwingung eines Tages
mehr als 35 % über dem Median der letzten 20 Produktionstage derselben Maschine, gibt es einen Alarm und noch am selben
Tag eine Kurzinspektion. Für den Pilot hat die Instandhaltungsleitung die acht Maschinen mit dem meisten ungeplanten
Stillstand im 4. Quartal 2025 ausgewählt. Am 2. März 2026 hat der Einkauf an allen Maschinen auf einen neuen Schmierstoff
umgestellt.

### maschinen.csv (20 Zeilen)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `maschine` | Text | Kennung `M-01` bis `M-20` |
| `name`, `linie`, `typ`, `baujahr` | | wie in den Kursdaten |
| `pilot` | 0 oder 1 | 1 für die acht Pilotmaschinen |
| `pilot_start` | Datum (Text), leer | Beginn des Pilots |

### maschinentage.csv (eine Zeile je Maschine und Produktionstag)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `datum` | Datum (Text `JJJJ-MM-TT`) | Produktionstag |
| `maschine` | Text | `M-01` bis `M-20` |
| `laufzeit_h` | Ganzzahl | geplante Laufzeit in Stunden (24 an Werktagen, 8 an Samstagen mit Frühschicht) |
| `vibration_mm_s` | Kommazahl | mittlere Schwingstärke des Tages in mm/s |
| `lagertemp_c` | Kommazahl | mittlere Lagertemperatur des Tages in Grad Celsius |
| `strom_pct` | Kommazahl | mittlere Stromaufnahme in Prozent der Nennleistung |
| `stillstand_min` | Ganzzahl | ungeplanter Stillstand durch technische Störungen in Minuten, auf 5 gerundet |
| `ausfall_morgen` | 0 oder 1 | 1, wenn die Maschine am nächsten Produktionstag mindestens 60 Minuten ungeplant stillsteht |
| `alarm` | 0 oder 1, leer | Alarm des Warnsystems; leer außerhalb des Pilots |
| `inspektion_min` | Ganzzahl, leer | geplanter Stillstand durch die Kurzinspektion (30 Minuten, 45 mit Befund); leer außerhalb des Pilots |

**Annahmen der Werkleitung:** Eine Minute ungeplanter Stillstand kostet 20 Euro, eine Kurzinspektion 400 Euro
(geplanter Stillstand und Personal), das Warnsystem 5.000 Euro je Maschine und Jahr.

## Bekannte Eigenheiten

- Alle Datumsangaben liegen als Text vor. Zum Rechnen mit `pd.to_datetime` umwandeln.
- Die Pakete lassen sich mit `zipfile` aus der Standardbibliothek entpacken; die Vorlage im Notebook zu Modul 14 macht das.
- Zahlen aus verschiedenen Paketen sind nicht vergleichbar: Jedes Paket ist eine eigene Simulation.
