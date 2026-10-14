## Worum geht es?

<!-- Ein, zwei Sätze: Was ändert sich, und warum? Gibt es ein Issue, steht seine Nummer in der
nächsten Zeile (etwa "Fixes #1"); GitHub schließt das Issue dann beim Merge. Ohne Issue: lösch
die Zeile und nenn hier den Anlass. -->

Fixes #

## Definition of Done

- [ ] Issue verlinkt (`Fixes #…` oben) oder der Anlass ohne Issue in einem Satz beschrieben
- [ ] Tests neu geschrieben oder angepasst, die das geänderte Verhalten prüfen
- [ ] `uv run pytest` lokal grün
- [ ] `uv run ruff format --check`, `uv run ruff check` und `uv run mypy src` grün (pre-commit)
- [ ] CI grün (grünes Häkchen bei „pruefen“)
- [ ] Review erledigt: Diff unter „Files changed“ gelesen, Kommentare beantwortet oder umgesetzt
- [ ] README oder Docstrings angepasst, wo sich Verhalten ändert
- [ ] Keine Daten (`daten/`), keine `.env`, keine Schlüssel, Passwörter oder Tokens im Commit
