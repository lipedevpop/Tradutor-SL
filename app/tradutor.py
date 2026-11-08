"""Tradutor IM Alchemy — desktop companion, never sends messages."""
import os
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import queue
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from tkinter.scrolledtext import ScrolledText
from engine import load_settings, save_settings
from deepl_api import DeepLEngine, NeedsAttention
from key_store import load_key, save_key, forget_key
from log_reader import LogReader
from language_filter import EnglishFilter
from viewer_profiles import VIEWERS, HELP, browse_start, discover_folders
from soft_ui import SoftCard, SoftButton, SoftSwitch, BG, PANEL, FG, MUTED, BLUE
from app_identity import APP_NAME, APP_VERSION, set_window_icon
from viewer_detection import AUTO_VIEWER, VIEWER_CHOICES, detect_viewers
from account_profiles import AUTO_ACCOUNT, ACCOUNT_CHOICES, PREFERRED_ACCOUNTS, account_for_folder, account_folders
from update_ui import Updates, mark_startup_ready


class Worker(threading.Thread):
    def __init__(self, events):
        # A network request cannot be cancelled safely by Tk.  A daemon worker
        # lets Windows close the app immediately instead of waiting on timeout.
        super().__init__(daemon=True, name='tradutor-worker')
        self.events = events
        self.commands = queue.Queue()
        self.stopped = threading.Event()

    def run(self):
        try:
            self.language_filter = EnglishFilter()
        except Exception:
            self.events.put(('fatal', 'Não foi possível iniciar o filtro de idioma. Execute 1_INSTALAR.bat. Nenhuma mensagem foi enviada à API.'))
            return
        engine = DeepLEngine(self.events.put, self.stopped)
        try:
            self.process(engine)
        finally:
            engine.close()

    def process(self, engine):
        self.events.put(('ready', None))
        reader = None
        session = 0
        pending = deque()
        draft = None
        poll_at = 0
        ignored = 0
        force_english = False
        while not self.stopped.is_set():
            while True:
                try:
                    command, payload = self.commands.get_nowait()
                except queue.Empty:
                    break
                if command == 'quit':
                    return
                if command in ('api_configure', 'api_usage', 'api_resume'):
                    try:
                        if command == 'api_configure':
                            engine.configure(payload)
                            self.events.put(('api_resumed', None))
                        elif command == 'api_usage':
                            engine.usage()
                        else:
                            engine.resume()
                            self.events.put(('api_resumed', None))
                    except NeedsAttention:
                        pass
                    except Exception:
                        engine.blocked = True
                        self.events.put(('api_attention', 'Falha ao configurar DeepL. Confira a chave e a conexão.'))
                elif command == 'draft':
                    draft = payload  # Only the newest unsent draft is translated.
                elif command == 'start':
                    session, folder, aliases, force_english = payload
                    pending.clear()
                    try:
                        reader = LogReader(folder, aliases)
                        self.events.put(('watching', session))
                    except Exception as error:
                        reader = None
                        self.events.put(('watch_error', (session, str(error))))
                elif command == 'stop':
                    reader = None
                    pending.clear()
                elif command == 'mode':
                    force_english = payload
            if reader and time.monotonic() >= poll_at:
                poll_at = time.monotonic() + 1.0
                try:
                    raw_messages = reader.poll()
                    messages = [msg for msg in raw_messages if self.language_filter.accepts(msg.text)]
                    ignored += len(raw_messages) - len(messages)
                    if len(raw_messages) != len(messages):
                        self.events.put(('filtered', ignored))
                    if len(pending) + len(messages) > 200:
                        self.events.put(('watch_error', (session,
                            'Há mensagens demais na fila. A leitura foi pausada; parte das novas mensagens não foi traduzida.')))
                        reader = None
                    else:
                        pending.extend(messages)
                        if reader.errors:
                            self.events.put(('notice', reader.errors[0]))
                except Exception as error:
                    reader = None
                    self.events.put(('watch_error', (session, str(error))))
            if self.stopped.is_set():
                return
            if engine.blocked:
                self.stopped.wait(0.2)
                continue
            if draft is not None:
                revision, text = draft
                draft = None
                try:
                    translated = engine.translate(text, 'pt_en') if text.strip() else ''
                    self.events.put(('draft', (revision, translated, None)))
                except NeedsAttention:
                    draft = (revision, text)
                    self.events.put(('draft', (revision, '', 'DeepL pausado; confira o aviso e clique em Retomar API.')))
                except Exception as error:
                    self.events.put(('draft', (revision, '', str(error))))
            elif pending:
                msg = pending.popleft()
                try:
                    if len(msg.text) > 5000:
                        translation = '[Mensagem longa demais para esta versão. Consulte o original.]'
                    else:
                        translation = engine.translate(msg.text, 'en_pt')
                    self.events.put(('incoming', (session, msg, translation)))
                except NeedsAttention:
                    pending.appendleft(msg)
                except Exception:
                    self.events.put(('incoming', (session, msg, '[Falha na tradução. Original disponível abaixo.]')))
            else:
                # Wake immediately for a command instead of polling five times
                # a second while idle.
                self.stopped.wait(0.20)


