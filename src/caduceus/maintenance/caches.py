"""
Limpar as caches

Apaga a cache de transferências do Windows Update, a cache da Otimização da Entrega, as caches de
shaders do DirectX, da NVIDIA e da AMD, as caches dos navegadores (Chrome, Edge, Brave e Firefox, de
todos os perfis) e as de aplicações Electron conhecidas (Discord, Slack, VS Code e a loja do Steam).
Só mexe nas pastas de cache: nunca em cookies, palavras-passe, histórico nem dados das aplicações.
O Windows, os jogos, os navegadores e as aplicações voltam a criá-las quando precisam.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.cleaner import Location, clean_locations, estimate_locations

# As pastas de cache que as aplicações baseadas no Chromium guardam dentro de cada perfil
_CHROMIUM_CACHE_FOLDERS = ("Cache", "Code Cache", "GPUCache")


def _chromium_caches(profile_folder: str, label_key: str) -> tuple[Location, ...]:
    return tuple(
        Location(rf"{profile_folder}\{folder}", label_key) for folder in _CHROMIUM_CACHE_FOLDERS
    )


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
    *_chromium_caches(r"%LOCALAPPDATA%\Google\Chrome\User Data\*", "category.browser_cache"),
    *_chromium_caches(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\*", "category.browser_cache"),
    *_chromium_caches(
        r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\*", "category.browser_cache"
    ),
    Location(r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\cache2", "category.browser_cache"),
    *_chromium_caches(r"%APPDATA%\discord", "category.app_cache"),
    *_chromium_caches(r"%APPDATA%\Slack", "category.app_cache"),
    *_chromium_caches(r"%APPDATA%\Code", "category.app_cache"),
    *_chromium_caches(r"%LOCALAPPDATA%\Steam\htmlcache\*", "category.app_cache"),
)


def clean_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_caches() -> int:
    return estimate_locations(LOCATIONS)
