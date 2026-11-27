"""
Limpar o lixo escondido

Apaga as caches de miniaturas e de ícones do Explorer, os relatórios de erros do Windows, os
despejos de falhas e os despejos de memória.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.cleaner import Location, clean_locations

LOCATIONS = (
    Location(
        r"%LOCALAPPDATA%\Microsoft\Windows\Explorer",
        "category.thumbnail_cache",
        pattern="thumbcache_*.db",
    ),
    Location(
        r"%LOCALAPPDATA%\Microsoft\Windows\Explorer",
        "category.icon_cache",
        pattern="iconcache_*.db",
    ),
    Location(r"%LOCALAPPDATA%\Microsoft\Windows\WER", "category.error_reports"),
    Location(r"%PROGRAMDATA%\Microsoft\Windows\WER", "category.error_reports", needs_admin=True),
    Location(r"%LOCALAPPDATA%\CrashDumps", "category.crash_dumps"),
    Location(r"%WINDIR%\Minidump", "category.memory_dumps", needs_admin=True),
    Location("%WINDIR%", "category.memory_dumps", pattern="MEMORY.DMP", needs_admin=True),
)


def clean_hidden_junk(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)
