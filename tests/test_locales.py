import json
import re
from pathlib import Path

import pytest

from caduceus.controllers.menus import MAIN_MENU, Menu
from caduceus.ui.assets import NAME_WIDTH
from caduceus.ui.render import CONFIRM_HINTS, HINTS, NOTICE_HINTS, OUTCOME_HINTS, VERSION_LABEL

LOCALES_DIR = Path(__file__).parent.parent / "src" / "caduceus" / "ui" / "locales"
LANGUAGES = sorted(path.stem for path in LOCALES_DIR.glob("*.json"))
PLACEHOLDER = re.compile(r"\{\w+\}")


def read_locale(language: str) -> dict[str, str]:
    """Lê o ficheiro tal como está, sem o completar com o inglês."""
    texts: dict[str, str] = json.loads((LOCALES_DIR / f"{language}.json").read_text("utf-8"))
    return texts


def placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text))


def menu_text_keys(menu: Menu) -> set[str]:
    keys = {menu.title_key}
    for item in menu.items:
        keys.add(item.label_key)
        if item.admin is not None:
            keys.add(item.admin.value)
        if item.description_key is not None:
            keys.add(item.description_key)
        if item.confirm_key is not None:
            keys.add(item.confirm_key)
        if item.submenu is not None:
            keys |= menu_text_keys(item.submenu)
    return keys


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_has_the_same_keys_as_english(language: str) -> None:
    assert read_locale(language).keys() == read_locale("en").keys()


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_keeps_the_placeholders_of_english(language: str) -> None:
    translated = read_locale(language)
    for key, text in read_locale("en").items():
        assert placeholders(translated[key]) == placeholders(text), key


@pytest.mark.parametrize("language", LANGUAGES)
def test_tagline_fits_beside_the_version_under_the_banner(language: str) -> None:
    tagline = read_locale(language)["app.tagline"]
    assert len(tagline) + 1 + len(VERSION_LABEL) <= NAME_WIDTH


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_text_the_screens_use_exists(language: str) -> None:
    texts = read_locale(language)
    used = menu_text_keys(MAIN_MENU) | {
        text_key for _, text_key in HINTS + OUTCOME_HINTS + CONFIRM_HINTS + NOTICE_HINTS
    }
    used |= {
        "app.tagline",
        "notice.not_available",
        "cleanup.recycle_bin.step",
        "cleanup.cleaning.step",
        "cleanup.closing_apps.step",
        "action.step",
        "estimate.step",
        "setting.on",
        "setting.off",
        "table.action",
        "table.gain",
        "confirm.title",
        "confirm.skipped",
        "result.more",
        "notice.settings_not_saved",
    }
    used |= {"result.items", "result.freed"}
    used |= {"result.admin", "result.failures", "result.category", "result.total", "admin.tag"}
    used |= {
        "cleanup.components.step",
        "cleanup.windows_old.step",
        "cleanup.restore_points.step",
        "cleanup.hibernation.step",
    }
    used |= {
        "performance.startup.title",
        "performance.startup.column.memory",
        "performance.startup.column.impact",
        "performance.startup.none",
        "performance.startup.none.description",
        "performance.startup.source.run_user",
        "performance.startup.source.run_machine",
        "performance.startup.source.folder_user",
        "performance.startup.source.folder_machine",
        "performance.startup.source.service",
        "performance.startup.source.service_updater",
        "notice.restart_cancelled",
        "notice.nothing_selectable",
        "performance.tasks.description",
        "performance.tasks.title",
        "performance.tasks.column.trigger",
        "performance.tasks.logon",
        "performance.tasks.boot",
        "performance.tasks.none",
        "performance.tasks.none.description",
        "performance.tasks.item.description",
        "performance.tasks.item.protected.description",
        "blocked.safe_mode",
        "mode.normal",
        "mode.administrator",
        "performance.impact.low",
        "performance.impact.medium",
        "performance.impact.high",
        "table.program",
        "table.state",
        "hint.sort",
        "apps.uninstall.title",
        "apps.uninstall.column.size",
        "apps.uninstall.none",
        "apps.uninstall.none.description",
        "apps.uninstall.item.description",
        "apps.uninstall.item.protected.description",
        "apps.uninstall.confirm",
        "apps.uninstall.item.stale.description",
        "apps.uninstall.stale.confirm",
        "apps.uninstall.backup.step",
        "category.removed_entry",
        "apps.uninstall.step",
        "category.uninstalled_program",
        "notice.program_still_installed",
        "notice.uninstall_cancelled",
        "notice.uninstaller_not_opened",
        "loading.step",
        "apps.update.title",
        "apps.update.step",
        "apps.update.item.description",
        "apps.update.none",
        "apps.update.none.description",
        "apps.update.failed",
        "apps.update.failed.description",
        "apps.update.column.current",
        "apps.update.column.available",
        "category.updated_app",
        "apps.repair.title",
        "apps.repair.item.description",
        "apps.repair.step",
        "category.repaired_app",
        "apps.reset.title",
        "apps.reset.item.description",
        "apps.reset.confirm",
        "apps.reset.step",
        "category.reset_app",
        "apps.store.none",
        "apps.store.none.description",
        "apps.store.column.version",
        "apps.open_with.step",
        "category.open_with_entries",
        "notice.open_with_clean",
    }
    assert all(texts.get(key) for key in used)
