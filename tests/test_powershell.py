import subprocess

import pytest

from caduceus.maintenance.powershell import run_powershell


class FakeResult:
    def __init__(self, returncode: int, stdout: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_the_script_output_is_returned_as_utf_8_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: FakeResult(0, "ação".encode()))

    assert run_powershell("whatever") == "ação"


def test_a_failed_script_gives_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: FakeResult(1, b"partial"))

    assert run_powershell("whatever") is None


def test_a_missing_or_slow_powershell_gives_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def too_slow(*_args: object, **_kwargs: object) -> FakeResult:
        raise subprocess.TimeoutExpired("powershell", 1)

    monkeypatch.setattr(subprocess, "run", too_slow)

    assert run_powershell("whatever") is None
