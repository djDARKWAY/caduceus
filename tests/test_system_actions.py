import subprocess
import winreg
from pathlib import Path

import pytest

from caduceus.maintenance import components, windows_old


def refuse_to_launch(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("nenhum processo devia ter sido lançado")


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (b"[=====                      10.0%                          ]", 10),
        (b"\r[==========================100.0%==========================]\r\n", 100),
        (b"[===  5.0% ]\r[====  12.5% ]", 12),
        (b"Deployment Image Servicing and Management tool", None),
    ],
)
def test_dism_progress_is_read_from_its_output(output: bytes, expected: int | None) -> None:
    assert components.parse_percent(output) == expected


def test_component_cleanup_without_administrator_asks_for_it_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(components, "is_admin", lambda: False)
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)

    outcome = components.clean_components(lambda _: None)

    assert outcome.admin_required
    assert outcome.rows == ()


def test_windows_old_without_administrator_asks_for_it_and_touches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "Windows.old").mkdir()
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(windows_old, "is_admin", lambda: False)
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)
    monkeypatch.setattr(winreg, "OpenKey", refuse_to_launch)

    outcome = windows_old.clean_windows_old(lambda _: None)

    assert outcome.admin_required == (str(tmp_path / "Windows.old"),)
    assert (tmp_path / "Windows.old").is_dir()


def test_windows_old_that_does_not_exist_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SystemDrive", str(tmp_path))
    monkeypatch.setattr(subprocess, "Popen", refuse_to_launch)

    outcome = windows_old.clean_windows_old(lambda _: None)

    assert (outcome.items, outcome.bytes_freed, outcome.rows) == (0, 0, ())


def test_the_cleanup_profile_is_never_one_that_another_handler_already_uses() -> None:
    taken = {6471, 6472, 6474}

    assert windows_old.free_profile(taken) == 6473
    assert windows_old.free_profile(set()) == 6471


def test_without_any_free_cleanup_profile_nothing_runs() -> None:
    with pytest.raises(OSError, match="perfis"):
        windows_old.free_profile(set(range(10000)))
