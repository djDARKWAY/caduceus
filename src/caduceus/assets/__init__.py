"""
Assets

Arte ASCII do cabeçalho, em ficheiros de texto desta pasta: `logo.txt` (o ícone, o caduceu) e
`name.txt` (o nome por extenso). Para mudar a arte, edita o ficheiro.
"""

from importlib import resources

_FOLDER = resources.files("caduceus.assets")


def _read_lines(file_name: str) -> tuple[str, ...]:
    return tuple((_FOLDER / file_name).read_text(encoding="utf-8").splitlines())


LOGO_LINES = _read_lines("logo.txt")
NAME_LINES = _read_lines("name.txt")
NAME_WIDTH = max(len(line) for line in NAME_LINES)
