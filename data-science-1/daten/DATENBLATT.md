# Datenblatt: Nordwerk-Werksdaten

**Herkunft:** synthetisch, erzeugt mit `nordwerk_ds/generate.py`, `nordwerk_ds/lieferungen.py`, `nordwerk_ds/sensoren.py`, `nordwerk_ds/haerterei.py`, `nordwerk_ds/zyklen.py`, `nordwerk_ds/energie.py` und `nordwerk_ds/versuche.py` (Seed 2026) für den Kurs Data Science 1 von linkit courses. Die Nordwerk GmbH ist erfunden. Ähnlichkeiten mit echten Werken sind gewollt, echte Messwerte stecken nicht darin.

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
| `hallentemp_c` | Grad Celsius | mittlere Temperatur am Logger der Linie während der Schicht (Linien in derselben Halle messen an verschiedenen Stellen) |

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

## lieferungen.csv (eine Zeile je Wareneingang, 4.624 Zeilen)

Aus dem Wareneingang: jede Anlieferung eines Lieferanten mit zugesagtem Zeitfenster, tatsächlicher Ankunft und dem Ergebnis der Eingangsprüfung. Geliefert wird nur an Arbeitstagen (Montag bis Freitag, ohne Feiertage und Werksruhe).

| Spalte | Typ | Bedeutung |
|---|---|---|
| `lieferung_id` | Text | Kennung `LF-00001` ff., eindeutig |
| `lieferant` | Text | Kennung des Lieferanten, `L-01` bis `L-06` |
| `material` | Text | Stahl-Rohteile (L-01), Bleche (L-02), Elektronik (L-03), Normteile (L-04), Gussgehäuse (L-05), Verpackung (L-06) |
| `bestellt_am` | Datum (Text `JJJJ-MM-TT`) | Tag der Bestellung |
| `soll_termin` | Zeitpunkt (Text `JJJJ-MM-TT HH:MM`) | Beginn des zugesagten Anlieferfensters, volle Stunde zwischen 6 und 20 Uhr |
| `ist_ankunft` | Zeitpunkt (Text `JJJJ-MM-TT HH:MM`) | tatsächliche Ankunft an der Warenannahme |
| `verzug_h` | Kommazahl | Ankunft minus Soll-Termin in Stunden, auf 0,1 gerundet; negativ heißt zu früh |
| `menge` | Ganzzahl | gelieferte Stückzahl |
| `geprueft_stueck` | Ganzzahl | Stichprobe der Eingangsprüfung: 50 Stück, ab 1.000 gelieferten Stück 80 |
| `mangel_stueck` | Ganzzahl | davon mangelhaft |

Als **verspätet** gilt im Werk eine Lieferung, die mehr als 2 Stunden nach dem Soll-Termin ankommt (`verzug_h > 2`). L-05 liefert Gussgehäuse für eine Kleinserie und hat deshalb nur wenige Lieferungen.

## messwerte.csv (Wellendurchmesser aus der Endkontrolle, 5.652 Zeilen)

Endkontrolle der Wellenfertigung (Linie 1): An jedem Werktag von Montag bis Freitag (ohne Feiertage und Werksruhe) werden in jeder Schicht je Drehmaschine zwei zufällig gewählte Wellen gemessen. Samstagsschichten sind nicht erfasst. Sollmaß 25,000 mm, Toleranz ±0,025 mm (24,975 bis 25,025 mm).

| Spalte | Typ | Bedeutung |
|---|---|---|
| `datum` | Datum (Text `JJJJ-MM-TT`) | Tag der Messung |
| `schicht` | Text | `Früh`, `Spät` oder `Nacht` |
| `maschine` | Text | `M-03` (CNC-Drehmaschine, Baujahr 2009) oder `M-09` (CNC-Drehmaschine 2, Baujahr 2020) |
| `durchmesser_mm` | Kommazahl | gemessener Durchmesser in Millimetern, auf 0,001 mm gerundet |

## sensordaten.csv (Zustandsüberwachung, eine Zeile je Maschine und Produktionsschicht, 28.920 Zeilen)

