"""Regression examples of actual chat styles, plus a worker/API boundary test."""
from collections import OrderedDict
import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from language_filter import EnglishFilter
from tradutor import Worker


ENGLISH_CASES = {
    'compliments_and_flirting': [
        'hot couple', 'HOT COUPLE!', 'hot-couple', 'Hot couple 😍🔥',
        'you are a hot couple', 'u r a hot couple', 'such a lovely couple',
        'you two look amazing together', 'both of you look gorgeous',
        'very sexy couple', 'cute couples', 'beautiful couple', 'nice couple',
        'pretty girl', 'handsome guy', 'you look stunning', 'looking gorgeous',
        'beautiful eyes', 'nice smile', 'love your outfit', 'love your hair',
        'nice body', 'cute avatar', 'you look cute', 'you are adorable',
        'so pretty', 'so hot', 'too hot', 'hot af', 'sexy af',
        'damn hot', 'hot as hell', 'you turn me on', 'you are sweet',
        'are you single?', 'are you married?', 'do you have a partner?',
        'wanna dance?', 'want to cuddle?', 'can I kiss you?', 'kiss me',
        'hold me', 'come closer', 'I miss your hugs', 'I like you a lot',
        'you make me blush', 'you are making me shy', 'wanna hang out?',
        'not interested', 'please stop', 'leave me alone', 'respect my boundaries',
    ],
    'chat_abbreviations': [
        'wyd', 'wbu', 'hbu', 'hru', 'idk', 'idc', 'ikr', 'brb', 'bbl',
        'gtg', 'ttyl', 'afk', 'asap', 'btw', 'fyi', 'imo', 'imho',
        'irl', 'jk', 'ofc', 'omw', 'lmk', 'nvm', 'np', 'ty', 'tysm',
        'tyvm', 'thx', 'pls', 'plz', 'sry', 'yw', 'rn', 'tbh',
        'gr8', 'l8r', 'cya', 'cu later', 'wb', 'ily', 'ilysm',
        'u there?', 'r u there?', 'r u single?', 'how old r u?',
        'ur cute', 'ur hot', 'ur sexy', 'u look hot', 'luv u',
        'wyd rn?', 'idk yet', 'brb a minute', 'ty so much', 'thx a lot',
        'see u later', 'can u help me?', 'lemme see', 'gimme a sec', 'u 2', '4 u',
        'dunno yet', 'gonna sleep', 'gotta go', 'wanna come over?',
    ],
    'daily_conversation': [
        'not much', 'nothing much', 'sounds good', 'my bad', 'I see',
        'good job', 'well done', 'no way', 'no rush', 'no idea', 'not sure',
        'what else?', 'anything else?', 'so far so good', 'all yours',
        'let me know', 'let me check', 'give me a second', 'long time no see',
        'nice to meet you', 'pleased to meet you', 'on my way', 'be back soon',
        'are you busy?', 'what happened?', 'where did you go?', 'how was your day?',
        'I am tired', 'I feel lonely', 'I am bored', 'just chilling', 'sleep well',
        'sweet dreams', 'take care', 'have a nice day', 'see you tomorrow',
        "I'm sorry", "I’m here", "I‘m back", "Iʼm ready", "don't worry",
        'dont worry', 'cant hear you', 'im back', 'youre welcome', 'its okay',
        "I'll be right back", "I've missed you", "we're good", "isn't it cute?",
        'hello darling', 'hiya', 'howdy', 'heya', 'wassup', 'sup', 'yup',
        'yeah', 'nah', 'aww', 'oops', 'ouch', 'yikes', 'goodnight', 'goodmorning',
        'Can we talk later?', 'I will meet you at the party tonight.',
        'I live in LA', 'AI is amazing',
        'I really enjoyed spending the evening with you and I hope we can meet again tomorrow.',
        'I sincerely appreciate your patience while I figure out why my microphone is not working.',
    ],
    'second_life': [
        'tp me', 'tp pls', 'send tp', 'send me a tp', 'send me a lm',
        'accept my teleport', 'need to relog', 'I crashed', 'got disconnected',
        'so laggy', 'my viewer crashed', 'check your inventory', 'read the notecard',
        'wear the hud', 'detach your hud', 'rez the box', 'unpack your gift',
        'nice mesh body', 'new skin', 'bento head', 'bom layers', 'new sim',
        'the sim is full', 'region restart', 'parcel is private', 'try this demo',
        'where is the store?', 'join my group', 'can you hear me?', 'voice chat',
        'your mic is muted', 'turn on voice', 'mute your mic', 'im me', 'pm me',
        'local chat', 'nice ao', 'sit on the poseball', 'change your windlight',
        'free gifts', 'group gift', 'where did you buy that?', 'how much is it?',
        'copy and modify', 'no transfer', 'script error', 'missing texture',
    ],
    'adult_and_strong_language': [
        'horny', 'naughty', 'kinky', 'naked', 'wanna have sex?', 'nice ass',
        'sexy body', 'fuck', 'fucking hell', 'wtf', 'wth', 'stfu', 'idgaf',
        'fwb', 'nsfw', 'consent matters', 'are you comfortable?',
    ],
    'formatting': [
        '  hot   couple  ', 'hot\ncouple', 'ｈｏｔ ｃｏｕｐｌｅ',
        'hot couple https://example.com/oi', '@friend hot couple',
        'hot couple 💕 https://example.com/123', 'gr8!', 'l8r!',
    ],
}

