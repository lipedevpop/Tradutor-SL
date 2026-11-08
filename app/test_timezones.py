"""Cool VL PST/PDT regression without real conversations or network calls."""
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock

from language_filter import EnglishFilter
from log_reader import LogReader, parse_line
from tradutor import Worker


class TimezoneTests(unittest.TestCase):
    def test_cool_clock_and_date_with_timezone(self):
        for stamp in ['14:18:46 PST', '14:19:25 PDT', '2:19 PM PST',
                      '2:19:25 pm pdt', '05/11/2026 14:18:46 PST',
                      '2026/11/05 14:19:25 PDT', '2026-11-05 14:19:25 UTC',
                      '14:18 BRT', '14:18 SLT']:
            for peer in ['testpeer', 'TestPeer Resident']:
                with self.subTest(stamp=stamp, peer=peer):
                    msg = parse_line(f'[{stamp}] TestPeer: Hello', peer)
                    self.assertIsNotNone(msg)
                    self.assertEqual(msg.text, 'Hello')
                    self.assertEqual(msg.timestamp, stamp)

    def test_timezone_offsets_and_original_body(self):
        for stamp in ['14:18:46 UTC-08:00', '14:18:46 GMT+3', '14:18:46 -0800',
                      '14:18:46 +03:00', '2026/11/05 14:18:46 UTC+00:00']:
            with self.subTest(stamp=stamp):
                msg = parse_line(f'[{stamp}] Friend (friend.resident): hot couple: 😍', 'friend_resident')
                self.assertIsNotNone(msg)
                self.assertEqual(msg.text, 'hot couple: 😍')

    def test_timezone_does_not_bypass_sender_and_group_filters(self):
        for line, peer, aliases in [
            ('[14:19:25 PST] You: hello', 'friend', []),
            ('[14:19:25 PST] Lipe Vortex: hello', 'lipe_vortex', ['lipe.vortex']),
            ('[14:19:25 PST] Friend: hello', 'news (group)', []),
            ('[14:19:25 PST] Object (shop.object): buy this', 'friend', []),
            ('[14:19:25 PST] Friend: hello', 'other', []),
            ('[14:19:25 PST] Second Life: notice', 'friend', []),
            ('[14:19:25 PST] Friend: https://example.com', 'friend', []),
            ('[14:19:25 PST] Friend is Offline', 'friend', []),
        ]:
            with self.subTest(line=line):
                self.assertIsNone(parse_line(line, peer, aliases))

    def test_reader_starts_at_eof_then_reads_new_timezone_lines(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'TestPeer Resident.txt'
            path.write_text('[05/11/2026 14:18:00 PST] TestPeer: old history\n', encoding='utf-8')
            reader = LogReader(d, ['lipe.vortex'])
            self.assertEqual(reader.poll(), [])
            bodies = ['Hello', 'hello', 'hi', 'how are you']
            with path.open('a', encoding='utf-8', newline='') as file:
                for body in bodies:
                    file.write(f'[05/11/2026 14:19:25 PST] TestPeer: {body}\r\n')
            self.assertEqual([m.text for m in reader.poll()], bodies)
            self.assertEqual(reader.poll(), [])

    def test_real_reader_worker_and_english_gate_deliver_timezone_messages(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'TestPeer Resident.txt'
            path.write_text('[05/11/2026 14:18:00 PST] TestPeer: old history\n', encoding='utf-8')
            events = queue.Queue()
            worker = Worker(events)
            worker.language_filter = EnglishFilter()
            engine = Mock(blocked=False)
            engine.translate.side_effect = lambda text, direction: 'PT: ' + text
            import threading
            thread = threading.Thread(target=worker.process, args=(engine,))
            worker.commands.put(('start', (1, d, ['lipe.vortex'], False)))
            thread.start()
            try:
                while events.get(timeout=5)[0] != 'watching':
                    pass
                bodies = ['Hello', 'hello', 'hi', 'how are you']
                with path.open('a', encoding='utf-8') as file:
                    for body in bodies:
                        file.write(f'[05/11/2026 14:19:25 PST] TestPeer: {body}\n')
                delivered = []
                while len(delivered) < len(bodies):
                    kind, data = events.get(timeout=5)
                    if kind == 'incoming':
                        delivered.append(data[1].text)
                self.assertEqual(delivered, bodies)
                self.assertEqual([call.args for call in engine.translate.call_args_list],
                                 [(body, 'en_pt') for body in bodies])
            finally:
                worker.stopped.set()
                thread.join(3)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
