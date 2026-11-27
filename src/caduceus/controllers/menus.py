"""
Menus

Estrutura dos menus, só dados: que menus existem e que opções cada um tem. Os textos vêm dos
ficheiros de idiomas, pelas chaves aqui indicadas. Juntar um menu ou uma opção é juntar dados.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from caduceus.maintenance.actions import Action, Estimator
from caduceus.maintenance.free_space.app_caches import clean_app_caches, estimate_app_caches
from caduceus.maintenance.free_space.browser_caches import (
    clean_browser_caches,
    estimate_browser_caches,
)
from caduceus.maintenance.free_space.components import clean_components
from caduceus.maintenance.free_space.developer_caches import (
    clean_developer_caches,
    estimate_developer_caches,
)
from caduceus.maintenance.free_space.hidden_junk import clean_hidden_junk, estimate_hidden_junk
from caduceus.maintenance.free_space.recycle_bin import empty_recycle_bin, estimate_recycle_bin
from caduceus.maintenance.free_space.restore_points import clean_restore_points
from caduceus.maintenance.free_space.system_caches import (
    clean_system_caches,
    estimate_system_caches,
)
from caduceus.maintenance.free_space.temp_files import clean_temp_files, estimate_temp_files
from caduceus.maintenance.free_space.windows_logs import clean_windows_logs, estimate_windows_logs
from caduceus.maintenance.free_space.windows_old import clean_windows_old, estimate_windows_old
from caduceus.maintenance.system_tweaks.hibernation import is_hibernation_on, toggle_hibernation


class AdminNeed(Enum):
    """Quanto da opção exige administrador; o valor é a chave do texto do aviso."""

    SOME = "admin.some"
    ALL = "admin.all"


# Sem submenu, ação nem quits, a opção ainda não tem ecrã e mostra um aviso.
# `admin` diz se (parte d)a opção só funciona como administrador; `risky`, as ações que o
# Modo seguro bloqueia; `confirm_key`, as que só correm depois de o utilizador confirmar o aviso
# com esse texto; `estimate`, o que calcula quanto a ação deve libertar (para a tabela do menu);
# `setting`, o nome da definição que a opção liga ou desliga; `runs_all`, a opção que corre todas as
# ações do menu que o Modo seguro deixa correr; `state`, o estado atual (ligado ou desligado) que a
# ação inverte, mostrado ao lado do nome. O aviso de `confirm_key` só aparece quando o estado é
# ligado (a direção que pode ter consequências).
@dataclass(frozen=True)
class MenuItem:
    label_key: str
    submenu: "Menu | None" = None
    action: Action | None = None
    quits: bool = False
    description_key: str | None = None
    admin: AdminNeed | None = None
    risky: bool = False
    confirm_key: str | None = None
    estimate: Estimator | None = None
    setting: str | None = None
    runs_all: bool = False
    state: Callable[[], bool] | None = None


@dataclass(frozen=True)
class Menu:
    title_key: str
    items: tuple[MenuItem, ...]


CLEANUP_MENU = Menu(
    "cleanup.title",
    (
        MenuItem(
            "cleanup.temp_files",
            action=clean_temp_files,
            description_key="cleanup.temp_files.description",
            admin=AdminNeed.SOME,
            estimate=estimate_temp_files,
        ),
        MenuItem(
            "cleanup.recycle_bin",
            action=empty_recycle_bin,
            description_key="cleanup.recycle_bin.description",
            estimate=estimate_recycle_bin,
        ),
        MenuItem(
            "cleanup.hidden_junk",
            action=clean_hidden_junk,
            description_key="cleanup.hidden_junk.description",
            admin=AdminNeed.SOME,
            estimate=estimate_hidden_junk,
        ),
        MenuItem(
            "cleanup.windows_logs",
            action=clean_windows_logs,
            description_key="cleanup.windows_logs.description",
            admin=AdminNeed.ALL,
            estimate=estimate_windows_logs,
        ),
        MenuItem(
            "cleanup.system_caches",
            action=clean_system_caches,
            description_key="cleanup.system_caches.description",
            admin=AdminNeed.SOME,
            estimate=estimate_system_caches,
        ),
        MenuItem(
            "cleanup.browser_caches",
            action=clean_browser_caches,
            description_key="cleanup.browser_caches.description",
            estimate=estimate_browser_caches,
        ),
        MenuItem(
            "cleanup.app_caches",
            action=clean_app_caches,
            description_key="cleanup.app_caches.description",
            estimate=estimate_app_caches,
        ),
        MenuItem(
            "cleanup.developer_caches",
            action=clean_developer_caches,
            description_key="cleanup.developer_caches.description",
            estimate=estimate_developer_caches,
        ),
        MenuItem(
            "cleanup.components",
            action=clean_components,
            description_key="cleanup.components.description",
            admin=AdminNeed.ALL,
        ),
        MenuItem(
            "cleanup.restore_points",
            action=clean_restore_points,
            description_key="cleanup.restore_points.description",
            admin=AdminNeed.ALL,
            risky=True,
            confirm_key="cleanup.restore_points.confirm",
        ),
        MenuItem(
            "cleanup.windows_old",
            action=clean_windows_old,
            description_key="cleanup.windows_old.description",
            admin=AdminNeed.ALL,
            risky=True,
            confirm_key="cleanup.windows_old.confirm",
            estimate=estimate_windows_old,
        ),
        MenuItem(
            "cleanup.all",
            description_key="cleanup.all.description",
            admin=AdminNeed.SOME,
            confirm_key="cleanup.all.confirm",
            runs_all=True,
        ),
    ),
)

TWEAKS_MENU = Menu(
    "tweaks.title",
    (
        MenuItem(
            "tweaks.hibernation",
            action=toggle_hibernation,
            state=is_hibernation_on,
            description_key="tweaks.hibernation.description",
            admin=AdminNeed.ALL,
            risky=True,
            confirm_key="tweaks.hibernation.confirm",
        ),
    ),
)

MAINTENANCE_MENU = Menu(
    "maintenance.title",
    (
        MenuItem(
            "maintenance.cleanup",
            CLEANUP_MENU,
            description_key="maintenance.cleanup.description",
        ),
        MenuItem(
            "maintenance.tweaks",
            TWEAKS_MENU,
            description_key="maintenance.tweaks.description",
        ),
    ),
)

SETTINGS_MENU = Menu(
    "settings.title",
    (
        MenuItem(
            "settings.safe_mode",
            description_key="settings.safe_mode.description",
            setting="safe_mode",
        ),
    ),
)

MAIN_MENU = Menu(
    "menu.title",
    (
        MenuItem("menu.scan", description_key="menu.scan.description"),
        MenuItem(
            "menu.maintenance",
            MAINTENANCE_MENU,
            description_key="menu.maintenance.description",
        ),
        MenuItem(
            "menu.settings",
            SETTINGS_MENU,
            description_key="menu.settings.description",
        ),
        MenuItem("menu.exit", quits=True),
    ),
)
