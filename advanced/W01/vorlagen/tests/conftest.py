"""Gemeinsame Fixtures für alle Testdateien in tests/ (mitgeliefert mit Modul 1).

pytest lädt diese Datei von selbst; Fixtures von hier gelten in jeder Testdatei ohne Import.
logger_zuruecksetzen läuft nach jedem Test: richte_logging_ein() aus Modul 0 setzt beim Logger
"nordwerk" propagate = False, und ohne Rücksetzen sähe ein späterer Test mit caplog keine
Meldungen mehr, je nachdem, in welcher Reihenfolge die Testdateien laufen.
"""

import logging

import pytest


@pytest.fixture(autouse=True)
def logger_zuruecksetzen():
    """Setzt den Logger nordwerk nach jedem Test zurück, auch wenn main() ihn eingerichtet hat."""
    yield
    logger = logging.getLogger("nordwerk")
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
