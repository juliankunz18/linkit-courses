# Datenblatt: Nordwerk-Werksdaten

**Herkunft:** synthetisch, erzeugt mit `nordwerk_ds/generate.py` (Seed 2026) für den Kurs Data Science 1 von linkit courses. Die Nordwerk GmbH ist erfunden. Ähnlichkeiten mit echten Werken sind gewollt, echte Messwerte stecken nicht darin.

**Zeitraum:** 1. Oktober 2024 bis 30. September 2026.

**Arbeitskalender:** Montag bis Freitag drei Schichten (Früh 6 bis 14 Uhr, Spät 14 bis 22 Uhr, Nacht 22 bis 6 Uhr). An manchen Samstagen eine Frühschicht, wenn die Auftragslage hoch ist. Keine Produktion an Sonntagen, an gesetzlichen Feiertagen in Baden-Württemberg, vom 24.12. bis 1.1. und in den Kalenderwochen 33 und 34 (Werksferien).

## linien.csv (4 Zeilen)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `linie` | Ganzzahl | Nummer der Fertigungslinie, 1 bis 4 |
| `name` | Text | Wellenfertigung, Gehäusefertigung, Schweißbaugruppen, Endmontage |
| `halle` | Ganzzahl | Halle, in der die Linie steht (1 bis 3) |
| `kapazitaet_stueck` | Ganzzahl | höchstens mögliche Stückzahl pro Schicht |

## maschinen.csv (20 Zeilen)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `maschine` | Text | Kennung `M-01` bis `M-20`, eindeutig |
| `name` | Text | Bezeichnung, zum Beispiel „CNC-Drehmaschine“ |
| `linie` | Ganzzahl | Linie, zu der die Maschine gehört |
| `halle` | Ganzzahl | Halle |
| `typ` | Text | Verfahren, zum Beispiel Zerspanung, Fügen, Montage |
| `baujahr` | Ganzzahl | Baujahr der Maschine |

## produktion.csv (eine Zeile je Linie, Tag und Schicht, 5.788 Zeilen)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `datum` | Datum (Text `JJJJ-MM-TT`) | Produktionstag |
| `linie` | Ganzzahl | Linie 1 bis 4 |
| `schicht` | Text | `Früh`, `Spät` oder `Nacht` |
| `soll_stueck` | Ganzzahl | geplante Stückzahl der Schicht |
| `ist_stueck` | Ganzzahl | tatsächlich gefertigte Stückzahl |
| `ausschuss_stueck` | Ganzzahl | davon fehlerhaft, also Ausschuss |
| `personal` | Ganzzahl | Anzahl Beschäftigte in der Schicht |
| `auslastung` | Anteil (0 bis 1) | geplante Stückzahl geteilt durch die Kapazität der Linie |
| `hallentemp_c` | Grad Celsius | mittlere Hallentemperatur während der Schicht |

Der Schlüssel einer Zeile ist die Kombination aus `datum`, `linie` und `schicht`.

## stoerungen.csv (eine Zeile je Störungsmeldung, 14.263 Zeilen)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `id` | Text | Kennung `S-00001` ff., eindeutig |
| `datum` | Datum (Text) | Tag der Störung |
| `schicht` | Text | Schicht, in der die Störung begann |
| `maschine` | Text | betroffene Maschine, passt zu `maschinen.csv` |
| `kategorie` | Text | mechanisch, elektrisch, Software, Material, Bedienung |
| `stillstand_min` | Ganzzahl | Stillstand in Minuten, auf 5 gerundet, 5 bis 480 |
| `beschreibung` | Text | Freitext aus der Meldung |
| `behoben` | Wahrheitswert | `False` nur bei offenen Meldungen der letzten zwei Wochen |

Erfasst sind Störungen ab 5 Minuten Stillstand. Eine Maschine kann in einer Schicht mehrere Meldungen haben.

## wochenbericht_breit.csv (eine Zeile je Kalenderwoche)

Der Wochenbericht, wie ihn die Werksleitung aus der Tabellenkalkulation bekommt: Spalte `kw` (zum Beispiel `2025-KW07`, Kalenderwoche nach ISO 8601) und je eine Spalte pro Linie und Schicht (`L1_Früh` bis `L4_Nacht`) mit der Summe der gefertigten Stück. Er ist aus `produktion.csv` abgeleitet und enthält keine neuen Informationen, nur ein anderes Format.

## Bekannte Eigenheiten

- Die Ausschussquote ist ein Anteil an den gefertigten Stück (`ausschuss_stueck / ist_stueck`), nicht an den geplanten.
- Nachtschichten sind kleiner geplant als Früh- und Spätschichten. Wer Quoten über Schichten mittelt, muss das berücksichtigen.
- `datum` liegt als Text vor. Damit pandas damit rechnen kann, muss die Spalte in einen Zeitstempel umgewandelt werden.
