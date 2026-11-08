"""Build an offline, per-user Windows installer with the OS C# compiler.

Only selected Python/dependency files are copied. No user configuration,
credentials, browser data or chat logs are read by this build.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
CSC = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


def copy_tree(source, destination, *, skip=()):
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', *skip))


def runtime(base, dependency_sites, destination):
    destination.mkdir(parents=True)
    for name in ('python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll',
                 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt'):
        shutil.copy2(base / name, destination / name)
    for name in ('DLLs', 'tcl'):
        copy_tree(base / name, destination / name)
    copy_tree(base / 'Lib', destination / 'Lib', skip=('site-packages', 'test', 'tests', 'idlelib', 'turtledemo'))
    site = destination / 'Lib/site-packages'
    site.mkdir()
    patterns = ('langid', 'langid-*.dist-info', 'numpy', 'numpy.libs', 'numpy-*.dist-info',
                'PIL', 'pillow.libs', 'pillow-*.dist-info')
    selected = {}
    for pattern in patterns:
        for directory in dependency_sites:
            matches = list(directory.glob(pattern))
            if matches:
                for source in matches:
                    if source.name not in selected:
                        selected[source.name] = source
                break
    for name in ('langid', 'numpy', 'PIL'):
        if name not in selected:
            raise RuntimeError('Dependência não encontrada: ' + name)
    for name, source in selected.items():
        copy_tree(source, site / name, skip=('tests', 'test', 'direct_url.json', 'REQUESTED'))
    licenses = {}
    for name in selected:
        if name.endswith('.dist-info'):
            metadata = site / name / 'METADATA'
            text = metadata.read_text(encoding='utf-8')
            package = re.search(r'^Name: (.+)$', text, re.M).group(1)
            version = re.search(r'^Version: (.+)$', text, re.M).group(1)
            licenses[package] = version
    (destination / 'COMPONENTES.json').write_text(json.dumps(licenses, indent=2), encoding='utf-8')
    return licenses


def compile_exe(source, output, icon, *, setup=False, payload=None, version='1.1.0'):
    build_info = output.parent / ('BuildInfo-setup.cs' if setup else 'BuildInfo-launcher.cs')
    digest = hashlib.sha256(payload.read_bytes()).hexdigest() if payload else ''
    build_info.write_text('using System.Reflection;\n[assembly: AssemblyTitle("Tradutor SL")]\n'
                          '[assembly: AssemblyProduct("Tradutor SL")]\n[assembly: AssemblyCompany("lipedevpop")]\n'
                          '[assembly: AssemblyVersion("' + version + '.0")]\n'
                          'internal static class BuildInfo {internal const string Version="' + version +
                          '"; internal const string PayloadHash="' + digest + '";}\n', encoding='utf-8')
    args = [str(CSC), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/codepage:65001',
            '/out:' + str(output), '/win32icon:' + str(icon), '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
            '/resource:' + str(PROJECT / 'app/assets/tradutor-sl.png') + ',branding.png',
            '/win32manifest:' + str(PROJECT / 'installer/app.manifest'),
            '/r:System.Web.Extensions.dll', '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll']
    if setup:
        args += ['/define:SETUP', '/resource:' + str(payload) + ',payload.zip']
    args += [str(source), str(build_info)]
    subprocess.run(args, check=True)
    build_info.unlink()


def build(version, build_dir, output, base, dependency_sites):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Versão inválida.')
    if build_dir.exists():
        raise ValueError('Use uma pasta nova para cada compilação.')
    build_dir.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('release_builder', PROJECT / 'tools/build_release.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    update_zip = builder.build(version, output)
    stage = build_dir / 'payload'
    stage.mkdir()
    app_relative = 'versions/' + version + '-installed'
    python_relative = 'runtimes/bundled-' + version + '/pythonw.exe'
    app_dir = stage / app_relative
    app_dir.mkdir(parents=True)
    with zipfile.ZipFile(update_zip) as package:
        prefix = next(n for n in package.namelist() if n.endswith('/app/release-manifest.json'))[:-len('release-manifest.json')]
        for name in package.namelist():
            if name.startswith(prefix):
                destination = app_dir / name[len(prefix):]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(package.read(name))
    components = runtime(base, dependency_sites, stage / ('runtimes/bundled-' + version))
    pointer = {'app': app_relative, 'python': python_relative, 'version': version}
    (stage / '.install-version.json').write_text(json.dumps(pointer, indent=2), encoding='utf-8')
    (stage / 'bootstrap-runtime.txt').write_text(python_relative, encoding='ascii')
    shutil.copy2(PROJECT / 'iniciar.py', stage / 'iniciar.py')
    shutil.copy2(PROJECT / 'installer/verificar_instalacao.py', stage / 'verificar_instalacao.py')
    guide = (PROJECT / 'installer/LEIA_AQUI.txt').read_text(encoding='utf-8').replace('Tradutor_SL_Setup_1.1.0.exe', 'Tradutor_SL_Setup_' + version + '.exe')
    (stage / 'LEIA_AQUI.txt').write_text(guide, encoding='utf-8')
    icon = PROJECT / 'app/assets/tradutor-sl.ico'
    compile_exe(PROJECT / 'installer/WindowsApp.cs', stage / 'Tradutor SL.exe', icon, version=version)
    probe = subprocess.run([str(stage / python_relative.replace('pythonw.exe', 'python.exe')), '-E', '-s',
                            str(stage / 'verificar_instalacao.py')], cwd=stage, capture_output=True, text=True, timeout=90)
    if probe.returncode:
        raise RuntimeError('Falha ao testar os componentes: ' + probe.stderr)
    actual = json.loads(probe.stdout)
    if actual['pillow'] != '13.0.0' or actual['numpy'] != '2.3.5':
        raise RuntimeError('As versões dos componentes não correspondem ao pacote: ' + str(actual))
    files = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in stage.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    # Remove caches created by the offline probe before embedding the payload.
    for directory in list(stage.rglob('__pycache__')):
        if directory.exists():
            shutil.rmtree(directory)
    (stage / 'payload-manifest.json').write_text(json.dumps({'Id': 'lipedevpop.TradutorSL', 'Version': version,
                                                          'Files': files}, indent=2), encoding='utf-8')
    payload = build_dir / 'payload.zip'
    with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(stage).as_posix())
    installer = output / ('Tradutor_SL_Setup_' + version + '.exe')
    compile_exe(PROJECT / 'installer/WindowsApp.cs', installer, icon, setup=True, payload=payload, version=version)
    distribution = output / ('Tradutor_SL_v' + version.replace('.', '_') + '_Instalacao.zip')
    with zipfile.ZipFile(distribution, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(installer, installer.name)
        archive.write(stage / 'LEIA_AQUI.txt', 'LEIA_AQUI.txt')
    for path in (installer, distribution):
        path.with_suffix(path.suffix + '.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n', encoding='ascii')
    report = {'version': version, 'components': components, 'probe': actual, 'files': len(files),
              'payload_bytes': payload.stat().st_size, 'installer_bytes': installer.stat().st_size,
              'standalone': True, 'signed': False}
    (build_dir / 'build-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-python', type=Path, required=True)
    parser.add_argument('--dependency-sites', type=Path, nargs='+', required=True)
    args = parser.parse_args()
    build(args.version, args.build_dir.resolve(), args.output.resolve(), args.base_python.resolve(),
          [p.resolve() for p in args.dependency_sites])
