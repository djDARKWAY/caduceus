"""
Definições

As preferências do utilizador, guardadas num ficheiro JSON na pasta de dados da aplicação
(`%LOCALAPPDATA%/Caduceus/settings.json`) para não terem de ser mudadas de cada vez que o Caduceus
abre. Um ficheiro em falta ou inválido dá as predefinições, que são as mais prudentes.
"""

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from caduceus.config import SETTINGS_FILE, SETTINGS_FOLDER


@dataclass(frozen=True)
class Settings:
    safe_mode: bool = True

    def with_value(self, name: str, value: bool) -> "Settings":
        return replace(self, **{name: value})


def _settings_path() -> Path:
    app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(app_data) / SETTINGS_FOLDER / SETTINGS_FILE


def load_settings() -> Settings:
    try:
        stored = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(stored, dict):
        return Settings()
    defaults = Settings()
    return Settings(
        **{
            name: stored[name]
            for name, default in asdict(defaults).items()
            if isinstance(stored.get(name), type(default))
        }
    )


def save_settings(settings: Settings) -> bool:
    """Guarda as definições; devolve False se não foi possível (a definição vale até fechar)."""
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    except OSError:
        return False
    return True
