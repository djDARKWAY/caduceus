import re
from pathlib import Path

import pytest

from caduceus.branding import BANNER_WIDTH
from caduceus.i18n import load_texts
from caduceus.ui import HINTS, VERSION_LABEL, MainMenuOption

LOCALES_DIR = Path(__file__).parent.parent / "src" / "caduceus" / "locales"
LANGUAGES = sorted(path.stem for path in LOCALES_DIR.glob("*.json"))
PLACEHOLDER = re.compile(r"\{\w+\}")


def placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER.findall(text))


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_has_the_same_keys_as_english(language: str) -> None:
    assert load_texts(language).keys() == load_texts("en").keys()


@pytest.mark.parametrize("language", LANGUAGES)
def test_translation_keeps_the_placeholders_of_english(language: str) -> None:
    english = load_texts("en")
    translated = load_texts(language)
    for key, text in english.items():
        assert placeholders(translated[key]) == placeholders(text), key


@pytest.mark.parametrize("language", LANGUAGES)
def test_tagline_fits_beside_the_version_under_the_banner(language: str) -> None:
    tagline = load_texts(language)["app.tagline"]
    assert len(tagline) + 1 + len(VERSION_LABEL) <= BANNER_WIDTH


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_control_hint_has_a_text(language: str) -> None:
    texts = load_texts(language)
    for _, text_key in HINTS:
        assert texts[text_key]


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_main_menu_option_has_a_text(language: str) -> None:
    texts = load_texts(language)
    for option in MainMenuOption:
        assert texts[option.value]
