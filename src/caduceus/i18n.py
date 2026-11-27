"""
Traduções

Carrega os textos da interface a partir dos ficheiros JSON em `locales/`.
"""

import json
from importlib import resources

Texts = dict[str, str]


def load_texts(language: str) -> Texts:
    """Devolve os textos da interface no idioma indicado.

    Args:
        language: código do idioma, igual ao nome do ficheiro em `locales/` (por exemplo, `pt-PT`).

    Returns:
        Dicionário da chave do texto para o texto traduzido.
    """
    path = resources.files("caduceus") / "locales" / f"{language}.json"
    texts: Texts = json.loads(path.read_text(encoding="utf-8"))
    return texts
