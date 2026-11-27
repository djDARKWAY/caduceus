"""
Ações

Os tipos comuns a todas as ações da Manutenção manual: o passo em curso (para a barra de
progresso), o resultado e a forma de uma ação. Cada ação vive num ficheiro de `maintenance/`.
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
class Outcome:
    items: int
    bytes_freed: int
    failures: tuple[str, ...] = ()
    skipped: int = 0
    admin_required: tuple[str, ...] = ()


Report = Callable[[Step], None]
Action = Callable[[Report], Outcome]
