"""
Menus

Estrutura dos menus, só dados: que menus existem e que opções cada um tem. Os textos vêm dos
ficheiros de idiomas, pelas chaves aqui indicadas. Juntar um menu ou uma opção é juntar dados.
"""

from dataclasses import dataclass
from enum import Enum

from caduceus.maintenance.actions import Action, Estimator
from caduceus.maintenance.caches import clean_caches, estimate_caches
from caduceus.maintenance.components import clean_components
from caduceus.maintenance.hidden_junk import clean_hidden_junk, estimate_hidden_junk
from caduceus.maintenance.recycle_bin import empty_recycle_bin, estimate_recycle_bin
from caduceus.maintenance.temp_files import clean_temp_files, estimate_temp_files
from caduceus.maintenance.windows_old import clean_windows_old, estimate_windows_old


class AdminNeed(Enum):
    """Quanto da opção exige administrador; o valor é a chave do texto do aviso."""

    SOME = "admin.some"
    ALL = "admin.all"


# Sem submenu, ação nem quits, a opção ainda não tem ecrã e mostra um aviso.
# `admin` diz se (parte d)a opção só funciona como administrador; `risky`, as ações que o
# Modo seguro bloqueia; `confirm_key`, as que só correm depois de o utilizador confirmar o aviso
# com esse texto; `estimate`, o que calcula quanto a ação deve libertar (para a tabela do menu);
# `setting`, o nome da definição que a opção liga ou desliga; `runs_all`, a opção que corre todas as
# ações do menu que o Modo seguro deixa correr.
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
            confirm_key="cleanup.recycle_bin.confirm",
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
            "cleanup.caches",
            action=clean_caches,
            description_key="cleanup.caches.description",
            admin=AdminNeed.SOME,
            estimate=estimate_caches,
        ),
        MenuItem(
            "cleanup.components",
            action=clean_components,
            description_key="cleanup.components.description",
            admin=AdminNeed.ALL,
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

MAINTENANCE_MENU = Menu(
    "maintenance.title",
    (
        MenuItem(
            "maintenance.cleanup",
            CLEANUP_MENU,
            description_key="maintenance.cleanup.description",
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