Alle 20 Maschinen tragen Sensoren zur Zustandsüberwachung. Je Schicht wird der Mittelwert gespeichert. Die letzte Schicht des Zeitraums fehlt, weil es für sie keine nächste Schicht gibt.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `datum` | Datum (Text `JJJJ-MM-TT`) | Produktionstag |
| `schicht` | Text | `Früh`, `Spät` oder `Nacht` |
| `maschine` | Text | `M-01` bis `M-20`, passt zu `maschinen.csv` |
| `vibration_mm_s` | Kommazahl | Schwingstärke (Effektivwert der Schwinggeschwindigkeit) in mm/s |
| `lagertemp_c` | Kommazahl | Temperatur am Hauptlager in Grad Celsius |
| `strom_pct` | Kommazahl | Stromaufnahme in Prozent der Nennleistung |
| `ausfall_naechste` | 0 oder 1 | 1, wenn die Maschine in der **nächsten** Produktionsschicht mechanische Störungen mit zusammen mindestens 60 Minuten Stillstand hat (aus `stoerungen.csv`); sonst 0 |

Die nächste Produktionsschicht ist die nächste Schicht im Arbeitskalender, nach einer Freitagsnachtschicht also die Frühschicht am Samstag, wenn dort gearbeitet wird, sonst am Montag. Fehlt ein Messwert, war der Sensor in dieser Schicht ausgefallen (leeres Feld). Am 2. März 2026 wurden die Schwingungssensoren an allen Maschinen der Linie 2 gegen ein neues Modell getauscht.

## haerterei.csv (Härterei, eine Zeile je Ofencharge, 2.816 Zeilen)

Im Härteofen M-10 der Wellenfertigung (Linie 1) werden Wellen chargenweise erwärmt, gehalten und im Ölbad abgeschreckt. Danach misst die Qualitätssicherung die Oberflächenhärte an einer Probewelle der Charge. Gehärtet wird an Werktagen von Montag bis Freitag.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `charge_id` | Text | Kennung `C-00001` ff., eindeutig |
| `datum` | Datum (Text `JJJJ-MM-TT`) | Tag der Charge |
| `schicht` | Text | `Früh`, `Spät` oder `Nacht` |
| `ofentemp_c` | Ganzzahl | eingestellte Ofentemperatur in Grad Celsius |
| `haltezeit_min` | Ganzzahl | Haltezeit im Ofen in Minuten |
| `chargengewicht_kg` | Ganzzahl | Gewicht der Charge in Kilogramm |
| `kohlenstoff_pct` | Kommazahl | Kohlenstoffgehalt des Stahls in Prozent laut Prüfzeugnis des Materialloses |
| `oeltemp_c` | Kommazahl | Temperatur des Abschrecköls in Grad Celsius |
| `transfer_s` | Kommazahl | Zeit vom Öffnen des Ofens bis zum Eintauchen ins Öl in Sekunden |
| `haerte_hrc` | Kommazahl | gemessene Oberflächenhärte in HRC (Rockwell C) |
| `in_toleranz` | 0 oder 1 | 1, wenn die Härte zwischen 52 und 58 HRC liegt (Zeichnungsvorgabe), sonst 0 |

Die Einstellungen wählen die Bedienenden innerhalb der Arbeitsanweisung (Sollwerte 870 °C und 75 Minuten). Bei schweren Chargen verlängern sie die Haltezeit oft etwas.

## zyklen.csv (Bearbeitungszyklen der Fräszentren M-01 und M-02, eine Zeile je Zyklus, 8.426 Zeilen)

