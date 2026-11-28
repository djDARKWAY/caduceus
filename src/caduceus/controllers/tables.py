"""
Tabelas

Os menus que se criam ao abrir, a partir do que o Windows tem agora: os programas de arranque, as
tarefas agendadas, as unidades, os programas (instalados e da Store) e as atualizações.
Cada um devolve um `Menu` com uma opção por linha da tabela.
"""

from caduceus.controllers.menu_model import AdminNeed, Menu, MenuItem
from caduceus.maintenance.apps.installed_programs import (
    InstalledProgram,
    list_installed_programs,
    remove_leftover_entry,
    uninstall_program,
)
from caduceus.maintenance.apps.store_apps import (
    StoreApp,
    list_store_apps,
    repair_store_app,
    reset_store_app,
)
from caduceus.maintenance.apps.winget_upgrades import (
    UpgradableApp,
    list_upgradable,
    update_apps,
)
from caduceus.maintenance.performance.optimize_drives import Drive, list_drives, optimize_drive
from caduceus.maintenance.performance.scheduled_tasks import (
    TaskEntry,
    list_scheduled_tasks,
    toggle_task,
)
from caduceus.maintenance.performance.startup_programs import (
    StartupEntry,
    StartupSource,
    impact_of,
    is_enabled,
    list_startup_entries,
    toggle_startup,
)

_SOURCE_DESCRIPTIONS = {
    StartupSource.RUN_USER: "performance.startup.source.run_user",
    StartupSource.RUN_MACHINE: "performance.startup.source.run_machine",
    StartupSource.RUN_MACHINE_32: "performance.startup.source.run_machine",
    StartupSource.FOLDER_USER: "performance.startup.source.folder_user",
    StartupSource.FOLDER_MACHINE: "performance.startup.source.folder_machine",
    StartupSource.SERVICE: "performance.startup.source.service",
}
_UPDATER_DESCRIPTION = "performance.startup.source.service_updater"


def _description_key(entry: StartupEntry) -> str:
    if entry.source is StartupSource.SERVICE and not entry.needs_safe_mode_off:
        return _UPDATER_DESCRIPTION
    return _SOURCE_DESCRIPTIONS[entry.source]


def _startup_item(entry: StartupEntry) -> MenuItem:
    impact = impact_of(entry.memory_bytes)
    is_service = entry.source is StartupSource.SERVICE
    kind = "performance.startup.type.service" if is_service else "performance.startup.type.program"
    return MenuItem(
        f"startup:{entry.source.value}:{entry.name}",
        label=entry.label,
        action=toggle_startup(entry),
        state=lambda: is_enabled(entry),
        description_key=_description_key(entry),
        description_values={"command": entry.command or "-", "name": entry.name},
        admin=AdminNeed.ALL if entry.needs_admin else None,
        risky=entry.needs_safe_mode_off,
        cells=(entry.memory_bytes, f"performance.impact.{impact}" if impact else None, kind),
        instant=True,
    )


def startup_menu() -> Menu:
    """O menu dos programas de arranque, criado a partir do que o Windows tem registado agora."""
    items = tuple(_startup_item(entry) for entry in list_startup_entries())
    return Menu(
        "performance.startup.title",
        items
        or (
            MenuItem(
                "performance.startup.none", description_key="performance.startup.none.description"
            ),
        ),
        (
            ("performance.startup.column.memory", 9),
            ("performance.startup.column.impact", 6),
            ("performance.startup.column.type", 7),
        ),
    )


def _task_item(entry: TaskEntry) -> MenuItem:
    impact = impact_of(entry.memory_bytes)
    description_key = (
        "performance.tasks.item.protected.description"
        if entry.needs_safe_mode_off
        else "performance.tasks.item.description"
    )
    return MenuItem(
        f"task:{entry.full_name}",
        label=entry.name,
        action=toggle_task(entry),
        state=lambda: entry.enabled,
        description_key=description_key,
        description_values={"command": entry.command or "-", "name": entry.full_name},
        admin=AdminNeed.ALL,
        risky=entry.needs_safe_mode_off,
        cells=(
            entry.memory_bytes,
            f"performance.impact.{impact}" if impact else None,
            f"performance.tasks.{entry.trigger}",
        ),
        instant=True,
    )


def tasks_menu() -> Menu:
    """O menu das tarefas agendadas de arranque, criado a partir do que o Windows tem agora."""
    items = tuple(_task_item(entry) for entry in list_scheduled_tasks())
    return Menu(
        "performance.tasks.title",
        items
        or (
            MenuItem(
                "performance.tasks.none", description_key="performance.tasks.none.description"
            ),
        ),
        (
            ("performance.startup.column.memory", 9),
            ("performance.startup.column.impact", 6),
            ("performance.tasks.column.trigger", 7),
        ),
    )


def _drive_item(drive: Drive) -> MenuItem:
    media_key = f"performance.optimize_drives.media.{drive.media or 'unknown'}"
    return MenuItem(
        f"drive:{drive.letter}",
        label=drive.label,
        action=optimize_drive(drive) if drive.media is not None else None,
        description_key=f"{media_key}.description",
        description_values={"drive": drive.label},
        admin=AdminNeed.ALL,
        cells=(media_key, drive.size_bytes, drive.free_bytes),
        slow=True,
        refreshes_menu=True,
    )


