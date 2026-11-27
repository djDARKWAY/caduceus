r"""
Limpar os registos do Windows

Apaga os registos de manutenção e de instalação do Windows (`Logs\CBS`, `Logs\DISM`,
`Logs\WindowsUpdate`, os `.log` de `Panther` e os `setupapi*.log` de `INF`), sem tocar no que tem
menos de 24 horas (`LOG_MIN_AGE_HOURS` no `config`), para ainda haver os registos do próprio dia
com que diagnosticar problemas. Exige administrador.
"""

from caduceus.config import LOG_MIN_AGE_HOURS
from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

_CATEGORY = "category.windows_logs"


def _log_location(path: str, pattern: str = "*") -> Location:
    return Location(
        path, _CATEGORY, pattern=pattern, min_age_hours=LOG_MIN_AGE_HOURS, needs_admin=True
    )


LOCATIONS = (
    _log_location(r"%WINDIR%\Logs\CBS"),
    _log_location(r"%WINDIR%\Logs\DISM"),
    _log_location(r"%WINDIR%\Logs\WindowsUpdate"),
    _log_location(r"%WINDIR%\Panther", "*.log"),
    _log_location(r"%WINDIR%\INF", "setupapi*.log"),
)


def clean_windows_logs(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_windows_logs() -> int:
    return estimate_locations(LOCATIONS)
