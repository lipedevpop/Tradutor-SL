"""GitHub Actions release gate, asset checks and draft-first publishing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from prepare_release import ROOT, app_version


def api(repo, tag, token=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Tradutor-SL-CI'}
    token = token or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with urlopen(Request('https://api.github.com/repos/' + repo + '/releases/tags/' + tag, headers=headers), timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            # A draft whose tag has not been created yet is absent from the
            # by-tag endpoint. Authenticated release listing still includes it.
            with urlopen(Request('https://api.github.com/repos/' + repo + '/releases?per_page=100', headers=headers), timeout=30) as response:
                return next((release for release in json.load(response) if release.get('tag_name') == tag), None)
        raise RuntimeError('O GitHub recusou a consulta da release: HTTP ' + str(error.code)) from None


def gate(repo, root=ROOT, lookup=api):
    version = app_version(root)
    notes = Path(root) / 'release-notes' / (version + '.md')
    if not notes.exists() or not notes.read_text(encoding='utf-8').strip():
        raise ValueError('Faltam as notas de correção para a versão ' + version)
    existing = lookup(repo, 'v' + version)
    return version, existing is None or bool(existing.get('draft'))


def assets(dist, version):
    root = Path(dist)
    suffix = version.replace('.', '_')
    names = ['Tradutor_SL_Setup_' + version + '.exe',
             'Tradutor_Hot_SL_v' + suffix + '_Atualizacoes.zip',
             'Tradutor_SL_v' + suffix + '_Instalacao.zip']
    result = {}
    for name in names:
        file = root / name
        if not file.is_file() or not file.stat().st_size:
            raise ValueError('Artefato ausente ou vazio: ' + name)
        result[name] = {'size': file.stat().st_size, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    return result


def verify_release(release, expected):
    uploaded = {a['name']: a for a in release.get('assets', [])}
    for name, data in expected.items():
        asset = uploaded.get(name, {})
        if (asset.get('state') != 'uploaded' or asset.get('size') != data['size'] or
                asset.get('digest') != 'sha256:' + data['sha256']):
            raise ValueError('Arquivo publicado não corresponde ao pacote gerado: ' + name)


def publish(repo, commit, dist, root=ROOT, lookup=api, execute=subprocess.run):
    version = app_version(root)
    tag = 'v' + version
    existing = lookup(repo, tag)
    if existing is not None and not existing.get('draft'):
        raise ValueError('A versão já existe; não será substituída.')
    expected = assets(dist, version)
    notes = Path(root) / 'release-notes' / (version + '.md')
    if not notes.is_file() or not notes.read_text(encoding='utf-8').strip():
        raise ValueError('Notas de correção ausentes.')
    if existing is None:
        command = ['gh', 'release', 'create', tag, '--repo', repo, '--target', commit,
                   '--draft', '--title', 'Tradutor SL ' + version, '--notes-file', str(notes)]
        command.extend(str(Path(dist) / name) for name in expected)
        execute(command, check=True)
    else:
        # Resume only an unpublished draft left by an interrupted run. A
        # published release is rejected above and is never clobbered.
        execute(['gh', 'release', 'edit', tag, '--repo', repo, '--target', commit,
                 '--draft', '--title', 'Tradutor SL ' + version, '--notes-file', str(notes)], check=True)
        execute(['gh', 'release', 'upload', tag, '--repo', repo, '--clobber',
                 *(str(Path(dist) / name) for name in expected)], check=True)
    last_error = None
    for _ in range(10):
        try:
            release = lookup(repo, tag)
            if release is None or not release.get('draft'):
                raise ValueError('O rascunho não foi encontrado.')
            verify_release(release, expected)
            break
        except ValueError as error:
            last_error = error
            time.sleep(2)
    else:
        raise last_error
    execute(['gh', 'release', 'edit', tag, '--repo', repo, '--draft=false', '--latest'], check=True)
    release = lookup(repo, tag)
    if release is None or release.get('draft') or release.get('prerelease'):
        raise ValueError('A publicação final não foi confirmada.')
    verify_release(release, expected)
    return release['html_url']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['gate', 'plan', 'publish'])
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    repo = os.environ.get('GITHUB_REPOSITORY', 'lipedevpop/Tradutor-SL')
    if args.action == 'gate':
        version, new = gate(repo)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
                output.write('version=' + version + '\npublish=' + str(new).lower() + '\n')
        print('Versão:', version, '|', 'nova publicação' if new else 'já publicada; mantendo arquivos existentes')
    elif args.action == 'plan':
        version = app_version()
        (args.dist / 'release-plan.json').write_text(json.dumps({'version': version, 'files': assets(args.dist, version)}, indent=2), encoding='utf-8')
    else:
        version = app_version()
        plan = json.loads((args.dist / 'release-plan.json').read_text(encoding='utf-8'))
        if plan != {'version': version, 'files': assets(args.dist, version)}:
            raise ValueError('Os artefatos não correspondem ao plano da compilação.')
        url = publish(repo, os.environ['GITHUB_SHA'], args.dist)
        print('Publicação confirmada:', url)
