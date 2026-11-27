"""
Navegação

Lógica pura da navegação nos menus: dado o estado e uma tecla, devolve o novo estado. Não lê
teclas, não desenha e não corre ações: quando uma opção tem ação, o estado fica com `running` e
é a aplicação que a corre e depois chama `complete`.
"""

from dataclasses import dataclass, replace

from caduceus.controllers.keys import Key
from caduceus.controllers.menus import MAIN_MENU, Menu, MenuItem
from caduceus.maintenance.actions import Action, Outcome


@dataclass(frozen=True)
class Navigation:
    menus: tuple[Menu, ...] = (MAIN_MENU,)
    selected: tuple[int, ...] = (0,)
    notice: bool = False
    running: Action | None = None
    outcome: Outcome | None = None
    finished: bool = False

    @property
    def menu(self) -> Menu:
        return self.menus[-1]

    @property
    def index(self) -> int:
        return self.selected[-1]

    @property
    def item(self) -> MenuItem:
        return self.menu.items[self.index]


def _move(navigation: Navigation, step: int) -> Navigation:
    index = (navigation.index + step) % len(navigation.menu.items)
    return replace(navigation, selected=(*navigation.selected[:-1], index))


def _enter(navigation: Navigation) -> Navigation:
    item = navigation.item
    if item.quits:
        return replace(navigation, finished=True)
    if item.action is not None:
        return replace(navigation, running=item.action)
    if item.submenu is not None:
        return replace(
            navigation,
            menus=(*navigation.menus, item.submenu),
            selected=(*navigation.selected, 0),
        )
    return replace(navigation, notice=True)


def _back(navigation: Navigation) -> Navigation:
    if len(navigation.menus) == 1:
        return navigation
    return replace(navigation, menus=navigation.menus[:-1], selected=navigation.selected[:-1])


def press(navigation: Navigation, key: Key) -> Navigation:
    if key is Key.QUIT:
        return replace(navigation, finished=True)
    if navigation.notice:
        return replace(navigation, notice=False)
    if navigation.outcome is not None:
        return replace(navigation, outcome=None)
    if key is Key.UP:
        return _move(navigation, -1)
    if key is Key.DOWN:
        return _move(navigation, 1)
    if key is Key.ENTER:
        return _enter(navigation)
    if key is Key.BACK:
        return _back(navigation)
    return navigation


def complete(navigation: Navigation, outcome: Outcome) -> Navigation:
    return replace(navigation, running=None, outcome=outcome)
