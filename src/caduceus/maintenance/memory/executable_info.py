"""
Informação dos executáveis

Lê, só em leitura, o nome legível que um executável traz nas suas propriedades (separador
Detalhes): o nome do produto e a descrição. É assim que `utweb.exe` passa a «µTorrent Web» e
`amd_dc_opt.exe` a «AMD Dual-Core Optimizer». Quando o fabricante é a Microsoft prefere-se a
descrição, porque o nome do produto é só «Microsoft Windows Operating System».
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

_TRANSLATION = "\\VarFileInfo\\Translation"
_STRING_FILE_INFO = "\\StringFileInfo\\{language:04x}{codepage:04x}\\{field}"
_MICROSOFT = "microsoft"

_version = ctypes.WinDLL("version")
_info_size = _version.GetFileVersionInfoSizeW
_info_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_info_size.restype = wintypes.DWORD
_get_info = _version.GetFileVersionInfoW
_get_info.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
_get_info.restype = wintypes.BOOL
_query = _version.VerQueryValueW
_query.argtypes = [
    ctypes.c_void_p,
    wintypes.LPCWSTR,
    ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(wintypes.UINT),
]
_query.restype = wintypes.BOOL


def _read_field(block: ctypes.Array[ctypes.c_char], field: str) -> str:
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not _query(block, _TRANSLATION, ctypes.byref(pointer), ctypes.byref(length)):
        return ""
    if not pointer.value or length.value < ctypes.sizeof(wintypes.DWORD):
        return ""
    language, codepage = ctypes.cast(pointer, ctypes.POINTER(wintypes.WORD * 2)).contents
    path = _STRING_FILE_INFO.format(language=language, codepage=codepage, field=field)
    if not _query(block, path, ctypes.byref(pointer), ctypes.byref(length)) or not pointer.value:
        return ""
    return ctypes.wstring_at(pointer.value).strip()


@dataclass(frozen=True)
class ExecutableInfo:
    name: str | None  # o nome legível, ou None se o ficheiro não o traz
    from_microsoft: bool


def describe(executable: str) -> ExecutableInfo:
    """O nome legível e o fabricante de um executável (vazio se não se consegue ler)."""
    size = _info_size(executable, None)
    if not size:
        return ExecutableInfo(None, False)
    block = ctypes.create_string_buffer(size)
    if not _get_info(executable, 0, size, block):
        return ExecutableInfo(None, False)
    product = _read_field(block, "ProductName")
    description = _read_field(block, "FileDescription")
    from_microsoft = _read_field(block, "CompanyName").lower().startswith(_MICROSOFT)
    name = (description or product) if from_microsoft else (product or description)
    return ExecutableInfo(name or None, from_microsoft)
