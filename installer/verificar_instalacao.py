"""Offline installation probe. Does not load settings, keys or viewer logs."""
import json
from pathlib import Path
import sys
import tkinter as tk
import PIL
import numpy
import langid

root_dir = Path(__file__).resolve().parent
pointer = json.loads((root_dir / '.install-version.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(root_dir / pointer['app']))
from language_filter import EnglishFilter
from app_identity import set_window_icon

gate = EnglishFilter()
assert gate.accepts('hello there')
assert not gate.accepts('bom dia tudo bem')
window = tk.Tk()
window.withdraw()
set_window_icon(window)
window.update_idletasks()
window.destroy()
print(json.dumps({'python': sys.version.split()[0], 'prefix': sys.prefix,
                  'pillow': PIL.__version__, 'numpy': numpy.__version__,
                  'filter': 'ok', 'window_icon': 'ok'}))
