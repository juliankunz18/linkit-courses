# Advanced Data Science und Advanced AI Engineering

Notebooks und Daten zu den beiden Advanced-Kursen von linkit e.V. auf **linkit courses**. Beide Kurse machen dich jobfertig: Ab Modul 0 arbeitest du auf deinem eigenen Laptop mit VS Code, uv und Git in einem eigenen Repository, mit Tests, Review und CI. Lerneinheiten, Tutoriumsblätter und Selbsttests liegen auf der Lernplattform, hier liegen die Notebooks und die Daten.

Die Module 0, 1 und 13 sind gemeinsam: Sie stehen einmal in diesem Ordner und zählen für beide Kurse. Kurseigene Module liegen in `advanced-data-science/` (entsteht mit dem ersten kurseigenen Modul) und `advanced-ai-engineering/` (entsteht mit dem ersten kurseigenen Modul).

## Advanced Data Science

Nach Data Science 1: große Daten, Pipelines, die halten, erklärbare Modelle und Wirkungen schätzen bis Double ML, im eigenen Repo mit Tests und CI. Voraussetzung: Data Science 1. Dein Repository heißt `nordwerk-analysen`, das Paket darin `nordwerk`.

**Testseite (Pilot mit Modul 0 und 1):** https://juliankunz18.github.io/linkit-courses/advanced-ds.html

| Modul | Thema | Stand | Orte | Notebook |
|---|---|---|---|---|
| 0 | Deine Entwicklungsumgebung (gemeinsam) | verfügbar | Browser, Laptop | [W00_Entwicklungsumgebung_Teilnehmende](W00/W00_Entwicklungsumgebung_Teilnehmende.ipynb) |
| 1 | Git, Tests und Teamarbeit (gemeinsam) | verfügbar | Browser, Laptop | [W01_Git-und-Tests_Teilnehmende](W01/W01_Git-und-Tests_Teilnehmende.ipynb) |
| 2 | Große Daten und Datenverträge | in Arbeit | | |
| 3 | ML-Pipelines, die halten | in Arbeit | | |
| 4 | Modelle erklären, Fehler finden, Drift erkennen | in Arbeit | | |
| 5 | Methoden per Simulation prüfen | in Arbeit | | |
| 6 | Experimente, wenn nicht alle mitmachen | in Arbeit | | |
| 7 | Doppelt robust und Double ML | in Arbeit | | |
| 8 | Heterogene Effekte und gezieltes Handeln | in Arbeit | | |
| 9 | Gestaffelte Einführung | in Arbeit | | |
| 10 | Schwellen und Instrumente | in Arbeit | | |
| 11 | Sensitivität und Refutation | in Arbeit | | |
| 12 | Analysen in Betrieb | in Arbeit | | |
| 13 | Kundenarbeit, Team und Englisch (gemeinsam) | in Arbeit | | |
| 14 | Projektwerkstatt zu zweit | in Arbeit | | |

## Advanced AI Engineering

Nach AI Engineering: Training und Fine-Tuning, drei Anbieter, Inferenz messen, Dokumente im Großen und ein Dienst in der Cloud, im eigenen Repo mit Tests und CI. Voraussetzung: AI Engineering. Dein Repository heißt `nordwerk-assistent`, das Paket darin `nordwerk`.

**Testseite (Pilot mit Modul 0 und 1):** https://juliankunz18.github.io/linkit-courses/advanced-ai.html

| Modul | Thema | Stand | Orte | Notebook |
|---|---|---|---|---|
| 0 | Deine Entwicklungsumgebung (gemeinsam) | verfügbar | Browser, Laptop | [W00_Entwicklungsumgebung_Teilnehmende](W00/W00_Entwicklungsumgebung_Teilnehmende.ipynb) |
| 1 | Git, Tests und Teamarbeit (gemeinsam) | verfügbar | Browser, Laptop | [W01_Git-und-Tests_Teilnehmende](W01/W01_Git-und-Tests_Teilnehmende.ipynb) |
| 2 | Training in PyTorch | in Arbeit | | |
| 3 | Hugging Face und Fine-Tuning | in Arbeit | | |
| 4 | LoRA, Quantisierung und Lizenzen | in Arbeit | | |
| 5 | Sichtprüfung mit Transfer Learning | in Arbeit | | |
| 6 | Drei Anbieter, eine Aufgabe | in Arbeit | | |
| 7 | Inferenz messen | in Arbeit | | |
| 8 | Dokumente im Großen | in Arbeit | | |
| 9 | Retrieval im Großen | in Arbeit | | |
| 10 | Evaluation im Betrieb | in Arbeit | | |
| 11 | Vom Notebook zum Dienst | in Arbeit | | |
| 12 | Betrieb und Cloud | in Arbeit | | |
| 13 | Kundenarbeit, Team und Englisch (gemeinsam) | in Arbeit | | |
| 14 | Projektwerkstatt zu zweit | in Arbeit | | |

## Daten

Im Ordner [`daten/`](daten/) liegen die Dateien, die die Notebooks laden: `lieferungen.zip`, `schichten.csv`, `nachlieferung.zip`. Jede Tabelle ist in [`DATENBLATT_LIEFERUNGEN.md`](daten/DATENBLATT_LIEFERUNGEN.md) beschrieben. Die Datenzelle am Anfang jedes Notebooks lädt fehlende Dateien von hier nach. Alle Daten sind erfunden.

## So arbeitest du mit den Notebooks

1. **Im Browser:** Auf der Testseite öffnest du das Notebook im Schritt Notebook. Python läuft dort ohne Installation, die Daten liegen schon bereit. Das ist zum Üben gedacht.
2. **In VS Code mit eigener Umgebung (Hauptweg):** Lade die Teilnehmenden-Fassung herunter (auf der Plattform im Schritt Notebook oder hier aus dem Modulordner), leg sie in dein Repository und wähl in VS Code als Kernel die Umgebung `.venv` deines Projekts. Modul 0 zeigt Schritt für Schritt, wie du die Umgebung mit uv einrichtest.
3. **In Colab:** nur bei Modulen, in deren Tabelle „Colab“ als Ort steht (vor allem in Advanced AI Engineering, wenn eine GPU nötig ist). Dort führt der Link „in Colab öffnen“ direkt zum Notebook.

Nach jeder Aufgabe zeigt ein Selbsttest ✅ oder ❌. Die Lösungs-Notebooks liegen nicht in diesem Repository.
