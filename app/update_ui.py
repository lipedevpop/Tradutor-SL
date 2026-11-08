"""Tk update dialog. All network and preparation work runs outside Tk's thread."""
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from app_identity import APP_VERSION
from update_core import (INSTALL, UpdateError, atomic_json, launch_change,
                         latest_release, prepare_release, read_json, save_source, source_config)


def mark_startup_ready():
    path, token = os.environ.get('TRADUTOR_UPDATE_READY'), os.environ.get('TRADUTOR_UPDATE_TOKEN')
    if path and token:
        destination = Path(path).resolve()
        if destination.is_relative_to(INSTALL / '.updates'):
            atomic_json(destination, {'token': token})


class Updates:
    def __init__(self, app):
        self.app, self.root = app, app.root
        self.events = queue.Queue()
        self.window = None
        self.busy = False
        self.release = None
        self.plan = None
        self.quiet = False
        self.status = tk.StringVar(value='Versão instalada: ' + APP_VERSION)
        try:
            self.repo = source_config()
            prefs = read_json(INSTALL / 'update-preferences.json') if (INSTALL / 'update-preferences.json').exists() else {}
        except Exception:
            self.repo, prefs = '', {}
            self.status.set('Confira o repositório de atualizações nas configurações.')
        self.auto = tk.BooleanVar(value=bool(prefs.get('check_on_start', True)))
        self.repo_text = tk.StringVar(value=self.repo)
        self.root.after(200, self.poll)
        self.root.after(2200, self.startup_check)
        self.root.after(1200, self.show_result)

    def show_result(self):
        result = INSTALL / '.updates' / 'result.json'
        if os.environ.get('TRADUTOR_UPDATE_READY'):
            # Bootstrap commits after the language filter reports readiness.
            if not result.exists() or (INSTALL / '.pending-update.json').exists():
                self.root.after(500, self.show_result)
                return
        if result.exists():
            try:
                data = read_json(result)
                self.status.set(data['message'])
                result.unlink()
                if not data['ok']:
                    messagebox.showwarning('Atualização restaurada', data['message'], parent=self.root)
            except (OSError, ValueError, KeyError):
                pass

    def startup_check(self):
        if self.repo and self.auto.get():
            self.check(quiet=True)

    def open(self):
        if self.window and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            return
        self.window = tk.Toplevel(self.root)
        self.window.title('Atualizações · Tradutor Hot SL')
        self.window.transient(self.root)
        self.window.geometry('540x510')
        self.window.minsize(460, 450)
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(4, weight=1)
        frame = ttk.Frame(self.window, padding=16)
        frame.grid(row=0, column=0, sticky='ew')
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text='Atualizações', font=(self.app.UI_FONT, 15, 'bold')).grid(row=0, column=0, sticky='w')
        ttk.Label(frame, text='Versão instalada: ' + APP_VERSION).grid(row=1, column=0, sticky='w', pady=(3, 12))
        ttk.Label(frame, text='Repositório oficial no GitHub (público)').grid(row=2, column=0, sticky='w')
        self.entry = ttk.Entry(frame, textvariable=self.repo_text)
        self.entry.grid(row=3, column=0, sticky='ew', pady=5)
        ttk.Label(frame, text='Exemplo: seu-usuario/tradutor-hot-sl', foreground=self.app.MUTED).grid(row=4, column=0, sticky='w')
        self.check_button = ttk.Button(frame, text='Salvar e verificar', command=self.save_and_check)
        self.check_button.grid(row=5, column=0, sticky='w', pady=10)
        self.auto_button = ttk.Checkbutton(frame, text='Verificar atualizações ao abrir', variable=self.auto, command=self.save_preference)
        self.auto_button.grid(row=6, column=0, sticky='w')
        ttk.Label(self.window, textvariable=self.status, wraplength=470, padding=(16, 5)).grid(row=1, column=0, sticky='ew')
        self.progress = ttk.Progressbar(self.window, mode='indeterminate')
        self.progress.grid(row=2, column=0, sticky='ew', padx=16, pady=5)
        ttk.Label(self.window, text='Correções desta versão', padding=(16, 5)).grid(row=3, column=0, sticky='w')
        self.notes = ScrolledText(self.window, height=6, wrap='word', font=(self.app.UI_FONT, 10))
        self.notes.grid(row=4, column=0, sticky='nsew', padx=16, pady=5)
        self.set_notes()
        controls = ttk.Frame(self.window, padding=16)
        controls.grid(row=5, column=0, sticky='ew')
        self.install_button = ttk.Button(controls, text='Baixar atualização', command=self.install)
        self.install_button.pack(side='left')
        self.rollback_button = ttk.Button(controls, text='Restaurar anterior', command=self.rollback)
        self.rollback_button.pack(side='right')
        self.refresh()

    def set_notes(self):
        self.notes.configure(state='normal')
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', (self.release['notes'] or 'Sem descrição de correções.') if self.release else
                          'As correções aparecem aqui quando uma nova versão estiver disponível.')
        self.notes.configure(state='disabled')

    def refresh(self):
        if not self.window or not self.window.winfo_exists():
            return
        for widget in (self.entry, self.check_button, self.auto_button):
            widget.configure(state='disabled' if self.busy else 'normal')
        self.install_button.configure(state='normal' if not self.busy and (self.release or self.plan) else 'disabled',
                                      text='Reiniciar e atualizar' if self.plan else 'Baixar atualização')
        self.rollback_button.configure(state='normal' if not self.busy and (INSTALL / '.previous-version.json').exists() else 'disabled')
        if self.busy:
            self.progress.start(15)
        else:
            self.progress.stop()

    def save_preference(self):
        try:
            atomic_json(INSTALL / 'update-preferences.json', {'check_on_start': self.auto.get()})
        except OSError:
            self.status.set('Não foi possível salvar a preferência. Confira a permissão da pasta.')

    def save_and_check(self):
        if self.busy:
            return
        try:
            repo = save_source(self.repo_text.get())
            if repo != self.repo:
                self.release, self.plan = None, None
            self.repo = repo
            self.repo_text.set(repo)
        except (OSError, UpdateError) as error:
            self.status.set(str(error))
            return
        self.check()

    def task(self, function, kind):
        self.busy = True
        self.refresh()
        def run():
            try:
                self.events.put((kind, function()))
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=run, daemon=True, name='tradutor-update').start()

    def check(self, quiet=False):
        if self.busy or not self.repo:
            return
        self.release, self.plan = None, None
        self.quiet = quiet
        self.status.set('Procurando atualizações…')
        self.task(lambda: latest_release(self.repo, APP_VERSION), 'checked')

    def install(self):
        if self.busy:
            return
        if self.plan:
            self.restart(plan=self.plan)
        elif self.release:
            release = dict(self.release)
            self.status.set('Preparando o download…')
            self.task(lambda: prepare_release(release, lambda text: self.events.put(('progress', text))), 'prepared')

    def restart(self, plan=None, rollback=False):
        if not messagebox.askokcancel('Reiniciar tradutor',
                'A leitura será pausada e o tradutor vai reiniciar.\n\n'
                'Copie qualquer resposta ainda não enviada antes de continuar.\n'
                'A chave DeepL, as contas e as configurações serão mantidas.', parent=self.window):
            return
        try:
            self.app.persist()
            process = launch_change(plan, rollback)
            if process.poll() is not None:
                raise UpdateError('O atualizador não iniciou. Tente novamente.')
        except Exception as error:
            self.status.set(str(error))
            return
        self.app.close()

    def rollback(self):
        if not self.busy and (INSTALL / '.previous-version.json').exists():
            self.restart(rollback=True)

    def poll(self):
        for _ in range(100):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                self.status.set(data)
                continue
            self.busy = False
            if kind == 'checked':
                self.release = data
                self.status.set('Nova versão disponível: ' + data['version'] if data else 'Você já está na versão mais recente.')
                if data:
                    self.app.updates_button.configure(text='Atualização disponível')
                    if self.quiet:
                        messagebox.showinfo('Atualização disponível', 'A versão ' + data['version'] +
                                            ' está disponível. Abra Configurações → Atualizações para instalar.', parent=self.root)
                if self.window and self.window.winfo_exists():
                    self.set_notes()
            elif kind == 'prepared':
                self.plan = data
                self.status.set('Tudo pronto. Clique em Reiniciar e atualizar.')
            elif kind == 'error':
                self.status.set(data)
            self.refresh()
        self.root.after(150 if self.busy else 400, self.poll)
