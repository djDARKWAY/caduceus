"""
Limpar as caches

Apaga a cache de transferências do Windows Update, a cache da Otimização da Entrega e as caches
de shaders do DirectX, da NVIDIA e da AMD. O Windows e os jogos voltam a criá-las quando precisam.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.cleaner import Location, clean_locations

LOCATIONS = (
    Location("%WINDIR%\\SoftwareDistribution\\Download", needs_admin=True),
    Location(
        "%WINDIR%\\ServiceProfiles\\NetworkService\\AppData\\Local\\Microsoft\\Windows"
        "\\DeliveryOptimization\\Cache",
        needs_admin=True,
    ),
    Location("%LOCALAPPDATA%\\D3DSCache"),
    Location("%LOCALAPPDATA%\\NVIDIA\\DXCache"),
    Location("%LOCALAPPDATA%\\NVIDIA\\GLCache"),
    Location("%LOCALAPPDATA%\\AMD\\DxCache"),
    Location("%LOCALAPPDATA%\\AMD\\GLCache"),
)


def clean_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)
