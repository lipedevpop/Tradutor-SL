import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from language_filter import EnglishFilter
from log_reader import LogReader, parse_line, eligible
from tradutor import Worker

class FilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.detector=EnglishFilter()
    def test_message_only_not_english_name(self):
        msg=parse_line('[2026/09/23 10:00] John Black: Oi, tudo bem?', 'john_black')
        self.assertIsNotNone(msg)
        self.assertFalse(self.detector.accepts(msg.text))
        msg=parse_line('[2026/09/23 10:00] João Silva (joao.silva): Can we talk later?', 'joao_silva')
        self.assertTrue(self.detector.accepts(msg.text))
    def test_languages_and_noise(self):
        for text in ['Oi, tudo bem?', 'vou ficar online hoje', 'Hello John, tudo bem?',
                     'olá, eu preciso conversar com você', 'kkk', 'LOL', '👍', '123', 'ok',
                     'https://example.com/hello-world', 'hola como estas', 'merci beaucoup mon ami', 'John Black']:
            with self.subTest(text=text):self.assertFalse(self.detector.accepts(text))
        for text in ['hi', 'Hi!', 'hey', 'hello bro', 'hi bro', 'hey dude', 'yes', 'sorry', 'please', 'not much', 'Not much!', 'nothing much', 'sounds good', 'my bad', 'i see', 'Hello!', 'How are you?', 'I am fine', 'Can we talk later?', 'wyd?', 'I will meet you at the party tonight.']:
            with self.subTest(text=text):self.assertTrue(self.detector.accepts(text))
    def test_single_unknown_word_reaches_detector(self):
        from collections import OrderedDict
        from unittest.mock import Mock
        detector=EnglishFilter.__new__(EnglishFilter)
        detector.cache=OrderedDict()
        detector.identifier=Mock()
        detector.identifier.classify.return_value=('en', 0.99)
        self.assertTrue(detector.accepts('serendipitously'))
        detector.identifier.classify.assert_called_once_with('serendipitously')
    def test_groups_conferences_and_unknown_names(self):
        for name in ['news (group).txt','news (grupo).txt','Friend Conference hash123.txt',
                     'Ad-hoc Conference hash123.txt','Conferência teste.txt', 'chat-2026-09-23.txt',
                     'object.txt','many people here.txt','conversation.log.txt']:
            with self.subTest(name=name):self.assertFalse(eligible(Path(name)))
        # Old group logs without suffix are rejected when sender differs from filename.
        self.assertIsNone(parse_line('[2026/09/23 10:00] John Black: Hello there!', 'news'))
        self.assertIsNone(parse_line('[2026/09/23 10:00] Vendor (shop.object): Buy this today!', 'john_black'))
        # Account mismatches are not accepted based on matching display name.
        self.assertIsNone(parse_line('[2026/09/23 10:00] John Black (other.person): Hello!', 'john_black'))
        self.assertIsNotNone(parse_line('[2026/09/23 10:00] John Black: Hello!', 'john_black-2026-09'))
    def test_reader_filters_before_language_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);reader=LogReader(root)
            (root/'john_black.txt').write_text('[2026/09/23 10:00] John Black: Oi, tudo bem?\n')
            (root/'joao_silva.txt').write_text('[2026/09/23 10:00] João Silva (joao.silva): Hello!\n')
            (root/'club (group).txt').write_text('[2026/09/23 10:00] John Black: Hello!\n')
            messages=reader.poll()
            accepted=[m for m in messages if self.detector.accepts(m.text)]
            self.assertEqual([(m.conversation,m.text) for m in accepted],[('joao_silva','Hello!')])
    def test_200_portuguese_ims_make_zero_translation_calls(self):
        events=queue.Queue();worker=Worker(events);worker.language_filter=self.detector
        raw=[SimpleNamespace(text=f'Olá, estou conversando em português com você hoje {i}',conversation=f'person{i}') for i in range(200)]
        delivered=threading.Event()
        class Reader:
            errors=[]
            def __init__(self,*args):pass
            def poll(self):
                if delivered.is_set(): return []
                delivered.set();return raw
        class Engine:
            blocked=False
            calls=[]
            def translate(self,*args):self.calls.append(args);return 'unexpected'
        engine=Engine()
        with patch('tradutor.LogReader',Reader):
            worker.commands.put(('start',(1,'unused',[],False)))
            thread=threading.Thread(target=worker.process,args=(engine,));thread.start()
            try:
                while True:
                    kind,data=events.get(timeout=10)
                    if kind=='filtered':break
                self.assertEqual(data,200)
                self.assertEqual(engine.calls,[])
                self.assertFalse(any(item[0]=='incoming' for item in list(events.queue)))
            finally:
                worker.stopped.set();thread.join(3)
            self.assertFalse(thread.is_alive())

if __name__=='__main__':unittest.main()
