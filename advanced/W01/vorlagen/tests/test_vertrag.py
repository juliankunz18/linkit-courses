"""Vertragstests für das Paket nordwerk: prüfen das Verhalten, das in Modul 0 festgelegt ist.

Mitgeliefert mit Modul 1. Jede Meldung sagt, welche Regel aus Modul 0 verletzt ist. Ändere diese
Datei nicht, um einen Test grün zu bekommen: Ein roter Vertragstest heißt, dass sich das Verhalten
des Pakets geändert hat, auf das sich andere verlassen.

Die Tests bauen kleine Lieferdateien in tmp_path (BOM, Windows-1252, Summenzeile, leere Datei,
fehlende Spalte, Dublette, unplausibler Wert). Nur der Test mit der Marke "daten" braucht die echten
Lieferungen in daten/roh/ und überspringt sich, wenn sie fehlen.
"""

import codecs
import dataclasses
import datetime as dt
import hashlib
import importlib.metadata
import inspect
import io
import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from nordwerk import cli, importer, konfig

ROH = Path(__file__).resolve().parents[1] / "daten" / "roh"
IL_KOPF = "Date,Line,Shift,Planned Qty,Actual Qty,Scrap Qty,Headcount,Hall Temp (F)"
SW_KOPF = "Datum;Linie;Schicht;Soll;Ist;Ausschuss;Personal;Auslastung;Hallentemperatur"
KEINE_ARGUMENTE: dict[str, str | None] = {"eingang": None, "ausgang": None, "log_level": None}
ERWARTET_CSV = (
    "werk,datum,linie,schicht,soll_stueck,ist_stueck,ausschuss_stueck,personal,hallentemp_c,quelle\n"
    "Illinois,2026-06-29,A,Früh,178,165,7,12,29.5,IL_shift_report_06292026.csv\n"
    "Illinois,2026-06-29,B,Spät,150,140,2,10,29.0,IL_shift_report_06292026.csv\n"
    "Stammwerk,2026-06-29,1,Früh,377,322,10,8,24.7,stammwerk_2026-06-29.csv\n"
    "Stammwerk,2026-06-29,1,Spät,300,290,5,8,,stammwerk_2026-06-29.csv\n"
    "Stammwerk,2026-06-30,1,Früh,377,320,9,8,24.1,stammwerk_2026-06-30.csv\n"
    "Stammwerk,2026-06-30,2,Spät,200,190,4,7,23.0,stammwerk_2026-06-30.csv\n"
).encode()


# ---------------------------------------------------------------- Hilfen und Testdaten
def wirft(fehler: type[Exception], regel: str, aufruf: Callable[..., Any], *args: Any) -> Exception:
    """Ruft aufruf(*args) auf und liefert die erwartete Ausnahme; sonst Fehlschlag mit regel."""
    try:
        aufruf(*args)
    except fehler as e:
        return e
    except Exception as e:  # jede andere Ausnahme ist hier ein Befund
        pytest.fail(f"{regel} Stattdessen kam {type(e).__name__}: {e}")
    pytest.fail(f"{regel} Es kam keine {fehler.__name__}.")


def illinois(*zeilen: str, kopf: str = IL_KOPF) -> bytes:
    """Wochendatei aus Illinois: UTF-8 mit BOM, Komma, am Ende die Summenzeile TOTAL."""
    text = "\n".join([kopf, *zeilen, "TOTAL,,,0,0,0,,"]) + "\n"
    return codecs.BOM_UTF8 + text.encode("utf-8")


def stammwerk(*zeilen: str, kodierung: str = "cp1252") -> bytes:
    """Tagesdatei aus dem Stammwerk: Semikolon, Dezimalkomma, Zeilenende CRLF."""
    return ("\r\n".join([SW_KOPF, *zeilen]) + "\r\n").encode(kodierung)


def werte(**anders: str) -> dict[str, str]:
    """Eine gültige Zeile aus Illinois mit Feldnamen als Schlüssel; anders ersetzt Werte."""
    basis = {
        "datum": "06/29/2026",
        "linie": "A",
        "schicht": "1st",
        "soll_stueck": "178",
        "ist_stueck": "165",
        "ausschuss_stueck": "7",
        "personal": "12",
        "hallentemp": "85.1",
    }
    return basis | anders


