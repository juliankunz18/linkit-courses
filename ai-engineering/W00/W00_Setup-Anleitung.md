# Setup-Anleitung · AI Engineering: von LLMs zu Agenten

Bitte vor dem ersten Termin erledigen. Zeitbedarf: etwa 15 Minuten, dazu rund drei Stunden für das Selbstlern-Notebook.

## Was ihr braucht

- Einen Laptop mit aktuellem Browser (Chrome, Firefox, Edge oder Safari)
- Ein Google-Konto für Google Colab. Ein privates Konto reicht. Ihr müsst nichts installieren.
- Euren KIT-Account für die **KI-Toolbox des KIT**. Darüber laufen alle Sprachmodelle im Kurs.

## Schritt für Schritt

1. **Notebook öffnen.** Öffnet den Link zum Notebook `W00_Python-in-3-Stunden_Selbstlernen.ipynb`, den ihr vom Kursleiter bekommen habt. Erscheint eine Warnung, dass das Notebook nicht von Google stammt, wählt „Trotzdem ausführen“.
2. **Eigene Kopie speichern.** *Datei → Kopie in Drive speichern*. Ab jetzt arbeitet ihr nur noch in dieser Kopie.
3. **Erste Zelle ausführen.** Klickt in die erste Codezelle und drückt Shift + Enter. Erscheint „Hallo aus Python!“, läuft alles.
4. **Kapitel 0 bis 7 durcharbeiten.** Ein ❌ in einem Selbsttest ist kein Problem, sondern ein Hinweis.
5. **Schlüssel für die KI-Toolbox erstellen** (Kapitel 8):
   - https://ki-toolbox.scc.kit.edu/ öffnen und mit dem KIT-Account anmelden.
   - In den Einstellungen unter *Konto* einen **API-Schlüssel** erstellen. Er beginnt mit `sk-`. Nicht das Anmelde-Token nehmen, das mit `eyJ` beginnt.
6. **Schlüssel als Secret anlegen:**
   - In Colab in der linken Seitenleiste auf das **Schlüssel-Symbol** klicken.
   - Neues Secret hinzufügen: Name `KIT_TOOLBOX_KEY`, Wert = euer Schlüssel.
   - Den Schalter für den **Notebook-Zugriff** einschalten.
7. **Setup-Check ausführen.** Die beiden letzten Codezellen installieren die OpenAI-Bibliothek und schicken eine Testanfrage an ein Modell der KI-Toolbox. Erscheint ein Begrüßungssatz, seid ihr startklar.

## Regeln für den Schlüssel

Der Schlüssel funktioniert wie ein Passwort und läuft auf euer KIT-Konto.
- Nie in eine Codezelle schreiben, immer nur als Colab-Secret.
- Nie teilen, nie auf GitHub hochladen, nie auf Screenshots zeigen.
- Ist er versehentlich öffentlich geworden: in der KI-Toolbox löschen und einen neuen erstellen.

Für euch entstehen keine Kosten. Die Toolbox ist ein Dienst des KIT mit **Fair Use**: Nutzung im üblichen Umfang ist in Ordnung, große automatisierte Läufe sprechen wir vorher mit dem SCC ab.

## Wenn etwas nicht klappt

| Meldung | Ursache | Lösung |
|---|---|---|
| Fehler mit „Secret“ im Text | Secret fehlt, ist anders benannt oder der Notebook-Zugriff ist aus | Name exakt `KIT_TOOLBOX_KEY`, Schalter einschalten |
| `AuthenticationError` mit 401 | Schlüssel falsch kopiert, Anmelde-Token statt API-Schlüssel, oder Schlüssel gelöscht | Neuen API-Schlüssel erstellen und als Secret eintragen |
| `NotFoundError` oder Meldung zum Modell | Modellname falsch oder Modell nicht verfügbar | Kursleiter fragen, das aktuelle Modell steht im Notebook |
| `ModuleNotFoundError: No module named 'openai'` | Installationszelle nicht ausgeführt | Zelle mit `%pip install` ausführen |
| `NameError` | Eine Zelle davor wurde nicht ausgeführt | *Laufzeit → Vorherige Zellen ausführen* |
| Variablen sind plötzlich weg | Colab hat die Laufzeit nach einer Pause getrennt | *Laufzeit → Alle ausführen* |

Klappt es trotzdem nicht: Schreibt dem Kursleiter **vor** dem ersten Termin, mit einem Screenshot der letzten Fehlerzeile (ohne Schlüssel).

## Datenschutz

Die Modelle mit `kit.` im Namen laufen auf Servern des SCC am KIT, eure Eingaben verlassen das KIT nicht. Colab selbst ist aber ein Dienst von Google. Ladet deshalb keine personenbezogenen Daten hoch, weder eigene noch fremde. Alle Kursdaten sind erfunden.
