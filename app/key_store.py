"""Windows DPAPI, current-user scope. No plaintext credential fallback."""
import ctypes
import os
from deepl_api import DATA

KEY_FILE = DATA / 'deepl_key.dpapi'

class Blob(ctypes.Structure):
    _fields_ = [('size', ctypes.c_uint32), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise OSError('A proteção de chave exige Windows.')
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p if decrypt else ctypes.c_wchar_p,
                   ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_uint32, ctypes.POINTER(Blob)]
    fn.restype = ctypes.c_int
    # UI forbidden; user-scope default. Never set LOCAL_MACHINE.
    if not fn(ctypes.byref(source), None if decrypt else 'Tradutor DeepL',
              None, None, None, 1, ctypes.byref(result)):
        raise OSError('O Windows não conseguiu proteger ou recuperar a chave.')
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(ctypes.cast(result.data, ctypes.c_void_p))
        ctypes.memset(buf, 0, len(buf))

def load_key():
    if not KEY_FILE.exists(): return ''
    return _crypt(KEY_FILE.read_bytes(), decrypt=True).decode('utf-8')

def save_key(key):
    if not key.strip():
        forget_key()
        return
    protected = _crypt(key.strip().encode('utf-8'))
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = KEY_FILE.with_suffix('.tmp')
    try:
        temp.write_bytes(protected)
        temp.replace(KEY_FILE)
    finally:
        temp.unlink(missing_ok=True)

def forget_key():
    KEY_FILE.unlink(missing_ok=True)
