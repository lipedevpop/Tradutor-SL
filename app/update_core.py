"""Public GitHub release updates; no access to chat logs or DeepL credentials."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid
import zipfile

APP_ID = 'tradutor-hot-sl'
PROTOCOL = 1
MAX_DOWNLOAD = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_FILES = 500
APP_DIR = Path(__file__).resolve().parent
INSTALL = Path(os.environ.get('TRADUTOR_INSTALL_DIR', str(APP_DIR.parent))).resolve()


class UpdateError(RuntimeError):
    pass


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d{1,5}\.\d{1,5}\.\d{1,5}', value):
        raise UpdateError('Versão inválida; use números como 1.0.1.')
    return tuple(map(int, value.lstrip('v').split('.')))


def repository(value):
    value = value.strip().removeprefix('https://github.com/').rstrip('/')
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', value)
            or value.split('/')[-1] in ('.', '..')):
        raise UpdateError('Informe o endereço do repositório: usuario/tradutor-hot-sl.')
    return value


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def source_config(install=INSTALL):
    for path in (Path(install) / 'update-source.json', APP_DIR / 'update-source.json'):
        if path.exists():
            data = read_json(path)
            return repository(data['repository']) if data.get('repository') else ''
    return ''


def save_source(value, install=INSTALL):
    value = repository(value)
    atomic_json(Path(install) / 'update-source.json', {'repository': value})
    return value


def https_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    if (parsed.scheme != 'https' or parsed.username or parsed.password or
            parsed.port not in (None, 443) or not (host in ('github.com', 'api.github.com') or
                                                  host.endswith('.githubusercontent.com'))):
        raise UpdateError('Endereço de atualização não autorizado.')
    return url


class ReleaseRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_url(url):
    return build_opener(ReleaseRedirects()).open(Request(https_url(url), headers={
        'User-Agent': 'Tradutor-Hot-SL-Updater/1', 'Accept': 'application/vnd.github+json'
    }), timeout=15)


def latest_release(repo, current, opener=open_url):
    repo = repository(repo)
    try:
        with opener('https://api.github.com/repos/' + repo + '/releases/latest') as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise UpdateError('Resposta de atualização muito grande.')
        release = json.loads(raw)
        if release.get('draft') or release.get('prerelease'):
            raise UpdateError('A versão publicada ainda não é estável.')
        tag = release['tag_name']
        if version(tag) <= version(current):
            return None
        assets = [a for a in release.get('assets', []) if a.get('name', '').startswith('Tradutor_Hot_SL_')
                  and a['name'].endswith('.zip')]
        if len(assets) != 1:
            raise UpdateError('Publique exatamente um pacote Tradutor_Hot_SL_*.zip na versão.')
        asset = assets[0]
        digest = asset.get('digest') or ''
        if not re.fullmatch(r'sha256:[a-fA-F0-9]{64}', digest):
            raise UpdateError('O GitHub ainda não informou a verificação do pacote. Tente depois.')
        url = asset['browser_download_url']
        if not url.casefold().startswith(('https://github.com/' + repo + '/releases/download/').casefold()):
            raise UpdateError('O pacote não pertence ao repositório configurado.')
        if not 0 < asset['size'] <= MAX_DOWNLOAD:
            raise UpdateError('Tamanho do pacote fora do limite de 64 MB.')
        return {'version': tag.lstrip('v'), 'notes': str(release.get('body') or '')[:12000],
                'url': https_url(url), 'sha256': digest[7:].lower(), 'size': asset['size']}
    except UpdateError:
        raise
    except HTTPError as error:
        if error.code == 404:
            raise UpdateError('Repositório não encontrado ou ainda sem versões públicas publicadas.') from error
        if error.code in (403, 429):
            raise UpdateError('O GitHub limitou as consultas. Aguarde um pouco e tente novamente.') from error
        raise UpdateError('O GitHub não respondeu à consulta. Tente novamente mais tarde.') from error
    except Exception as error:
        raise UpdateError('Não foi possível consultar o GitHub. Confira a internet e se o repositório e a versão são públicos.') from error


def download_release(release, destination, progress=lambda text: None, opener=open_url):
    destination = Path(destination)
    partial = destination.with_suffix('.part')
    digest, total, started = hashlib.sha256(), 0, time.monotonic()
    try:
        with opener(release['url']) as response, partial.open('wb') as output:
            while True:
                if time.monotonic() - started > 180:
                    raise UpdateError('O download demorou demais. Tente novamente.')
                block = response.read(128 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_DOWNLOAD or total > release['size']:
                    raise UpdateError('O download ultrapassou o tamanho esperado.')
                digest.update(block)
                output.write(block)
                progress(f'Baixando atualização: {min(100, total * 100 // release["size"])}%')
        if total != release['size'] or digest.hexdigest() != release['sha256']:
            raise UpdateError('O pacote está incompleto ou não passou na verificação. Nada foi instalado.')
        os.replace(partial, destination)
    except UpdateError:
        raise
    except Exception as error:
        raise UpdateError('Falha no download. A versão atual continua disponível.') from error
    finally:
        partial.unlink(missing_ok=True)


def safe_name(name):
    parts = PurePosixPath(name).parts
    if (not parts or name.startswith('/') or '\\' in name or ':' in name or
            '/'.join(parts) != name.rstrip('/') or
            any(p in ('..', '.') or p.endswith((' ', '.')) or
                p.split('.')[0].upper() in ('CON', 'PRN', 'AUX', 'NUL',
                                           *('COM' + str(n) for n in range(10)),
                                           *('LPT' + str(n) for n in range(10))) for p in parts)):
        raise UpdateError('O pacote contém um caminho inválido.')
    return parts


def validate_app(folder, expected=None):
    folder = Path(folder)
    try:
        manifest = read_json(folder / 'release-manifest.json')
        if manifest['app_id'] != APP_ID or manifest['protocol'] != PROTOCOL:
            raise UpdateError('Este pacote não é compatível com o Tradutor Hot SL.')
        version(manifest['version'])
        if expected and version(manifest['version']) != version(expected):
            raise UpdateError('A versão dentro do pacote não corresponde à publicação.')
        files = manifest['files']
        if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
            raise UpdateError('Lista de arquivos inválida.')
        for required in ('tradutor.py', 'app_identity.py', 'requirements.txt', 'update_core.py', 'update_ui.py'):
            if required not in files:
                raise UpdateError('Faltam arquivos essenciais no pacote.')
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts and p.name != 'release-manifest.json'}
        if actual != set(files):
            raise UpdateError('Os arquivos não correspondem ao manifesto da versão.')
        for name, digest in files.items():
            safe_name(name)
            if not re.fullmatch('[a-f0-9]{64}', digest) or hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
                raise UpdateError('Um arquivo do pacote não passou na verificação.')
        return manifest
    except UpdateError:
        raise
    except Exception as error:
        raise UpdateError('Pacote inválido ou incompleto.') from error


def extract_release(archive, destination, expected):
    destination = Path(destination)
    if destination.exists():
        raise UpdateError('A pasta de preparação já existe.')
    destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            if len(entries) > MAX_FILES + 30 or sum(e.file_size for e in entries) > MAX_EXPANDED:
                raise UpdateError('Pacote excede os limites de extração.')
            seen = set()
            for entry in entries:
                safe_name(entry.filename)
                if stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                    raise UpdateError('Links e arquivos criptografados não são aceitos.')
                key = entry.filename.casefold().rstrip('/')
                if key in seen:
                    raise UpdateError('O pacote tem caminhos duplicados.')
                seen.add(key)
            manifests = [e for e in entries if e.filename.endswith('/app/release-manifest.json')]
            if len(manifests) != 1:
                raise UpdateError('O pacote não tem um manifesto de aplicativo único.')
            prefix = manifests[0].filename[:-len('release-manifest.json')]
            for entry in entries:
                if entry.filename.startswith(prefix) and not entry.is_dir():
                    relative = entry.filename[len(prefix):]
                    safe_name(relative)
                    if relative.split('/')[0].startswith('.') or '__pycache__' in relative:
                        raise UpdateError('O pacote contém arquivos de instalação indevidos.')
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(entry) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
        return validate_app(destination, expected)
    except Exception:
        shutil.rmtree(destination)
        raise


def prepare_release(release, progress=lambda text: None, install=INSTALL, app_dir=APP_DIR):
    install, app_dir = Path(install).resolve(), Path(app_dir).resolve()
    jobs = install / '.updates'
    jobs.mkdir(exist_ok=True)
    job = Path(tempfile.mkdtemp(prefix='job-', dir=jobs))
    staged = install / 'versions' / (release['version'] + '-' + uuid.uuid4().hex[:10])
    try:
        download_release(release, job / 'release.zip', progress)
        progress('Verificando arquivos da atualização…')
        extract_release(job / 'release.zip', staged, release['version'])
        runtime = Path(sys.executable).resolve()
        # A changed requirements file gets its own environment. Never modify the
        # running or previous environment, so rollback restores code AND libraries.
        if (staged / 'requirements.txt').read_bytes() != (app_dir / 'requirements.txt').read_bytes():
            progress('Preparando os componentes da nova versão…')
            environment = install / 'runtimes' / ('runtime-' + uuid.uuid4().hex[:10])
            environment.parent.mkdir(exist_ok=True)
            hidden = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
            with (job / 'components.log').open('w', encoding='utf-8') as log:
                subprocess.run([sys._base_executable, '-m', 'venv', str(environment)],
                               check=True, timeout=120, stdout=log, stderr=log, **hidden)
                runtime = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                subprocess.run([str(runtime), '-m', 'pip', 'install', '--disable-pip-version-check',
                                '-r', str(staged / 'requirements.txt')], check=True, timeout=600,
                               stdout=log, stderr=log, **hidden)
        progress('Conferindo os componentes instalados…')
        hidden = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        subprocess.run([str(runtime), '-c',
                        'import tkinter, PIL, numpy, langid; from language_filter import EnglishFilter; EnglishFilter()'],
                       cwd=staged, check=True, timeout=90, capture_output=True, **hidden)
        # Only relative paths inside this installation can be handed to bootstrap.
        runtime_relative = runtime.relative_to(install).as_posix()
        plan = {'app': staged.relative_to(install).as_posix(), 'python': runtime_relative,
                'version': release['version'], 'notes': release['notes']}
        atomic_json(job / 'plan.json', plan)
        (job / 'release.zip').unlink(missing_ok=True)
        return job / 'plan.json'
    except Exception as error:
        if staged.exists():
            shutil.rmtree(staged)
        if isinstance(error, UpdateError):
            raise
        raise UpdateError('Não foi possível preparar a atualização. O tradutor atual não foi alterado. Detalhes em ' + str(job)) from error


def launch_change(plan=None, rollback=False, install=INSTALL):
    install = Path(install).resolve()
    args = [str(install / 'iniciar.py')]
    if rollback:
        args.append('--rollback')
    elif plan:
        args.extend(['--activate', str(plan)])
    else:
        raise UpdateError('Atualização não preparada.')
    interpreter = Path(sys._base_executable)
    if os.name == 'nt' and interpreter.with_name('pythonw.exe').exists():
        interpreter = interpreter.with_name('pythonw.exe')
    hidden = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    return subprocess.Popen([str(interpreter), *args], cwd=install, **hidden)
