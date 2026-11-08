"""Small, event-driven Tk widgets. Shadows redraw only on resize/state changes."""
import tkinter as tk
import math
from tkinter import font as tkfont
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageTk

BG = '#eee6df'
PANEL = '#faf5ef'
FG = '#293442'
MUTED = '#766f6b'
BLUE = '#557f9e'
PEACH = '#f5c3aa'

@lru_cache(maxsize=96)
def surface(width, height, background, fill, radius, pressed=False):
    # Supersampling keeps edges smooth at Windows display scales.
    scale = 2
    size = (max(2, width) * scale, max(2, height) * scale)
    img = Image.new('RGB', size, background)
    box = (6 * scale, 5 * scale, (width - 6) * scale, (height - 7) * scale)
    radius *= scale
    for color, offset in [('#c9bcb3', (2, 3)), ('#ffffff', (-2, -2))]:
        alpha = Image.new('L', size)
        draw = ImageDraw.Draw(alpha)
        x, y = offset
        draw.rounded_rectangle(tuple(v + (x if i % 2 == 0 else y) * scale for i, v in enumerate(box)), radius, fill=110 if color == '#c9bcb3' else 210)
        alpha = alpha.filter(ImageFilter.GaussianBlur(3 * scale))
        layer = Image.new('RGB', size, color)
        img.paste(layer, (0, 0), alpha)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(box, radius, fill=fill, outline='#e1d5cc' if pressed else '#ffffff', width=scale)
    return img.resize((width, height), Image.Resampling.LANCZOS)

class SoftCard(tk.Canvas):
    def __init__(self, parent, fill=PANEL, padding=16, radius=22, **kwargs):
        super().__init__(parent, bg=parent.cget('background'), highlightthickness=0, bd=0, **kwargs)
        self.fill, self.padding, self.radius = fill, padding, radius
        self.content = tk.Frame(self, bg=fill)
        self._back = self.create_image(0, 0, anchor='nw')
        self._window = self.create_window(padding, padding, anchor='nw', window=self.content)
        self._pending = None
        self.bind('<Configure>', self._schedule)

    def _schedule(self, event=None):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(25, self._draw)

    def _draw(self):
        self._pending = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 35 or h < 35:
            return
        self._image = ImageTk.PhotoImage(surface(w, h, self.cget('background'), self.fill, self.radius), master=self)
        self.itemconfigure(self._back, image=self._image)
        self.itemconfigure(self._window, width=max(1, w - 2 * self.padding), height=max(1, h - 2 * self.padding))

class SoftButton(tk.Canvas):
    def __init__(self, parent, text='', command=None, state='normal', width=None, accent=False, **kwargs):
        self._text, self._command, self._state = text, command, state
        self._accent, self._pressed, self._hover = accent, False, False
        self._font = tkfont.Font(family='Segoe UI' if 'Segoe UI' in tkfont.families(parent) else 'DejaVu Sans', size=10)
        self._fixed_width = width
        pixels = (width * 9 + 24) if width else self._font.measure(text) + 38
        super().__init__(parent, width=pixels, height=44, bg=parent.cget('background'), highlightthickness=0, bd=0, takefocus=1, cursor='hand2', **kwargs)
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', lambda e: self._appearance(hover=True))
        self.bind('<Leave>', lambda e: self._appearance(hover=False, pressed=False))
        self.bind('<ButtonPress-1>', self._press)
        self.bind('<ButtonRelease-1>', self._release)
        self.bind('<space>', self._key)
        self.bind('<Return>', self._key)
        self.bind('<FocusIn>', self._draw)
        self.bind('<FocusOut>', self._draw)

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        for key in ('text', 'state', 'command'):
            if key in kwargs:
                setattr(self, '_' + key, kwargs.pop(key))
        if not self._fixed_width:
            kwargs['width'] = self._font.measure(self._text) + 38
        result = super().configure(**kwargs)
        self._draw()
        return result
    config = configure

    def _appearance(self, **changes):
        for key, value in changes.items():
            setattr(self, '_' + key, value)
        self._draw()

    def _draw(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 15 or h < 15:
            return
        disabled = self._state == 'disabled'
        fill = '#eadfd7' if disabled else (PEACH if self._accent else PANEL)
        if self._hover and not disabled:
            fill = '#f7ceb9' if self._accent else '#fffaf5'
        self._image = ImageTk.PhotoImage(surface(w, h, self.cget('background'), fill, 18, self._pressed), master=self)
        self.delete('all')
        self.create_image(0, 0, anchor='nw', image=self._image)
        if self._text == '⚙':
            cx, cy = w / 2, h / 2 - 1
            for angle in range(0, 360, 45):
                a = math.radians(angle)
                self.create_line(cx + 6 * math.cos(a), cy + 6 * math.sin(a), cx + 10 * math.cos(a), cy + 10 * math.sin(a), fill=MUTED, width=4)
            self.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=MUTED, outline='')
            self.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=fill, outline='')
        else:
            self.create_text(w / 2, h / 2 - 1 + int(self._pressed), text=self._text, fill='#8f8279' if disabled else FG, font=self._font)
        if self.focus_get() == self and not disabled:
            self.create_line(16, h - 11, w - 16, h - 11, fill=BLUE, width=2)

    def _press(self, event):
        if self._state != 'disabled':
            self.focus_set()
            self._appearance(pressed=True)

    def _release(self, event):
        pressed = self._pressed
        self._appearance(pressed=False)
        if pressed and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()

    def _key(self, event):
        self.invoke()
        return 'break'

    def invoke(self):
        if self._state != 'disabled' and self._command:
            return self._command()

class SoftSwitch(tk.Canvas):
    def __init__(self, parent, variable, command):
        super().__init__(parent, width=51, height=32, bg=parent.cget('background'), highlightthickness=0, bd=0, takefocus=1, cursor='hand2')
        self.variable, self.command = variable, command
        self._trace = variable.trace_add('write', self._draw)
        self.bind('<Button-1>', self._toggle)
        self.bind('<space>', self._toggle)
        self.bind('<Return>', self._toggle)
        self.bind('<FocusIn>', self._draw)
        self.bind('<FocusOut>', self._draw)
        self.bind('<Destroy>', self._destroy, add='+')
        self._draw()

    def _destroy(self, event):
        if event.widget == self:
            self.variable.trace_remove('write', self._trace)

    def _draw(self, *args):
        self.delete('all')
        on = self.variable.get()
        self.create_rectangle(16, 6, 35, 26, fill='#8db4ce' if on else '#cabdb3', outline='')
        self.create_oval(6, 6, 26, 26, fill='#8db4ce' if on else '#cabdb3', outline='')
        self.create_oval(25, 6, 45, 26, fill='#8db4ce' if on else '#cabdb3', outline='')
        x = 25 if on else 6
        self.create_oval(x, 7, x + 19, 26, fill=PANEL, outline='#fffaf6')
        if self.focus_get() == self:
            self.create_line(8, 30, 43, 30, fill=BLUE, width=2)

    def _toggle(self, event):
        self.focus_set()
        self.variable.set(not self.variable.get())
        self.command()
        return 'break'
