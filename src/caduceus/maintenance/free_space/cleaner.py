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

from caduceus.config import CLEANUP_MIN_AGE_HOURS
from caduceus.maintenance.actions import Outcome, Report, Row, Step
from caduceus.maintenance.admin import is_admin

_SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class Location:
    path: str
    label_key: str
    pattern: str = "*"
    min_age_hours: int = CLEANUP_MIN_AGE_HOURS
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


def _remove_file(path: Path, info: os.stat_result, cutoff: float | None) -> _Stats:
    if _too_recent(info, cutoff):
        return _Stats()
    if _delete_file(path):
        return _Stats(items=1, bytes_freed=info.st_size)
    return _Stats()


def _remove_directory(path: Path, cutoff: float | None) -> _Stats:
    # `scandir` dá o tipo e o tamanho de cada entrada na própria listagem, sem mais chamadas ao
    # sistema por ficheiro. A lista fecha-se antes de apagar, para não mudar a pasta que se lê
    with os.scandir(path) as listing:
        children = list(listing)
    stats = _Stats()
    for child in children:
        stats += _remove_entry(child, cutoff)
    # A pasta fica quando ainda tem ficheiros (em uso, protegidos ou recentes)
    with contextlib.suppress(OSError):
        path.rmdir()
    return stats


def _remove_entry(entry: os.DirEntry[str], cutoff: float | None) -> _Stats:
    try:
        if entry.is_symlink() or entry.is_junction():
            return _Stats()
        if entry.is_dir(follow_symlinks=False):
            return _remove_directory(Path(entry.path), cutoff)
        return _remove_file(Path(entry.path), entry.stat(follow_symlinks=False), cutoff)
    except OSError:
        return _Stats()


def _remove(path: Path, cutoff: float | None) -> _Stats:
    """Apaga uma entrada do local (um ficheiro ou uma pasta com tudo o que tem dentro)."""
    try:
        if path.is_symlink() or path.is_junction():
            return _Stats()
        if path.is_dir():
            return _remove_directory(path, cutoff)
        return _remove_file(path, path.lstat(), cutoff)
    except OSError:
        return _Stats()


def _cutoff(location: Location, now: float) -> float | None:
    if not location.min_age_hours:
        return None
    return now - location.min_age_hours * _SECONDS_PER_HOUR


def _is_behind_a_link(folder: Path) -> bool:
    """Verdadeiro se a pasta, ou uma das que a contêm, é um atalho ou junção: o que lá está
    pertence a outro sítio, e quem os pode criar pode apontá-los para fora do local de limpeza."""
    return any(path.is_symlink() or path.is_junction() for path in (folder, *folder.parents))


def _too_recent(info: os.stat_result, cutoff: float | None) -> bool:
    return cutoff is not None and info.st_mtime > cutoff


def _entry_size(entry: os.DirEntry[str], cutoff: float | None) -> int:
    try:
        if entry.is_symlink() or entry.is_junction():
            return 0
        if entry.is_dir(follow_symlinks=False):
            return _directory_size(entry.path, cutoff)
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return 0  # o que não se consegue ler não conta para a estimativa
    return 0 if _too_recent(info, cutoff) else info.st_size


def _directory_size(path: str, cutoff: float | None) -> int:
    try:
        with os.scandir(path) as listing:
            return sum(_entry_size(entry, cutoff) for entry in listing)
    except OSError:
        return 0


def folder_size(path: Path, cutoff: float | None = None) -> int:
    """Bytes de um ficheiro ou pasta, só de leitura e sem seguir atalhos nem junções."""
    try:
        if path.is_symlink() or path.is_junction():
            return 0
        if path.is_dir():
            return _directory_size(str(path), cutoff)
        info = path.lstat()
    except OSError:
        return 0
    return 0 if _too_recent(info, cutoff) else info.st_size


