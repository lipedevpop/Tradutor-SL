"""Prepare a new local app version and its release notes; never publishes by itself."""
import argparse
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def app_version(root=ROOT):
    tree = ast.parse((Path(root) / 'app/app_identity.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and re.fullmatch(r'\d+\.\d+\.\d+', value):
                return value
    raise ValueError('APP_VERSION inválida.')


def prepare(notes, new_version=None, root=ROOT):
    root = Path(root)
    current = app_version(root)
    parts = tuple(map(int, current.split('.')))
    new_version = new_version or '.'.join(map(str, (*parts[:2], parts[2] + 1)))
    if not re.fullmatch(r'\d+\.\d+\.\d+', new_version) or tuple(map(int, new_version.split('.'))) <= parts:
        raise ValueError('A nova versão precisa ser maior que ' + current + '.')
    if not notes.strip():
        raise ValueError('Descreva as correções antes de preparar a versão.')
    destination = root / 'release-notes' / (new_version + '.md')
    if destination.exists():
        raise ValueError('Já existem notas para essa versão. Confira antes de substituir.')
    path = root / 'app/app_identity.py'
    source, count = re.subn(r"APP_VERSION = ['\"][^'\"]+['\"]", "APP_VERSION = '" + new_version + "'", path.read_text(encoding='utf-8'))
    if count != 1:
        raise ValueError('Não foi possível definir APP_VERSION.')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(notes.strip() + '\n', encoding='utf-8')
    path.write_text(source, encoding='utf-8')
    return new_version


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version')
    parser.add_argument('--notes-file', type=Path, required=True)
    args = parser.parse_args()
    print('Versão local preparada:', prepare(args.notes_file.read_text(encoding='utf-8'), args.version))
