import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_release as ci
import prepare_release as prepare


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.root = Path(self.temp.name)
        (self.root / 'app').mkdir()
        (self.root / 'release-notes').mkdir()
        (self.root / 'app/app_identity.py').write_text("APP_VERSION = '1.1.0'\n", encoding='utf-8')
        (self.root / 'release-notes/1.1.0.md').write_text('Correção testada.', encoding='utf-8')
        self.dist = self.root / 'dist'
        self.dist.mkdir()
        for name in ('Tradutor_SL_Setup_1.1.0.exe', 'Tradutor_Hot_SL_v1_1_0_Atualizacoes.zip', 'Tradutor_SL_v1_1_0_Instalacao.zip'):
            (self.dist / name).write_bytes(('test fixture: ' + name).encode())

    def tearDown(self):
        self.temp.cleanup()

    def release(self, draft=True):
        return {'draft': draft, 'prerelease': False,
                'html_url': 'https://github.com/owner/repo/releases/tag/v1.1.0',
                'assets': [{'name': name, 'state': 'uploaded', 'size': data['size'],
                            'digest': 'sha256:' + data['sha256']} for name, data in ci.assets(self.dist, '1.1.0').items()]}

    def test_prepare_increments_patch_and_records_notes(self):
        self.assertEqual(prepare.prepare('Corrigido o filtro.', root=self.root), '1.1.1')
        self.assertEqual(prepare.app_version(self.root), '1.1.1')
        self.assertIn('Corrigido', (self.root / 'release-notes/1.1.1.md').read_text(encoding='utf-8'))

    def test_prepare_rejects_reused_version_and_empty_notes(self):
        for notes, version in (('fix', '1.1.0'), ('fix', '1.0.0'), ('', '1.1.1'), ('fix', '../bad')):
            with self.assertRaises(ValueError):
                prepare.prepare(notes, version, self.root)
        self.assertEqual(prepare.app_version(self.root), '1.1.0')

    def test_gate_requires_notes_and_does_not_replace_published_versions(self):
        self.assertEqual(ci.gate('owner/repo', self.root, lookup=lambda repo, tag: None), ('1.1.0', True))
        self.assertEqual(ci.gate('owner/repo', self.root, lookup=lambda repo, tag: self.release(False)), ('1.1.0', False))
        with self.assertRaises(ValueError):
            ci.gate('owner/repo', self.root, lookup=lambda repo, tag: self.release(True))
        (self.root / 'release-notes/1.1.0.md').unlink()
        with self.assertRaises(ValueError):
            ci.gate('owner/repo', self.root, lookup=lambda repo, tag: None)

    def test_verify_all_asset_digests_and_sizes(self):
        expected = ci.assets(self.dist, '1.1.0')
        ci.verify_release(self.release(), expected)
        for key, value in (('size', 1), ('digest', 'sha256:wrong'), ('state', 'new')):
            broken = self.release()
            broken['assets'][0][key] = value
            with self.assertRaises(ValueError):
                ci.verify_release(broken, expected)

    def test_missing_installer_is_not_published(self):
        (self.dist / 'Tradutor_SL_Setup_1.1.0.exe').unlink()
        with self.assertRaises(ValueError):
            ci.assets(self.dist, '1.1.0')

    def test_publish_uploads_to_draft_then_confirms_before_publishing(self):
        lookup = Mock(side_effect=[None, self.release(True), self.release(False)])
        execute = Mock()
        url = ci.publish('owner/repo', 'a' * 40, self.dist, root=self.root, lookup=lookup, execute=execute)
        self.assertIn('/releases/tag/v1.1.0', url)
        create, edit = [call.args[0] for call in execute.call_args_list]
        self.assertIn('--draft', create)
        self.assertIn('--target', create)
        self.assertIn('a' * 40, create)
        self.assertIn('--draft=false', edit)
        self.assertIn('--latest', edit)

    def test_corrupt_uploaded_asset_leaves_release_as_draft(self):
        broken = self.release(True)
        broken['assets'][0]['digest'] = 'sha256:wrong'
        lookup = Mock(side_effect=[None] + [broken] * 10)
        execute = Mock()
        with patch.object(ci.time, 'sleep'), self.assertRaises(ValueError):
            ci.publish('owner/repo', 'a' * 40, self.dist, root=self.root, lookup=lookup, execute=execute)
        self.assertEqual(execute.call_count, 1)
        self.assertIn('--draft', execute.call_args.args[0])

    def test_existing_release_is_never_overwritten(self):
        execute = Mock()
        with self.assertRaises(ValueError):
            ci.publish('owner/repo', 'a' * 40, self.dist, root=self.root,
                       lookup=lambda repo, tag: self.release(False), execute=execute)
        execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
