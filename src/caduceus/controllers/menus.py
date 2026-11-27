"""
Menus

Estrutura dos menus, só dados: que menus existem e que opções cada um tem. Os textos vêm dos
ficheiros de idiomas, pelas chaves aqui indicadas. Juntar um menu ou uma opção é juntar dados. Os
menus que se criam ao abrir (as tabelas) estão em `tables.py`.
"""

from caduceus.controllers.menu_model import AdminNeed, Menu, MenuItem
from caduceus.controllers.tables import (
    drives_menu,
    programs_menu,
    repair_store_menu,
    reset_store_menu,
    startup_menu,
    tasks_menu,
    update_menu,
)
from caduceus.maintenance.admin import restart_as_administrator
from caduceus.maintenance.apps.open_with import clean_open_with
from caduceus.maintenance.free_space.app_caches import clean_app_caches, estimate_app_caches
from caduceus.maintenance.free_space.browser_caches import (
    clean_browser_caches,
    estimate_browser_caches,
)
from caduceus.maintenance.free_space.components import clean_components
from caduceus.maintenance.free_space.crash_dumps import clean_crash_dumps, estimate_crash_dumps
from caduceus.maintenance.free_space.developer_caches import (
    clean_developer_caches,
    estimate_developer_caches,
)
from caduceus.maintenance.free_space.hibernation import (
    is_hibernation_on,
    turn_off_hibernation,
    turn_on_hibernation,
)
from caduceus.maintenance.free_space.hidden_junk import clean_hidden_junk, estimate_hidden_junk
from caduceus.maintenance.free_space.icon_cache import clean_icon_cache, estimate_icon_cache
from caduceus.maintenance.free_space.install_leftovers import (
    clean_install_leftovers,
    estimate_install_leftovers,
)
from caduceus.maintenance.free_space.recent_history import clear_recent_history
from caduceus.maintenance.free_space.recycle_bin import empty_recycle_bin, estimate_recycle_bin
from caduceus.maintenance.free_space.restore_points import clean_restore_points
from caduceus.maintenance.free_space.system_caches import (
    clean_system_caches,
    estimate_system_caches,
)
from caduceus.maintenance.free_space.temp_files import clean_temp_files, estimate_temp_files
from caduceus.maintenance.free_space.windows_logs import clean_windows_logs, estimate_windows_logs
from caduceus.maintenance.free_space.windows_old import clean_windows_old, estimate_windows_old
from caduceus.maintenance.performance.free_standby import free_standby_memory
from caduceus.maintenance.performance.power_plan import (
    active_plan_name,
    balanced_is_active,
    high_performance_is_active,
    set_balanced,
    set_high_performance,
)
from caduceus.maintenance.performance.restart_explorer import restart_explorer

