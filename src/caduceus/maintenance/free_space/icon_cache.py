r"""
Reconstruir a cache de ícones

Fecha o Explorer enquanto apaga os ficheiros das caches de ícones e miniaturas da pasta
`%LOCALAPPDATA%\Microsoft\Windows\Explorer`. Volta a abrir a shell mesmo se a limpeza falhar.
"""

from dataclasses import replace

from caduceus.config import EXPLORER_EXE
from caduceus.maintenance.actions import Outcome, Report, Step
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations
from caduceus.maintenance.performance.restart_explorer import start_explorer, stop_explorer

_EXPLORER_CACHE = r"%LOCALAPPDATA%\Microsoft\Windows\Explorer"
LOCATIONS = (
    Location(_EXPLORER_CACHE, "category.icon_cache", "iconcache*.db", 0, files_only=True),
    Location(_EXPLORER_CACHE, "category.thumbnail_cache", "thumbcache*.db", 0, files_only=True),
)


def clean_icon_cache(report: Report) -> Outcome:
    report(Step("cleanup.icon_cache.step", 0, 0))
    if not stop_explorer():
        return Outcome(0, 0, failures=(EXPLORER_EXE,))
    try:
        outcome = clean_locations(LOCATIONS, report)
    finally:
        restarted = start_explorer()
    if not restarted:
        return replace(outcome, failures=(*outcome.failures, EXPLORER_EXE))
    return outcome


def estimate_icon_cache() -> int:
    return estimate_locations(LOCATIONS)
