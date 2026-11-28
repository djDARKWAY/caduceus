"""
Apagar os despejos de falhas do sistema

Apaga a imagem de memória completa, os minidespejos e os despejos de falhas de controladores
e de hardware (exigem administrador), e os despejos de falhas das aplicações na pasta do
utilizador (não exigem).
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

LOCATIONS = (
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


def clean_crash_dumps(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_crash_dumps() -> int:
    return estimate_locations(LOCATIONS)
