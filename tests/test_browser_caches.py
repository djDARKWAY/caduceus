import os
import time
from pathlib import Path

import pytest

from caduceus.maintenance.free_space import browser_caches


def make_file(root: Path, name: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"test")
    old = time.time() - 2 * 3600  # o motor deixa em paz o que tem menos de 1 hora
    os.utime(path, (old, old))
    return path


def test_every_graphics_cache_of_a_chromium_browser_is_removed_and_the_user_data_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    root = r"Google\Chrome\User Data"
    caches = [
        make_file(tmp_path, rf"{root}\{folder}\data.bin")
        for folder in (
            "GrShaderCache",
            "GraphiteDawnCache",
            "DawnGraphiteCache",
            "DawnWebGPUCache",
            "GPUPersistentCache",
        )
    ]
    cookies = make_file(tmp_path, rf"{root}\Default\Network\Cookies")
    passwords = make_file(tmp_path, rf"{root}\Default\Login Data")

    outcome = browser_caches.clean_browser_caches(lambda _: None)

    assert not any(file.exists() for file in caches)
    assert cookies.exists() and passwords.exists()
    assert (outcome.items, outcome.bytes_freed) == (5, 20)
