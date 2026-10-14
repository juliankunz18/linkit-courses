# Nachlieferung KW 40: alle Zeilen aus Illinois verworfen

Am 1. Oktober 2026 kam die Nachlieferung für den 28. bis 30. September (Montag bis Mittwoch der
KW 40): drei Tagesdateien aus dem Stammwerk, eine Wochendatei aus Illinois und `liesmich.txt`.

**So stellst du es nach**

```text
uv run nordwerk import daten/nachlieferung --aus daten/aufbereitet-nachlieferung
```

**Was passiert:** Der Import läuft durch, übernimmt aber nur das Stammwerk.

```text
Dateien: 4 gelesen, 0 abgelehnt
Zeilen: 36 übernommen, 12 verworfen, 0 Dubletten
```

Im Bericht `qualitaet.json` steht `"unlesbar": 12`, und auf stderr stehen 12 Warnungen zu
`IL_shift_report_09282026.csv`. Illinois fehlt damit im Wochenbericht der KW 40.

**Was passieren soll:** Alle 48 Schichten werden übernommen (36 Stammwerk, 12 Illinois),
nichts wird verworfen.

**Hinweis der Werks-IT** (`liesmich.txt`): Illinois hat am 28. September eine neue Version
seines Berichtswerkzeugs eingeführt; am Inhalt der Berichte ändere sich nichts.
