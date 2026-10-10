# Datenblatt: Rohdatenbank der Nordwerk GmbH (`nordwerk_roh.db`)

**Was das ist:** ein ungeprüfter Abzug aus vier Werkssystemen als SQLite-Datenbank, für den Kurs Data Science 1 von linkit courses. Die Nordwerk GmbH ist erfunden, alle Daten sind synthetisch, auch alle Namen, E-Mail-Adressen und Telefonnummern.

**Stand:** Abzug vom 1. Oktober 2026, Zeitraum 1. Oktober 2024 bis 30. September 2026 (Wartungen zusätzlich mit geplanten Terminen bis Ende November 2026).

**Achtung:** Die Daten kommen so, wie die Systeme sie liefern. Niemand hat sie geprüft. Die geprüften Fassungen von `schichten` und `stoerungen` kennst du aus Modul 2 (`produktion.csv`, `stoerungen.csv`).

| System | Tabellen |
|---|---|
| MES (Fertigungssteuerung) | `schichten` |
| Instandhaltung | `stoerungen`, `wartungen` |
| ERP (Aufträge und Kunden) | `auftraege` |
| Personalverwaltung | `bedienende` |
| Stammdaten | `linien`, `maschinen` |

## linien
`linie` (Schlüssel, 1 bis 4), `name`, `halle`, `kapazitaet_stueck` (höchstens mögliche Stückzahl pro Schicht).

## maschinen
`maschine` (Schlüssel, `M-01` bis `M-20`), `name`, `linie`, `halle`, `typ`, `baujahr`.

## schichten (MES, eine Zeile je Linie, Tag und Schicht)
`datum`, `linie`, `schicht` (Früh, Spät, Nacht), `soll_stueck`, `ist_stueck`, `ausschuss_stueck`, `personal`, `auslastung` (Anteil 0 bis 1), `hallentemp_c` (Grad Celsius, vom Temperaturlogger an der Linie; Linien in derselben Halle messen an verschiedenen Stellen). Fachlicher Schlüssel: `datum`, `linie`, `schicht`. In der Datenbank ist er nicht als Schlüssel hinterlegt.

## stoerungen (Instandhaltung, eine Zeile je Meldung)
`id`, `datum`, `schicht`, `maschine`, `kategorie` (mechanisch, elektrisch, Software, Material, Bedienung), `stillstand_min` (Minuten), `beschreibung`, `behoben` (1 oder 0). Die Kategorie wählt die meldende Person aus einer Liste; das Feld ist nicht verpflichtend.

## wartungen (Instandhaltung, geplante Wartungen)
`wartung_id` (Schlüssel), `maschine`, `datum`, `art` (Inspektion, Schmierung, Kalibrierung, Verschleißteile, Großwartung), `status` (erledigt oder geplant), `dauer_min` (nur bei erledigten Wartungen), `techniker` (Kürzel `T-01` bis `T-08`). Wartungsplan je Maschine: Inspektion etwa alle 6 Wochen, Schmierung alle 8, Kalibrierung und Verschleißteile alle 13, Großwartung einmal im Jahr (52 Wochen); die tatsächlichen Abstände schwanken um diese Werte.

## auftraege (ERP)
`auftrag_id` (Schlüssel), `kunde` (Kundennummer), `linie` (fertigende Linie), `menge` (Stück), `bestellt_am`, `liefertermin` (zugesagt), `geliefert_am` (leer, solange nicht geliefert), `status` (offen oder geliefert).

## bedienende (Personalverwaltung, personenbezogene Daten)
`personal_nr` (Schlüssel), `vorname`, `nachname`, `geburtsdatum`, `linie`, `schichtgruppe` (A, B, C), `eintritt`, `qualifikation`, `email`, `telefon`. Alle Personen sind erfunden. Behandle die Tabelle trotzdem so, als wären es echte Beschäftigte.

Datumsangaben stehen als Text in der Datenbank. SQLite kennt keinen eigenen Datumstyp.