@pytest.fixture(autouse=True)
def sauberer_zustand(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Ohne NORDWERK_-Variablen starten und den Logger "nordwerk" danach wiederherstellen."""
    for name in ("NORDWERK_EINGANG", "NORDWERK_AUSGANG", "NORDWERK_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    logger = logging.getLogger("nordwerk")
    vorher = (logger.handlers[:], logger.level, logger.propagate)
    yield
    logger.handlers[:], logger.level, logger.propagate = vorher


@pytest.fixture
def eingang(tmp_path: Path) -> Path:
    """Ein kleiner Eingangsordner mit allen Befunden aus Modul 0 in sieben Dateien."""
    ordner = tmp_path / "roh"
    ordner.mkdir()
    dateien = {
        "IL_shift_report_06292026.csv": illinois(
            "06/29/2026,A,1st,178,165,7,12,85.1",
            "06/29/2026,B,2nd,150,140,2,10,84.2",
            "06/30/2026,A,1st,170,,3,12,85.0",  # Pflichtwert fehlt (Zeile 4)
        ),
        "IL_shift_report_07062026.csv": illinois(
            "07/06/2026,A,1st,178,165,12,85.1",
            kopf="Date,Line,Shift,Planned Qty,Actual Qty,Headcount,Hall Temp (F)",
        ),
        "stammwerk_2026-06-29.csv": stammwerk(
            "29.06.2026;1;Früh;377;322;10;8;0,90;24,7",
            "29.06.2026;1;Spät;300;290;5;8;0,80;",  # ohne Temperatur
            "29.06.2026;2;Nacht;220;169;961;8;0,84;24,6",  # unplausibel
        ),
        "stammwerk_2026-06-30.csv": stammwerk(
            "30.06.2026;1;Früh;377;320;9;8;0,90;24,1",
            "29.06.2026;1;Früh;377;999;1;8;0,90;20,0",  # Dublette des Vortags
            "",
            "30.06.2026; 2 ;Spät;200;190;4;7;0,80;23,0",
            "31.06.2026;3;Früh;377;300;5;8;0,90;22,0",  # unlesbares Datum
            kodierung="utf-8",
        ),
        "stammwerk_2026-07-01.csv": b"",
        "liesmich.txt": b"Bitte lesen.\n",
    }
    for name, inhalt in dateien.items():
        (ordner / name).write_bytes(inhalt)
    return ordner


# ---------------------------------------------------------------- Namen und Signaturen
@pytest.mark.parametrize(
    ("modul", "name", "parameter"),
    [
        (importer, "lieferungen", ["eingang"]),
        (importer, "lies_text", ["pfad"]),
        (importer, "lies_datum", ["text", "fmt"]),
        (importer, "lies_temperatur", ["text", "fmt"]),
        (importer, "zeile", ["werte", "werk", "fmt", "quelle"]),
        (importer, "zeilen", ["pfad", "werk", "zaehler"]),
        (importer, "importiere", ["eingang"]),
        (importer, "schreibe_csv", ["schichten"]),
        (importer, "pruefsumme", ["daten"]),
        (konfig, "lade_konfig", ["toml_text", "umgebung", "argumente"]),
        (cli, "richte_logging_ein", ["stufe", "ziel"]),
        (cli, "main", ["argv"]),
    ],
)
def test_signaturen(modul: Any, name: str, parameter: list[str]) -> None:
    regel = f"Modul 0 legt fest: {modul.__name__}.{name}({', '.join(parameter)})."
    funktion = getattr(modul, name, None)
    assert callable(funktion), regel
    assert list(inspect.signature(funktion).parameters) == parameter, regel


def test_voreinstellungen_der_parameter() -> None:
    logging_param = inspect.signature(cli.richte_logging_ein).parameters
    assert logging_param["stufe"].default == "WARNING", (
        "Modul 0: richte_logging_ein hat die Voreinstellung stufe='WARNING'."
    )
    assert logging_param["ziel"].default is None, "Modul 0: richte_logging_ein hat ziel=None."
    assert inspect.signature(cli.main).parameters["argv"].default is None, (
        "Modul 0: main(argv=None) liest ohne Argument die echte Kommandozeile."
    )


def test_konstanten_und_logger() -> None:
    assert importer.GRUENDE == ("pflichtwert_fehlt", "unlesbar", "unplausibel"), (
        "Modul 0: GRUENDE nennt genau die drei Gründe pflichtwert_fehlt, unlesbar, unplausibel."
    )
    assert importer.SCHICHT_RANG == {"Früh": 0, "Spät": 1, "Nacht": 2}, (
        "Modul 0: SCHICHT_RANG ordnet Früh, Spät, Nacht die Ränge 0, 1, 2 zu."
    )
    assert importer.PFLICHT == (
        "datum",
        "linie",
        "schicht",
        "soll_stueck",
        "ist_stueck",
        "ausschuss_stueck",
        "personal",
    ), "Modul 0: PFLICHT nennt die sieben Pflichtfelder in fester Reihenfolge."
    assert importer.log.name == "nordwerk.importer", (
        "Modul 0: importer.py loggt über den Logger 'nordwerk.importer'."
    )


def test_ausnahmen() -> None:
    assert issubclass(importer.LieferungsFehler, Exception), (
        "Modul 0: LieferungsFehler ist eine eigene Ausnahme für unbrauchbare Dateien."
    )
    assert issubclass(importer.ZeilenFehler, ValueError), (
        "Modul 0: ZeilenFehler erbt von ValueError."
    )
    e = importer.ZeilenFehler("unlesbar", "Datum kaputt")
    assert e.grund == "unlesbar" and str(e) == "Datum kaputt", (
        "Modul 0: ZeilenFehler(grund, text) merkt sich grund und zeigt text als Meldung."
    )


def test_formate() -> None:
    felder = [f.name for f in dataclasses.fields(importer.Format)]
    regel = (
        "Modul 0: Felder von Format: muster, trenn, datum, dezimal, fahrenheit, spalten, schichten."
    )
    assert felder == [
        "muster",
        "trenn",
        "datum",
        "dezimal",
        "fahrenheit",
        "spalten",
        "schichten",
    ], regel
    assert sorted(importer.FORMATE) == ["Illinois", "Stammwerk"], (
        "Modul 0: FORMATE kennt genau die Werke Illinois und Stammwerk."
    )
    il, sw = importer.FORMATE["Illinois"], importer.FORMATE["Stammwerk"]
    assert (il.muster, il.trenn, il.datum, il.dezimal, il.fahrenheit) == (
        "IL_shift_report_*.csv",
        ",",
        "%m/%d/%Y",
        ".",
        True,
    ), "Modul 0: Illinois liefert IL_shift_report_*.csv mit Komma, MM/DD/YYYY, Punkt, Fahrenheit."
    assert (sw.muster, sw.trenn, sw.datum, sw.dezimal, sw.fahrenheit) == (
        "stammwerk_*.csv",
        ";",
        "%d.%m.%Y",
        ",",
        False,
    ), "Modul 0: Das Stammwerk liefert stammwerk_*.csv mit Semikolon, TT.MM.JJJJ, Komma, Celsius."
    assert il.spalten == {
        "Date": "datum",
        "Line": "linie",
        "Shift": "schicht",
        "Planned Qty": "soll_stueck",
        "Actual Qty": "ist_stueck",
        "Scrap Qty": "ausschuss_stueck",
        "Headcount": "personal",
        "Hall Temp (F)": "hallentemp",
    }, "Modul 0: spalten ordnet jede Spalte aus Illinois einem Feld zu (Datenblatt)."
    assert sw.spalten == {
        "Datum": "datum",
        "Linie": "linie",
        "Schicht": "schicht",
        "Soll": "soll_stueck",
        "Ist": "ist_stueck",
        "Ausschuss": "ausschuss_stueck",
        "Personal": "personal",
        "Hallentemperatur": "hallentemp",
    }, "Modul 0: spalten ordnet jede Spalte aus dem Stammwerk einem Feld zu (Datenblatt)."
    assert {"1st": "Früh", "2nd": "Spät"}.items() <= il.schichten.items(), (
        "Modul 0: In Illinois steht 1st für Früh und 2nd für Spät."
    )
    assert {"Früh": "Früh", "Spät": "Spät", "Nacht": "Nacht"}.items() <= sw.schichten.items(), (
        "Modul 0: Das Stammwerk liefert die Schichten Früh, Spät und Nacht unverändert."
    )


def test_schicht() -> None:
    felder = [f.name for f in dataclasses.fields(importer.Schicht)]
    assert felder == [
        "werk",
        "datum",
        "linie",
        "schicht",
        "soll_stueck",
        "ist_stueck",
        "ausschuss_stueck",
        "personal",
        "hallentemp_c",
        "quelle",
    ], "Modul 0: Schicht hat zehn Felder in fester Reihenfolge."
    assert importer.SPALTEN == felder, "Modul 0: SPALTEN sind die Feldnamen von Schicht."
    s = importer.Schicht("Illinois", dt.date(2026, 6, 29), "A", "Früh", 1, 1, 0, 1, None, "x.csv")
    assert s.schluessel() == ("Illinois", dt.date(2026, 6, 29), "A", "Früh"), (
        "Modul 0: schluessel() liefert (werk, datum, linie, schicht)."
    )
    wirft(
        dataclasses.FrozenInstanceError,
        "Modul 0: Schicht ist unveränderlich (frozen=True).",
        setattr,
        s,
        "linie",
        "B",
    )


# ---------------------------------------------------------------- Lesen
def test_lieferungen_sortiert(eingang: Path) -> None:
    namen = [(werk, pfad.name) for werk, pfad in importer.lieferungen(eingang)]
    assert namen == [
        ("Illinois", "IL_shift_report_06292026.csv"),
        ("Illinois", "IL_shift_report_07062026.csv"),
        ("Stammwerk", "stammwerk_2026-06-29.csv"),
        ("Stammwerk", "stammwerk_2026-06-30.csv"),
        ("Stammwerk", "stammwerk_2026-07-01.csv"),
    ], "Modul 0: lieferungen sortiert nach Werk und je Werk nach Dateiname, ohne liesmich.txt."


def test_lies_text_kodierungen(tmp_path: Path) -> None:
    faelle = {
        "bom.csv": (codecs.BOM_UTF8 + "Date,Früh\n".encode(), "utf-8-sig"),
        "utf8.csv": ("Datum;Spät\n".encode(), "utf-8"),
        "cp1252.csv": ("Datum;Früh\n".encode("cp1252"), "cp1252"),
    }
    for name, (inhalt, kodierung) in faelle.items():
        (tmp_path / name).write_bytes(inhalt)
        text, gefunden = importer.lies_text(tmp_path / name)
        assert gefunden == kodierung, (
            f"Modul 0: lies_text erkennt {kodierung} (BOM zuerst, dann UTF-8, sonst Windows-1252)."
        )
        assert text == inhalt.removeprefix(codecs.BOM_UTF8).decode(
            kodierung.removesuffix("-sig")
        ), "Modul 0: lies_text liefert den Text ohne BOM und mit richtigen Umlauten."


@pytest.mark.parametrize("inhalt", [b"", b"  \r\n\n"])
def test_lies_text_leere_datei(tmp_path: Path, inhalt: bytes) -> None:
    pfad = tmp_path / "stammwerk_2026-07-22.csv"
    pfad.write_bytes(inhalt)
    e = wirft(
        importer.LieferungsFehler,
        "Modul 0: Eine leere Datei (nur Leerraum) löst LieferungsFehler aus.",
        importer.lies_text,
        pfad,
    )
    assert str(e) == "stammwerk_2026-07-22.csv: Datei ist leer", (
        "Modul 0: Die Meldung lautet '<Dateiname>: Datei ist leer'."
    )


def test_datum_und_temperatur() -> None:
    il, sw = importer.FORMATE["Illinois"], importer.FORMATE["Stammwerk"]
    assert importer.lies_datum("07/02/2026", il) == dt.date(2026, 7, 2), (
        "Modul 0: Illinois schreibt das Datum als MM/DD/YYYY."
    )
    assert importer.lies_datum(" 02.07.2026 ", sw) == dt.date(2026, 7, 2), (
        "Modul 0: Das Stammwerk schreibt TT.MM.JJJJ; Leerraum außen zählt nicht."
    )
    assert importer.lies_temperatur("23,4", sw) == 23.4, (
        "Modul 0: Im Stammwerk ist das Komma das Dezimalzeichen."
    )
    assert importer.lies_temperatur("85.7", il) == 29.8, (
        "Modul 0: Fahrenheit wird mit (f - 32) * 5/9 umgerechnet und auf eine Stelle gerundet."
    )
    for leer in ("", "  "):
        assert importer.lies_temperatur(leer, sw) is None, (
            "Modul 0: Eine leere Temperatur ergibt None, nicht 0."
        )


def test_zeile_gueltig() -> None:
    il = importer.FORMATE["Illinois"]
    s = importer.zeile(werte(linie=" A "), "Illinois", il, "x.csv")
    assert s == importer.Schicht(
        "Illinois", dt.date(2026, 6, 29), "A", "Früh", 178, 165, 7, 12, 29.5, "x.csv"
    ), "Modul 0: zeile liefert eine Schicht mit Werk, Datum, Zahlen, Celsius und Quelle."


@pytest.mark.parametrize(
    ("anders", "grund"),
    [
        ({"datum": "TOTAL", "ist_stueck": ""}, "summenzeile"),
        ({"ist_stueck": ""}, "pflichtwert_fehlt"),
        ({"personal": " "}, "pflichtwert_fehlt"),
        ({"datum": "06/31/2026"}, "unlesbar"),
        ({"schicht": "3rd"}, "unlesbar"),
        ({"soll_stueck": "viele"}, "unlesbar"),
        ({"ausschuss_stueck": "166"}, "unplausibel"),
        ({"soll_stueck": "-1"}, "unplausibel"),
    ],
)
def test_zeile_gruende(anders: dict[str, str], grund: str) -> None:
    il = importer.FORMATE["Illinois"]
    regel = f"Modul 0: zeile meldet diesen Fall als ZeilenFehler mit grund '{grund}'."
    e = wirft(
        importer.ZeilenFehler, regel, importer.zeile, werte(**anders), "Illinois", il, "x.csv"
    )
    assert getattr(e, "grund", None) == grund, regel
    if grund == "unlesbar":
        assert e.__cause__ is not None, (
            "Modul 0: Bei 'unlesbar' hängt die ursprüngliche Ausnahme an (raise ... from e)."
        )


def test_zeilen_generator_und_zaehler(eingang: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert inspect.isgeneratorfunction(importer.zeilen), (
        "Modul 0: zeilen ist eine Generatorfunktion (yield statt Liste)."
    )
    zaehler: dict[str, int] = {}
    with caplog.at_level(logging.DEBUG, logger="nordwerk.importer"):
        schichten = list(
            importer.zeilen(eingang / "IL_shift_report_06292026.csv", "Illinois", zaehler)
        )
    assert [s.linie for s in schichten] == ["A", "B"], (
        "Modul 0: zeilen liefert die gültigen Zeilen in der Reihenfolge der Datei."
    )
    gezaehlt = {k: v for k, v in zaehler.items() if v}
    assert gezaehlt == {"utf-8-sig": 1, "pflichtwert_fehlt": 1, "summenzeile": 1}, (
        "Modul 0: zeilen zählt in zaehler die Kodierung und jeden Grund, auch die Summenzeile."
    )
    warnungen = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnungen) == 1 and warnungen[0].startswith(
        "IL_shift_report_06292026.csv Zeile 4: "
    ), (
        "Modul 0: Je verworfene Zeile eine Warnung '<Datei> Zeile <n>: …' (Kopf = Zeile 1), "
        "die Summenzeile nur auf Stufe DEBUG."
    )


def test_zeilen_fehlende_spalte(eingang: Path) -> None:
    gen = importer.zeilen(eingang / "IL_shift_report_07062026.csv", "Illinois", {})
    e = wirft(
        importer.LieferungsFehler,
        "Modul 0: Fehlt eine Spalte, löst zeilen beim ersten next() LieferungsFehler aus.",
        next,
        gen,
    )
    assert str(e) == "IL_shift_report_07062026.csv: Pflichtspalte fehlt: Scrap Qty", (
        "Modul 0: Die Meldung lautet '<Dateiname>: Pflichtspalte fehlt: <Spalten>'."
    )


# ---------------------------------------------------------------- Zusammenführen und Schreiben
def test_importiere_bericht(eingang: Path) -> None:
    try:
        schichten, bericht = importer.importiere(eingang)
    except importer.LieferungsFehler as e:
        pytest.fail(
            f"Modul 0: importiere fängt LieferungsFehler je Datei ab und macht weiter ({e})."
        )
    assert list(bericht)[:4] == ["dateien", "kodierung", "zeilen", "werke"], (
        "Modul 0: Der Bericht hat die Schlüssel dateien, kodierung, zeilen, werke in dieser Folge."
    )
    assert bericht["dateien"] == {
        "gelesen": 3,
        "abgelehnt": [
            {"datei": "IL_shift_report_07062026.csv", "grund": "Pflichtspalte fehlt: Scrap Qty"},
            {"datei": "stammwerk_2026-07-01.csv", "grund": "Datei ist leer"},
        ],
        "ignoriert": ["liesmich.txt"],
    }, "Modul 0: Abgelehnte Dateien stehen mit Grund im Bericht, der Import läuft weiter."
    assert bericht["kodierung"] == {"utf-8-sig": 2, "utf-8": 1, "cp1252": 1}, (
        "Modul 0: kodierung zählt jede gelesene Datei, die leere Datei nicht."
    )
    assert bericht["zeilen"] == {
        "gelesen": 10,
        "verworfen": {"pflichtwert_fehlt": 1, "unlesbar": 1, "unplausibel": 1},
        "dubletten": 1,
        "uebernommen": 6,
        "summenzeilen": 1,
    }, "Modul 0: Bilanz gelesen - verworfen - Dubletten = übernommen, Summenzeilen extra."
    assert bericht["werke"] == {
        "Illinois": {"zeilen": 2, "von": "2026-06-29", "bis": "2026-06-29", "ohne_temperatur": 0},
        "Stammwerk": {"zeilen": 4, "von": "2026-06-29", "bis": "2026-06-30", "ohne_temperatur": 1},
    }, "Modul 0: werke nennt je Werk Zeilen, ersten und letzten Tag und fehlende Temperaturen."
    erste_sw = next(s for s in schichten if s.werk == "Stammwerk")
    assert (erste_sw.ist_stueck, erste_sw.quelle) == (322, "stammwerk_2026-06-29.csv"), (
        "Modul 0: Bei Dubletten bleibt die zuerst gelesene Zeile."
    )
    assert [(s.werk, s.datum.isoformat(), s.linie, s.schicht) for s in schichten] == [
        ("Illinois", "2026-06-29", "A", "Früh"),
        ("Illinois", "2026-06-29", "B", "Spät"),
        ("Stammwerk", "2026-06-29", "1", "Früh"),
        ("Stammwerk", "2026-06-29", "1", "Spät"),
        ("Stammwerk", "2026-06-30", "1", "Früh"),
        ("Stammwerk", "2026-06-30", "2", "Spät"),
    ], "Modul 0: importiere sortiert nach Werk, Datum, Linie und Schicht (Früh, Spät, Nacht)."


def test_schreibe_csv_und_pruefsumme(eingang: Path) -> None:
    schichten, _ = importer.importiere(eingang)
    daten = importer.schreibe_csv(schichten)
    assert b"\r" not in daten and not daten.startswith(codecs.BOM_UTF8), (
        "Modul 0: schichten.csv hat das Zeilenende \\n und ist UTF-8 ohne BOM."
    )
    assert daten == ERWARTET_CSV, (
        "Modul 0: Kopf SPALTEN, Komma, Datum ISO, Temperatur mit einer Stelle oder leer, Quelle."
    )
    assert importer.pruefsumme(daten) == hashlib.sha256(daten).hexdigest()[:12], (
        "Modul 0: Die Prüfsumme sind die ersten zwölf Zeichen von SHA-256."
    )


# ---------------------------------------------------------------- Konfiguration und Logging
def test_lade_konfig_vorrang() -> None:
    toml = '[import]\neingang = "aus_datei"\nlog_level = "ERROR"\n'
    regel = "Modul 0: Argument vor Umgebungsvariable vor nordwerk.toml vor Voreinstellung."
    assert konfig.lade_konfig("", {}, KEINE_ARGUMENTE) == {
        "eingang": "daten/roh",
        "ausgang": "daten/aufbereitet",
        "log_level": "WARNING",
    }, "Modul 0: Ohne Angaben gelten daten/roh, daten/aufbereitet und WARNING."
    assert konfig.lade_konfig(toml, {}, KEINE_ARGUMENTE)["eingang"] == "aus_datei", regel
    umgebung = {"NORDWERK_EINGANG": "aus_umgebung", "NORDWERK_LOG_LEVEL": "INFO"}
    assert konfig.lade_konfig(toml, umgebung, KEINE_ARGUMENTE) == {
        "eingang": "aus_umgebung",
        "ausgang": "daten/aufbereitet",
        "log_level": "INFO",
    }, regel
    argumente = KEINE_ARGUMENTE | {"eingang": "aus_argument"}
    assert konfig.lade_konfig(toml, umgebung, argumente)["eingang"] == "aus_argument", regel


def test_richte_logging_ein() -> None:
    puffer = io.StringIO()
    cli.richte_logging_ein("INFO", puffer)
    logger = cli.richte_logging_ein("INFO", puffer)
    logging.getLogger("nordwerk.importer").info("Probe")
    assert puffer.getvalue() == "INFO nordwerk.importer: Probe\n", (
        "Modul 0: Genau ein Handler mit dem Format '%(levelname)s %(name)s: %(message)s', "
        "auch nach dem zweiten Aufruf."
    )
    assert logger.name == "nordwerk" and logger.propagate is False, (
        "Modul 0: richte_logging_ein richtet den Logger 'nordwerk' ein, mit propagate = False."
    )
    cli.richte_logging_ein("WARNING", puffer)
    logging.getLogger("nordwerk.importer").info("leise")
    assert "leise" not in puffer.getvalue(), "Modul 0: Mit WARNING erscheinen keine INFO-Zeilen."


# ---------------------------------------------------------------- Kommandozeile
def test_main_import(eingang: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    aus = tmp_path / "neu" / "aufbereitet"
    rc = cli.main(["import", str(eingang), "--aus", str(aus)])
    ausgabe = capsys.readouterr()
    assert rc == 0, "Modul 0: main gibt nach einem erfolgreichen Import 0 zurück."
    pruefsumme = importer.pruefsumme(ERWARTET_CSV)
    assert ausgabe.out.splitlines() == [
        "Dateien: 3 gelesen, 2 abgelehnt",
        "Zeilen: 6 übernommen, 3 verworfen, 1 Dubletten",
        f"Prüfsumme: {pruefsumme}",
    ], "Modul 0: Die Zusammenfassung hat genau drei Zeilen auf stdout."
    assert "WARNING nordwerk.importer: IL_shift_report_06292026.csv Zeile 4: " in ausgabe.err, (
        "Modul 0: Warnungen gehen auf stderr, im Format '<STUFE> <logger>: <Meldung>'."
    )
    assert "ERROR nordwerk.importer: stammwerk_2026-07-01.csv: Datei ist leer" in ausgabe.err, (
        "Modul 0: Eine abgelehnte Datei meldet importiere mit log.error."
    )
    assert (aus / "schichten.csv").read_bytes() == ERWARTET_CSV, (
        "Modul 0: main schreibt schichten.csv nach ausgang und legt den Ordner an."
    )
    text = (aus / "qualitaet.json").read_text(encoding="utf-8")
    bericht = json.loads(text)
    assert text.startswith('{\n  "dateien": {') and list(bericht)[-1] == "pruefsumme", (
        "Modul 0: qualitaet.json ist mit indent=2 geschrieben und endet mit der Prüfsumme."
    )
    assert bericht["pruefsumme"] == pruefsumme, "Modul 0: Der Bericht enthält die Prüfsumme."


@pytest.mark.parametrize("ordner", ["leer", "gibt_es_nicht"])
def test_main_ohne_lieferungen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ordner: str
) -> None:
    (tmp_path / "leer").mkdir()
    try:
        rc = cli.main(["import", str(tmp_path / ordner), "--aus", str(tmp_path / "aus")])
    except SystemExit as e:
        pytest.fail(
            f"Modul 0: main gibt ohne Lieferdateien 1 zurück, statt sys.exit({e.code}) zu rufen."
        )
    ausgabe = capsys.readouterr()
    assert rc == 1, "Modul 0: Ohne Lieferdateien gibt main 1 zurück (kein sys.exit)."
    assert ausgabe.err.strip() and "Traceback" not in ausgabe.err, (
        "Modul 0: Ohne Lieferdateien kommt eine Meldung auf stderr, kein Traceback."
    )


def test_main_vorrang_der_konfiguration(
    eingang: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "nordwerk.toml").write_text(
        f'[import]\neingang = "{eingang.name}"\nausgang = "aus_datei"\n', encoding="utf-8"
    )
    monkeypatch.setenv("NORDWERK_AUSGANG", "aus_umgebung")
    assert cli.main(["import"]) == 0, "Modul 0: nordwerk import liest eingang aus nordwerk.toml."
    assert (tmp_path / "aus_umgebung" / "schichten.csv").is_file(), (
        "Modul 0: Die Umgebungsvariable NORDWERK_AUSGANG schlägt nordwerk.toml."
    )
    assert cli.main(["import", "--aus", "aus_argument", "--log-level", "INFO"]) == 0, (
        "Modul 0: nordwerk import nimmt --aus und --log-level als Argumente."
    )
    assert (tmp_path / "aus_argument" / "schichten.csv").is_file(), (
        "Modul 0: Das Argument --aus schlägt die Umgebungsvariable."
    )
    assert not (tmp_path / "aus_datei").exists(), (
        "Modul 0: nordwerk.toml hat den kleinsten Vorrang."
    )
    assert "INFO nordwerk.importer: " in capsys.readouterr().err, (
        "Modul 0: --log-level INFO zeigt zusätzlich die INFO-Zeilen des Importers."
    )


def test_main_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as ende:
        cli.main(["--version"])
    assert ende.value.code == 0, "Modul 0: nordwerk --version endet mit Exit-Code 0."
    assert capsys.readouterr().out == f"nordwerk {importlib.metadata.version('nordwerk')}\n", (
        "Modul 0: nordwerk --version zeigt 'nordwerk <Version>' mit der Version aus pyproject.toml."
    )


# ---------------------------------------------------------------- Echte Lieferungen
@pytest.mark.daten
def test_echte_lieferungen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    if not ROH.is_dir():
        pytest.skip(f"Die echten Lieferungen fehlen in {ROH} (Modul 0, Lieferungen holen).")
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["import", str(ROH), "--aus", str(tmp_path / "aufbereitet")])
    assert rc == 0, "Modul 0: Der Import der echten Lieferungen läuft durch."
    assert capsys.readouterr().out.splitlines() == [
        "Dateien: 70 gelesen, 2 abgelehnt",
        "Zeilen: 892 übernommen, 4 verworfen, 12 Dubletten",
        "Prüfsumme: 0bc618f824be",
    ], "Modul 0: Die echten Lieferungen ergeben 892 Zeilen und die Prüfsumme 0bc618f824be."
