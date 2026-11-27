import uuid
import winreg
from collections.abc import Callable, Iterator

import pytest


def _delete_tree(path: str) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            children = [winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0])]
    except OSError:
        return  # a chave nunca chegou a existir, ou o teste já a apagou
    for child in children:
        _delete_tree(rf"{path}\{child}")
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


@pytest.fixture
def test_key() -> Iterator[str]:
    """Uma chave só deste teste, no registo do utilizador, que se apaga no fim."""
    root = r"Software\CaduceusTests"
    path = rf"{root}\{uuid.uuid4().hex}"
    yield path
    _delete_tree(path)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, root)
    except OSError:
        pass  # a raiz só sai quando ficar vazia


@pytest.fixture
def delete_key_tree() -> Callable[[str], None]:
    """Apaga uma chave do registo do utilizador, com tudo o que tem dentro."""
    return _delete_tree