def _roots(location: Location) -> list[Path]:
    """As pastas do local: o caminho com as variáveis expandidas, ou as que um `*` encontra."""
    expanded = os.path.expandvars(location.path)
    if not Path(expanded).is_absolute():
        return []  # uma variável em falta não pode redirecionar a limpeza para a pasta atual
    if "*" not in expanded:
        return [Path(expanded)]
    return [Path(match) for match in sorted(glob.glob(expanded))]


# As pastas de cache que as aplicações baseadas no Chromium guardam dentro de cada perfil. A `Code
# Cache` já inclui a `Code Cache\js`
_CHROMIUM_CACHE_FOLDERS = ("Cache", "Code Cache", "GPUCache", r"Service Worker\CacheStorage")


def chromium_caches(profile_folder: str, label_key: str) -> tuple[Location, ...]:
    """Os locais de cache de um perfil de uma aplicação baseada no Chromium."""
    return tuple(
        Location(rf"{profile_folder}\{folder}", label_key) for folder in _CHROMIUM_CACHE_FOLDERS
    )


def estimate_locations(locations: Sequence[Location]) -> int:
    """Quanto `clean_locations` libertaria agora, pelas mesmas regras e sem apagar nada."""
    admin = is_admin()
    now = time.time()
    total = 0
    for location in locations:
        if location.needs_admin and not admin:
            continue
        cutoff = _cutoff(location, now)
        for root in _roots(location):
            try:
                if _is_behind_a_link(root):
                    continue
                entries = [e for e in root.iterdir() if fnmatch(e.name, location.pattern)]
            except OSError:
                continue
            total += sum(folder_size(entry, cutoff) for entry in entries)
    return total


class _NeedsAdministrator(Exception):
    """O local só se limpa como administrador."""


class _Refused(Exception):
    """O local não se limpa: não se consegue ler, ou é (ou está dentro de) um atalho ou junção."""


def _entries_to_clean(location: Location, root: Path, admin: bool) -> list[Path] | None:
    """As entradas do local que a limpeza apaga, ou None se a pasta não existe."""
    needs_admin = location.needs_admin and not admin
    try:
        if not root.is_dir():
            return None
        if needs_admin:
            raise _NeedsAdministrator
        if _is_behind_a_link(root):
            raise _Refused
        return [entry for entry in root.iterdir() if fnmatch(entry.name, location.pattern)]
    except PermissionError as error:
        # Sem administrador, até ver se a pasta existe pode ser negado
        raise (_NeedsAdministrator if needs_admin else _Refused) from error
    except OSError as error:
        raise _Refused from error


def clean_locations(locations: Sequence[Location], report: Report) -> Outcome:
    admin = is_admin()
    now = time.time()
    admin_required: list[str] = []
    failures: list[str] = []
    work: list[tuple[Path, float | None, str]] = []
    totals: dict[str, _Stats] = {}
    admin_categories: set[str] = set()
    for location in locations:
        cutoff = _cutoff(location, now)
        for root in _roots(location):
            try:
                entries = _entries_to_clean(location, root, admin)
            except _NeedsAdministrator:
                admin_required.append(str(root))
                continue
            except _Refused:
                failures.append(str(root))
                continue
            if entries is None:
                continue
            totals.setdefault(location.label_key, _Stats())
            if location.needs_admin:
                admin_categories.add(location.label_key)
            work += [(entry, cutoff, location.label_key) for entry in entries]

    for done, (entry, cutoff, label_key) in enumerate(work):
        report(Step("cleaning.step", done, len(work), {"path": str(entry)}))
        totals[label_key] += _remove(entry, cutoff)
    return _outcome(totals, admin_categories, tuple(failures), tuple(admin_required))


def _outcome(
    totals: dict[str, _Stats],
    admin_categories: set[str],
    failures: tuple[str, ...],
    admin_required: tuple[str, ...],
) -> Outcome:
    overall = sum(totals.values(), _Stats())
    rows = tuple(
        Row(key, stats.items, stats.bytes_freed, needs_admin=key in admin_categories)
        for key, stats in totals.items()
    )
    return Outcome(overall.items, overall.bytes_freed, failures, admin_required, rows)
