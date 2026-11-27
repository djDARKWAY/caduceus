"""
Traduções

Descobre os idiomas em `locales/` e carrega os textos da interface. Juntar um idioma é
juntar um ficheiro JSON: não é preciso alterar código.
"""

import json
from importlib import resources

from caduceus.config import FALLBACK_LANGUAGE

Texts = dict[str, str]

_LOCALES = resources.files("caduceus") / "locales"
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
    """Lista os idiomas disponíveis.

    Returns:
        Dicionário do código do idioma (por exemplo, `en`) para o seu nome (`language.name`).
    """
    return {code: _read_locale(code)["language.name"] for code in _language_codes()}


def load_texts(language: str) -> Texts:
    """Devolve os textos da interface no idioma indicado.

    Os textos que faltem na tradução vêm do idioma de recurso (`FALLBACK_LANGUAGE`).

    Args:
        language: código de um idioma disponível, igual ao nome do ficheiro em `locales/`.

    Returns:
        Dicionário da chave do texto para o texto traduzido.

    Raises:
        ValueError: se o idioma não existir em `locales/`.
    """
    if language not in _language_codes():
        raise ValueError(f"Unsupported language: {language}")
    return _read_locale(FALLBACK_LANGUAGE) | _read_locale(language)
