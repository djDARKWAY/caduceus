"""
Menus

Estrutura dos menus, só dados: que menus existem e que opções cada um tem. Os textos vêm dos
ficheiros de idiomas, pelas chaves aqui indicadas. Juntar um menu ou uma opção é juntar dados.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    """Uma opção de menu.

    Sem `submenu` e sem `quits`, a opção ainda não tem ecrã e mostra um aviso. A descrição, se
    existir, aparece à direita do menu enquanto a opção está selecionada.
    """

    label_key: str
    submenu: "Menu | None" = None
    quits: bool = False
    description_key: str | None = None


@dataclass(frozen=True)
class Menu:
    title_key: str
    items: tuple[MenuItem, ...]


MAINTENANCE_MENU = Menu(
    "maintenance.title",
    (MenuItem("maintenance.cleanup", description_key="maintenance.cleanup.description"),),
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
