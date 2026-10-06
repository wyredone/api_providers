import base64
import sys

ENCRYPTION_AVAILABLE = sys.platform == "win32"

if ENCRYPTION_AVAILABLE:
    import ctypes
    from ctypes import windll, c_char_p, c_wchar_p, POINTER, Structure
    from ctypes.wintypes import DWORD

    class DATA_BLOB(Structure):
        _fields_ = [("cbData", DWORD), ("pbData", POINTER(ctypes.c_byte))]


def encrypt_key(key: str) -> str:
    """Legacy writer requires Windows DPAPI; never silently downgrade storage."""
    if not ENCRYPTION_AVAILABLE:
        raise RuntimeError("Legacy key saving requires Windows DPAPI. Use the v2 manager.")
    key_bytes = key.encode("utf-8")
    buffer = ctypes.create_string_buffer(key_bytes)
    data_in = DATA_BLOB(len(key_bytes), ctypes.cast(buffer, POINTER(ctypes.c_byte)))
    data_out = DATA_BLOB()
    result = windll.crypt32.CryptProtectData(ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out))
    if not result:
        raise RuntimeError("Windows credential encryption failed.")
    try:
        return base64.b64encode(ctypes.string_at(data_out.pbData, data_out.cbData)).decode()
    finally:
        windll.kernel32.LocalFree(data_out.pbData)


def decrypt_key(encrypted_key: str) -> str:
    """Decrypt API key using Windows DPAPI. Falls back to base64 on non-Windows."""
    if not ENCRYPTION_AVAILABLE:
        try:
            return base64.b64decode(encrypted_key.encode()).decode()
        except Exception:
            return encrypted_key

    try:
        encrypted_bytes = base64.b64decode(encrypted_key.encode())
        data_in = DATA_BLOB()
        data_in.pbData = ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), POINTER(ctypes.c_byte))
        data_in.cbData = len(encrypted_bytes)

        data_out = DATA_BLOB()
        result = windll.crypt32.CryptUnprotectData(
            ctypes.byref(data_in),
            c_wchar_p(None),
            None,
            None,
            None,
            0,
            ctypes.byref(data_out)
        )

        if not result:
            try:
                return base64.b64decode(encrypted_key.encode()).decode()
            except Exception:
                return encrypted_key

        decrypted = ctypes.string_at(data_out.pbData, data_out.cbData).decode("utf-8")
        windll.kernel32.LocalFree(data_out.pbData)

        return decrypted
    except Exception:
        try:
            return base64.b64decode(encrypted_key.encode()).decode()
        except Exception:
            return encrypted_key
