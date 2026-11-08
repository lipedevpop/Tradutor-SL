"""Display name, release version and bundled window icon."""
import os
from pathlib import Path
import tkinter as tk

APP_NAME = 'Tradutor Hot SL'
APP_VERSION = '1.1.0'
ASSETS = Path(__file__).resolve().parent / 'assets'


def set_window_icon(window):
    # Preserve the official speech-bubble/flame artwork on every platform.
    window._app_icon = tk.PhotoImage(master=window, file=str(ASSETS / 'tradutor-sl.png'))
    window.iconphoto(True, window._app_icon)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('lipedevpop.TradutorSL')
        # Windows uses the small ICO frames in title bars and larger taskbar icons.
        icon_path = str(ASSETS / 'tradutor-sl.ico')
        window.iconbitmap(default=icon_path)
        window.iconbitmap(icon_path)
