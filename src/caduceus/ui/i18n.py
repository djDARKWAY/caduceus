"""
Traduções

Descobre os idiomas em `locales/` e carrega os textos da interface. Juntar um idioma é
juntar um ficheiro JSON: não é preciso alterar código.
"""

import json
from importlib import resources

from caduceus.config import FALLBACK_LANGUAGE

Texts = dict[str, str]

_LOCALES = resources.files("caduceus.ui") / "locales"
_SUFFIX = ".json"


def _language_codes() -> list[str]:
    return sorted(
        path.name.removesuffix(_SUFFIX)
        for path in _LOCALES.iterdir()
        if path.name.endswith(_SUFFIX)
    )


def _read_locale(language: str) -> Texts:
    text = (_LOCALES / f"{language}{_SUFFIX}").read_text(encoding="utf-8")
    texts: Texts = json.loads(text)
    return texts


def available_languages() -> dict[str, str]:
    return {code: _read_locale(code)["language.name"] for code in _language_codes()}


def load_texts(language: str) -> Texts:
    if language not in _language_codes():
        raise ValueError(f"Unsupported language: {language}")
    return _read_locale(FALLBACK_LANGUAGE) | _read_locale(language)
