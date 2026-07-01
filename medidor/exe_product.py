import ctypes
from ctypes import wintypes

_PRODUCT_CACHE: dict[str, str] = {}


def get_exe_product_name(exe_path: str) -> str:
    if not exe_path:
        return ""

    cached = _PRODUCT_CACHE.get(exe_path)
    if cached is not None:
        return cached

    product = _read_product_name(exe_path)
    _PRODUCT_CACHE[exe_path] = product
    return product


def _read_product_name(path: str) -> str:
    size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return ""

    data = ctypes.create_string_buffer(size)
    if not ctypes.windll.version.GetFileVersionInfoW(path, None, size, data):
        return ""

    for key in ("ProductName", "FileDescription"):
        value = _query_version_string(data, f"\\StringFileInfo\\040904b0\\{key}")
        if value:
            return value

    trans_ptr = ctypes.c_void_p()
    length = wintypes.UINT()
    if not ctypes.windll.version.VerQueryValueW(
        data, "\\VarFileInfo\\Translation", ctypes.byref(trans_ptr), ctypes.byref(length)
    ):
        return ""

    lang, codepage = ctypes.cast(
        trans_ptr.value, ctypes.POINTER(ctypes.c_ushort * (length.value // 2))
    ).contents[0]
    subblock = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\ProductName"
    return _query_version_string(data, subblock)


def _query_version_string(data: ctypes.Array, subblock: str) -> str:
    value_ptr = ctypes.c_void_p()
    length = wintypes.UINT()
    if not ctypes.windll.version.VerQueryValueW(
        data, subblock, ctypes.byref(value_ptr), ctypes.byref(length)
    ):
        return ""
    return ctypes.wstring_at(value_ptr.value, length.value).rstrip("\x00")
