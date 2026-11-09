"""Synthetic fixtures following Aurora 0.9.x's published transcript format."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from account_profiles import account_folders, account_for_folder
from aurora_profiles import ROOT, folder_account, folder_label
from log_reader import LogReader, parse_line
from viewer_detection import ViewerDetection, detect_viewers, viewer_from_executable
from viewer_profiles import browse_start, discover_folders

A = '00000000-0000-4000-8000-000000000001'
B = '00000000-0000-4000-8000-000000000002'


class AuroraTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / ROOT
        self.config.mkdir(parents=True)
        self.env = patch.dict(os.environ, {'APPDATA': str(self.root)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def grid(self, agent=A, grid='agni', root=None):
        folder = (root or self.config / 'accounts') / agent / 'chat_logs' / grid
        folder.mkdir(parents=True)
        (folder / 'Jane Doe.txt').write_text('', encoding='utf-8')
        return folder

    def catalogue(self):
        entries = [{'agent': A, 'username': 'Lipe Vortex'},
                   {'agent': B, 'username': 'mab.leeeroy'},
                   {'agent': '../escape', 'username': 'lipe.vortex'}]
        (self.config / 'login_accounts.json').write_text(json.dumps(entries), encoding='utf-8')

    def test_executable_and_config_detection(self):
        for name in ['aurora-viewer.exe', 'AuroraViewer.exe', r'C:\Aurora\aurora-viewer.exe']:
            self.assertEqual(viewer_from_executable(name), 'Aurora Viewer')
        for name in ['aurora.exe', 'aurora-viewer-setup.exe', 'aurora-viewer-helper.exe']:
            self.assertIsNone(viewer_from_executable(name))
        self.assertEqual(detect_viewers(str(self.root), []), ViewerDetection(('Aurora Viewer',), 'settings'))
        (self.root / 'Firestorm_x64').mkdir()
        self.assertEqual(detect_viewers(str(self.root), ['aurora-viewer.exe']),
                         ViewerDetection(('Aurora Viewer',), 'running'))
        self.assertEqual(detect_viewers(str(self.root), ['aurora-viewer.exe', 'Alchemy.exe']).viewers,
                         ('Alchemy', 'Aurora Viewer'))
        self.assertEqual(browse_start('Aurora Viewer', appdata=str(self.root)), self.config)

    def test_default_layout_keeps_accounts_and_grids_separate(self):
        folders = [self.grid(), self.grid(B), self.grid(A, 'aditi')]
        other = self.config / 'unrelated' / 'deep'
        other.mkdir(parents=True)
        (other / 'friend.txt').write_text('ignored')
        self.assertEqual(set(discover_folders('Aurora Viewer')), set(folders))

    def test_custom_preference_is_accounts_root(self):
        old = self.grid()
        custom = self.root / 'Histórico com espaços e acentos'
        selected = self.grid(root=custom)
        (self.config / 'settings.json').write_text(json.dumps({'chat_log_location': str(custom)}))
        self.assertEqual(discover_folders('Aurora Viewer'), [selected])
        self.assertNotIn(old, discover_folders('Aurora Viewer'))

    def test_catalogue_matches_preferred_accounts_and_labels(self):
        lipe, mab = self.grid(), self.grid(B)
        self.catalogue()
        self.assertEqual(folder_account(lipe), 'Lipe Vortex')
        self.assertEqual(account_for_folder(lipe), 'lipe.vortex')
        self.assertEqual(account_for_folder(mab), 'mab.leeeroy')
        self.assertEqual(account_folders([mab, lipe], 'lipe.vortex'), [lipe])
        self.assertEqual(account_folders([mab, lipe], 'mab.leeeroy'), [mab])
        self.assertEqual(account_folders([mab, lipe]), [mab, lipe])
        self.assertIn('Lipe Vortex · agni', folder_label(lipe))
        self.assertEqual(folder_account(self.root / A / 'other' / 'agni'), '')

    def test_missing_or_malformed_catalogue_never_guesses_account(self):
        folder = self.grid()
        for text in ['{invalid', '{}', '[null, {"agent": 12, "username": []}]']:
            (self.config / 'login_accounts.json').write_text(text)
            self.assertEqual(folder_account(folder), '')
            self.assertIsNone(account_for_folder(folder))
            self.assertEqual(account_folders([folder], 'lipe.vortex'), [])
            self.assertEqual(discover_folders('Aurora Viewer'), [folder])

    def test_conflicting_catalogue_entries_never_choose_an_avatar(self):
        folder = self.grid()
        entries = [{'agent': A, 'username': name} for name in ['lipe.vortex', 'mab.leeeroy', 'lipe.vortex']]
        (self.config / 'login_accounts.json').write_text(json.dumps(entries))
        self.assertEqual(folder_account(folder), '')
        self.assertEqual(account_folders([folder], 'lipe.vortex'), [])

    def test_malformed_settings_and_invalid_account_dirs(self):
        folder = self.grid()
        self.grid('not-an-avatar')
        (self.config / 'settings.json').write_text('{invalid')
        self.assertEqual(discover_folders('Aurora Viewer'), [folder])

    def test_detection_never_opens_transcript_contents(self):
        folder = self.grid()
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.suffix.casefold() == '.txt':
                raise AssertionError('Transcript content must not be read by detection')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            self.assertEqual(discover_folders('Aurora Viewer'), [folder])

    def test_transcripts_and_individual_message_exclusions(self):
        for stamp in ['[2026/11/09 14:05]  ', '[2:05:30 PM]  ', '']:
            msg = parse_line(stamp + 'Display%3A Name (jane.doe): Hello, how are you?', 'Jane Doe-2026-11')
            self.assertEqual(msg.text, 'Hello, how are you?')
            for sender, conversation in [('Lipe Vortex', 'Jane Doe'), ('Second Life', 'Jane Doe'),
                                         ('Jane Doe', 'Friends (group)'), ('Jane Doe', 'chat-2026-11-09'),
                                         ('Jane Doe', 'Jane Doe Conference 2026_11_09 14_05 abcd')]:
                self.assertIsNone(parse_line(stamp + sender + ': Hello there', conversation))

    def test_incremental_reader_no_old_history_or_duplicate_or_partial_utf8(self):
        folder = self.grid()
        path = folder / 'Jane Doe-2026-11.txt'
        path.write_bytes(b'[2026/11/09 14:00]  Jane Doe: Old message\r\n')
        reader = LogReader(folder, ['lipe.vortex'])
        self.assertEqual(reader.poll(), [])
        line = '[2026/11/09 14:05]  Jane Doe: Hello, café!\r\n'.encode('utf-8')
        cut = line.index(b'\xc3') + 1
        with path.open('ab') as file:
            file.write(line[:cut])
        self.assertEqual(reader.poll(), [])
        with path.open('ab') as file:
            file.write(line[cut:])
        self.assertEqual([msg.text for msg in reader.poll()], ['Hello, café!'])
        self.assertEqual(reader.poll(), [])


if __name__ == '__main__':
    unittest.main()
