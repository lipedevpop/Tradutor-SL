import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv
import zipfile

PROJECT = Path(__file__).resolve().parents[1]
if not (PROJECT / 'app').is_dir():
    PROJECT = PROJECT / 'tradutor-hot-sl'
sys.path.insert(0, str(PROJECT / 'app'))
import update_core as core


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = load('bootstrap', PROJECT / 'iniciar.py')
builder = load('builder', PROJECT / 'tools' / 'build_release.py')


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def release(self, tag='v1.0.1', **asset_changes):
        asset = {'name': 'Tradutor_Hot_SL_v1_0_1_Atualizacoes.zip', 'size': 100,
                 'digest': 'sha256:' + 'a' * 64,
                 'browser_download_url': 'https://github.com/owner/tradutor/releases/download/v1.0.1/app.zip'}
        asset.update(asset_changes)
        return {'tag_name': tag, 'body': 'Correção', 'assets': [asset]}

    def metadata(self, data, current='1.0.0'):
        return core.latest_release('owner/tradutor', current,
                                   opener=lambda url: io.BytesIO(json.dumps(data).encode()))

    def package(self):
        return builder.build('1.0.1', self.root, 'owner/tradutor')

    def extract(self):
        destination = self.root / 'staged'
        core.extract_release(self.package(), destination, '1.0.1')
        return destination

    def test_numeric_version_and_no_downgrade(self):
        self.assertGreater(core.version('1.0.10'), core.version('1.0.9'))
        self.assertIsNone(self.metadata(self.release(tag='v1.0.0')))
        self.assertIsNone(self.metadata(self.release(tag='v0.9.6')))
        self.assertEqual(self.metadata(self.release())['version'], '1.0.1')

    def test_reject_invalid_version_and_repository(self):
        for value in ('1.2', '1.0.1-beta', '1.0.1/../../a'):
            with self.assertRaises(core.UpdateError):
                core.version(value)
        for value in ('owner/repo/other', 'https://example.com/x', 'owner/repo?token=secret', 'owner/..'):
            with self.assertRaises(core.UpdateError):
                core.repository(value)
        self.assertEqual(core.repository('https://github.com/owner/repo/'), 'owner/repo')

    def test_require_trusted_asset_digest_and_size(self):
        for changed in ({'digest': None}, {'size': core.MAX_DOWNLOAD + 1},
                        {'browser_download_url': 'https://example.com/app.zip'},
                        {'browser_download_url': 'https://github.com/other/repo/releases/download/v1/app.zip'}):
            with self.assertRaises(core.UpdateError):
                self.metadata(self.release(**changed))
        with self.assertRaises(core.UpdateError):
            self.metadata(dict(self.release(), prerelease=True))

    def test_reject_ambiguous_release(self):
        data = self.release()
        data['assets'] *= 2
        with self.assertRaises(core.UpdateError):
            self.metadata(data)

    def test_offline_error_has_no_credentials(self):
        with self.assertRaises(core.UpdateError) as caught:
            core.latest_release('owner/repo', '1.0.0', opener=lambda url: (_ for _ in ()).throw(OSError('offline')))
        self.assertIn('internet', str(caught.exception))

    def test_redirects_only_https_github_hosts(self):
        for url in ('http://github.com/x', 'https://github.com.evil.test/x',
                    'https://user:pass@github.com/x', 'https://github.com:8443/x'):
            with self.assertRaises(core.UpdateError):
                core.https_url(url)
        core.https_url('https://release-assets.githubusercontent.com/file')

    def test_repository_case_is_insensitive(self):
        data = self.release(browser_download_url='https://github.com/Owner/Tradutor/releases/download/v1.0.1/app.zip')
        self.assertEqual(self.metadata(data)['version'], '1.0.1')

    def test_new_check_discards_previously_prepared_release(self):
        from update_ui import Updates
        from unittest.mock import Mock
        ui = Updates.__new__(Updates)
        ui.busy, ui.repo = False, 'owner/repo'
        ui.release, ui.plan = {'version': '1.0.1'}, Path('old-plan.json')
        ui.status, ui.task = Mock(), Mock()
        ui.check()
        self.assertIsNone(ui.plan)
        self.assertIsNone(ui.release)

    def test_download_integrity_and_partial_cleanup(self):
        data = b'release bytes'
        release = {'url': 'https://github.com/o/r/a', 'size': len(data),
                   'sha256': hashlib.sha256(data).hexdigest()}
        path = self.root / 'release.zip'
        core.download_release(release, path, opener=lambda url: io.BytesIO(data))
        self.assertEqual(path.read_bytes(), data)
        for body in (b'short', b'other bytes!!', data + b'extra'):
            path.unlink(missing_ok=True)
            with self.assertRaises(core.UpdateError):
                core.download_release(release, path, opener=lambda url: io.BytesIO(body))
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix('.part').exists())

    def test_clean_full_package_extracts_with_version(self):
        staged = self.extract()
        manifest = core.validate_app(staged, '1.0.1')
        self.assertEqual(manifest['version'], '1.0.1')
        self.assertIn("APP_VERSION = '1.0.1'", (staged / 'app_identity.py').read_text())
        self.assertFalse((staged / 'iniciar.py').exists())
        self.assertFalse(any('.venv' in p.parts for p in staged.rglob('*')))

    def test_builder_preserves_configured_repository_by_default(self):
        package = builder.build('1.0.2', self.root)
        with zipfile.ZipFile(package) as archive:
            config = json.loads(archive.read('Tradutor_Hot_SL_v1_0_2/app/update-source.json'))
        self.assertEqual(config['repository'], core.read_json(PROJECT / 'app' / 'update-source.json')['repository'])

    def test_modified_or_extra_or_missing_file_rejected(self):
        staged = self.extract()
        original = (staged / 'tradutor.py').read_bytes()
        (staged / 'tradutor.py').write_bytes(original + b'\n# altered')
        with self.assertRaises(core.UpdateError):
            core.validate_app(staged)
        (staged / 'tradutor.py').write_bytes(original)
        (staged / 'unexpected.py').write_text('pass')
        with self.assertRaises(core.UpdateError):
            core.validate_app(staged)
        (staged / 'unexpected.py').unlink()
        (staged / 'tradutor.py').unlink()
        with self.assertRaises(core.UpdateError):
            core.validate_app(staged)

    def test_wrong_version_or_app_rejected(self):
        staged = self.extract()
        with self.assertRaises(core.UpdateError):
            core.validate_app(staged, '9.0.0')
        path = staged / 'release-manifest.json'
        data = json.loads(path.read_text())
        data['app_id'] = 'different-program'
        path.write_text(json.dumps(data))
        with self.assertRaises(core.UpdateError):
            core.validate_app(staged)

    def test_zip_path_traversal_and_symlink_rejected(self):
        for i, name in enumerate(('../escape.py', 'C:/escape.py', 'a\\escape.py', 'p/app/CON.txt', '/absolute.py', 'p/app/./file.py', 'p/app//file.py')):
            path = self.root / ('bad' + str(i) + '.zip')
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(name, b'x')
            destination = self.root / ('stage' + str(i))
            with self.assertRaises(core.UpdateError):
                core.extract_release(path, destination, '1.0.1')
            self.assertFalse(destination.exists())
        path = self.root / 'symlink.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            info = zipfile.ZipInfo('p/app/link.py')
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '../../elsewhere')
        with self.assertRaises(core.UpdateError):
            core.extract_release(path, self.root / 'symlink-stage', '1.0.1')

    def test_zip_size_and_duplicate_paths_rejected(self):
        path = self.package()
        with patch.object(core, 'MAX_EXPANDED', 1):
            with self.assertRaises(core.UpdateError):
                core.extract_release(path, self.root / 'big', '1.0.1')
        path = self.root / 'duplicate.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('p/app/file.py', 'one')
            archive.writestr('p/app/FILE.py', 'two')
        with self.assertRaises(core.UpdateError):
            core.extract_release(path, self.root / 'duplicate', '1.0.1')

    def test_save_source_does_not_overwrite_personal_files(self):
        (self.root / 'settings.json').write_bytes(b'personal settings')
        core.save_source('owner/repo', self.root)
        self.assertEqual(core.source_config(self.root), 'owner/repo')
        self.assertEqual((self.root / 'settings.json').read_bytes(), b'personal settings')

    def test_prepare_preserves_existing_runtime_and_data(self):
        staged_original = self.extract()
        install = self.root / 'install'
        install.mkdir()
        runtime = install / '.venv' / 'Scripts' / 'python.exe'
        runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b'existing environment')
        (install / 'settings.json').write_bytes(b'keep me')
        package = self.package()
        release = {'version': '1.0.1', 'notes': 'fix'}
        def fake_download(release, destination, progress):
            shutil.copyfile(package, destination)
        with patch.object(core, 'download_release', side_effect=fake_download), \
             patch.object(core.sys, 'executable', str(runtime)), patch.object(core.subprocess, 'run') as run:
            plan = core.prepare_release(release, install=install, app_dir=staged_original)
        self.assertEqual(run.call_count, 1)  # probe only; no pip change
        self.assertEqual(json.loads(plan.read_text())['python'], '.venv/Scripts/python.exe')
        self.assertEqual(runtime.read_bytes(), b'existing environment')
        self.assertEqual((install / 'settings.json').read_bytes(), b'keep me')
        self.assertFalse((install / '.active-version.json').exists())

    def test_changed_dependencies_get_separate_runtime(self):
        old = self.extract()
        (old / 'requirements.txt').write_text('different dependencies')
        install = self.root / 'install'
        install.mkdir()
        runtime = install / '.venv' / 'Scripts' / 'python.exe'
        runtime.parent.mkdir(parents=True)
        runtime.write_bytes(b'old runtime')
        package = self.package()
        with patch.object(core, 'download_release', side_effect=lambda release, dest, progress: shutil.copyfile(package, dest)), \
             patch.object(core.sys, 'executable', str(runtime)), patch.object(core.subprocess, 'run') as run:
            plan = core.prepare_release({'version': '1.0.1', 'notes': ''}, install=install, app_dir=old)
        self.assertEqual(run.call_count, 3)  # venv, pip, component probe
        self.assertTrue(json.loads(plan.read_text())['python'].startswith('runtimes/'))
        self.assertEqual(runtime.read_bytes(), b'old runtime')


class BootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        cls.root = Path(cls.temp.name)
        venv.EnvBuilder(with_pip=False).create(cls.root / '.venv')
        (cls.root / '.updates').mkdir()
        cls.python = '.venv/Scripts/python.exe' if os.name == 'nt' else '.venv/bin/python'

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def fake_app(self, number, code=None):
        app = self.root / 'versions' / number
        app.mkdir(parents=True, exist_ok=True)
        if code is None:
            code = ("import os,json,time\nfrom pathlib import Path\n"
                    "if os.environ.get('TRADUTOR_UPDATE_READY'):\n"
                    " Path(os.environ['TRADUTOR_UPDATE_READY']).write_text(json.dumps({'token':os.environ['TRADUTOR_UPDATE_TOKEN']}))\n"
                    "time.sleep(0.5)\n")
        files = {'tradutor.py': code.encode(), 'update_core.py': b'', 'update_ui.py': b''}
        for name, data in files.items():
            (app / name).write_bytes(data)
        manifest = {'app_id': 'tradutor-hot-sl', 'protocol': 1, 'version': number,
                    'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        bootstrap.write(app / 'release-manifest.json', manifest)
        return {'app': 'versions/' + number, 'python': self.python, 'version': number}

    def setUp(self):
        self.old = self.fake_app('1.0.0')
        bootstrap.write(self.root / '.active-version.json', self.old)
        for name in ('.pending-update.json', '.previous-version.json'):
            (self.root / name).unlink(missing_ok=True)

    def activate(self, target, timeout=3):
        with (self.root / '.updates' / 'test.log').open('ab', buffering=0) as log:
            process = bootstrap.activate(self.root, target, log, health_timeout=timeout)
            self.assertEqual(process.wait(timeout=5), 0)

    def test_actual_process_success_and_manual_rollback(self):
        new = self.fake_app('1.0.1')
        self.activate(new)
        self.assertEqual(bootstrap.current(self.root)['version'], '1.0.1')
        self.assertEqual(bootstrap.read(self.root / '.previous-version.json')['version'], '1.0.0')
        self.assertFalse((self.root / '.pending-update.json').exists())
        self.activate(self.old)
        self.assertEqual(bootstrap.current(self.root)['version'], '1.0.0')
        self.assertEqual(bootstrap.read(self.root / '.previous-version.json')['version'], '1.0.1')

    def test_failed_child_restores_and_reopens_previous(self):
        new = self.fake_app('1.0.2', 'raise SystemExit(42)\n')
        self.activate(new)
        self.assertEqual(bootstrap.current(self.root), self.old)
        self.assertFalse(bootstrap.read(self.root / '.updates' / 'result.json')['ok'])

    def test_timeout_terminates_child_and_restores(self):
        new = self.fake_app('1.0.3', 'import time\ntime.sleep(30)\n')
        self.activate(new, timeout=0.2)
        self.assertEqual(bootstrap.current(self.root), self.old)

    def test_interrupted_transaction_restored_next_launch(self):
        new = self.fake_app('1.0.4')
        bootstrap.write(self.root / '.pending-update.json', {'previous': self.old, 'target': new})
        bootstrap.write(self.root / '.active-version.json', new)
        bootstrap.recover_interrupted(self.root)
        self.assertEqual(bootstrap.current(self.root), self.old)
        self.assertFalse((self.root / '.pending-update.json').exists())

    def test_invalid_install_paths_and_modified_code_rejected(self):
        for relative in ('../outside', 'C:/Windows/python.exe', '/absolute'):
            with self.assertRaises(ValueError):
                bootstrap.inside(self.root, relative)
        (self.root / self.old['app'] / 'tradutor.py').write_text('tampered')
        with self.assertRaises(ValueError):
            bootstrap.validate(self.root, self.old)

    def test_process_lock_blocks_second_launch(self):
        first, second = bootstrap.InstallLock(self.root), bootstrap.InstallLock(self.root)
        try:
            first.acquire()
            with self.assertRaises(RuntimeError):
                second.acquire()
        finally:
            first.close()
            second.close()
        second.acquire()
        second.close()

    def test_installed_baseline_is_used_without_a_virtual_environment(self):
        bootstrap.write(self.root / '.install-version.json', self.old)
        try:
            self.assertEqual(bootstrap.default_pointer(self.root), self.old)
        finally:
            (self.root / '.install-version.json').unlink()

    def test_new_installer_activates_through_readiness_transaction(self):
        new = self.fake_app('1.0.8')
        plan = self.root / '.updates/installer/plan.json'
        plan.parent.mkdir(exist_ok=True)
        bootstrap.write(plan, new)
        self.assertEqual(bootstrap.run(self.root, []), 0)
        self.assertEqual(bootstrap.current(self.root), new)
        self.assertEqual(bootstrap.read(self.root / '.previous-version.json'), self.old)
        self.assertFalse(plan.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
