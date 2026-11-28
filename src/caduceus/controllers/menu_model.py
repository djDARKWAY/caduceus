"""
Modelo dos menus

Os tipos com que os menus se descrevem: o `Menu`, a `MenuItem` (o que cada opção faz e mostra) e
o que uma opção exige de administrador. Só dados, sem lógica de navegação.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from caduceus.maintenance.actions import Action, Estimator


class AdminNeed(Enum):
    """Quanto da opção exige administrador; o valor é a chave do texto do aviso."""

    SOME = "admin.some"
    ALL = "admin.all"


# Sem submenu, ação nem quits, a opção ainda não tem ecrã e mostra um aviso.
# `admin` diz se (parte d)a opção só funciona como administrador; `risky`, as ações que o
# Modo seguro bloqueia; `confirm_key`, as que só correm depois de o utilizador confirmar o aviso
# com esse texto; `estimate`, o que calcula quanto a ação deve libertar (para a tabela do menu);
# `setting`, o nome da definição cujo estado a opção mostra (e que o seu submenu muda); `choice`, a
# definição e o valor que a opção grava ao ser escolhida (volta ao menu anterior);
# `runs_all`, a opção que corre todas as
# ações do menu que o Modo seguro deixa correr; `state`, o estado atual, mostrado ao lado do
# nome (ligado ou desligado). `label`, `description_values` e `cells` são para as
# opções que se criam ao abrir o menu: o nome (em vez de `label_key`), os valores que completam o
# texto da descrição e as colunas da tabela (um número é uma memória em bytes, um texto é a chave
# de um texto traduzido, e None é «não se sabe»); `submenu_loader`, o que cria o submenu ao entrar
# nele; `instant`, as ações que voltam logo ao menu quando não têm resultados a mostrar;
# `refreshes_menu`, as ações que mudam a lista (por exemplo, desinstalar), que volta a criar-se
# quando o utilizador sai do resultado; `unavailable`, a opção que não se aplica ao que o menu
# descreve (esbatida e saltada pelo cursor, mas sempre visível); `value`, o valor atual da opção
# (a chave do texto traduzido), mostrado ao lado do nome quando a opção troca entre valores.
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
    choice: tuple[str, bool] | None = None
    runs_all: bool = False
    skips_slow: bool = False  # `runs_all` sem as ações lentas ou arriscadas
    slow: bool = False  # ação demorada, que a versão rápida de `runs_all` salta
    state: Callable[[], bool] | None = None
    only_without_admin: bool = False  # só faz sentido sem administrador (fica esbatida com ele)
    label: str | None = None
    description_values: Mapping[str, str] = field(default_factory=dict)
    cells: tuple[int | str | None, ...] = ()
    submenu_loader: Callable[[], "Menu"] | None = None
    instant: bool = False
    refreshes_menu: bool = False
    unavailable: bool = False
    value: Callable[[], str] | None = None


# `columns` são os títulos (a chave do texto) e a largura das colunas das células das opções,
# quando o menu é uma tabela; `name_width`, a largura da coluna do nome, se não for a habitual;
# `title`, o título criado ao abrir o menu (por exemplo, o nome de um programa), em vez de
# `title_key`
@dataclass(frozen=True)
class Menu:
    title_key: str
    items: tuple[MenuItem, ...]
    columns: tuple[tuple[str, int], ...] = ()
    name_width: int | None = None
    name_key: str = "table.program"
    cells_are_estimates: bool = True
    title: str | None = None


def item_label(texts: Mapping[str, str], item: MenuItem) -> str:
    return item.label if item.label is not None else texts.get(item.label_key, item.label_key)


def menu_title(texts: Mapping[str, str], menu: Menu) -> str:
    return menu.title if menu.title is not None else texts[menu.title_key]
