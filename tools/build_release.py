"""Build a clean full-install ZIP also consumable by the in-app updater."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

PROJECT = Path(__file__).resolve().parents[1]


def build(version, output, repo=None, project=PROJECT):
    if not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}', version):
        raise ValueError('Use uma versão como 1.0.1.')
    project, output = Path(project), Path(output)
    if repo is None:
        repo = json.loads((project / 'app' / 'update-source.json').read_text(encoding='utf-8')).get('repository', '')
    if repo and (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}', repo)
                 or repo.split('/')[-1] in ('.', '..')):
        raise ValueError('Repositório inválido; use usuario/repositorio.')
    output.mkdir(parents=True, exist_ok=True)
    root_name = 'Tradutor_Hot_SL_v' + version.replace('.', '_')
    files = {}
    for path in (project / 'app').rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc' or path.name == 'release-manifest.json':
            continue
        relative = path.relative_to(project / 'app').as_posix()
        if path.suffix.lower() not in ('.py', '.txt', '.json', '.png', '.ico') or any(p.startswith('.') for p in Path(relative).parts):
            raise ValueError('Arquivo não permitido no aplicativo: ' + relative)
        files[relative] = path.read_bytes()
    identity = files['app_identity.py'].decode('utf-8')
    identity, count = re.subn(r"APP_VERSION = '[^']+'", "APP_VERSION = '" + version + "'", identity)
    if count != 1:
        raise ValueError('Não foi possível definir a versão.')
    files['app_identity.py'] = identity.encode('utf-8')
    files['update-source.json'] = json.dumps({'repository': repo}, indent=2).encode('utf-8')
    manifest = {'app_id': 'tradutor-hot-sl', 'protocol': 1, 'version': version,
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['release-manifest.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    destination = output / (root_name + '_Atualizacoes.zip')
    with tempfile.NamedTemporaryFile(dir=output, delete=False, suffix='.tmp') as temporary:
        temp = Path(temporary.name)
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(root_name + '/app/' + name, data)
            for name in ('iniciar.py', '1_INSTALAR.bat', '2_ABRIR_TRADUTOR.bat', '3_DIAGNOSTICO.bat',
                         '4_TESTAR_FILTRO.bat', '5_RESTAURAR_ANTERIOR.bat', 'LEIA_PRIMEIRO.txt', 'PUBLICAR_ATUALIZACOES.md'):
                data = (project / name).read_bytes()
                if name == '1_INSTALAR.bat':
                    data = data.replace(b'1.0.0 com Atualizacoes', version.encode() + b' com Atualizacoes')
                archive.writestr(root_name + '/' + name, data)
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.sha256').write_text(digest + '  ' + destination.name + '\n', encoding='ascii')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--repository', default=None)
    parser.add_argument('--output', type=Path, default=PROJECT.parent.parent / 'outputs')
    args = parser.parse_args()
    print(build(args.version, args.output, args.repository))
