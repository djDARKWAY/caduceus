"""
Limpar os ficheiros temporários

Apaga ficheiros das pastas temporárias do utilizador e do Windows e os ficheiros .pf do
Prefetch, seguindo a idade mínima configurada.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

LOCATIONS = (
    Location("%TEMP%", "category.user_temp"),
    Location(r"%WINDIR%\Temp", "category.windows_temp", needs_admin=True),
    Location("%WINDIR%\\Prefetch", "category.prefetch", pattern="*.pf", needs_admin=True),
)


def clean_temp_files(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_temp_files() -> int:
    return estimate_locations(LOCATIONS)
