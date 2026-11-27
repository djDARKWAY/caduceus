"""
Navegação

Lógica pura da navegação nos menus: dado o estado e uma tecla, devolve o novo estado. Um menu com
estimativas (o da limpeza) calcula-as ao abrir e, depois de cada ação, só a dessa ação. Uma opção
bloqueada pelo Modo seguro, ou que exige um administrador que não há, não se pode selecionar: o
cursor salta-a. Com o resultado de uma ação no ecrã, só o ENTER faz alguma coisa (volta ao menu);
com um pedido de confirmação, só o ENTER (confirma) e o BACKSPACE (cancela); com um aviso, só o
BACKSPACE (volta). Depois de uma ação que muda a lista (desinstalar um programa), a lista volta a
criar-se quando o utilizador sai do resultado ou do aviso. Nas tabelas, as teclas 1 a N (as colunas)
ordenam a coluna e, ao repetir, invertem a ordem: texto de A a Z, números por ordem crescente, e o
que não tem valor fica no fim. A ordenação só muda a ordem em que as opções aparecem
(`display_order`): o menu mantém a sua, que é a que «Correr todas as limpezas» segue. Não lê teclas,
não desenha e não corre ações: quando uma opção tem ação, o estado fica com `running` e é a
aplicação que a corre e depois chama `complete`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from caduceus.controllers.keys import Key
from caduceus.controllers.menus import MAIN_MENU, AdminNeed, Menu, MenuItem, item_label
from caduceus.maintenance.actions import Action, Outcome
from caduceus.maintenance.free_space.run_all import run_all
from caduceus.settings import Settings

NOT_AVAILABLE_NOTICE = "notice.not_available"
NOTHING_SELECTABLE_NOTICE = "notice.nothing_selectable"
SETTINGS_NOT_SAVED_NOTICE = "notice.settings_not_saved"


@dataclass(frozen=True)
class Sort:
    column: int  # a coluna ordenada, a contar do zero
    descending: bool = False


@dataclass(frozen=True)
class Navigation:
    menus: tuple[Menu, ...] = (MAIN_MENU,)
    selected: tuple[int, ...] = (0,)
    notice: str | None = None  # chave do texto do aviso no ecrã, se houver
    confirming: bool = False
    to_estimate: tuple[str, ...] = ()  # chaves das opções cuja estimativa falta calcular
    estimates: Mapping[str, int | None] = field(default_factory=dict)
    settings: Settings = field(default_factory=Settings)
    administrator: bool = True  # falso quando o Caduceus não corre como administrador
    running: Action | None = None
    outcome: Outcome | None = None
    finished: bool = False
    closes_console: bool = False  # ao sair, fecha também a consola (ao reabrir como administrador)
    texts: Mapping[str, str] = field(default_factory=dict)  # para ordenar o texto que se vê
    sort: Sort | None = None  # a coluna ordenada do menu aberto, se houver

    @property
    def estimating(self) -> bool:
        return bool(self.to_estimate)

    @property
    def menu(self) -> Menu:
        return self.menus[-1]

    @property
    def index(self) -> int:
        return self.selected[-1]

    @property
    def item(self) -> MenuItem:
        return self.menu.items[self.index]


def _estimable(menu: Menu) -> tuple[str, ...]:
    return tuple(item.label_key for item in menu.items if item.estimate is not None)


def has_state_column(menu: Menu) -> bool:
    return any(item.state is not None for item in menu.items)


def column_count(menu: Menu) -> int:
    """As colunas da tabela do menu (o nome, o estado se houver, e as células), ou 0 se o menu não
    é uma tabela."""
    if menu.columns:
        return 1 + has_state_column(menu) + len(menu.columns)
    if _estimable(menu):
        return 2  # a tabela das estimativas: a ação e o ganho
    return 0


def _sort_value(navigation: Navigation, item: MenuItem, column: int) -> int | str | None:
    """O valor da opção na coluna, ou None se não se conhece (essas ficam no fim)."""
    menu = navigation.menu
    if column == 0:
        return item_label(navigation.texts, item).casefold()
    if not menu.columns:
        return navigation.estimates.get(item.label_key)
    if has_state_column(menu):
        if column == 1:
            return item.state() if item.state is not None else False
        column -= 1
    cell = item.cells[column - 1] if column - 1 < len(item.cells) else None
    if isinstance(cell, str):
        return navigation.texts.get(cell, cell).casefold()
    return cell


def display_order(navigation: Navigation) -> list[int]:
    """Os índices das opções do menu pela ordem em que aparecem. Sem ordenação, é a do menu; com
    ela, a da coluna escolhida, com a opção que corre tudo sempre em último."""
    items = navigation.menu.items
    sort = navigation.sort
    if sort is None:
        return list(range(len(items)))
    valued: list[tuple[int | str, int]] = []
    unknown: list[int] = []
    for index, item in enumerate(items):
        if item.runs_all:
            continue
        value = _sort_value(navigation, item, sort.column)
        if value is None:
            unknown.append(index)
        else:
            valued.append((value, index))
    valued.sort(key=lambda pair: pair[0], reverse=sort.descending)
    runs_all = [index for index, item in enumerate(items) if item.runs_all]
    return [index for _value, index in valued] + unknown + runs_all


def blocked_by_safe_mode(navigation: Navigation, item: MenuItem) -> bool:
    return item.risky and navigation.settings.safe_mode


def blocked_by_missing_administrator(navigation: Navigation, item: MenuItem) -> bool:
    """As opções que só funcionam como administrador não se escolhem sem ele: não fariam nada."""
    return item.admin is AdminNeed.ALL and not navigation.administrator


def blocked_by_present_administrator(navigation: Navigation, item: MenuItem) -> bool:
    """Reabrir como administrador não faz sentido quando já se é."""
    return item.only_without_admin and navigation.administrator


def is_blocked(navigation: Navigation, item: MenuItem) -> bool:
    return (
        blocked_by_safe_mode(navigation, item)
        or blocked_by_missing_administrator(navigation, item)
        or blocked_by_present_administrator(navigation, item)
    )


def _action_for(navigation: Navigation, item: MenuItem) -> Action | None:
    """A ação da opção; a que corre tudo junta as do menu que o Modo seguro deixa correr."""
    if not item.runs_all:
        return item.action
    return run_all(
        [
            (other.label_key, other.admin is not None, other.action)
            for other in navigation.menu.items
            if other.action is not None and not is_blocked(navigation, other)
        ]
    )


def _move(navigation: Navigation, step: int) -> Navigation:
    """Passa à opção seguinte (ou anterior), pela ordem mostrada, que não esteja bloqueada: essas
    nunca se selecionam."""
    items = navigation.menu.items
    order = display_order(navigation)
    position = order.index(navigation.index)
    for _ in order:
        position = (position + step) % len(order)
        if not is_blocked(navigation, items[order[position]]):
            return replace(navigation, selected=(*navigation.selected[:-1], order[position]))
    return navigation


def _sort(navigation: Navigation, column: int) -> Navigation:
    """Ordena a coluna de A a Z (ou por ordem crescente); a mesma tecla outra vez inverte."""
    if column >= column_count(navigation.menu):
        return navigation
    current = navigation.sort
    descending = current is not None and current.column == column and not current.descending
    return replace(navigation, sort=Sort(column, descending))


def _enter(navigation: Navigation) -> Navigation:
    item = navigation.item
    if item.quits:
        return replace(navigation, finished=True)
    if item.choice is not None:
        setting, value = item.choice
        return _back(replace(navigation, settings=navigation.settings.with_value(setting, value)))
    if is_blocked(navigation, item):
        return navigation
    if item.action is not None or item.runs_all:
        if item.confirm_key is not None:
            return replace(navigation, confirming=True)
        return replace(navigation, running=_action_for(navigation, item))
    submenu = item.submenu_loader() if item.submenu_loader is not None else item.submenu
    if submenu is not None:
        free = [i for i, other in enumerate(submenu.items) if not is_blocked(navigation, other)]
        if not free:
            return replace(navigation, notice=NOTHING_SELECTABLE_NOTICE)
        first = free[0]
        return replace(
            navigation,
            menus=(*navigation.menus, submenu),
            selected=(*navigation.selected, first),
            to_estimate=_estimable(submenu),
            estimates={},
            sort=None,
        )
    return replace(navigation, notice=NOT_AVAILABLE_NOTICE)


def _back(navigation: Navigation) -> Navigation:
    if len(navigation.menus) == 1:
        return navigation
    return replace(
        navigation, menus=navigation.menus[:-1], selected=navigation.selected[:-1], sort=None
    )


def _reload(navigation: Navigation) -> Navigation:
    """Volta a criar a lista depois de uma ação que a muda, com o cursor na mesma posição da lista
    mostrada (e a mesma ordenação)."""
    if not navigation.item.refreshes_menu or len(navigation.menus) < 2:
        return navigation
    parent = navigation.menus[-2].items[navigation.selected[-2]]
    if parent.submenu_loader is None:
        return navigation
    position = display_order(navigation).index(navigation.index)
    reloaded = replace(navigation, menus=(*navigation.menus[:-1], parent.submenu_loader()))
    order = display_order(reloaded)
    index = order[min(position, len(order) - 1)]
    reloaded = replace(reloaded, selected=(*navigation.selected[:-1], index))
    return _move(reloaded, 1) if is_blocked(reloaded, reloaded.item) else reloaded


def _answer_confirmation(navigation: Navigation, key: Key) -> Navigation:
    if key is Key.ENTER:
        action = _action_for(navigation, navigation.item)
        return replace(navigation, confirming=False, running=action)
    if key is Key.BACK:
        return replace(navigation, confirming=False)
    return navigation


def _navigate(navigation: Navigation, key: Key) -> Navigation:
    if key.column is not None:
        return _sort(navigation, key.column)
    if key is Key.UP:
        return _move(navigation, -1)
    if key is Key.DOWN:
        return _move(navigation, 1)
    if key is Key.ENTER:
        return _enter(navigation)
    if key is Key.BACK:
        return _back(navigation)
    return navigation


def press(navigation: Navigation, key: Key) -> Navigation:
    if navigation.estimating:
        return navigation
    if navigation.outcome is not None:
        if key is not Key.ENTER:
            return navigation
        # Só se volta a estimar o que acabou de ser limpo: o resto da tabela mantém-se
        item = navigation.item
        again = _estimable(navigation.menu) if item.runs_all else (item.label_key,)
        again = tuple(key for key in again if key in _estimable(navigation.menu))
        return _reload(replace(navigation, outcome=None, to_estimate=again))
    if navigation.confirming:
        return _answer_confirmation(navigation, key)
    if key is Key.QUIT:
        return replace(navigation, finished=True)
    if navigation.notice is not None:
        return _reload(replace(navigation, notice=None)) if key is Key.BACK else navigation
    return _navigate(navigation, key)


def finish_estimates(navigation: Navigation, estimates: Mapping[str, int | None]) -> Navigation:
    return replace(navigation, to_estimate=(), estimates={**navigation.estimates, **estimates})


def complete(navigation: Navigation, outcome: Outcome) -> Navigation:
    if outcome.quit_after:
        return replace(navigation, running=None, finished=True, closes_console=True)
    if outcome.notice is not None:
        return replace(navigation, running=None, notice=outcome.notice)
    went_wrong = bool(outcome.failures or outcome.admin_required)
    if navigation.item.instant and not went_wrong:
        return replace(navigation, running=None)
    return replace(navigation, running=None, outcome=outcome)
