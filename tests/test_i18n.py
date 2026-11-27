import pytest

from caduceus.ui import i18n
from caduceus.ui.i18n import available_languages, load_texts


def test_available_languages_lists_english_with_its_name() -> None:
    assert available_languages()["en"] == "English"


@pytest.mark.parametrize("language", ["xx", "", "../config"])
def test_unsupported_language_is_rejected(language: str) -> None:
    with pytest.raises(ValueError, match="Unsupported language"):
        load_texts(language)


def test_missing_translation_falls_back_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    english = {"language.name": "English", "a": "A", "b": "B"}
    partial = {"language.name": "Partial", "a": "X"}
    monkeypatch.setattr(i18n, "_language_codes", lambda: ["en", "xx"])
    monkeypatch.setattr(i18n, "_read_locale", lambda code: english if code == "en" else partial)

    assert load_texts("xx") == {"language.name": "Partial", "a": "X", "b": "B"}
