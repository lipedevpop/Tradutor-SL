from pathlib import Path
import unittest
from account_profiles import AUTO_ACCOUNT, account_for_folder, account_folders
from log_reader import parse_line


class AccountMatchingTests(unittest.TestCase):
    def test_exact_accounts_with_viewer_separators_and_case(self):
        for name in ['lipe.vortex', 'LIPE_VORTEX', 'Lipe Vortex']:
            self.assertEqual(account_for_folder(Path('logs') / name), 'lipe.vortex')
        for name in ['mab.leeeroy', 'MAB_LEEEROY', 'Mab Leeeroy']:
            self.assertEqual(account_for_folder(Path('logs') / name), 'mab.leeeroy')

    def test_no_substring_or_similar_account_match(self):
        for name in ['lipe_vortex_2', 'xlipe_vortex', 'mab_leeroy', 'mab_leeeroy_old', 'other_resident']:
            self.assertIsNone(account_for_folder(name))

    def test_auto_prioritizes_one_preferred_account(self):
        paths = [Path('other_resident'), Path('lipe_vortex')]
        self.assertEqual(account_folders(paths), [Path('lipe_vortex')])

    def test_both_preferred_accounts_remain_choices(self):
        paths = [Path('lipe_vortex'), Path('other_resident'), Path('mab_leeeroy')]
        self.assertEqual(account_folders(paths), [Path('lipe_vortex'), Path('mab_leeeroy')])

    def test_selected_account_never_falls_back_to_another(self):
        paths = [Path('mab_leeeroy'), Path('other_resident')]
        self.assertEqual(account_folders(paths, 'lipe.vortex'), [])
        self.assertEqual(account_folders(paths, 'mab.leeeroy'), [Path('mab_leeeroy')])

    def test_other_users_can_still_choose_a_folder(self):
        paths = [Path('other_resident')]
        self.assertEqual(account_folders(paths, AUTO_ACCOUNT), paths)

    def test_only_active_account_is_ignored_as_self(self):
        line = 'Lipe Vortex (lipe.vortex): hot couple'
        self.assertIsNone(parse_line(line, 'lipe_vortex', ['lipe.vortex']))
        self.assertIsNotNone(parse_line(line, 'lipe_vortex', ['mab.leeeroy']))


if __name__ == '__main__':
    unittest.main()
