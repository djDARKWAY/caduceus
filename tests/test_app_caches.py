import pytest

from caduceus.maintenance.actions import Outcome
from caduceus.maintenance.free_space import app_caches


def test_open_apps_are_force_closed_before_their_caches_are_cleaned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_tool(executable: str, arguments: list[str], *_rest: object) -> bool:
        calls.append(f"{executable} {' '.join(arguments)}")
        return False

    def fake_clean(*_args: object) -> Outcome:
        calls.append("clean")
        return Outcome(0, 0)

    monkeypatch.setattr(app_caches, "run_system_tool", fake_tool)
    monkeypatch.setattr(app_caches, "clean_locations", fake_clean)

    app_caches.clean_app_caches(lambda _: None)

    assert calls[0].startswith("taskkill.exe /F /T /IM Discord.exe")
    assert calls[1] == "clean"


def test_code_editors_and_game_launchers_are_never_force_closed() -> None:
    names = {name.lower() for name in app_caches._APP_PROCESSES}

    assert names.isdisjoint({"code.exe", "cursor.exe", "steam.exe", "epicgameslauncher.exe"})
