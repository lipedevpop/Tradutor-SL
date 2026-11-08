from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from viewer_detection import (
    AUTO_VIEWER, ViewerDetection, detect_viewers, viewer_from_executable,
)
from tradutor import App
from account_profiles import AUTO_ACCOUNT


class AutomaticDetectionTests(unittest.TestCase):
    def test_executable_variants_and_helpers(self):
        for name in ['Firestorm-bin.exe', 'FirestormOS-bin.exe', 'PhoenixFirestorm.exe',
                     r'C:\Program Files\Firestorm\Firestorm-Releasex64.exe']:
            self.assertEqual(viewer_from_executable(name), 'Firestorm')
        for name in ['CoolVLViewer.exe', 'cool_vl_viewer.exe', 'CoolVLViewer-bin.exe']:
            self.assertEqual(viewer_from_executable(name), 'Cool VL Viewer')
        for name in ['Alchemy.exe', 'Alchemy-bin.exe', 'AlchemyNext.exe', 'AlchemyNext-bin.exe']:
            self.assertEqual(viewer_from_executable(name), 'Alchemy')
        for name in ['FirestormSetup.exe', 'FirestormUpdater.exe', 'CoolVLViewerCrashLogger.exe',
                     'SecondLifeViewer.exe', 'notfirestorm.exe', 'Firestorm.txt', 'python.exe']:
            self.assertIsNone(viewer_from_executable(name))

    def test_running_viewer_overrides_old_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'Firestorm_x64').mkdir()
            result = detect_viewers(d, ['CoolVLViewer.exe'])
            self.assertEqual(result, ViewerDetection(('Cool VL Viewer',), 'running'))

    def test_multiple_running_viewers_are_not_guessed(self):
        result = detect_viewers(executables=['CoolVLViewer.exe', 'Firestorm-bin.exe', 'Firestorm-bin.exe'])
        self.assertEqual(result.viewers, ('Firestorm', 'Cool VL Viewer'))
        self.assertEqual(result.source, 'running')

    def test_single_and_multiple_configuration_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'AlchemyNext').mkdir()
            (root / 'Firestorm_x64').mkdir()
            self.assertEqual(detect_viewers(d, []).viewers, ('Firestorm', 'Alchemy'))
            settings = root / 'SecondLife/user_settings'
            settings.mkdir(parents=True)
            (settings / 'settings_coolvlviewer_1324.xml').write_text('<llsd/>')
            self.assertEqual(detect_viewers(d, []).viewers, ('Firestorm', 'Alchemy', 'Cool VL Viewer'))

    def test_alchemy_running_overrides_other_viewers_settings(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'Firestorm_x64').mkdir()
            (Path(d) / 'CoolVLViewer').mkdir()
            result = detect_viewers(d, ['AlchemyNext-bin.exe'])
            self.assertEqual(result, ViewerDetection(('Alchemy',), 'running'))

    def test_alchemy_only_configuration_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'AlchemyNext').mkdir()
            self.assertEqual(detect_viewers(d, []), ViewerDetection(('Alchemy',), 'settings'))

    def test_all_three_running_need_selection(self):
        result = detect_viewers(executables=['Firestorm-bin.exe', 'Alchemy.exe', 'CoolVLViewer.exe'])
        self.assertEqual(result.viewers, ('Firestorm', 'Alchemy', 'Cool VL Viewer'))

    def test_secondlife_folder_alone_is_not_cool_viewer(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'SecondLife').mkdir()
            self.assertEqual(detect_viewers(d, []).viewers, ())

    def test_cool_per_account_marker(self):
        with tempfile.TemporaryDirectory() as d:
            avatar = Path(d) / 'SecondLife/test_resident'
            avatar.mkdir(parents=True)
            (avatar / 'settings_per_account_coolvlviewer.xml').write_text('<llsd/>')
            self.assertEqual(detect_viewers(d, []).viewers, ('Cool VL Viewer',))

    def test_process_failure_falls_back_to_settings(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'Firestorm').mkdir()
            with patch('viewer_detection.running_executables', side_effect=OSError('access denied')):
                self.assertEqual(detect_viewers(d).viewers, ('Firestorm',))

    def test_missing_settings_and_no_running_viewer(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(detect_viewers(d, []), ViewerDetection((), 'none'))


class ViewerSelectionUITests(unittest.TestCase):
    """Exercise real Tk state changes, with no keys, logs or network access."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fire = Path(self.temp.name) / 'fire_account'
        self.cool = Path(self.temp.name) / 'cool_account'
        self.alchemy = Path(self.temp.name) / 'alchemy_account'
        self.fire.mkdir()
        self.cool.mkdir()
        self.alchemy.mkdir()
        self.settings = {
            'viewer': 'Firestorm', 'folder': str(self.fire), 'aliases': 'Fire Name',
            'topmost': False,
            'viewer_profiles': {
                'Firestorm': {'folder': str(self.fire), 'aliases': 'Fire Name'},
                'Cool VL Viewer': {'folder': str(self.cool), 'aliases': 'Cool Name'},
                'Alchemy': {'folder': str(self.alchemy), 'aliases': 'Alchemy Name'},
            },
        }
        self.patches = [
            patch('tradutor.load_settings', return_value=self.settings),
            patch('tradutor.load_key', return_value=''),
            patch('tradutor.save_settings'),
            patch('tradutor.Worker.start'),
            patch.object(App, 'detect_folder'),
        ]
        for p in self.patches:
            p.start()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)

    def tearDown(self):
        self.root.destroy()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def deliver(self, viewers, source='running', generation=None):
        self.app.apply_viewer_detection((
            self.app.detect_generation if generation is None else generation,
            ViewerDetection(tuple(viewers), source), True, None))

    def test_default_is_auto_and_single_detected_viewer_restores_profile(self):
        self.assertEqual(self.app.viewer_choice.get(), AUTO_VIEWER)
        self.assertFalse(self.app.viewer_resolved)
        self.deliver(['Cool VL Viewer'])
        self.assertTrue(self.app.viewer_resolved)
        self.assertEqual(self.app.viewer.get(), 'Cool VL Viewer')
        self.assertEqual(self.app.folder.get(), str(self.cool))
        self.assertEqual(self.app.aliases.get(), 'Cool Name')
        self.assertIn('aberto', self.app.viewer_status.get())

    def test_manual_switch_restores_each_folder_and_is_persisted(self):
        with patch('tradutor.save_settings') as save:
            self.app.viewer_choice.set('Cool VL Viewer')
            self.app.change_viewer()
            self.assertEqual(self.app.folder.get(), str(self.cool))
            self.assertEqual(save.call_args.args[0]['viewer_mode'], 'manual')
            self.app.viewer_choice.set('Firestorm')
            self.app.change_viewer()
            self.assertEqual(self.app.folder.get(), str(self.fire))
            self.assertEqual(self.app.aliases.get(), 'Fire Name')

    def test_late_detection_cannot_override_manual_selection(self):
        generation = self.app.detect_generation
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.deliver(['Cool VL Viewer'], generation=generation)
        self.assertEqual(self.app.viewer.get(), 'Firestorm')
        self.assertEqual(self.app.viewer_choice.get(), 'Firestorm')

    def test_ambiguous_auto_keeps_saved_profiles_and_prevents_start(self):
        with patch.object(self.app, 'open_settings'):
            self.deliver(['Firestorm', 'Cool VL Viewer'])
            self.assertFalse(self.app.viewer_resolved)
            self.assertEqual(self.app.folder.get(), '')
            self.assertEqual(self.app.viewer_profiles['Firestorm']['folder'], str(self.fire))
            self.app.api_configured = True
            self.app.toggle()
        self.assertFalse(self.app.watching)
        self.assertTrue(self.app.worker.commands.empty())

    def test_no_auto_match_allows_manual_selection(self):
        self.deliver([], 'none')
        self.app.viewer_choice.set('Cool VL Viewer')
        self.app.change_viewer()
        self.assertTrue(self.app.viewer_resolved)
        self.assertEqual(self.app.folder.get(), str(self.cool))

    def test_auto_finds_new_viewer_and_requests_its_folder(self):
        self.app.viewer_profiles.pop('Cool VL Viewer')
        self.deliver(['Cool VL Viewer'], 'settings')
        self.app.detect_folder.assert_called_once_with(quiet=True)
        self.assertEqual(self.app.folder.get(), '')

    def test_viewer_cannot_change_while_reading(self):
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.set_controls(True)
        self.app.viewer_choice.set('Cool VL Viewer')
        self.app.change_viewer()
        self.assertEqual(self.app.viewer.get(), 'Firestorm')
        self.assertEqual(self.app.viewer_choice.get(), 'Firestorm')

    def test_return_to_auto_and_async_result(self):
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.viewer_choice.set(AUTO_VIEWER)
        result = ViewerDetection(('Cool VL Viewer',), 'running')
        with patch('tradutor.detect_viewers', return_value=result):
            self.app.change_viewer()
            kind, data = self.app.events.get(timeout=3)
        self.assertEqual(kind, 'viewer_detection')
        self.app.apply_viewer_detection(data)
        self.assertEqual(self.app.viewer_mode, 'auto')
        self.assertEqual(self.app.viewer.get(), 'Cool VL Viewer')

    def test_manual_preference_is_restored_on_next_launch(self):
        self.root.destroy()
        self.settings.update(viewer='Cool VL Viewer', viewer_mode='manual',
                             folder=str(self.cool), aliases='Cool Name')
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)
        self.assertEqual(self.app.viewer_choice.get(), 'Cool VL Viewer')
        self.assertEqual(self.app.viewer_mode, 'manual')
        self.assertTrue(self.app.viewer_resolved)
        self.assertEqual(self.app.folder.get(), str(self.cool))

    def test_auto_alchemy_then_manual_each_viewer_restores_its_account(self):
        self.deliver(['Alchemy'])
        self.assertEqual(self.app.viewer.get(), 'Alchemy')
        self.assertEqual(self.app.folder.get(), str(self.alchemy))
        self.assertEqual(self.app.aliases.get(), 'Alchemy Name')
        for viewer, folder in [('Firestorm', self.fire), ('Cool VL Viewer', self.cool), ('Alchemy', self.alchemy)]:
            self.app.viewer_choice.set(viewer)
            self.app.change_viewer()
            self.assertTrue(self.app.viewer_resolved)
            self.assertEqual(self.app.folder.get(), str(folder))

    def make_preferred_folders(self):
        lipe = Path(self.temp.name) / 'lipe_vortex'
        mab = Path(self.temp.name) / 'mab_leeeroy'
        lipe.mkdir()
        mab.mkdir()
        return lipe, mab

    def test_account_switch_restores_each_custom_path_and_alias(self):
        lipe, mab = self.make_preferred_folders()
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.set_detected_folder(lipe)
        self.app.aliases.set('lipe.vortex; Display Name')
        self.app.account_choice.set('mab.leeeroy')
        self.app.change_account()
        self.assertEqual(self.app.folder.get(), '')
        self.assertEqual(self.app.aliases.get(), 'mab.leeeroy')
        self.app.set_detected_folder(mab)
        self.app.account_choice.set('lipe.vortex')
        self.app.change_account()
        self.assertEqual(self.app.folder.get(), str(lipe))
        self.assertEqual(self.app.aliases.get(), 'lipe.vortex; Display Name')
        self.app.account_choice.set('mab.leeeroy')
        self.app.change_account()
        self.assertEqual(self.app.folder.get(), str(mab))

    def test_account_folder_detection_filters_results_before_autoselect(self):
        lipe, mab = self.make_preferred_folders()
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.account_choice.set('lipe.vortex')
        self.app.change_account()
        data = (self.app.detect_generation, 'Firestorm', [self.fire, mab, lipe], True, None)
        self.app.events.put(('folder_detection', data))
        self.app.receive()
        self.assertEqual(self.app.folder.get(), str(lipe))
        self.assertEqual(self.app.aliases.get(), 'lipe.vortex')

    def test_both_preferred_folders_require_selection_in_auto(self):
        lipe, mab = self.make_preferred_folders()
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.account_choice.set(AUTO_ACCOUNT)
        self.app.change_account()
        data = (self.app.detect_generation, 'Firestorm', [self.fire, lipe, mab], True, None)
        with patch.object(self.app, 'choose_detected_folder') as picker:
            self.app.events.put(('folder_detection', data))
            self.app.receive()
            picker.assert_called_once_with([lipe, mab])
        self.assertEqual(self.app.folder.get(), '')

    def test_account_cannot_change_during_reading(self):
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.set_controls(True)
        previous = self.app.account_choice.get()
        self.app.account_choice.set('mab.leeeroy')
        self.app.change_account()
        self.assertEqual(self.app.account_choice.get(), previous)
        self.assertEqual(self.app.folder.get(), str(self.fire))

    def test_preferred_account_and_custom_folder_restored_next_launch(self):
        self.app.viewer_choice.set('Firestorm')
        self.app.change_viewer()
        self.app.account_choice.set('lipe.vortex')
        self.app.change_account()
        self.app.set_detected_folder(self.fire)
        with patch('tradutor.save_settings') as save:
            self.app.persist()
            saved = save.call_args.args[0]
        self.root.destroy()
        self.settings.clear()
        self.settings.update(saved)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root)
        self.assertEqual(self.app.account_choice.get(), 'lipe.vortex')
        self.assertEqual(self.app.folder.get(), str(self.fire))
        self.assertEqual(self.app.aliases.get(), 'lipe.vortex')


if __name__ == '__main__':
    unittest.main()
