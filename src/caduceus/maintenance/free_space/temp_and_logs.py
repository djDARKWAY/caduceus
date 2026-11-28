r"""
Limpar os ficheiros temporários, os registos e os despejos de falhas

Apaga o que o Windows e os programas deixam para trás e só serve para diagnosticar: os ficheiros
das pastas temporárias do utilizador e do Windows e os `.pf` do Prefetch (com a idade mínima
configurada); os registos de manutenção e de instalação do Windows (`Logs\CBS`, `Logs\DISM`,
`Logs\WindowsUpdate`, os `.log` de `Panther`, os `setupapi*.log` de `INF` e os `.etl` do
orquestrador do Windows Update em `%PROGRAMDATA%\USOShared\Logs\System`), sem tocar no que tem
menos de 24 horas (`LOG_MIN_AGE_HOURS` no `config`), para ainda haver os registos do próprio dia
com que diagnosticar problemas; e a imagem de memória completa, os minidespejos e os despejos de
falhas de controladores e de hardware, mais os das aplicações na pasta do utilizador. Cada local
mantém a sua idade mínima e a sua exigência de administrador: só o que a exige fica por limpar
quando o Caduceus não é administrador.
"""

from caduceus.config import LOG_MIN_AGE_HOURS
from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

_LOGS = "category.windows_logs"


def _log_location(path: str, pattern: str = "*") -> Location:
    return Location(path, _LOGS, pattern=pattern, min_age_hours=LOG_MIN_AGE_HOURS, needs_admin=True)


LOCATIONS = (
    Location("%TEMP%", "category.user_temp"),
    Location(r"%WINDIR%\Temp", "category.windows_temp", needs_admin=True),
    Location(r"%WINDIR%\Prefetch", "category.prefetch", pattern="*.pf", needs_admin=True),
    _log_location(r"%WINDIR%\Logs\CBS"),
    _log_location(r"%WINDIR%\Logs\DISM"),
    _log_location(r"%WINDIR%\Logs\WindowsUpdate"),
    _log_location(r"%WINDIR%\Panther", "*.log"),
    _log_location(r"%WINDIR%\INF", "setupapi*.log"),
    _log_location(r"%PROGRAMDATA%\USOShared\Logs\System", "*.etl"),
    Location(r"%LOCALAPPDATA%\CrashDumps", "category.crash_dumps"),
    Location(
        "%WINDIR%", "category.memory_dumps", "MEMORY.DMP", 0, needs_admin=True, files_only=True
    ),
    Location(r"%WINDIR%\Minidump", "category.memory_dumps", min_age_hours=0, needs_admin=True),
    Location(
        r"%WINDIR%\LiveKernelReports",
        "cleanup.crash_dumps.live_kernel",
        min_age_hours=0,
        needs_admin=True,
    ),
)


def clean_temp_and_logs(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_temp_and_logs() -> int:
    return estimate_locations(LOCATIONS)
