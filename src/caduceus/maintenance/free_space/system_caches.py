"""
Limpar as caches do sistema

Apaga a cache de transferências do Windows Update, a da Otimização da Entrega, as caches de shaders
do DirectX, da NVIDIA e da AMD, a cache da Microsoft Store, a da Pesquisa do Windows e a cache de
Internet do Windows (`INetCache`). O Windows e os jogos voltam a criá-las quando precisam.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

_PACKAGES = r"%LOCALAPPDATA%\Packages"
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
    Location(
        _PACKAGES + r"\Microsoft.WindowsStore_8wekyb3d8bbwe\LocalCache", "category.store_cache"
    ),
    Location(
        _PACKAGES + r"\Microsoft.Windows.Search_cw5n1h2txyewy\AC\INetCache",
        "category.search_cache",
    ),
    Location(r"%LOCALAPPDATA%\Microsoft\Windows\INetCache", "category.internet_cache"),
)


def clean_system_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_system_caches() -> int:
    return estimate_locations(LOCATIONS)
