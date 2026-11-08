"""Detect viewers from running executable names, then known settings roots.

Windows API: https://learn.microsoft.com/windows/win32/api/tlhelp32/ns-tlhelp32-processentry32w
No command lines, process access, transcript contents or subprocesses.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re
from viewer_profiles import ROOTS, VIEWERS

AUTO_VIEWER = 'Automático'
VIEWER_CHOICES = (AUTO_VIEWER, 'Firestorm', 'Alchemy', 'Cool VL Viewer')


@dataclass(frozen=True)
class ViewerDetection:
    viewers: tuple
    source: str


def viewer_from_executable(executable):
    filename = str(executable).replace('\\', '/').rsplit('/', 1)[-1].casefold()
    if not filename.endswith('.exe'):
        return None
    if any(word in filename for word in ('setup', 'install', 'update', 'crash', 'report', 'helper', 'plugin')):
        return None
    name = re.sub('[^a-z0-9]', '', filename[:-4])
    if name.startswith(('firestorm', 'phoenixfirestorm')):
        return 'Firestorm'
    if name.startswith('coolvlviewer'):
        return 'Cool VL Viewer'
    if name in {'alchemy', 'alchemybin', 'alchemynext', 'alchemynextbin'}:
        return 'Alchemy'
    return None


def running_executables():
    """Use Toolhelp32 without opening other processes or requesting admin rights."""
    if os.name != 'nt':
        return []
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
            ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
            ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
            ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
            ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        function = getattr(kernel, name)
        function.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
        function.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel.Process32FirstW(handle, ctypes.byref(entry)):
            raise ctypes.WinError(ctypes.get_last_error())
        names = [entry.szExeFile]
        while kernel.Process32NextW(handle, ctypes.byref(entry)):
            names.append(entry.szExeFile)
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(error)
        return names
    finally:
        kernel.CloseHandle(handle)


def _cool_settings_present(root):
    """The official viewer also uses SecondLife: require a Cool-specific marker."""
    try:
        directories = [root, root / 'user_settings']
        with os.scandir(root) as entries:
            for count, entry in enumerate(entries):
                if count >= 250:
                    break
                if entry.is_dir(follow_symlinks=False):
                    directories.append(Path(entry.path))
        for directory in directories:
            if (directory / 'settings_per_account_coolvlviewer.xml').is_file():
                return True
            if next(directory.glob('settings_coolvlviewer_*.xml'), None) is not None:
                return True
    except OSError:
        pass
    return False


def configured_viewers(appdata=None):
    roaming = Path(appdata or os.environ.get('APPDATA', str(Path.home())))
    found = []
    for viewer in VIEWERS:
        for name in ROOTS[viewer]:
            root = roaming / name
            if not root.is_dir() or root.is_symlink():
                continue
            if viewer == 'Cool VL Viewer' and name == 'SecondLife' and not _cool_settings_present(root):
                continue
            found.append(viewer)
            break
    return found


def detect_viewers(appdata=None, executables=None):
    try:
        names = running_executables() if executables is None else executables
        running = {viewer_from_executable(name) for name in names}
        running.discard(None)
    except OSError:
        running = set()
    if running:
        return ViewerDetection(tuple(v for v in VIEWER_CHOICES if v in running), 'running')
    configured = configured_viewers(appdata)
    candidates = tuple(v for v in VIEWER_CHOICES if v in configured)
    return ViewerDetection(tuple(candidates), 'settings' if candidates else 'none')