HIBERNATION_MENU = Menu(
    "cleanup.hibernation.title",
    (
        MenuItem(
            "cleanup.hibernation.off",
            action=turn_off_hibernation,
            description_key="cleanup.hibernation.off.description",
            admin=AdminNeed.ALL,
            risky=True,
            confirm_key="cleanup.hibernation.confirm",
        ),
        MenuItem(
            "cleanup.hibernation.on",
            action=turn_on_hibernation,
            description_key="cleanup.hibernation.on.description",
            admin=AdminNeed.ALL,
            risky=True,
        ),
    ),
)

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
            "cleanup.hidden_junk",
            action=clean_hidden_junk,
            description_key="cleanup.hidden_junk.description",
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
            "cleanup.icon_cache",
            action=clean_icon_cache,
            description_key="cleanup.icon_cache.description",
            estimate=estimate_icon_cache,
            slow=True,
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
            slow=True,
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
            slow=True,
        ),
        MenuItem(
            "cleanup.install_leftovers",
            action=clean_install_leftovers,
            description_key="cleanup.install_leftovers.description",
            admin=AdminNeed.ALL,
            risky=True,
            confirm_key="cleanup.install_leftovers.confirm",
            estimate=estimate_install_leftovers,
            slow=True,
        ),
        MenuItem(
            "cleanup.crash_dumps",
            action=clean_crash_dumps,
            description_key="cleanup.crash_dumps.description",
            admin=AdminNeed.ALL,
            estimate=estimate_crash_dumps,
        ),
        MenuItem(
            "cleanup.recent_history",
            action=clear_recent_history,
            description_key="cleanup.recent_history.description",
        ),
        # A reciclagem fica por último, para esvaziar também o que as limpezas anteriores lá deixem
        MenuItem(
            "cleanup.recycle_bin",
            action=empty_recycle_bin,
            description_key="cleanup.recycle_bin.description",
            estimate=estimate_recycle_bin,
        ),
        MenuItem(
            "cleanup.hibernation",
            HIBERNATION_MENU,
            state=is_hibernation_on,
            description_key="cleanup.hibernation.description",
            admin=AdminNeed.ALL,
            risky=True,
        ),
        MenuItem(
            "cleanup.fast",
            description_key="cleanup.fast.description",
            admin=AdminNeed.SOME,
            runs_all=True,
            skips_slow=True,
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

POWER_PLAN_MENU = Menu(
    "performance.power_plan.title",
    (
        MenuItem(
            "performance.power_plan.balanced",
            action=set_balanced,
            state=balanced_is_active,
            description_key="performance.power_plan.balanced.description",
            instant=True,
        ),
        MenuItem(
            "performance.power_plan.high",
            action=set_high_performance,
            state=high_performance_is_active,
            description_key="performance.power_plan.high.description",
            instant=True,
        ),
    ),
)

PERFORMANCE_MENU = Menu(
    "performance.title",
    (
        MenuItem(
            "performance.startup",
            submenu_loader=startup_menu,
            description_key="performance.startup.description",
        ),
        MenuItem(
            "performance.tasks",
            submenu_loader=tasks_menu,
            description_key="performance.tasks.description",
            admin=AdminNeed.ALL,
        ),
        MenuItem(
            "performance.power_plan",
            POWER_PLAN_MENU,
            state=active_plan_name,
            description_key="performance.power_plan.description",
        ),
        MenuItem(
            "performance.restart_explorer",
            action=restart_explorer,
            description_key="performance.restart_explorer.description",
            instant=True,
        ),
        MenuItem(
            "performance.free_standby",
            action=free_standby_memory,
            description_key="performance.free_standby.description",
            admin=AdminNeed.ALL,
            instant=True,
        ),
        MenuItem(
            "performance.optimize_drives",
            submenu_loader=drives_menu,
            description_key="performance.optimize_drives.description",
            admin=AdminNeed.ALL,
            slow=True,
        ),
    ),
)


APPS_MENU = Menu(
    "apps.title",
    (
        MenuItem(
            "apps.uninstall",
            submenu_loader=programs_menu,
            description_key="apps.uninstall.description",
        ),
        MenuItem(
            "apps.update",
            submenu_loader=update_menu,
            description_key="apps.update.description",
        ),
        MenuItem(
            "apps.repair",
            submenu_loader=repair_store_menu,
            description_key="apps.repair.description",
        ),
        MenuItem(
            "apps.reset",
            submenu_loader=reset_store_menu,
            description_key="apps.reset.description",
            risky=True,
        ),
        MenuItem(
            "apps.open_with",
            action=clean_open_with,
            description_key="apps.open_with.description",
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
            "maintenance.performance",
            PERFORMANCE_MENU,
            description_key="maintenance.performance.description",
        ),
        MenuItem(
            "maintenance.apps",
            APPS_MENU,
            description_key="maintenance.apps.description",
        ),
    ),
)

SAFE_MODE_MENU = Menu(
    "settings.safe_mode.title",
    (
        MenuItem(
            "setting.on",
            description_key="settings.safe_mode.on.description",
            choice=("safe_mode", True),
        ),
        MenuItem(
            "setting.off",
            description_key="settings.safe_mode.off.description",
            choice=("safe_mode", False),
        ),
    ),
)

SETTINGS_MENU = Menu(
    "settings.title",
    (
        MenuItem(
            "settings.safe_mode",
            SAFE_MODE_MENU,
            description_key="settings.safe_mode.description",
            setting="safe_mode",
        ),
        MenuItem(
            "menu.restart_admin",
            action=restart_as_administrator,
            description_key="menu.restart_admin.description",
            only_without_admin=True,
            instant=True,
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
