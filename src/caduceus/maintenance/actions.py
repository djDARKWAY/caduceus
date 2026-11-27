"""
Ações

Os tipos comuns a todas as ações da Manutenção manual: o passo em curso (para a barra de
progresso), o resultado (com uma linha por categoria) e a forma de uma ação. Cada ação vive num
ficheiro de `maintenance/`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    text_key: str
    done: int
    total: int
    values: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Row:
    label_key: str
    items: int
    bytes_freed: int
    values: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    items: int
    bytes_freed: int
    failures: tuple[str, ...] = ()
    admin_required: tuple[str, ...] = ()
    rows: tuple[Row, ...] = ()


Report = Callable[[Step], None]
Action = Callable[[Report], Outcome]