Pilotprojekt der Linie 2: Seit dem 1. Juli 2026 hängt an den beiden Fräszentren M-01 und M-02 je eine nachgerüstete Messbox. Sie erkennt jeden Bearbeitungszyklus (Programmstart bis Programmende der Spindel) und speichert dafür Kennwerte. Erfasst sind alle Zyklen vom 1. Juli bis 30. September 2026. Die Box hat keinen Zugang zur CNC-Steuerung und kennt das gefahrene Programm nicht. Seit dem **14. September 2026** ordnet der Leitstand jedem Zyklus das CNC-Programm zu; davor ist die Spalte `programm` leer.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `zyklus_id` | Text | Kennung `Z-00001` ff., eindeutig, nach Beginn sortiert |
| `maschine` | Text | `M-01` (CNC-Fräszentrum 1, Baujahr 2014) oder `M-02` (CNC-Fräszentrum 2, Baujahr 2017) |
| `datum` | Datum (Text `JJJJ-MM-TT`) | Produktionstag; bei der Nachtschicht der Tag, an dem die Schicht begann |
| `schicht` | Text | `Früh`, `Spät` oder `Nacht` |
| `beginn` | Zeitpunkt (Text `JJJJ-MM-TT HH:MM:SS`) | Start des Zyklus (Kalenderzeit; nach Mitternacht steht hier schon der nächste Kalendertag) |
| `dauer_s` | Ganzzahl | Dauer des Zyklus in Sekunden |
| `energie_kwh` | Kommazahl | elektrische Energie der Maschine während des Zyklus in kWh |
| `leistung_max_kw` | Kommazahl | höchste elektrische Leistung während des Zyklus in kW |
| `vibration_mm_s` | Kommazahl | Schwingstärke am Spindelgehäuse (Effektivwert der Schwinggeschwindigkeit über den Zyklus) in mm/s |
| `kuehlmittel_bar` | Kommazahl | mittlerer Druck des Kühlmittels während des Zyklus in bar |
| `spindeltemp_c` | Kommazahl | Temperatur am Spindelgehäuse am Ende des Zyklus in Grad Celsius; leer, wenn der Sensor keinen Wert lieferte |
| `programm` | Text | CNC-Programm laut Leitstand, erst ab 14. September 2026, davor leer |

Zwischen zwei Zyklen liegen Nebenzeiten: Werkstück wechseln, Rüsten, Prüfen, Pausen und Stillstände. Störungen der beiden Maschinen stehen wie immer in `stoerungen.csv` (Schlüssel `datum`, `schicht`, `maschine`).

## energie.csv (Energieverbrauch des Werks, eine Zeile je Kalendertag, 730 Zeilen)

Das Energiemanagement liest jeden Morgen die Zähler am Netzanschluss (Strom) und an der Gasübergabe ab, die Werte gelten für den ganzen Standort und den Kalendertag von 0 bis 24 Uhr. Dazu kommen die werkseigene Wetterstation und die Wettervorhersage, die am Vortag um 9 Uhr abgerufen wird. Jede Zeile ist ein Kalendertag, auch Sonntage, Feiertage und die Werksruhe.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `datum` | Datum (Text `JJJJ-MM-TT`) | Kalendertag |
| `strom_kwh` | Ganzzahl | Stromverbrauch des Werks in kWh; leer, wenn die Datenübertragung ausgefallen ist |
| `gas_kwh` | Ganzzahl | Erdgasverbrauch des Werks in kWh (Hallenheizung, Härteofen, Warmwasser); leer wie `strom_kwh` |
| `aussentemp_c` | Kommazahl | gemessene Tagesmitteltemperatur der Wetterstation in Grad Celsius |
| `temp_vorhersage_c` | Kommazahl | vorhergesagte Tagesmitteltemperatur für diesen Tag, abgerufen am Vortag um 9 Uhr |

Fällt die Datenübertragung aus, bleiben `strom_kwh` und `gas_kwh` an diesem Tag leer. Die Zähler zählen weiter, deshalb steht am folgenden Tag der Verbrauch beider Tage zusammen. Gesteuert wird der Strombezug über eine Prognose, die am Vormittag für den nächsten Tag abgegeben wird. Zu diesem Zeitpunkt ist der laufende Tag noch nicht abgelesen. Was im Werk am nächsten Tag geplant ist (Schichten und geplante Stückzahl, siehe `produktion.csv`), steht dann schon fest.

## schleifversuch.csv (Versuch mit einer neuen Schleifscheibe an M-04, eine Zeile je Los, 120 Zeilen)

