# Datenblatt: Rohlieferungen beider Werke (`lieferungen.zip`)

**Herkunft:** synthetisch, für die Advanced-Kurse von linkit courses. Die Nordwerk GmbH ist erfunden. Die Zahlen des
Stammwerks sind dieselben wie in `produktion.csv` aus Data Science 1, nur so geliefert, wie das Fertigungssystem sie
ausgibt. Das Werk Illinois bei Chicago gehört seit Januar 2025 zu Nordwerk; seine Zahlen sind neu.

**Zeitraum:** Montag, 29. Juni 2026, bis Sonntag, 27. September 2026 (13 Kalenderwochen).

**Inhalt:** Das Zip enthält den Ordner `roh/` mit 73 Dateien: den Schichtmeldungen beider Werke und `liesmich.txt` von der
Werks-IT. Die Daten kommen so, wie die Werke sie schicken. Niemand hat sie geprüft.

## Stammwerk: `stammwerk_JJJJ-MM-TT.csv`

Eine Datei je Produktionstag (Montag bis Freitag, an manchen Samstagen eine Frühschicht; Werksferien vom 10. bis
21. August 2026). Export aus dem Fertigungssystem (MES): Trennzeichen Semikolon, Dezimalkomma, Datum `TT.MM.JJJJ`.

| Spalte | Bedeutung |
|---|---|
| `Datum` | Produktionstag |
| `Linie` | Fertigungslinie 1 bis 4 (Wellenfertigung, Gehäusefertigung, Schweißbaugruppen, Endmontage) |
| `Schicht` | `Früh`, `Spät` oder `Nacht` |
| `Soll` | geplante Stückzahl der Schicht |
| `Ist` | tatsächlich gefertigte Stückzahl |
| `Ausschuss` | davon fehlerhaft |
| `Personal` | Anzahl Beschäftigte in der Schicht |
| `Auslastung` | geplante Stückzahl geteilt durch die Kapazität der Linie |
| `Hallentemperatur` | mittlere Temperatur am Logger der Linie in Grad Celsius |

## Werk Illinois: `IL_shift_report_MMDDYYYY.csv`

Eine Datei je Woche, im Namen das Datum des Montags. Export aus dem Berichtswerkzeug des Werks: Trennzeichen Komma,
Dezimalpunkt, Datum `MM/DD/YYYY`, Spaltennamen auf Englisch. Gefertigt wird Montag bis Freitag in zwei Schichten, nicht an
US-Feiertagen.

| Spalte | Bedeutung |
|---|---|
| `Date` | Produktionstag |
| `Line` | `A` (Zerspanung) oder `B` (Montage) |
| `Shift` | `1st` (entspricht der Frühschicht) oder `2nd` (Spätschicht) |
| `Planned Qty` | geplante Stückzahl |
| `Actual Qty` | tatsächlich gefertigte Stückzahl |
| `Scrap Qty` | davon fehlerhaft (Ausschuss) |
| `Headcount` | Anzahl Beschäftigte |
| `Hall Temp (F)` | Hallentemperatur in Grad Fahrenheit |

## Ziel der Aufbereitung in Modul 0: `schichten.csv`

Eine Zeile je Werk, Tag, Linie und Schicht, beide Werke in einer Tabelle, Komma als Trennzeichen, Dezimalpunkt, UTF-8,
Zeilenende `\n`. Fachlicher Schlüssel: `werk`, `datum`, `linie`, `schicht`.

| Spalte | Bedeutung |
|---|---|
| `werk` | `Illinois` oder `Stammwerk` |
| `datum` | Produktionstag als `JJJJ-MM-TT` |
| `linie` | `1` bis `4` im Stammwerk, `A` oder `B` in Illinois |
| `schicht` | `Früh`, `Spät` oder `Nacht` |
| `soll_stueck`, `ist_stueck`, `ausschuss_stueck`, `personal` | ganze Zahlen |
| `hallentemp_c` | Grad Celsius mit einer Nachkommastelle, leer, wenn nicht gemessen |
| `quelle` | Name der Lieferdatei, aus der die Zeile stammt |

Wie genau die Datei aussehen muss (Reihenfolge, Format, Prüfsumme), steht im Notebook von Modul 0.

## Für Modul 1: `schichten.csv` und `nachlieferung.zip`

- **`schichten.csv`** ist das Ergebnis von `nordwerk import` aus Modul 0 für die Lieferungen oben: 892 Zeilen, Format wie im
  Abschnitt „Ziel der Aufbereitung“, Prüfsumme `0bc618f824be`. Das Notebook von Modul 1 rechnet daraus Kennzahlen für den
  Wochenbericht, damit es nicht von deinem eigenen Importer abhängt.
- **`nachlieferung.zip`** enthält den Ordner `nachlieferung/` mit den Schichtmeldungen vom 28. bis 30. September 2026
  (Montag bis Mittwoch der KW 40): drei Dateien aus dem Stammwerk, eine Wochendatei aus Illinois und `liesmich.txt`. Die
  Dateinamen folgen denselben Mustern wie oben. Ob sich sonst etwas geändert hat, findest du in Modul 1 heraus.
