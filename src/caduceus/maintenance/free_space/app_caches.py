"""
Limpar as caches das aplicações

Apaga as caches de aplicações conhecidas: Discord, Slack, Microsoft Teams, Telegram, Signal,
Spotify, Zoom (neste, os registos), Notion, Obsidian, Figma, Postman, VS Code (incluindo as
extensões descarregadas), Cursor, GitHub Desktop, a loja e a cache de transferências do Steam
(`depotcache`), o Epic Games Launcher, o Ubisoft Connect, o Adobe (a cache de multimédia), o
OneDrive e o Google Drive (só os registos). Só mexe nas pastas de cache: nunca em contas, mensagens,
notas, definições, jogos instalados nem nas músicas descarregadas do Spotify. As aplicações de
conversa, trabalho e multimédia que estiverem abertas são fechadas à força antes de limpar (não as
de programação, nem o Steam e o Epic, para não perder trabalho nem uma transferência). O que não
está instalado é ignorado.
"""

import time

from caduceus.maintenance.actions import Outcome, Report
from caduceus.maintenance.free_space.cleaner import (
    Location,
    chromium_caches,
    clean_locations,
    estimate_locations,
)
from caduceus.maintenance.system_tool import run_system_tool

_VSCODE = "category.app_vscode"
_STEAM = "category.app_steam"
_NEW_TEAMS = r"%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams"
_SPOTIFY_STORE = r"%LOCALAPPDATA%\Packages\SpotifyAB.SpotifyMusic_zpdnekdrzrea0\LocalCache\Spotify"
# O código de saída do `taskkill` é 0 quando fechou algo; sem nada aberto, devolve outro e segue-se
_APP_PROCESSES = (
    "Discord.exe",
    "slack.exe",
    "Teams.exe",
    "ms-teams.exe",
    "Telegram.exe",
    "Signal.exe",
    "Spotify.exe",
    "Zoom.exe",
    "Notion.exe",
    "Obsidian.exe",
    "Figma.exe",
    "Postman.exe",
    "GitHubDesktop.exe",
)
_RELEASE_SECONDS = 1  # o tempo para o Windows libertar os ficheiros das aplicações fechadas
_TELEGRAM = r"%APPDATA%\Telegram Desktop\tdata\user_data"
LOCATIONS = (
    *chromium_caches(r"%APPDATA%\discord", "category.app_discord"),
    *chromium_caches(r"%APPDATA%\Slack", "category.app_slack"),
    *chromium_caches(r"%APPDATA%\Signal", "category.app_signal"),
    Location(r"%LOCALAPPDATA%\Google\DriveFS\Logs", "category.app_google_drive"),
    Location(r"%LOCALAPPDATA%\Ubisoft Game Launcher\cache", "category.app_ubisoft"),
    *chromium_caches(r"%APPDATA%\Code", _VSCODE),
    Location(r"%APPDATA%\Code\CachedData", _VSCODE),
    Location(r"%APPDATA%\Code\CachedExtensionVSIXs", _VSCODE),
    *chromium_caches(r"%APPDATA%\Cursor", "category.app_cursor"),
    *chromium_caches(r"%APPDATA%\Notion", "category.app_notion"),
    *chromium_caches(r"%APPDATA%\obsidian", "category.app_obsidian"),
    *chromium_caches(r"%APPDATA%\Figma", "category.app_figma"),
    *chromium_caches(r"%APPDATA%\Postman", "category.app_postman"),
    Location(r"%LOCALAPPDATA%\EpicGamesLauncher\Saved\webcache*", "category.app_epic"),
    *chromium_caches(r"%LOCALAPPDATA%\Steam\htmlcache\*", _STEAM),
    Location(r"%PROGRAMFILES(X86)%\Steam\depotcache", _STEAM),
    Location(r"%PROGRAMFILES(X86)%\Steam\appcache\httpcache", _STEAM),
    *chromium_caches(r"%APPDATA%\Microsoft\Teams", "category.app_teams"),
    *chromium_caches(_NEW_TEAMS + r"\EBWebView\Default", "category.app_teams"),
    Location(r"%LOCALAPPDATA%\Spotify\Data", "category.app_spotify"),
    Location(_SPOTIFY_STORE + r"\Data", "category.app_spotify"),
    Location(_TELEGRAM + r"\cache", "category.app_telegram"),
    Location(_TELEGRAM + r"\media_cache", "category.app_telegram"),
    Location(r"%APPDATA%\Zoom\logs", "category.app_zoom"),
    *chromium_caches(r"%APPDATA%\GitHub Desktop", "category.app_github_desktop"),
    Location(r"%APPDATA%\Adobe\Common\Media Cache Files", "category.app_adobe"),
    Location(r"%APPDATA%\Adobe\Common\Media Cache", "category.app_adobe"),
    Location(r"%LOCALAPPDATA%\Microsoft\OneDrive\logs", "category.app_onedrive"),
)


def _close_running_apps(report: Report) -> None:
    command = ["/F", "/T"] + [argument for name in _APP_PROCESSES for argument in ("/IM", name)]
    try:
        closed_any = run_system_tool("taskkill.exe", command, report, "cleanup.closing_apps.step")
    except OSError:
        return  # sem o taskkill, limpa-se na mesma o que não estiver em uso
    if closed_any:
        time.sleep(_RELEASE_SECONDS)


def clean_app_caches(report: Report) -> Outcome:
    _close_running_apps(report)
    return clean_locations(LOCATIONS, report)


def estimate_app_caches() -> int:
    return estimate_locations(LOCATIONS)
