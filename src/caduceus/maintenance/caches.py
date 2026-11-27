"""
Limpar as caches

Apaga a cache de transferências do Windows Update, a cache da Otimização da Entrega e as caches
de shaders do DirectX, da NVIDIA e da AMD. O Windows e os jogos voltam a criá-las quando precisam.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.cleaner import Location, clean_locations

LOCATIONS = (
    Location(
        r"%WINDIR%\SoftwareDistribution\Download",
        "category.windows_update_cache",
        needs_admin=True,
    ),
    Location(
        r"%WINDIR%\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows"
        r"\DeliveryOptimization\Cache",
        "category.delivery_optimization_cache",
        needs_admin=True,
    ),
    Location(r"%LOCALAPPDATA%\D3DSCache", "category.directx_shader_cache"),
    Location(r"%LOCALAPPDATA%\NVIDIA\DXCache", "category.nvidia_shader_cache"),
    Location(r"%LOCALAPPDATA%\NVIDIA\GLCache", "category.nvidia_shader_cache"),
    Location(r"%LOCALAPPDATA%\AMD\DxCache", "category.amd_shader_cache"),
    Location(r"%LOCALAPPDATA%\AMD\GLCache", "category.amd_shader_cache"),
)


def clean_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)