NON_ENGLISH_CASES = {
    'portuguese': [
        'oi', 'olá', 'oi tudo bem?', 'bom dia', 'boa noite', 'sim', 'não', 'nao',
        'casal lindo', 'casal gostoso', 'muito quente', 'vc e seu namorado',
        'vou ficar online hoje', 'você está muito bonita', 'quero dançar',
        'me manda tp', 'manda o landmark', 'estou afk', 'vou relogar',
        'esse hud é bom', 'o sim está cheio', 'meu viewer crashou',
        'legal', 'bom', 'bem', 'obg', 'vlw', 'tbm', 'tchau', 'saudades',
        'meu amor', 'beijos', 'pra você', 'a gente pode conversar amanhã',
        'eu gosto de você', 'sou casada', 'sou solteiro', 'amo esse casal',
    ],
    'mixed_portuguese': [
        'Hello John, tudo bem?', 'hey vc', 'hi você', 'hello obrigada',
        'hot casal', 'casal sexy', 'hot couple muito lindo', 'sexy demais',
        'nice roupa', 'thanks meu amor', 'meu friend', 'hot com vc',
        'eu love you', 'you are linda', 'manda tp please', 'new skin bonita',
    ],
    'other_languages_and_names': [
        'hola como estas', 'merci beaucoup mon ami', 'buenas noches',
        'guten morgen', 'buenos dias', 'bonjour tout le monde',
        'John Black', 'João Silva', 'Maria Clara', 'Juan Carlos',
        'Привет как дела', 'こんにちは', '你好',
    ],
    'noise': [
        '', ' ', '123', '12345', '👍', '💕🔥', '!!!', 'ok', 'okay', 'no',
        'LOL', 'lmao', 'rofl', 'haha', 'hahaha', 'kkkk', 'rsrsrs', 'hehe',
        'https://example.com/hello-world', 'www.example.com/hot-couple',
        'secondlife:///app/agent/123/about', '@JohnBlack', 'john@example.com',
    ],
}


class EnglishReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = EnglishFilter()

    def test_chat_examples(self):
        for category, examples in ENGLISH_CASES.items():
            for text in examples:
                with self.subTest(category=category, text=text):
                    self.assertTrue(self.detector.accepts(text))

    def test_non_english_examples(self):
        for category, examples in NON_ENGLISH_CASES.items():
            for text in examples:
                with self.subTest(category=category, text=text):
                    self.assertFalse(self.detector.accepts(text))

    def test_known_combinations_override_statistical_false_negative(self):
        detector = EnglishFilter.__new__(EnglishFilter)
        detector.cache = OrderedDict()
        detector.identifier = Mock()
        detector.identifier.classify.return_value = ('fr', 0.99)
        self.assertTrue(detector.accepts('hot couple'))
        self.assertTrue(detector.accepts('gorgeous couple'))
        self.assertTrue(detector.accepts('your outfit looks amazing'))
        self.assertFalse(detector.accepts('unlistedword'))

    def test_limits_and_cache(self):
        self.assertFalse(self.detector.accepts(None))
        self.assertFalse(self.detector.accepts('hot ' * 1300))
        for i in range(350):
            self.detector.accepts(f'hot couple {i}')
        self.assertLessEqual(len(self.detector.cache), 300)

    def test_worker_delivers_original_short_english_to_translation(self):
        events = queue.Queue()
        worker = Worker(events)
        worker.language_filter = self.detector
        original = 'Hot couple 😍🔥'
        msg = SimpleNamespace(text=original, conversation='jane_resident')
        delivered = False

        class Reader:
            errors = []
            def __init__(self, *args): pass
            def poll(self):
                nonlocal delivered
                if delivered: return []
                delivered = True
                return [msg, SimpleNamespace(text='casal lindo', conversation='other')]

        engine = Mock(blocked=False)
        engine.translate.return_value = 'Casal sexy 😍🔥'
        with patch('tradutor.LogReader', Reader):
            worker.commands.put(('start', (1, 'unused', [], False)))
            thread = threading.Thread(target=worker.process, args=(engine,))
            thread.start()
            try:
                while True:
                    kind, data = events.get(timeout=5)
                    if kind == 'incoming': break
                self.assertEqual(data, (1, msg, 'Casal sexy 😍🔥'))
                engine.translate.assert_called_once_with(original, 'en_pt')
            finally:
                worker.stopped.set()
                thread.join(3)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