Die Wellenfertigung hat an der Rundschleifmaschine M-04 eine neue Schleifscheibe (B) gegen die bisherige (A) geprüft, vom 8. Juni bis 17. Juli 2026, montags bis freitags. In jeder Früh- und Spätschicht wurden zwei Lose geschliffen, eines mit jeder Scheibe. Welche Scheibe zuerst lief, hat vor Schichtbeginn ein Münzwurf am Rechner entschieden. Die Wellen eines Loses stammen aus einer Härtecharge des vorigen Härtetags, die in Toleranz war (`charge_id`, siehe `haerterei.csv`). Nach dem Schleifen misst die Qualitätssicherung an fünf Wellen des Loses die Rauheit und mittelt sie; die Schleifzeit stammt aus der Maschinensteuerung.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `los_id` | Text | Kennung `L-001` ff., eindeutig |
| `datum` | Datum (Text `JJJJ-MM-TT`) | Tag des Schleifens |
| `schicht` | Text | `Früh` oder `Spät` |
| `reihenfolge` | Ganzzahl | 1 für das erste, 2 für das zweite Los der Schicht |
| `scheibe` | Text | `A` (bisherige Scheibe) oder `B` (neue Scheibe) |
| `charge_id` | Text | Härtecharge, aus der die Wellen stammen, passt zu `haerterei.csv` |
| `wellen` | Ganzzahl | Zahl der Wellen im Los |
| `ra_um` | Kommazahl | mittlere Rauheit Ra der fünf gemessenen Wellen in Mikrometer; kleiner ist besser |
| `schleifzeit_s` | Kommazahl | mittlere Schleifzeit je Welle in Sekunden |

## portal_konten.csv (A/B-Test im Ersatzteilportal, eine Zeile je Kundenkonto, 2.548 Zeilen)

Im Ersatzteilportal der Nordwerk GmbH bestellen Geschäftskunden Ersatz- und Verschleißteile. Vom 31. August bis 27. September 2026 lief ein A/B-Test: Variante B zeigt auf der Startseite einen Knopf „Schnell nachbestellen“ mit den zuletzt bestellten Teilen, Variante A die bisherige Seite. Beim ersten Besuch im Versuchszeitraum teilt das Portal jedes Kundenkonto per Zufall mit Wahrscheinlichkeit 1/2 einer Variante zu; das Konto sieht danach immer dieselbe Variante. Die Tabelle enthält alle Konten, die im Versuchszeitraum mindestens einmal das Portal besucht haben.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `konto` | Text | Kennung `K-0001` ff., eindeutig |
| `gruppe` | Text | zugeteilte Variante, `A` oder `B` |
| `branche` | Text | Branche des Kunden: Maschinenbau, Fahrzeugbau, Landtechnik, Lebensmittel, Energie, Handel |
| `umsatz_vorjahr_eur` | Ganzzahl | Umsatz des Kunden mit der Nordwerk GmbH im Vorjahr in Euro, auf 10 gerundet; 0 bei Neukunden |
| `umsatz_vorperiode_eur` | Kommazahl | Umsatz des Kontos im Portal in den vier Wochen vor dem Versuch in Euro |
| `erster_besuch` | Datum (Text `JJJJ-MM-TT`) | Tag des ersten Besuchs im Versuchszeitraum, an dem die Zuteilung erfolgte |

## portal_sitzungen.csv (A/B-Test im Ersatzteilportal, eine Zeile je Sitzung, 17.658 Zeilen)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `sitzung_id` | Text | Kennung `S-000001` ff., eindeutig, nach Datum sortiert |
| `konto` | Text | Kundenkonto, passt zu `portal_konten.csv` |
| `datum` | Datum (Text `JJJJ-MM-TT`) | Tag der Sitzung |
| `gruppe` | Text | Variante, die das Konto in dieser Sitzung gesehen hat |
| `bestellt` | 0 oder 1 | 1, wenn in der Sitzung eine Bestellung abgeschickt wurde |
| `umsatz_eur` | Kommazahl | Bestellwert der Sitzung in Euro, 0 ohne Bestellung |

Ein Konto kann im Versuchszeitraum viele Sitzungen haben; zugeteilt wurde je Konto, nicht je Sitzung.

## Bekannte Eigenheiten

- Die Ausschussquote ist ein Anteil an den gefertigten Stück (`ausschuss_stueck / ist_stueck`), nicht an den geplanten.
- Nachtschichten sind kleiner geplant als Früh- und Spätschichten. Wer Quoten über Schichten mittelt, muss das berücksichtigen.
- `datum` liegt als Text vor. Damit pandas damit rechnen kann, muss die Spalte in einen Zeitstempel umgewandelt werden.
- `soll_termin` und `ist_ankunft` liegen als Text vor. `verzug_h` ist schon daraus berechnet; wer selbst rechnet, wandelt beide Spalten mit `pd.to_datetime` um.
- Die Messwerte sind Stichproben: Aus ihnen lässt sich schätzen, wie viele Wellen außerhalb der Toleranz liegen, gezählt wurden aber nicht alle Wellen.
