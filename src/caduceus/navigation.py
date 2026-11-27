"""
Navegação

Lógica pura da navegação nos menus: dado o estado e uma tecla, devolve o novo estado. Não lê
teclas nem desenha nada.
"""

from dataclasses import dataclass, replace

from caduceus.keys import Key
from caduceus.menus import MAIN_MENU, Menu


@dataclass(frozen=True)
class Navigation:
    menus: tuple[Menu, ...] = (MAIN_MENU,)
    selected: tuple[int, ...] = (0,)
    notice: bool = False
    finished: bool = False

    @property
    def menu(self) -> Menu:
        return self.menus[-1]

    @property
    def index(self) -> int:
        return self.selected[-1]


def _move(navigation: Navigation, step: int) -> Navigation:
    index = (navigation.index + step) % len(navigation.menu.items)
    return replace(navigation, selected=(*navigation.selected[:-1], index))


def _enter(navigation: Navigation) -> Navigation:
    item = navigation.menu.items[navigation.index]
    if item.quits:
        return replace(navigation, finished=True)
    if item.submenu is None:
        return replace(navigation, notice=True)
    return replace(
        navigation,
        menus=(*navigation.menus, item.submenu),
        selected=(*navigation.selected, 0),
    )


def _back(navigation: Navigation) -> Navigation:
    if len(navigation.menus) == 1:
        return navigation
    return replace(navigation, menus=navigation.menus[:-1], selected=navigation.selected[:-1])


def press(navigation: Navigation, key: Key) -> Navigation:
    if key is Key.QUIT:
        return replace(navigation, finished=True)
    if navigation.notice:
        return replace(navigation, notice=False)
    if key is Key.UP:
        return _move(navigation, -1)
    if key is Key.DOWN:
        return _move(navigation, 1)
    if key is Key.ENTER:
        return _enter(navigation)
    if key is Key.BACK:
        return _back(navigation)
    return navigation
