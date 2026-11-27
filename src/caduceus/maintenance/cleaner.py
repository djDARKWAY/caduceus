"""
Limpeza de pastas

O motor comum às ações que apagam ficheiros: recebe uma lista de locais, apaga o que está dentro
deles e devolve o resultado. Regras: nunca apaga a própria pasta do local, nunca segue atalhos nem
junções (e recusa um local que seja um, ou esteja dentro de um), salta os ficheiros em uso ou
protegidos, ignora o que for mais recente do que a idade mínima do local, e salta os locais que
exigem administrador quando o Caduceus não o é.
"""

import contextlib
import glob
import os
import stat
import time
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.admin import is_admin

_SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class Location:
    path: str
    label_key: str
    pattern: str = "*"
    min_age_hours: int = 0
    needs_admin: bool = False


@dataclass(frozen=True)
class _Stats:
    items: int = 0
    bytes_freed: int = 0

    def __add__(self, other: "_Stats") -> "_Stats":
        return _Stats(self.items + other.items, self.bytes_freed + other.bytes_freed)


def _delete_file(path: Path) -> bool:
    try:
        path.unlink()
    except PermissionError:
        try:
            path.chmod(stat.S_IWRITE)
            path.unlink()
        except OSError:
            return False
    except OSError:
        return False
    return True


def _remove_file(path: Path, cutoff: float | None) -> _Stats:
    size_and_time = path.lstat()
    if cutoff is not None and size_and_time.st_mtime > cutoff:
        return _Stats()
    if _delete_file(path):
        return _Stats(items=1, bytes_freed=size_and_time.st_size)
    return _Stats()


def _remove_directory(path: Path, cutoff: float | None) -> _Stats:
    stats = _Stats()
    for child in path.iterdir():
        stats += _remove(child, cutoff)
    # A pasta fica quando ainda tem ficheiros (em uso, protegidos ou recentes)
    with contextlib.suppress(OSError):
        path.rmdir()
    return stats


def _remove(path: Path, cutoff: float | None) -> _Stats:
    try:
        if path.is_symlink() or path.is_junction():
            return _Stats()
        if path.is_dir():
            return _remove_directory(path, cutoff)
        return _remove_file(path, cutoff)
    except OSError:
        return _Stats()


def _cutoff(location: Location) -> float | None:
    if not location.min_age_hours:
        return None
    return time.time() - location.min_age_hours * _SECONDS_PER_HOUR


def _is_behind_a_link(folder: Path) -> bool:
    """Verdadeiro se a pasta, ou uma das que a contêm, é um atalho ou junção: o que lá está
    pertence a outro sítio, e quem os pode criar pode apontá-los para fora do local de limpeza."""
    return any(path.is_symlink() or path.is_junction() for path in (folder, *folder.parents))


def folder_size(path: Path, cutoff: float | None = None) -> int:
    """Bytes de um ficheiro ou pasta, só de leitura e sem seguir atalhos nem junções."""
    try:
        if path.is_symlink() or path.is_junction():
            return 0
        if path.is_dir():
            return sum(folder_size(child, cutoff) for child in path.iterdir())
        info = path.lstat()
    except OSError:
        return 0  # o que não se consegue ler não conta para a estimativa
    return 0 if cutoff is not None and info.st_mtime > cutoff else info.st_size


def _roots(location: Location) -> list[Path]:
    """As pastas do local: o caminho com as variáveis expandidas, ou as que um `*` encontra."""
    expanded = os.path.expandvars(location.path)
    if "*" not in expanded:
        return [Path(expanded)]
    return [Path(match) for match in sorted(glob.glob(expanded))]


def estimate_locations(locations: Sequence[Location]) -> int:
    """Quanto `clean_locations` libertaria agora, pelas mesmas regras e sem apagar nada."""
    admin = is_admin()
    total = 0
    for location in locations:
        if location.needs_admin and not admin:
            continue
        cutoff = _cutoff(location)
        for root in _roots(location):
            try:
                if _is_behind_a_link(root):
                    continue
                entries = [e for e in root.iterdir() if fnmatch(e.name, location.pattern)]
            except OSError:
                continue
            total += sum(folder_size(entry, cutoff) for entry in entries)
    return total


def clean_locations(locations: Sequence[Location], report: Report) -> Outcome:
    admin = is_admin()
    admin_required: list[str] = []
    failures: list[str] = []
    work: list[tuple[Path, float | None, str]] = []
    totals: dict[str, _Stats] = {}
    admin_categories: set[str] = set()
    for location in locations:
        for root in _roots(location):
            try:
                if not root.is_dir():
                    continue
                if location.needs_admin and not admin:
                    admin_required.append(str(root))
                    continue
                if _is_behind_a_link(root):
                    failures.append(str(root))
                    continue
                entries = [e for e in root.iterdir() if fnmatch(e.name, location.pattern)]
            except PermissionError:
                # Sem administrador, até ver se a pasta existe pode ser negado
                denied = admin_required if location.needs_admin and not admin else failures
                denied.append(str(root))
                continue
            except OSError:
                failures.append(str(root))
                continue
            totals.setdefault(location.label_key, _Stats())
            if location.needs_admin:
                admin_categories.add(location.label_key)
            work += [(entry, _cutoff(location), location.label_key) for entry in entries]

    for done, (entry, cutoff, label_key) in enumerate(work):
        report(Step("cleaning.step", done, len(work), {"path": str(entry)}))
        totals[label_key] += _remove(entry, cutoff)
    overall = sum(totals.values(), _Stats())
    return Outcome(
        overall.items,
        overall.bytes_freed,
        tuple(failures),
        tuple(admin_required),
        tuple(
            Row(key, stats.items, stats.bytes_freed, needs_admin=key in admin_categories)
            for key, stats in totals.items()
        ),
    )