class App:
    BG = BG
    PANEL = PANEL
    FG = FG
    MUTED = MUTED
    ACCENT = BLUE

    def __init__(self, root):
        self.root = root
        self.UI_FONT = "Segoe UI" if "Segoe UI" in tkfont.families(root) else "DejaVu Sans"
        self.root.title(APP_NAME)
        set_window_icon(self.root)
        self.root.geometry('440x660')
        self.root.minsize(400, 640)
        self.root.configure(bg=self.BG)
        self.config = load_settings()
        self.key_load_error = False
        try:
            saved_key = load_key()
        except (OSError, ValueError, UnicodeError):
            saved_key = ''
            self.key_load_error = True
        self.api_key = tk.StringVar(value=saved_key)
        self.remember_key = tk.BooleanVar(value=bool(saved_key))
        self.api_configured = False
        self.usage_status = tk.StringVar(value='Consumo: consulte após aplicar sua chave.')
        self.filter_status = tk.StringVar(value='Filtro local: somente inglês em IMs individuais.')
        self.layout = tk.StringVar(value='Mini horizontal')
        self.events = queue.Queue()
        self.worker = Worker(self.events)
        self.ready = False
        self.watching = False
        self.session = 0
        self.revision = 0
        self.translated_revision = -1
        self.debounce = None
        self.history = defaultdict(lambda: deque(maxlen=60))
        self.conversations = []
        self.unread = defaultdict(int)
        self.active = None
        self.show_original = False
        selected_viewer = self.config.get('viewer', 'Firestorm')
        if selected_viewer not in VIEWERS:
            selected_viewer = 'Firestorm'
        self.viewer = tk.StringVar(value=selected_viewer)
        self.viewer_choice = tk.StringVar(value=selected_viewer if self.config.get('viewer_mode') == 'manual' else AUTO_VIEWER)
        self.viewer_mode = 'manual' if self.viewer_choice.get() != AUTO_VIEWER else 'auto'
        self.viewer_resolved = self.viewer_choice.get() != AUTO_VIEWER
        self.viewer_status = tk.StringVar(value='Manual: ' + selected_viewer if self.viewer_resolved else 'Automático: aguardando identificação do viewer.')
        self._profile_name = selected_viewer
        self.detect_generation = 0
        self.detecting = False
        stored_profiles = self.config.get('viewer_profiles', {})
        self.viewer_profiles = stored_profiles if isinstance(stored_profiles, dict) else {}
        self.viewer_help = tk.StringVar(value=HELP[selected_viewer])
        self.folder = tk.StringVar(value=self.config.get('folder', ''))
        self.aliases = tk.StringVar(value=self.config.get('aliases', ''))
        selected_profile = self.viewer_profiles.get(selected_viewer, {})
        if not isinstance(selected_profile, dict):
            selected_profile = {}
        account = selected_profile.get('account', account_for_folder(self.folder.get()) or AUTO_ACCOUNT)
        self._account_name = account if account in ACCOUNT_CHOICES else AUTO_ACCOUNT
        self.account_choice = tk.StringVar(value=self._account_name)
        self.topmost = tk.BooleanVar(value=self.config.get('topmost', True))
        self.force = tk.BooleanVar(value=self.config.get('force', False))
        self.status = tk.StringVar(value='DeepL online · textos enviados ao DeepL para traduzir.')
        self.draft_status = tk.StringVar(value='A tradução aparece após uma breve pausa na digitação.')
        self.build()
        self.updates = Updates(self)
        self.apply_layout(save=False)
        self.root.attributes('-topmost', self.topmost.get())
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.worker.start()
        if saved_key:
            self.worker.commands.put(('api_configure', saved_key))
        elif self.key_load_error:
            self.root.after(300, lambda: messagebox.showwarning('Chave salva', 'Não consegui recuperar a chave protegida. Cole novamente nas configurações.'))
        self.root.after(200, self.receive)
        if self.viewer_choice.get() == AUTO_VIEWER:
            self.root.after(350, lambda: self.detect_viewer(quiet=True))
        elif not self.folder.get():
            self.root.after(350, lambda: self.detect_folder(quiet=True))

    def build(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=(self.UI_FONT, 10), background=self.BG, foreground=self.FG)
        style.configure('TFrame', background=self.BG)
        style.configure('TLabel', background=self.BG, foreground=self.FG)
        style.configure('TButton', padding=(10, 7), background='#f4e8de', foreground=self.FG, borderwidth=1)
        style.map('TButton', background=[('active', '#f5c3aa')], foreground=[('disabled', '#8f8279')])
        style.configure('TEntry', fieldbackground=self.PANEL, foreground=self.FG, padding=7)
        style.configure('TCombobox', fieldbackground=self.PANEL, foreground=self.FG, padding=7, arrowsize=13)
        style.map('TCombobox', fieldbackground=[('readonly', self.PANEL)], foreground=[('readonly', self.FG)], selectbackground=[('readonly', '#d9e8f2')], selectforeground=[('readonly', self.FG)])
        style.configure('TCheckbutton', background=self.BG, foreground=self.MUTED, padding=4)
        style.map('TCheckbutton', background=[('active', self.BG)])
        self.root.option_add('*TCombobox*Listbox.background', self.PANEL)
        self.root.option_add('*TCombobox*Listbox.foreground', self.FG)
        outer = tk.Frame(self.root, bg=self.BG, padx=12, pady=8)
        outer.pack(fill='both', expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        header = tk.Frame(outer, bg=self.BG)
        header.grid(row=0, column=0, sticky='ew', pady=(0, 2))
        image = self.root._app_icon
        scale = max(1, (max(image.width(), image.height()) + 31) // 32)
        self.header_icon = image.subsample(scale, scale)
        tk.Label(header, image=self.header_icon, bg=self.BG).pack(side='left', padx=(4, 6))
        tk.Label(header, text=APP_NAME, bg=self.BG, fg=self.FG, font=(self.UI_FONT, 13, 'bold')).pack(side='left')
        tk.Label(header, text='MINI HORIZONTAL', bg=self.BG, fg=self.MUTED, font=(self.UI_FONT, 8)).pack(side='right', padx=6)

        toolbar = tk.Frame(outer, bg=self.BG)
        toolbar.grid(row=1, column=0, sticky='ew', pady=(0, 5))
        toolbar.columnconfigure(2, weight=1)
        self.read_state = tk.StringVar(value='○ Pausado')
        tk.Label(toolbar, textvariable=self.read_state, bg=self.BG, fg=self.ACCENT, font=(self.UI_FONT, 9, 'bold')).grid(row=0, column=0, padx=(5, 5))
        self.start_button = SoftButton(toolbar, text='Iniciar', command=self.toggle, state='disabled', width=6)
        self.start_button.grid(row=0, column=1, padx=(0, 5))
        self.conversation_choice = tk.StringVar(value='Aguardando conversas…')
        self.conversation_box = ttk.Combobox(toolbar, textvariable=self.conversation_choice, state='readonly', width=12)
        self.conversation_box.grid(row=0, column=2, sticky='ew')
        self.conversation_box.bind('<<ComboboxSelected>>', self.select_conversation)
        self.unread_label = tk.Label(toolbar, text='', bg=self.BG, fg=self.ACCENT, font=(self.UI_FONT, 8))
        self.unread_label.grid(row=0, column=3, padx=3)
        tk.Label(toolbar, text='Fixar', bg=self.BG, fg=self.MUTED, font=(self.UI_FONT, 9)).grid(row=0, column=4, padx=(4, 0))
        SoftSwitch(toolbar, self.topmost, self.update_topmost).grid(row=0, column=5)
        SoftButton(toolbar, text='⚙', width=2, command=self.open_settings).grid(row=0, column=6)

        body = tk.Frame(outer, bg=self.BG)
        body.grid(row=2, column=0, sticky='nsew')
        body.columnconfigure(0, weight=1, uniform='columns')
        body.columnconfigure(1, weight=1, uniform='columns')
        body.rowconfigure(0, weight=1)
        inbox_card = SoftCard(body, padding=18)
        inbox_card.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        inbox = inbox_card.content
        inbox.columnconfigure(0, weight=1)
        inbox.rowconfigure(1, weight=1)
        tk.Label(inbox, text='RECEBIDA · PT', bg=self.PANEL, fg=self.MUTED, font=(self.UI_FONT, 9, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 9))
        self.messages = self.text_widget(inbox, height=4)
        self.messages.grid(row=1, column=0, sticky='nsew')
        self.messages.tag_configure('sender', foreground=self.ACCENT, font=(self.UI_FONT, 10, 'bold'))
        self.messages.tag_configure('original', foreground=self.MUTED, font=(self.UI_FONT, 9))
        self.messages.insert('end', 'Inicie a leitura para receber novas IMs.\n\nPasta e chave na engrenagem.')
        self.messages.configure(state='disabled')
        self.original_button = SoftButton(inbox, text='Ver original', command=self.toggle_original)
        self.original_button.grid(row=2, column=0, sticky='e', pady=(5, 0))

        reply = tk.Frame(body, bg=self.BG)
        reply.grid(row=0, column=1, sticky='nsew')
        reply.columnconfigure(0, weight=1)
        reply.rowconfigure(0, weight=1)
        reply.rowconfigure(1, weight=1)
        for row, title, attr in [(0, 'SUA RESPOSTA · PT', 'draft'), (1, 'TRADUÇÃO · EN', 'output')]:
            card = SoftCard(reply, padding=16, radius=20)
            card.grid(row=row, column=0, sticky='nsew', pady=(0, 2))
            panel = card.content
            panel.columnconfigure(0, weight=1)
            panel.rowconfigure(1, weight=1)
            tk.Label(panel, text=title, bg=self.PANEL, fg=self.MUTED, font=(self.UI_FONT, 9, 'bold')).grid(row=0, column=0, sticky='w', pady=(0, 6))
            widget = self.text_widget(panel, height=2)
            widget.grid(row=1, column=0, sticky='nsew')
            setattr(self, attr, widget)
        self.draft.bind('<<Modified>>', self.edited)
        self.output.configure(state='disabled')
        bottom = tk.Frame(reply, bg=self.BG)
        bottom.grid(row=2, column=0, sticky='e', pady=(1, 0))
        SoftButton(bottom, text='Limpar', command=self.clear_draft).pack(side='left', padx=(0, 3))
        self.copy_button = SoftButton(bottom, text='Copiar inglês', accent=True, command=self.copy, state='disabled')
        self.copy_button.pack(side='left')
        self.draft_label = tk.Label(reply, textvariable=self.draft_status, bg=self.BG, fg=self.MUTED, font=(self.UI_FONT, 8), anchor='w', justify='left', wraplength=260)
        self.draft_label.grid(row=3, column=0, sticky='ew', padx=7, pady=(2, 0))
        reply.bind('<Configure>', lambda e: self.draft_label.configure(wraplength=max(100, e.width - 14)))
        self.status_label = tk.Label(outer, textvariable=self.status, bg=self.BG, fg=self.MUTED, font=(self.UI_FONT, 8), anchor='w', justify='left', wraplength=600)
        self.status_label.grid(row=3, column=0, sticky='ew', padx=6, pady=(5, 0))
        outer.bind('<Configure>', lambda e: self.status_label.configure(wraplength=max(200, e.width - 30)))
        self.build_settings()

    def build_settings(self):
        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.withdraw()
        self.settings_window.title(APP_NAME + ' • Configurações')
        self.settings_window.configure(bg=self.BG)
        self.settings_window.transient(self.root)
        self.settings_window.protocol('WM_DELETE_WINDOW', self.hide_settings)
        viewer_panel = ttk.Frame(self.settings_window, padding=(16, 12, 16, 0))
        viewer_panel.pack(fill='x')
        viewer_panel.columnconfigure(1, weight=1)
        ttk.Label(viewer_panel, text='Viewer').grid(row=0, column=0, padx=(0, 10))
        self.viewer_box = ttk.Combobox(viewer_panel, textvariable=self.viewer_choice, values=VIEWER_CHOICES, state='readonly')
        self.viewer_box.grid(row=0, column=1, sticky='ew')
        self.viewer_box.bind('<<ComboboxSelected>>', self.change_viewer)
        ttk.Label(viewer_panel, textvariable=self.viewer_help, foreground=self.MUTED, wraplength=425, justify='left').grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        panel = ttk.Frame(self.settings_window, padding=(16, 10))
        panel.pack(fill='both', expand=True)
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text='Pasta do avatar', font=(self.UI_FONT, 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.path_entry = ttk.Entry(panel, textvariable=self.folder, width=40)
        self.path_entry.grid(row=1, column=0, sticky='ew', pady=6)
        self.browse_button = ttk.Button(panel, text='Escolher…', command=self.browse)
        self.browse_button.grid(row=1, column=1, padx=(8, 0))
        self.detect_button = ttk.Button(viewer_panel, text='Detectar', command=self.detect_selection)
        self.detect_button.grid(row=0, column=2, padx=(8, 0))
        ttk.Label(viewer_panel, textvariable=self.viewer_status, foreground=self.ACCENT, wraplength=425).grid(row=2, column=0, columnspan=3, sticky='w', pady=(6, 0))
        ttk.Label(viewer_panel, text='Conta').grid(row=3, column=0, padx=(0, 10), pady=(6, 0))
        self.account_box = ttk.Combobox(viewer_panel, textvariable=self.account_choice, values=ACCOUNT_CHOICES,
                                      state='readonly' if self.viewer_resolved else 'disabled')
        self.account_box.grid(row=3, column=1, columnspan=2, sticky='ew', pady=(6, 0))
        self.account_box.bind('<<ComboboxSelected>>', self.change_account)
        ttk.Label(panel, text='Seu nome no chat').grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.alias_entry = ttk.Entry(panel, textvariable=self.aliases)
        self.alias_entry.grid(row=3, column=0, columnspan=2, sticky='ew', pady=6)
        ttk.Label(panel, text='Para ignorar suas próprias IMs. Separe nomes extras com ;', wraplength=400, foreground=self.MUTED).grid(row=4, column=0, columnspan=2, sticky='w')
        ttk.Label(panel, text='Filtro local: somente mensagens em inglês de IMs individuais.\nPortuguês e idioma incerto não são enviados ao DeepL.', wraplength=400, foreground=self.MUTED).grid(row=5, column=0, columnspan=2, sticky='w', pady=8)
        ttk.Label(panel, text='Pause a leitura para alterar a pasta ou seu nome.\nAo retomar, somente novas mensagens serão lidas.', wraplength=400, foreground=self.MUTED).grid(row=6, column=0, columnspan=2, sticky='w')
        version_panel = ttk.Frame(panel)
        version_panel.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        ttk.Label(version_panel, text=f'Versão {APP_VERSION} · Soft UI').pack(side='left')
        self.updates_button = ttk.Button(version_panel, text='Atualizações', command=lambda: self.updates.open())
        self.updates_button.pack(side='right')
        ttk.Label(panel, text='Chave da API DeepL').grid(row=8, column=0, columnspan=2, sticky='w', pady=(12, 3))
        ttk.Entry(panel, textvariable=self.api_key, show='*').grid(row=9, column=0, columnspan=2, sticky='ew')
        ttk.Label(panel, textvariable=self.usage_status, wraplength=400, foreground=self.MUTED).grid(row=10, column=0, columnspan=2, sticky='w', pady=6)
        ttk.Label(panel, textvariable=self.filter_status, wraplength=400, foreground=self.MUTED).grid(row=14, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Checkbutton(panel, text='Lembrar minha chave neste Windows', variable=self.remember_key).grid(row=11, column=0, columnspan=2, sticky='w')
        ttk.Label(panel, text='A chave salva é protegida pelo Windows para seu usuário.\nOs textos enviados ao DeepL consomem sua franquia.', wraplength=400, foreground=self.MUTED).grid(row=12, column=0, columnspan=2, sticky='w', pady=6)
        api_controls = ttk.Frame(panel)
        api_controls.grid(row=15, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Button(api_controls, text='Consultar consumo', command=lambda: self.worker.commands.put(('api_usage', None))).pack(side='left')
        self.resume_api = ttk.Button(api_controls, text='Retomar API', state='disabled', command=lambda: self.worker.commands.put(('api_resume', None)))
        self.resume_api.pack(side='right')
        ttk.Button(panel, text='Aplicar chave e fechar', command=self.hide_settings).grid(row=13, column=0, columnspan=2, sticky='e', pady=(8, 0))

    def apply_layout(self, save=True):
        self.root.title(APP_NAME)
        self.root.minsize(600, 380)
        self.root.geometry('680x420')
        if save:
            self.persist()

    def activate_conversation(self, name):
        self.active = name
        self.unread[name] = 0
        self.refresh_list()
        self.render_messages()

    def open_settings(self):
        self.settings_window.attributes('-topmost', self.topmost.get())
        self.settings_window.deiconify()
        self.settings_window.lift()
        self.settings_window.focus_set()

    def hide_settings(self):
        key = self.api_key.get().strip()
        try:
            if self.remember_key.get() and key:
                save_key(key)
            else:
                forget_key()
        except OSError:
            messagebox.showerror('Não foi possível salvar', 'O Windows não conseguiu atualizar a chave protegida. As configurações continuam abertas; tente novamente.')
            return
        self.worker.commands.put(('api_configure', key))
        self.api_configured = False
        self.persist()
        self.settings_window.withdraw()

    def update_topmost(self):
        self.root.attributes('-topmost', self.topmost.get())
        self.settings_window.attributes('-topmost', self.topmost.get())
        self.persist()

    def update_force(self):
        self.worker.commands.put(('mode', self.force.get()))
        self.persist()

    def toggle_original(self):
        self.show_original = not self.show_original
        self.original_button.configure(text='Ocultar original' if self.show_original else 'Ver original')
        if self.active is not None:
            self.render_messages()

    def text_widget(self, parent, **kwargs):
        widget = ScrolledText(parent, width=1, wrap='word', bg=self.PANEL, fg=self.FG,
                            insertbackground=self.ACCENT, selectbackground='#d9e8f2', selectforeground=self.FG,
                            relief='flat', borderwidth=0, highlightthickness=0, padx=6, pady=4,
                            font=(self.UI_FONT, 10), undo=False, **kwargs)
        widget.vbar.configure(bg=self.PANEL, activebackground='#d6e3ec', troughcolor=self.PANEL, relief='flat', bd=0, width=10, highlightthickness=0)
        return widget

    def change_viewer(self, event=None):
        if self.watching:
            self.viewer_choice.set(AUTO_VIEWER if self.viewer_mode == 'auto' else self._profile_name)
            return
        choice = self.viewer_choice.get()
        if choice == AUTO_VIEWER:
            self.viewer_mode = 'auto'
            self.detect_viewer(quiet=True)
        elif choice in VIEWERS:
            self.viewer_mode = 'manual'
            self.select_viewer(choice)
            self.viewer_status.set('Manual: ' + choice)

    def select_viewer(self, name, discover=True):
        """Switch only while paused and keep a separate folder/account per viewer."""
        if self.watching or name not in VIEWERS:
            return
        self.detect_generation += 1
        self.detecting = False
        self.detect_button.configure(state='normal')
        if self.viewer_resolved:
            self.save_viewer_profile()
        profile = self.viewer_profiles.get(name, {})
        if not isinstance(profile, dict):
            profile = {}
        # Migrate the old global folder only for its matching viewer.
        if name == self._profile_name and not profile and self.folder.get():
            profile = {'folder': self.folder.get(), 'aliases': self.aliases.get()}
        self.viewer.set(name)
        self._profile_name = name
        self.viewer_resolved = True
        self.account_box.configure(state='readonly')
        self.folder.set(profile.get('folder', ''))
        self.aliases.set(profile.get('aliases', ''))
        account = profile.get('account', account_for_folder(self.folder.get()) or AUTO_ACCOUNT)
        self._account_name = account if account in ACCOUNT_CHOICES else AUTO_ACCOUNT
        self.account_choice.set(self._account_name)
        self.viewer_help.set(HELP[name])
        # A paused worker can still finish a request from the previous viewer.
        self.session += 1
        self.history.clear()
        self.conversations.clear()
        self.unread.clear()
        self.active = None
        self.conversation_choice.set('Aguardando conversas…')
        self.refresh_list()
        self.messages.configure(state='normal')
        self.messages.delete('1.0', 'end')
        self.messages.insert('end', 'Selecione a pasta do avatar no ' + name + ' e inicie a leitura.')
        self.messages.configure(state='disabled')
        self.status.set('Viewer selecionado: ' + name + '. Confira a pasta das IMs.')
        self.persist()
        if discover and (not self.folder.get() or not Path(self.folder.get()).is_dir()):
            self.folder.set('')
            self.detect_folder(quiet=True)

    def detect_selection(self):
        if self.viewer_choice.get() == AUTO_VIEWER:
            self.detect_viewer()
        else:
            self.detect_folder()

    def detect_viewer(self, quiet=False):
        if self.watching:
            return
        if self.viewer_resolved:
            self.save_viewer_profile()
        self.viewer_resolved = False
        self.account_box.configure(state='disabled')
        self.detect_generation += 1
        generation = self.detect_generation
        self.detecting = True
        self.detect_button.configure(state='disabled')
        self.viewer_status.set('Automático: identificando o viewer…')
        self.status.set('Procurando Firestorm, Alchemy ou Cool VL Viewer…')
        self.persist()

        def search():
            try:
                result, error = detect_viewers(), None
            except Exception:
                result, error = None, 'Não foi possível detectar o viewer. Selecione manualmente nas configurações.'
            self.events.put(('viewer_detection', (generation, result, quiet, error)))
        threading.Thread(target=search, daemon=True, name='viewer-detection').start()

    def apply_viewer_detection(self, data):
        generation, result, quiet, error = data
        if generation != self.detect_generation or self.viewer_choice.get() != AUTO_VIEWER or self.watching:
            return
        self.detecting = False
        self.detect_button.configure(state='normal')
        if result and len(result.viewers) == 1:
            name = result.viewers[0]
            self.select_viewer(name, discover=False)
            source = 'aberto' if result.source == 'running' else 'configuração encontrada'
            self.viewer_status.set(f'Automático: {name} ({source}).')
            if not self.folder.get() or not Path(self.folder.get()).is_dir():
                self.folder.set('')
                self.detect_folder(quiet=quiet)
            else:
                self.status.set('Viewer identificado: ' + name + '. Usando a pasta salva; confira a conta antes de iniciar.')
        else:
            self.viewer_resolved = False
            self.folder.set('')
            self.aliases.set('')
            if result and result.viewers:
                text = 'Encontrei ' + ' e '.join(result.viewers) + '. Selecione o viewer manualmente.'
            else:
                text = error or 'Nenhum viewer identificado. Abra o viewer e clique Detectar, ou selecione manualmente.'
            self.viewer_status.set('Automático: seleção necessária.')
            self.status.set(text)
            # Put the explanation beside the choices as well as in the main status.
            self.viewer_help.set(text)
            self.persist()
            if not quiet or (result and result.viewers):
                self.open_settings()

    def browse(self):
        if self.watching:
            return
        if not self.viewer_resolved:
            self.status.set('Selecione Firestorm, Alchemy ou Cool VL Viewer antes de escolher a pasta do avatar.')
            return
        self.detect_generation += 1
        self.detecting = False
        self.detect_button.configure(state='normal')
        start = browse_start(self.viewer.get(), self.folder.get())
        folder = filedialog.askdirectory(title='Escolha a pasta do avatar — ' + self.viewer.get(), initialdir=str(start))
        if folder:
            self.detect_generation += 1
            self.detecting = False
            self.detect_button.configure(state='normal')
            self.set_detected_folder(Path(folder))

    def detect_folder(self, quiet=False):
        if self.watching:
            return
        if not self.viewer_resolved:
            self.detect_viewer(quiet=quiet)
            return
        self.detect_generation += 1
        generation, viewer = self.detect_generation, self.viewer.get()
        self.detecting = True
        self.detect_button.configure(state='disabled')
        self.status.set('Procurando a pasta de conversas do ' + viewer + '…')
        def search():
            try:
                paths = discover_folders(viewer)
                error = None
            except Exception:
                paths, error = [], 'Não foi possível verificar as pastas. Use Escolher… para selecionar manualmente.'
            self.events.put(('folder_detection', (generation, viewer, paths, quiet, error)))
        threading.Thread(target=search, daemon=True, name='viewer-folder-detection').start()

    def set_detected_folder(self, path):
        if self.watching:
            return
        self.folder.set(str(path))
        account = account_for_folder(path)
        if account:
            self._account_name = account
            self.account_choice.set(account)
        self.aliases.set(self._account_name if self._account_name in PREFERRED_ACCOUNTS else Path(path).name.replace('_', ' '))
        self.persist()
        self.status.set('Pasta encontrada para ' + self.viewer.get() + ': ' + Path(path).name)

    def change_account(self, event=None):
        if self.watching or not self.viewer_resolved:
            self.account_choice.set(self._account_name)
            return
        choice = self.account_choice.get()
        if choice not in ACCOUNT_CHOICES:
            return
        self.save_viewer_profile()
        profile = self.viewer_profiles.get(self._profile_name, {})
        accounts = profile.get('accounts', {})
        saved = accounts.get(choice, {}) if isinstance(accounts, dict) else {}
        if not isinstance(saved, dict):
            saved = {}
        self._account_name = choice
        self.detect_generation += 1
        self.detecting = False
        self.detect_button.configure(state='normal')
        self.folder.set(saved.get('folder', ''))
        self.aliases.set(saved.get('aliases', choice if choice in PREFERRED_ACCOUNTS else ''))
        self.session += 1
        self.history.clear()
        self.conversations.clear()
        self.unread.clear()
        self.active = None
        self.conversation_choice.set('Aguardando conversas…')
        self.refresh_list()
        self.messages.configure(state='normal')
        self.messages.delete('1.0', 'end')
        self.messages.insert('end', 'Conta selecionada: ' + choice + '. Confira a pasta e inicie a leitura.')
        self.messages.configure(state='disabled')
        self.status.set('Conta selecionada: ' + choice + '.')
        self.persist()
        if not self.folder.get() or not Path(self.folder.get()).is_dir():
            self.folder.set('')
            self.detect_folder(quiet=True)

    def save_viewer_profile(self):
        previous = self.viewer_profiles.get(self._profile_name, {})
        profile = dict(previous) if isinstance(previous, dict) else {}
        old_accounts = profile.get('accounts', {})
        accounts = dict(old_accounts) if isinstance(old_accounts, dict) else {}
        account = self._account_name if self._account_name in PREFERRED_ACCOUNTS else account_for_folder(self.folder.get())
        if account and self.folder.get():
            accounts[account] = {'folder': self.folder.get(), 'aliases': self.aliases.get()}
        profile.update(folder=self.folder.get(), aliases=self.aliases.get(), account=self._account_name, accounts=accounts)
        self.viewer_profiles[self._profile_name] = profile

    def choose_detected_folder(self, paths):
        self.open_settings()
        picker = tk.Toplevel(self.settings_window)
        picker.title('Escolha o avatar — ' + self.viewer.get())
        picker.configure(bg=self.BG)
        picker.transient(self.settings_window)
        picker.attributes('-topmost', self.topmost.get())
        picker.geometry('650x270')
        ttk.Label(picker, text='Encontrei várias pastas. Escolha a conta que está usando:', padding=12).pack(anchor='w')
        items = tk.Listbox(picker, font=(self.UI_FONT, 10), bg=self.PANEL, fg=self.FG, selectbackground='#d9e8f2', selectforeground=self.FG, exportselection=False)
        items.pack(fill='both', expand=True, padx=12)
        for path in paths:
            items.insert('end', str(path))
        scrollbar = ttk.Scrollbar(picker, orient='horizontal', command=items.xview)
        scrollbar.pack(fill='x', padx=12)
        items.configure(xscrollcommand=scrollbar.set)
        items.selection_set(0)
        viewer = self.viewer.get()
        generation = self.detect_generation
        def select(event=None):
            chosen = items.curselection()
            if chosen and generation == self.detect_generation and viewer == self.viewer.get() and not self.watching:
                self.set_detected_folder(paths[chosen[0]])
            picker.destroy()
        ttk.Button(picker, text='Usar esta pasta', command=select).pack(anchor='e', padx=12, pady=10)
        items.bind('<Double-1>', select)
        items.bind('<Return>', select)
        picker.bind('<Escape>', lambda event: picker.destroy())
        picker.grab_set()
        items.focus_set()

    def persist(self):
        if self.viewer_resolved:
            self.save_viewer_profile()
        try:
            save_settings({'viewer': self.viewer.get(), 'viewer_mode': self.viewer_mode, 'viewer_profiles': self.viewer_profiles, 'folder': self.folder.get(), 'aliases': self.aliases.get(),
                           'topmost': self.topmost.get(), 'force': self.force.get(), 'layout': self.layout.get(), 'layout_revision': 1})
        except OSError:
            self.status.set('Não foi possível salvar as preferências.')

    def set_controls(self, watching):
        self.watching = watching
        self.viewer_box.configure(state='disabled' if watching else 'readonly')
        self.account_box.configure(state='disabled' if watching or not self.viewer_resolved else 'readonly')
        self.detect_button.configure(state='disabled' if watching or self.detecting else 'normal')
        self.read_state.set('● Lendo' if watching else '○ Pausado')
        self.start_button.configure(text='Pausar' if watching else 'Iniciar')
        for widget in (self.path_entry, self.alias_entry, self.browse_button):
            widget.configure(state='disabled' if watching else 'normal')

    def toggle(self):
        if not self.watching and not self.viewer_resolved:
            self.open_settings()
            self.status.set('Identifique o viewer em Automático → Detectar, ou selecione Firestorm / Alchemy / Cool VL Viewer manualmente.')
            return
        if not self.api_configured and not self.watching:
            self.open_settings()
            self.status.set('Cole a chave DeepL na engrenagem e clique em Aplicar chave e fechar.')
            return
        if self.watching:
            self.session += 1
            self.worker.commands.put(('stop', None))
            self.set_controls(False)
            self.status.set('Pausado. Ao retomar, serão lidas somente as próximas mensagens.')
            return
        folder = Path(self.folder.get().strip())
        if not self.folder.get().strip() or not folder.is_dir():
            self.open_settings()
            messagebox.showinfo('Escolha a pasta', 'Selecione a pasta do avatar com as IMs do ' + self.viewer.get() + '.')
            return
        if not any(folder.glob('*.txt')):
            messagebox.showinfo('Pasta sem conversas', 'Escolha a pasta do avatar que contém os arquivos .txt das IMs.')
            return
        aliases = [folder.name] + self.aliases.get().split(';')
        self.session += 1
        self.persist()
        self.set_controls(True)
        self.status.set('Iniciando a leitura…')
        self.worker.commands.put(('start', (self.session, str(folder), aliases, self.force.get())))

    def edited(self, event=None):
        if not self.draft.edit_modified():
            return
        self.draft.edit_modified(False)
        self.revision += 1
        self.translated_revision = -1
        self.copy_button.configure(state='disabled')
        self.set_output('')
        if self.debounce:
            self.root.after_cancel(self.debounce)
        self.debounce = self.root.after(900, self.submit_draft)
        self.draft_status.set('Aguardando você terminar de digitar…')

    def submit_draft(self):
        self.debounce = None
        text = self.draft.get('1.0', 'end-1c').strip()
        if not self.ready:
            self.draft_status.set('Aguarde a preparação do tradutor.')
            return
        if len(text) > 4000:
            self.draft_status.set('Divida a resposta: máximo de 4.000 caracteres por tradução.')
            return
        self.worker.commands.put(('draft', (self.revision, text)))
        self.draft_status.set('Traduzindo no DeepL…' if text else 'Escreva sua resposta acima.')

    def set_output(self, text):
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')
        self.output.insert('1.0', text)
        self.output.configure(state='disabled')

    def copy(self):
        if self.translated_revision != self.revision:
            return
        text = self.output.get('1.0', 'end-1c').strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.draft_status.set('Copiado. Cole na IM desejada com Ctrl+V e envie pelo viewer.')

    def clear_draft(self):
        self.draft.delete('1.0', 'end')
        self.draft.focus_set()

    def refresh_list(self):
        labels = [name + (f' ({self.unread[name]})' if self.unread[name] else '') for name in self.conversations]
        self.conversation_box.configure(values=labels)
        if self.active in self.conversations:
            self.conversation_box.current(self.conversations.index(self.active))
        total = sum(self.unread.values())
        self.unread_label.configure(text=f'{total} nova(s)' if total else '')

    def select_conversation(self, event=None):
        index = self.conversation_box.current()
        if 0 <= index < len(self.conversations):
            self.active = self.conversations[index]
            self.unread[self.active] = 0
            self.refresh_list()
            self.render_messages()

    def render_messages(self):
        self.messages.configure(state='normal')
        self.messages.delete('1.0', 'end')
        for msg, translation in self.history[self.active]:
            self.messages.insert('end', f'{msg.sender}  ·  {msg.timestamp}\n', 'sender')
            self.messages.insert('end', translation + '\n')
            if self.show_original:
                self.messages.insert('end', 'Original: ' + msg.text + '\n', 'original')
            self.messages.insert('end', '\n')
        self.messages.configure(state='disabled')
        self.messages.see('end')

    def receive(self):
        list_changed = False
        active_changed = False
        for _ in range(100):
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'viewer_detection':
                self.apply_viewer_detection(data)
            elif kind == 'folder_detection':
                generation, viewer, paths, quiet, error = data
                if generation != self.detect_generation or viewer != self.viewer.get():
                    continue
                self.detecting = False
                self.detect_button.configure(state='disabled' if self.watching else 'normal')
                if self.watching:
                    continue
                paths = account_folders(paths, self.account_choice.get())
                if len(paths) == 1:
                    self.set_detected_folder(paths[0])
                elif paths:
                    self.status.set('Há várias contas. Escolha a pasta do avatar que está usando.')
                    self.choose_detected_folder(paths)
                else:
                    account = self.account_choice.get()
                    text = ('Pasta da conta ' + account + ' não encontrada. Use Escolher… para indicar o caminho.'
                            if account in PREFERRED_ACCOUNTS else
                            'Pasta não encontrada. Ative os logs de IMs no viewer e use Escolher… ou Detectar.')
                    self.status.set(error or text)
                    if not quiet:
                        messagebox.showinfo('Detectar pasta', self.status.get(), parent=self.settings_window)
            elif kind == 'ready':
                self.ready = True
                mark_startup_ready()
                self.start_button.configure(state='normal')
                self.read_state.set('○ Pausado')
                self.status.set('Configure sua chave DeepL na engrenagem para começar.')
                self.submit_draft()
            elif kind == 'filtered':
                self.filter_status.set(f'Ignoradas pelo filtro de idioma nesta sessão: {data}')
            elif kind == 'api_usage':
                self.usage_status.set(data)
                self.status.set(data)
            elif kind == 'api_attention':
                self.resume_api.configure(state='normal')
                self.status.set('DEEPL PAUSADO: ' + data)
            elif kind == 'api_resumed':
                self.resume_api.configure(state='disabled')
                self.api_configured = True
                self.status.set('DeepL conectado. ' + self.usage_status.get())
            elif kind == 'fatal':
                self.read_state.set('○ Indisponível')
                self.status.set('Não foi possível carregar os idiomas.')
                messagebox.showerror('Preparação necessária', data + '\n\nExecute 1_INSTALAR.bat. Se persistir, envie um print do erro.')
            elif kind == 'watching' and data == self.session:
                self.status.set('Lendo novas IMs do ' + self.viewer.get() + ' • DeepL online')
                if not self.conversations:
                    self.messages.configure(state='normal')
                    self.messages.delete('1.0', 'end')
                    self.messages.insert('end', 'Leitura ativa no ' + self.viewer.get() + '.\n\n'
                                         'Aguardando novas IMs após clicar em Iniciar.\n'
                                         'Peça para enviarem uma nova mensagem de teste.')
                    self.messages.configure(state='disabled')
            elif kind == 'watch_error' and data[0] == self.session:
                self.session += 1
                self.worker.commands.put(('stop', None))
                self.set_controls(False)
                self.status.set(data[1])
            elif kind == 'notice':
                self.status.set(data)
            elif kind == 'draft':
                revision, translation, error = data
                if revision == self.revision:
                    self.set_output(translation)
                    self.translated_revision = revision if not error else -1
                    self.copy_button.configure(state='normal' if translation and not error else 'disabled')
                    self.draft_status.set('Falha ao traduzir: ' + error if error else
                                          'Pronto para copiar. Revise a tradução antes de enviar.')
            elif kind == 'incoming':
                session, msg, translation = data
                if session != self.session:
                    continue
                conversation = msg.conversation
                if conversation not in self.conversations:
                    if len(self.conversations) >= 50:
                        self.status.set('Limite de 50 conversas na sessão. Reinicie o tradutor para começar outra sessão.')
                        continue
                    self.conversations.append(conversation)
                self.history[conversation].append((msg, translation))
                if self.active is None:
                    self.active = conversation
                if self.active != conversation:
                    self.unread[conversation] += 1
                list_changed = True
                if self.active == conversation:
                    active_changed = True
                self.status.set('Leitura ativa • nova mensagem em ' + conversation)
        # Render once for a burst of messages instead of rebuilding the full
        # history for every item in the queue.
        if list_changed:
            self.refresh_list()
        if active_changed:
            self.render_messages()
        self.root.after(120 if not self.events.empty() else 250, self.receive)

    def close(self):
        self.persist()
        self.worker.stopped.set()
        self.worker.commands.put(('quit', None))
        self.root.destroy()


if __name__ == '__main__':
    if os.name == 'nt':
        # Lower only this process's priority so the viewer gets CPU time first.
        import ctypes
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x00004000)
    root = tk.Tk()
    app = App(root)
    root.mainloop()
