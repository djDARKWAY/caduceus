"""
Limpar os ficheiros temporários

Apaga o conteúdo da pasta temporária do utilizador (%TEMP%) e da do Windows (C:\\Windows\\Temp),
sem tocar no que tem menos de um dia, e os ficheiros .pf do Prefetch (C:\\Windows\\Prefetch).
"""

from caduceus.config import TEMP_MIN_AGE_HOURS
from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.cleaner import Location, clean_locations

LOCATIONS = (
    Location("%TEMP%", "category.user_temp", min_age_hours=TEMP_MIN_AGE_HOURS),
    Location(
        "%WINDIR%\\Temp",
        "category.windows_temp",
        min_age_hours=TEMP_MIN_AGE_HOURS,
        needs_admin=True,
    ),
    Location("%WINDIR%\\Prefetch", "category.prefetch", pattern="*.pf", needs_admin=True),
)


def clean_temp_files(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)
