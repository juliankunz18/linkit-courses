# Data Science 1

Notebooks und Daten zum Selbstlernkurs **Data Science 1** von linkit e.V. auf **linkit courses**, dem Einstieg in Data Science: Tabellen, Datenbanken, Statistik und Modelle an den Werksdaten der erfundenen Nordwerk GmbH. Lerneinheiten, Tutoriumsblätter und Selbsttests liegen auf der Lernplattform, hier liegen die Notebooks zum Mitrechnen und die Daten.

**Testseite (Pilot mit Modul 0 bis 13):** https://juliankunz18.github.io/linkit-courses/ds1.html. Dort laufen die Notebooks direkt im Browser, Colab ist die Alternative.

| Modul | Thema | Stand | Notebook in Colab öffnen |
|---|---|---|---|
| 0 | Vorkurs: Python in 3 Stunden | verfügbar, gleich wie im Kurs AI Engineering | [W00_Python-in-3-Stunden_Selbstlernen](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/ai-engineering/W00/W00_Python-in-3-Stunden_Selbstlernen.ipynb) |
| 1 | Python-Crashkurs: Werksdaten verarbeiten | verfügbar, gleich wie im Kurs AI Engineering | [W01_Python-Crashkurs_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/ai-engineering/W01/W01_Python-Crashkurs_Teilnehmende.ipynb) |
| 2 | Tabellen mit pandas | verfügbar | [W02_pandas_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W02/W02_pandas_Teilnehmende.ipynb) |
| 3 | SQL und Datenqualität | verfügbar | [W03_SQL-Datenqualitaet_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W03/W03_SQL-Datenqualitaet_Teilnehmende.ipynb) |
| 4 | Explorative Analyse und Visualisierung | verfügbar | [W04_Explorative-Analyse_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W04/W04_Explorative-Analyse_Teilnehmende.ipynb) |
| 5 | Zufall simulieren: Wahrscheinlichkeit, Bootstrap, Permutation | verfügbar | [W05_Zufall-simulieren_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W05/W05_Zufall-simulieren_Teilnehmende.ipynb) |
| 6 | Schätzen und Testen | verfügbar | [W06_Schaetzen-Testen_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W06/W06_Schaetzen-Testen_Teilnehmende.ipynb) |
| 7 | Lineare Regression | verfügbar | [W07_Lineare-Regression_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W07/W07_Lineare-Regression_Teilnehmende.ipynb) |
| 8 | Klassifikation und Modellbewertung | verfügbar | [W08_Klassifikation_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W08/W08_Klassifikation_Teilnehmende.ipynb) |
| 9 | Bäume, Ensembles und Feature Engineering | verfügbar | [W09_Baeume-Ensembles_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W09/W09_Baeume-Ensembles_Teilnehmende.ipynb) |
| 10 | Unüberwachtes Lernen | verfügbar | [W10_Unueberwachtes-Lernen_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W10/W10_Unueberwachtes-Lernen_Teilnehmende.ipynb) |
| 11 | Zeitreihen und Forecasting | verfügbar | [W11_Zeitreihen-Forecasting_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W11/W11_Zeitreihen-Forecasting_Teilnehmende.ipynb) |
| 12 | Experimente und A/B-Tests | verfügbar | [W12_Experimente-AB-Tests_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W12/W12_Experimente-AB-Tests_Teilnehmende.ipynb) |
| 13 | Kausale Inferenz mit Beobachtungsdaten | verfügbar | [W13_Kausale-Inferenz_Teilnehmende](https://colab.research.google.com/github/juliankunz18/linkit-courses/blob/main/data-science-1/W13/W13_Kausale-Inferenz_Teilnehmende.ipynb) |
| 14 | Projektwerkstatt zu zweit | in Arbeit | |

## Daten

Im Ordner [`daten/`](daten/) liegen die Dateien, die die Notebooks laden: `produktion.csv`, `stoerungen.csv`, `maschinen.csv`, `linien.csv`, `wochenbericht_breit.csv`, `nordwerk_roh.db`, `lieferungen.csv`, `messwerte.csv`, `sensordaten.csv`, `haerterei.csv`, `zyklen.csv`, `energie.csv`, `schleifversuch.csv`, `portal_konten.csv`, `portal_sitzungen.csv`, `schulung.csv`, `ruestvorgaenge.csv`. Jede Tabelle ist in [`DATENBLATT.md`](daten/DATENBLATT.md) und [`DATENBLATT_ROH.md`](daten/DATENBLATT_ROH.md) beschrieben. Die Datenzelle am Anfang jedes Notebooks lädt fehlende Dateien von hier nach. Alle Daten sind erfunden.

## So arbeitest du mit den Notebooks in Colab

1. Link anklicken, das Notebook öffnet sich in Colab (Google-Konto nötig).
2. **Datei → Kopie in Drive speichern.** Sonst ist deine Arbeit nach einer Pause weg.
3. Zellen von oben nach unten ausführen. Nach jeder Aufgabe zeigt ein Selbsttest ✅ oder ❌.

Das Abschlussprojekt zu zweit mit Abnahme durch einen linkit Expert kommt später dazu. Die Lösungs-Notebooks liegen nicht in diesem Repository.
