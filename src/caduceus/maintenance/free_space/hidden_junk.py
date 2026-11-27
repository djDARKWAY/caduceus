"""
Limpar o lixo escondido

Apaga os despejos de falhas das aplicações na pasta do utilizador.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

LOCATIONS = (Location(r"%LOCALAPPDATA%\CrashDumps", "category.crash_dumps"),)


def clean_hidden_junk(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_hidden_junk() -> int:
    return estimate_locations(LOCATIONS)
