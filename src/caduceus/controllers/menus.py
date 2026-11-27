"""
Menus

Estrutura dos menus, só dados: que menus existem e que opções cada um tem. Os textos vêm dos
ficheiros de idiomas, pelas chaves aqui indicadas. Juntar um menu ou uma opção é juntar dados.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from caduceus.maintenance.actions import Action, Estimator
from caduceus.maintenance.admin import restart_as_administrator
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
from caduceus.maintenance.memory.hibernation import (
    is_hibernation_on,
    turn_off_hibernation,
    turn_on_hibernation,
)
from caduceus.maintenance.memory.startup_programs import (
    StartupEntry,
    StartupSource,
    impact_of,
    is_enabled,
    list_startup_entries,
    toggle_startup,
)


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
# ligado (a direção que pode ter consequências). `label`, `description_values` e `cells` são para as
# opções que se criam ao abrir o menu: o nome (em vez de `label_key`), os valores que completam o
# texto da descrição e as colunas da tabela (um número é uma memória em bytes, um texto é a chave
# de um texto traduzido, e None é «não se sabe»); `submenu_loader`, o que cria o submenu ao entrar
# nele; `instant`, as ações tão rápidas que só mostram o resultado se algo correr mal.
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
    state: Callable[[], bool] | None = None  # o estado ligado/desligado, mostrado ao lado do nome
    only_without_admin: bool = False  # só faz sentido sem administrador (fica esbatida com ele)
    label: str | None = None
    description_values: Mapping[str, str] = field(default_factory=dict)
    cells: tuple[int | str | None, ...] = ()
    submenu_loader: Callable[[], "Menu"] | None = None
    instant: bool = False


# `columns` são os títulos (a chave do texto) e a largura das colunas das células das opções,
# quando o menu é uma tabela
@dataclass(frozen=True)
class Menu:
    title_key: str
    items: tuple[MenuItem, ...]
    columns: tuple[tuple[str, int], ...] = ()


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

_SOURCE_DESCRIPTIONS = {
    StartupSource.RUN_USER: "startup.source.run_user",
    StartupSource.RUN_MACHINE: "startup.source.run_machine",
    StartupSource.RUN_MACHINE_32: "startup.source.run_machine",
    StartupSource.FOLDER_USER: "startup.source.folder_user",
    StartupSource.FOLDER_MACHINE: "startup.source.folder_machine",
    StartupSource.SERVICE: "startup.source.service",
}
_UPDATER_DESCRIPTION = "startup.source.service_updater"


def _description_key(entry: StartupEntry) -> str:
    if entry.source is StartupSource.SERVICE and not entry.needs_safe_mode_off:
        return _UPDATER_DESCRIPTION
    return _SOURCE_DESCRIPTIONS[entry.source]


def _startup_item(entry: StartupEntry) -> MenuItem:
    impact = impact_of(entry.memory_bytes)
    is_service = entry.source is StartupSource.SERVICE
    kind = "startup.type.service" if is_service else "startup.type.program"
    return MenuItem(
        f"startup:{entry.source.value}:{entry.name}",
        label=entry.label,
        action=toggle_startup(entry),
        state=lambda: is_enabled(entry),
        description_key=_description_key(entry),
        description_values={"command": entry.command or "-", "name": entry.name},
        admin=AdminNeed.ALL if entry.needs_admin else None,
        risky=entry.needs_safe_mode_off,
        cells=(entry.memory_bytes, f"impact.{impact}" if impact else None, kind),
        instant=True,
    )


def startup_menu() -> Menu:
    """O menu dos programas de arranque, criado a partir do que o Windows tem registado agora."""
    items = tuple(_startup_item(entry) for entry in list_startup_entries())
    return Menu(
        "startup.title",
        items or (MenuItem("startup.none", description_key="startup.none.description"),),
        (("startup.column.memory", 9), ("startup.column.impact", 6), ("startup.column.type", 7)),
    )


HIBERNATION_MENU = Menu(
    "memory.hibernation.title",
    (
        MenuItem(
            "memory.hibernation.off",
            action=turn_off_hibernation,
            description_key="memory.hibernation.off.description",
            admin=AdminNeed.ALL,
            risky=True,
            confirm_key="memory.hibernation.confirm",
        ),
        MenuItem(
            "memory.hibernation.on",
            action=turn_on_hibernation,
            description_key="memory.hibernation.on.description",
            admin=AdminNeed.ALL,
            risky=True,
        ),
    ),
)

MEMORY_MENU = Menu(
    "memory.title",
    (
        MenuItem(
            "memory.startup",
            submenu_loader=startup_menu,
            description_key="memory.startup.description",
        ),
        MenuItem(
            "memory.hibernation",
            HIBERNATION_MENU,
            state=is_hibernation_on,
            description_key="memory.hibernation.description",
            admin=AdminNeed.ALL,
            risky=True,
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
            "maintenance.memory",
            MEMORY_MENU,
            description_key="maintenance.memory.description",
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
            "menu.restart_admin",
            action=restart_as_administrator,
            description_key="menu.restart_admin.description",
            only_without_admin=True,
            instant=True,
        ),
        MenuItem(
            "menu.settings",
            SETTINGS_MENU,
            description_key="menu.settings.description",
        ),
        MenuItem("menu.exit", quits=True),
    ),
)
