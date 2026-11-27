"""
Limpar as caches das aplicações

Apaga as caches de aplicações conhecidas: Discord, Slack, Microsoft Teams, Telegram, Spotify, Zoom
(neste, os registos), Notion, Obsidian, Figma, Postman, VS Code (incluindo as extensões
descarregadas), Cursor, a loja do Steam e o Epic Games Launcher. Só mexe nas pastas de cache: nunca
em contas, mensagens, notas, definições nem nas músicas descarregadas do Spotify. O que não está
instalado é ignorado.
"""

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import (
    Location,
    chromium_caches,
    clean_locations,
    estimate_locations,
)

_VSCODE = "category.app_vscode"
_NEW_TEAMS = r"%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams"
_SPOTIFY_STORE = r"%LOCALAPPDATA%\Packages\SpotifyAB.SpotifyMusic_zpdnekdrzrea0\LocalCache\Spotify"
_TELEGRAM = r"%APPDATA%\Telegram Desktop\tdata\user_data"
LOCATIONS = (
    *chromium_caches(r"%APPDATA%\discord", "category.app_discord"),
    *chromium_caches(r"%APPDATA%\Slack", "category.app_slack"),
    *chromium_caches(r"%APPDATA%\Code", _VSCODE),
    Location(r"%APPDATA%\Code\CachedData", _VSCODE),
    Location(r"%APPDATA%\Code\CachedExtensionVSIXs", _VSCODE),
    *chromium_caches(r"%APPDATA%\Cursor", "category.app_cursor"),
    *chromium_caches(r"%APPDATA%\Notion", "category.app_notion"),
    *chromium_caches(r"%APPDATA%\obsidian", "category.app_obsidian"),
    *chromium_caches(r"%APPDATA%\Figma", "category.app_figma"),
    *chromium_caches(r"%APPDATA%\Postman", "category.app_postman"),
    Location(r"%LOCALAPPDATA%\EpicGamesLauncher\Saved\webcache*", "category.app_epic"),
    *chromium_caches(r"%LOCALAPPDATA%\Steam\htmlcache\*", "category.app_steam"),
    *chromium_caches(r"%APPDATA%\Microsoft\Teams", "category.app_teams"),
    *chromium_caches(_NEW_TEAMS + r"\EBWebView\Default", "category.app_teams"),
    Location(r"%LOCALAPPDATA%\Spotify\Data", "category.app_spotify"),
    Location(_SPOTIFY_STORE + r"\Data", "category.app_spotify"),
    Location(_TELEGRAM + r"\cache", "category.app_telegram"),
    Location(_TELEGRAM + r"\media_cache", "category.app_telegram"),
    Location(r"%APPDATA%\Zoom\logs", "category.app_zoom"),
)


def clean_app_caches(report: Report) -> Outcome:
    return clean_locations(LOCATIONS, report)


def estimate_app_caches() -> int:
    return estimate_locations(LOCATIONS)
