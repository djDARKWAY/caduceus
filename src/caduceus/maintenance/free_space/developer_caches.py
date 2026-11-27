r"""
Limpar as caches de programação

Apaga as caches de pacotes do npm, do pnpm, do Yarn, do Bun, do pip, do uv, do Poetry, do Composer,
do NuGet, do Gradle, do Cargo, do Go e do Dart, a cache de pacotes do Unity, a Derived Data Cache do
Unreal Engine, a cache de componentes do Visual Studio e as caches
dos IDE da JetBrains (que se reconstroem com uma nova indexação). Os pacotes voltam a ser
descarregados na próxima compilação ou instalação (sem rede, essa compilação falha). Não mexe nos
projetos, nos `node_modules` nem na pasta `.nuget\packages`. O que não está instalado é ignorado.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import Location, clean_locations, estimate_locations

LOCATIONS = (
    Location(r"%LOCALAPPDATA%\npm-cache", "category.npm_cache"),
    Location(r"%LOCALAPPDATA%\pnpm\store", "category.pnpm_cache"),
    Location(r"%LOCALAPPDATA%\pnpm-cache", "category.pnpm_cache"),
    Location(r"%LOCALAPPDATA%\Yarn\Cache", "category.yarn_cache"),
    Location(r"%LOCALAPPDATA%\Yarn\Berry\cache", "category.yarn_cache"),
    Location(r"%USERPROFILE%\.bun\install\cache", "category.bun_cache"),
    Location(r"%LOCALAPPDATA%\Composer\files", "category.composer_cache"),
    Location(r"%LOCALAPPDATA%\Composer\repo", "category.composer_cache"),
    Location(r"%LOCALAPPDATA%\pip\Cache", "category.pip_cache"),
    Location(r"%LOCALAPPDATA%\NuGet\v3-cache", "category.nuget_cache"),
    Location(r"%LOCALAPPDATA%\NuGet\plugins-cache", "category.nuget_cache"),
    Location(r"%USERPROFILE%\.gradle\caches", "category.gradle_cache"),
    Location(r"%USERPROFILE%\.cargo\registry\cache", "category.cargo_cache"),
    Location(r"%USERPROFILE%\.cargo\registry\src", "category.cargo_cache"),
    Location(r"%LOCALAPPDATA%\uv\cache", "category.uv_cache"),
    Location(r"%LOCALAPPDATA%\pypoetry\Cache", "category.poetry_cache"),
    Location(r"%LOCALAPPDATA%\go-build", "category.go_cache"),
    Location(r"%USERPROFILE%\go\pkg\mod\cache\download", "category.go_cache"),
    Location(r"%LOCALAPPDATA%\Pub\Cache", "category.dart_cache"),
    Location(
        r"%LOCALAPPDATA%\Microsoft\VisualStudio\*\ComponentModelCache",
        "category.visual_studio_cache",
    ),
    Location(r"%LOCALAPPDATA%\JetBrains\*\caches", "category.jetbrains_cache"),
    Location(r"%LOCALAPPDATA%\Unity\cache\packages", "category.unity_cache"),
    Location(r"%LOCALAPPDATA%\UnrealEngine\Common\DerivedDataCache", "category.unreal_cache"),
)


def clean_developer_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_developer_caches() -> int:
    return estimate_locations(LOCATIONS)
