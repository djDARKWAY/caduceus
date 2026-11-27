import json
import re
from pathlib import Path

import pytest

from caduceus.controllers.menus import MAIN_MENU, Menu
from caduceus.ui.assets import NAME_WIDTH
from caduceus.ui.render import HINTS, OUTCOME_HINTS, VERSION_LABEL

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
        if item.description_key is not None:
            keys.add(item.description_key)
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
    used = menu_text_keys(MAIN_MENU) | {text_key for _, text_key in HINTS + OUTCOME_HINTS}
    used |= {"app.tagline", "menu.not_available", "recycle_bin.step", "cleaning.step"}
    used |= {"result.done", "result.items", "result.freed"}
    used |= {"result.admin", "result.failures"}
    assert all(texts.get(key) for key in used)
