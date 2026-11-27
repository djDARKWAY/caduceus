"""
Limpar as caches do sistema

Apaga as transferências do Windows Update e da Otimização da Entrega, os relatórios de erros
antigos e as caches do Windows e de shaders. Limpa ainda os restos de instaladores de drivers
da NVIDIA e da AMD. O Windows e os jogos voltam a criar as caches quando precisam.
"""

from caduceus.config import LOG_MIN_AGE_HOURS
from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

_PACKAGES = r"%LOCALAPPDATA%\Packages"
_DRIVERS = "category.driver_installers"
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
    *(
        Location(
            rf"{root}\Microsoft\Windows\WER\{folder}",
            "category.error_reports",
            min_age_hours=LOG_MIN_AGE_HOURS,
            needs_admin=root == "%PROGRAMDATA%",
        )
        for root in ("%LOCALAPPDATA%", "%PROGRAMDATA%")
        for folder in ("ReportArchive", "ReportQueue", "Temp")
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
    Location(r"%SYSTEMDRIVE%\NVIDIA", _DRIVERS, needs_admin=True),
    Location(r"%SYSTEMDRIVE%\AMD", _DRIVERS, needs_admin=True),
    Location(
        r"%PROGRAMDATA%\NVIDIA Corporation\Downloader",
        _DRIVERS,
        needs_admin=True,
    ),
)


def clean_system_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_system_caches() -> int:
    return estimate_locations(LOCATIONS)
