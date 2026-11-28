r"""
Limpar as caches dos navegadores

Apaga as caches dos navegadores instalados (Chrome, Edge, Brave, Vivaldi, Opera, Opera GX e
Firefox), de todos os perfis: a cache de páginas, a de código, as de gráficos e a dos service
workers (`Service Worker\CacheStorage`). Só mexe nas pastas de cache: nunca em cookies,
palavras-passe, histórico nem extensões. O que não está instalado é ignorado.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import (
    Location,
    chromium_caches,
    clean_locations,
    estimate_locations,
)

_CATEGORY = "category.browser_cache"
_OPERA = r"%LOCALAPPDATA%\Opera Software\Opera Stable"
_OPERA_GX = r"%LOCALAPPDATA%\Opera Software\Opera GX Stable"
# As caches gráficas (shaders e WebGPU) ficam na raiz do navegador, ao lado dos perfis, e o
# navegador volta a criá-las. A `GraphiteDawnCache` e a `DawnGraphiteCache` são pastas distintas
# (as versões recentes usam a segunda)
_SHADER_FOLDERS = (
    "GrShaderCache",
    "ShaderCache",
    "GraphiteDawnCache",
    "DawnGraphiteCache",
    "DawnWebGPUCache",
    "GPUPersistentCache",
)
_CHROMIUM_ROOTS = (
    r"%LOCALAPPDATA%\Google\Chrome\User Data",
    r"%LOCALAPPDATA%\Microsoft\Edge\User Data",
    r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data",
    r"%LOCALAPPDATA%\Vivaldi\User Data",
    _OPERA,
    _OPERA_GX,
)
LOCATIONS = (
    *(
        Location(rf"{root}\{folder}", _CATEGORY)
        for root in _CHROMIUM_ROOTS
        for folder in _SHADER_FOLDERS
    ),
    *chromium_caches(r"%LOCALAPPDATA%\Google\Chrome\User Data\*", _CATEGORY),
    *chromium_caches(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\*", _CATEGORY),
    *chromium_caches(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\*", _CATEGORY),
    *chromium_caches(r"%LOCALAPPDATA%\Vivaldi\User Data\*", _CATEGORY),
    *chromium_caches(_OPERA, _CATEGORY),
    *chromium_caches(_OPERA + r"\Default", _CATEGORY),
    *chromium_caches(_OPERA_GX, _CATEGORY),
    *chromium_caches(_OPERA_GX + r"\Default", _CATEGORY),
    Location(r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\*\cache2", _CATEGORY),
)


def clean_browser_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_browser_caches() -> int:
    return estimate_locations(LOCATIONS)
