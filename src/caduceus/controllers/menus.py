"""
Menus

Estrutura dos menus, só dados: que menus existem e que opções cada um tem. Os textos vêm dos
ficheiros de idiomas, pelas chaves aqui indicadas. Juntar um menu ou uma opção é juntar dados.
"""

from dataclasses import dataclass

from caduceus.maintenance.actions import Action
from caduceus.maintenance.caches import clean_caches
from caduceus.maintenance.hidden_junk import clean_hidden_junk
from caduceus.maintenance.recycle_bin import empty_recycle_bin
from caduceus.maintenance.temp_files import clean_temp_files


# Sem submenu, ação nem quits, a opção ainda não tem ecrã e mostra um aviso
@dataclass(frozen=True)
class MenuItem:
    label_key: str
    submenu: "Menu | None" = None
    action: Action | None = None
    quits: bool = False
    description_key: str | None = None


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
        ),
        MenuItem(
            "cleanup.recycle_bin",
            action=empty_recycle_bin,
            description_key="cleanup.recycle_bin.description",
        ),
        MenuItem(
            "cleanup.hidden_junk",
            action=clean_hidden_junk,
            description_key="cleanup.hidden_junk.description",
        ),
        MenuItem(
            "cleanup.caches",
            action=clean_caches,
            description_key="cleanup.caches.description",
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

MAIN_MENU = Menu(
    "menu.title",
    (
        MenuItem("menu.scan", description_key="menu.scan.description"),
        MenuItem(
            "menu.maintenance",
            MAINTENANCE_MENU,
            description_key="menu.maintenance.description",
        ),
        MenuItem("menu.settings", description_key="menu.settings.description"),
        MenuItem("menu.exit", quits=True),
    ),
)
