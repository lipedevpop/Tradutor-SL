"""Stable Windows bootstrap. Protocol 1: version folders + atomic activation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def inside(root, relative):
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError('Caminho de instalação inválido.')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('Caminho fora da instalação.')
    return path


def validate(root, pointer):
    app = inside(root, pointer['app'])
    if pointer['app'].split('/')[0] not in ('app', 'versions'):
        raise ValueError('Pasta de aplicativo inválida.')
    runtime = inside(root, pointer['python'])
    if pointer['python'].split('/')[0] not in ('.venv', 'runtimes') or not runtime.is_file():
        raise ValueError('Python da versão não encontrado. Execute 1_INSTALAR.bat.')
    manifest = read(app / 'release-manifest.json')
    if (manifest['app_id'] != 'tradutor-hot-sl' or manifest['protocol'] != 1 or
            not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}', manifest['version']) or
            manifest['version'] != pointer['version']):
        raise ValueError('Versão incompatível.')
    for name, digest in manifest['files'].items():
        file = inside(app, name)
        if file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError('Arquivo da versão incompleto: ' + name)
    if not all(name in manifest['files'] for name in ('tradutor.py', 'update_core.py', 'update_ui.py')):
        raise ValueError('Faltam arquivos essenciais.')
    return app, runtime


class InstallLock:
    def __init__(self, root):
        self.path = Path(root) / '.updates' / 'app.lock'
        self.file = None

    def acquire(self, timeout=0):
        self.path.parent.mkdir(exist_ok=True)
        handle = self.path.open('a+b')
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.file = handle
                return
            except OSError:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise RuntimeError('O Tradutor Hot SL já está aberto ou está sendo atualizado. Feche a outra janela e tente novamente.')
                time.sleep(0.2)

    def close(self):
        if self.file:
            self.file.close()
            self.file = None


def default_pointer(root):
    installed = root / '.install-version.json'
    if installed.exists():
        return read(installed)
    runtime = '.venv/Scripts/pythonw.exe' if os.name == 'nt' else '.venv/bin/python'
    return {'app': 'app', 'python': runtime,
            'version': read(root / 'app' / 'release-manifest.json')['version']}


def current(root):
    path = root / '.active-version.json'
    return read(path) if path.exists() else default_pointer(root)


def recover_interrupted(root):
    pending = root / '.pending-update.json'
    if pending.exists():
        data = read(pending)
        validate(root, data['previous'])
        write(root / '.active-version.json', data['previous'])
        write(root / '.updates' / 'result.json', {'ok': False, 'message':
              'Uma atualização foi interrompida. A versão anterior foi restaurada.'})
        pending.unlink()


def show_error(text):
    import tkinter as tk
    from tkinter import messagebox
    window = tk.Tk()
    window.withdraw()
    messagebox.showerror('Tradutor Hot SL', text, parent=window)
    window.destroy()


def spawn(root, pointer, log, ready=None):
    app, runtime = validate(root, pointer)
    env = os.environ.copy()
    env['TRADUTOR_INSTALL_DIR'] = str(root)
    env.pop('TRADUTOR_UPDATE_READY', None)
    env.pop('TRADUTOR_UPDATE_TOKEN', None)
    if ready:
        env['TRADUTOR_UPDATE_READY'] = str(ready[0])
        env['TRADUTOR_UPDATE_TOKEN'] = ready[1]
    return subprocess.Popen([str(runtime), '-E', '-s', str(app / 'tradutor.py')], cwd=app,
                            env=env, stdout=log, stderr=log)


def activate(root, target, log, health_timeout=45):
    previous = current(root)
    validate(root, previous)
    validate(root, target)
    if previous['app'] == target['app']:
        raise ValueError('Esta versão já está ativa.')
    ready = root / '.updates' / ('ready-' + uuid.uuid4().hex + '.json')
    token = uuid.uuid4().hex
    pending = root / '.pending-update.json'
    write(pending, {'previous': previous, 'target': target})
    write(root / '.active-version.json', target)
    child = None
    try:
        child = spawn(root, target, log, (ready, token))
        deadline = time.monotonic() + health_timeout
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError('A nova versão fechou antes de iniciar.')
            if ready.exists() and read(ready).get('token') == token:
                write(root / '.previous-version.json', previous)
                write(root / '.updates' / 'result.json', {'ok': True, 'message':
                      'Versão ' + target['version'] + ' instalada e iniciada com sucesso.'})
                pending.unlink()
                ready.unlink(missing_ok=True)
                return child
            time.sleep(0.15)
        raise RuntimeError('A nova versão não conseguiu iniciar a tempo.')
    except Exception as error:
        if child and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        write(root / '.active-version.json', previous)
        write(root / '.updates' / 'result.json', {'ok': False, 'message':
              'A atualização falhou ao iniciar. Restauramos a versão ' + previous['version'] + '.'})
        pending.unlink(missing_ok=True)
        ready.unlink(missing_ok=True)
        log.write(('\nFalha na atualização: ' + str(error) + '\n').encode('utf-8'))
        log.flush()
        return spawn(root, previous, log)


def run(root=ROOT, argv=None):
    root = Path(root).resolve()
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--activate')
    group.add_argument('--rollback', action='store_true')
    args = parser.parse_args(argv)
    lock = InstallLock(root)
    try:
        lock.acquire(timeout=45 if args.activate or args.rollback else 0)
        recover_interrupted(root)
        target = None
        if args.activate:
            plan = Path(args.activate).resolve()
            if not plan.is_relative_to(root / '.updates') or plan.name != 'plan.json':
                raise ValueError('Plano de atualização inválido.')
            target = read(plan)
        elif args.rollback:
            target = read(root / '.previous-version.json')
        # An installer stages its baseline beside existing versions. Activate it
        # through the same readiness/rollback transaction on the next launch.
        installer_plan = root / '.updates' / 'installer' / 'plan.json'
        if target is None and not args.rollback and installer_plan.exists():
            proposed = read(installer_plan)
            if proposed['app'] != current(root)['app']:
                target = proposed
            installer_plan.unlink()
        with (root / '.updates' / 'startup.log').open('ab', buffering=0) as log:
            child = activate(root, target, log) if target else spawn(root, current(root), log)
            return child.wait()
    except Exception as error:
        show_error(str(error))
        return 1
    finally:
        lock.close()


if __name__ == '__main__':
    raise SystemExit(run())
