import tempfile
import unittest
from pathlib import Path
from log_reader import LogReader, parse_line


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'friend_resident.txt'

    def tearDown(self):
        self.temp.cleanup()

    def test_no_old_history_and_no_duplicate_on_repoll(self):
        self.path.write_text('[2026/09/21 18:20] Friend: old message\n', encoding='utf-8')
        reader = LogReader(self.folder)
        self.assertEqual(reader.poll(), [])
        with self.path.open('a', encoding='utf-8') as file:
            file.write('[2026/09/21 18:22] Friend (friend.resident): hello\n')
        messages = reader.poll()
        self.assertEqual([m.text for m in messages], ['hello'])
        self.assertEqual(messages[0].sender, 'Friend (friend.resident)')
        self.assertEqual(reader.poll(), [])

    def test_partial_utf8_and_crlf(self):
        reader = LogReader(self.folder)
        raw = '[2026/09/21 18:22] Friend: café\r\n'.encode()
        cut = raw.index('é'.encode()) + 1
        self.path.write_bytes(raw[:cut])
        self.assertEqual(reader.poll(), [])
        with self.path.open('ab') as file:
            file.write(raw[cut:])
        self.assertEqual([m.text for m in reader.poll()], ['café'])

    def test_new_conversation_and_repeated_message(self):
        reader = LogReader(self.folder)
        self.path.write_text('[2026/09/21 18:22] Friend: hello\n' * 2)
        self.assertEqual([m.text for m in reader.poll()], ['hello', 'hello'])

    def test_system_own_links_groups_excluded(self):
        reader = LogReader(self.folder, ['my_avatar'])
        self.path.write_text(
            '[2026/09/21 18:22] Second Life: system notification\n'
            '[2026/09/21 18:22] My Avatar: own message\n'
            '[2026/09/21 18:22] Display Name (my.avatar): another own message\n'
            '[2026/09/21 18:22] Friend: https://example.com/\n'
            '[2026/09/21 18:22] Friend: hello\n')
        (self.folder / 'news (group).txt').write_text('[2026/09/21 18:22] Friend: group\n')
        (self.folder / 'chat.txt').write_text('[2026/09/21 18:22] Friend: local\n')
        self.assertEqual([m.text for m in reader.poll()], ['hello'])

    def test_replaced_file_and_truncation(self):
        self.path.write_text('[2026/09/21 18:22] Friend: ' + 'old' * 40 + '\n')
        reader = LogReader(self.folder)
        self.path.write_text('[2026/09/21 18:23] Friend: new\n')
        self.assertEqual([m.text for m in reader.poll()], ['new'])
        other = self.folder / 'replacement.tmp'
        other.write_text('[2026/09/21 18:24] Friend: replaced\n')
        other.replace(self.path)
        self.assertEqual([m.text for m in reader.poll()], ['replaced'])

    def test_emojis_and_colons_preserved(self):
        msg = parse_line('[2026/09/21 18:22:03] Friend: hello: how are you? 🙂', 'friend')
        self.assertEqual(msg.text, 'hello: how are you? 🙂')
        self.assertIsNone(parse_line('not a message', 'friend'))


if __name__ == '__main__':
    unittest.main()