def drives_menu() -> Menu:
    drives = list_drives()
    items = tuple(_drive_item(drive) for drive in drives or ())
    empty_key = (
        "performance.optimize_drives.failed"
        if drives is None
        else "performance.optimize_drives.none"
    )
    return Menu(
        "performance.optimize_drives.title",
        items or (MenuItem(empty_key, description_key=f"{empty_key}.description"),),
        (
            ("performance.optimize_drives.column.type", 8),
            ("performance.optimize_drives.column.size", 9),
            ("performance.optimize_drives.column.free", 9),
        ),
        name_key="performance.optimize_drives.column.name",
        cells_are_estimates=False,
    )


def _repair_reset_options(app: StoreApp | None) -> tuple[MenuItem, MenuItem]:
    if app is None:
        repair = MenuItem("programs.repair", unavailable=True)
        return repair, MenuItem("programs.reset", unavailable=True)
    values = {"name": app.full_name, "version": app.version or "-"}
    repair = MenuItem(
        "programs.repair",
        action=repair_store_app(app),
        description_key="programs.repair.description",
        description_values=values,
    )
    reset = MenuItem(
        "programs.reset",
        action=reset_store_app(app),
        description_key="programs.reset.description",
        description_values=values,
        risky=True,
        confirm_key="programs.reset.confirm",
    )
    return repair, reset


def _uninstall_option(program: InstalledProgram | None) -> MenuItem:
    """Desinstalar. Se o desinstalador já não existe, escolher a opção limpa o resto que ficou no
    registo (e não abre nada); essa limpeza não põe o sistema em risco."""
    if program is None:
        return MenuItem("programs.uninstall", unavailable=True)
    values = {
        "name": program.name,
        "publisher": program.publisher or "-",
        "version": program.version or "-",
        "installed": program.installed_on or "-",
        "command": program.uninstall_command,
        "location": program.install_location or "-",
    }
    if program.has_missing_uninstaller:
        return MenuItem(
            "programs.uninstall",
            action=remove_leftover_entry(program),
            description_key="programs.uninstall.stale.description",
            description_values=values,
            admin=AdminNeed.ALL if program.entry_needs_admin else None,
            confirm_key="programs.uninstall.stale.confirm",
            refreshes_menu=True,
        )
    return MenuItem(
        "programs.uninstall",
        action=uninstall_program(program),
        description_key=(
            "programs.uninstall.protected.description"
            if program.needs_safe_mode_off
            else "programs.uninstall.description"
        ),
        description_values=values,
        risky=program.needs_safe_mode_off,
        refreshes_menu=True,
    )


def _actions_menu(name: str, app: StoreApp | None, program: InstalledProgram | None) -> Menu:
    """As três possibilidades de um programa; as que não se aplicam a ele ficam esbatidas."""
    repair, reset = _repair_reset_options(app)
    return Menu("programs.title", (repair, reset, _uninstall_option(program)), title=name)


def _program_row(program: InstalledProgram) -> MenuItem:
    return MenuItem(
        f"program:{program.hive}:{program.key_path}",
        label=program.name,
        submenu=_actions_menu(program.name, None, program),
        description_key="programs.item.description",
        description_values={
            "name": program.name,
            "publisher": program.publisher or "-",
            "version": program.version or "-",
            "installed": program.installed_on or "-",
        },
        cells=(program.version or None, program.size_bytes),
    )


def _store_row(app: StoreApp) -> MenuItem:
    return MenuItem(
        f"store:{app.full_name}",
        label=app.name,
        submenu=_actions_menu(app.name, app, None),
        description_key="programs.item.store.description",
        description_values={"name": app.full_name, "version": app.version or "-"},
        cells=(app.version or None, None),
    )


def programs_menu() -> Menu:
    """O menu dos programas instalados e das aplicações da Store, criado a partir do que o Windows
    tem registado agora. Cada linha abre o menu com o que se pode fazer com ela."""
    rows = [
        *(_program_row(program) for program in list_installed_programs()),
        *(_store_row(app) for app in list_store_apps()),
    ]
    items = tuple(sorted(rows, key=lambda item: (item.label or "").casefold()))
    return Menu(
        "programs.title",
        items or (MenuItem("programs.none", description_key="programs.none.description"),),
        (("programs.column.version", 14), ("programs.column.size", 9)),
        name_width=22,
        cells_are_estimates=False,
    )


def _update_item(app: UpgradableApp) -> MenuItem:
    return MenuItem(
        f"update:{app.package_id}",
        label=app.name,
        action=update_apps([app]),
        description_key="updates.item.description",
        description_values={
            "name": app.name,
            "id": app.package_id,
            "version": app.version or "-",
            "available": app.available or "-",
        },
        cells=(app.version or None, app.available or None),
        refreshes_menu=True,
    )


def _update_empty_item(failed: bool) -> MenuItem:
    key = "updates.failed" if failed else "updates.none"
    return MenuItem(key, description_key=f"{key}.description")


def updates_menu() -> Menu:
    """O menu das aplicações com atualização, criado a partir do que o winget encontra agora, com
    a opção que as atualiza todas no fim."""
    listed = list_upgradable()
    apps = listed or []
    items = tuple(_update_item(app) for app in apps)
    if apps:
        items += (
            MenuItem(
                "updates.update_all",
                action=update_apps(apps),
                description_key="updates.update_all.description",
                runs_all=True,
                refreshes_menu=True,
            ),
        )
    return Menu(
        "updates.title",
        items or (_update_empty_item(failed=listed is None),),
        (("updates.column.current", 18), ("updates.column.latest", 18)),
        name_width=22,
    )
