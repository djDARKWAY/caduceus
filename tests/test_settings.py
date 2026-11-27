from pathlib import Path

import pytest

from caduceus.settings import Settings, load_settings, save_settings


@pytest.fixture(autouse=True)
def app_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


def test_without_a_saved_file_safe_mode_is_on() -> None:
    assert load_settings() == Settings(safe_mode=True)


def test_a_saved_setting_is_still_there_the_next_time() -> None:
    assert save_settings(Settings(safe_mode=False))

    assert load_settings() == Settings(safe_mode=False)


@pytest.mark.parametrize("content", ["not json", "[]", '{"safe_mode": "no"}', '{"safe_mode": 0}'])
def test_a_damaged_file_falls_back_to_safe_mode_on(app_data: Path, content: str) -> None:
    (app_data / "Caduceus").mkdir()
    (app_data / "Caduceus" / "settings.json").write_text(content, encoding="utf-8")

    assert load_settings() == Settings(safe_mode=True)


def test_a_folder_that_cannot_be_written_does_not_break_saving(app_data: Path) -> None:
    (app_data / "Caduceus").write_text("a file where the folder should be", encoding="utf-8")

    assert not save_settings(Settings(safe_mode=False))
