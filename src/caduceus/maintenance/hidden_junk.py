"""
Limpar o lixo escondido

Apaga as caches de miniaturas e de ícones do Explorer, os relatórios de erros do Windows, os
despejos de falhas e os despejos de memória.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.cleaner import Location, clean_locations

LOCATIONS = (
    Location("%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer", pattern="thumbcache_*.db"),
    Location("%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer", pattern="iconcache_*.db"),
    Location("%LOCALAPPDATA%\\Microsoft\\Windows\\WER"),
    Location("%PROGRAMDATA%\\Microsoft\\Windows\\WER", needs_admin=True),
    Location("%LOCALAPPDATA%\\CrashDumps"),
    Location("%WINDIR%\\Minidump", needs_admin=True),
    Location("%WINDIR%", pattern="MEMORY.DMP", needs_admin=True),
)


def clean_hidden_junk(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)
