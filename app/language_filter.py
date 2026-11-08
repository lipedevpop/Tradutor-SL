"""Conservative, offline English gate. Accept message bodies only."""
from collections import OrderedDict
import re
import unicodedata
from english_terms import ENGLISH_WORDS, SHARED_WORDS, EXTRA_PHRASES, PORTUGUESE_HINTS

SHORT_ENGLISH = {
    'yes', 'nope', 'yep', 'sure', 'sorry', 'please', 'really', 'nice',
    'welcome', 'goodbye', 'morning', 'evening', 'night', 'cool', 'awesome',
    'wait', 'ready', 'busy', 'later', 'same', 'maybe', 'why', 'what',
    'where', 'when', 'who', 'how',
    'not much', 'nothing much', 'not really', 'not yet', 'not now',
    'all good', 'all right', 'pretty good', 'doing well', 'very well',
    'just chilling', 'just chillin', 'just relaxing', 'just looking',
    'sounds good', 'sounds great', 'my bad', 'my pleasure', 'no problem',
    'no thanks', 'yes please', 'of course', 'for sure', 'why not',
    'maybe later', 'talk later', 'take care', 'sleep well', 'sweet dreams',
    'good luck', 'have fun', 'you too', 'me too', 'same here',
    'right now', 'come over', 'hold on', 'hang on', 'one sec',
    'a little', 'a bit', 'too bad', 'so cute', 'very nice', 'looks good',
    'looks great', 'so sorry', 'sorry about that', 'welcome home',
    'what happened', 'who knows', 'where exactly', 'how come',
    'you okay', 'you ok', 'are you okay', 'are you ok',
    'i see', 'i know', 'i agree', 'i understand', 'i forgot',
    'i can', "i can't", 'i do', "i don't", 'i will', "i won't",
    'be right back', 'gotta go', 'got it', 'got you',

    'hello', 'hi', 'hey', 'hello there', 'hey there', 'thank you', 'thanks',
    'good morning', 'good afternoon', 'good evening', 'good night',
    'how are you', 'how are you doing', 'what are you doing', 'where are you',
    'are you there', 'see you later', 'see you soon', 'welcome back',
    'no worries', 'never mind', 'you are welcome', "you're welcome",
    'i miss you', 'i love you', 'miss you', 'love you', 'wyd', 'wbu', 'hbu',
    'idk', 'brb', 'gtg', 'ttyl', 'tysm', 'wyd rn', 'hru', 'thank u',
    'i am fine', "i'm fine", "i'm good", 'im good', 'see you',
    'hi darling', 'hello darling', 'hey babe', 'hey baby', "what's up",
    'whats up', 'u there', 'you there', 'are u there', "i'm here",
    'come here', 'i am here',
    'how r u', 'how about you', 'what about you', 'see ya', 'bye',
}
NO_LANGUAGE = {'ok','okay','kk','lol','lmao','rofl','haha','hahaha','sim','não','nao','no'}

KNOWN_WORDS = ENGLISH_WORDS | SHARED_WORDS
ENGLISH_CUES = ENGLISH_WORDS - SHARED_WORDS
# Some Portuguese tokens also have ordinary English / viewer meanings.
PORTUGUESE_CUES = PORTUGUESE_HINTS - ENGLISH_WORDS - {
    'a', 'as', 'am', 'do', 'no', 'so', 'me', 'he', 'sim', 'bom', 'legal',
    'ai', 'la',  # Also common English acronyms / place names.
}


def normalize_for_detection(body):
    """Discard metadata/noise only here; preserve the text sent to DeepL."""
    text = unicodedata.normalize('NFKC', body).casefold()
    text = text.translate(str.maketrans({'’': "'", '‘': "'", '`': "'", 'ʼ': "'"}))
    text = re.sub(
        r'(?:https?://|secondlife://|www\.)\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|@\w+',
        ' ', text, flags=re.I)
    # Unlike a letters-only tokenizer, retain chat forms such as gr8 / l8r.
    words = re.findall(r"[^\W_]+(?:'[^\W_]+)?", text)
    has_letters = any(any(char.isalpha() for char in word) for word in words)
    words = [word for word in words if not word.isdecimal()
             or (has_letters and word in {'2', '4'})]
    return words, ' '.join(words)


def known_short_english(words):
    """Composition covers new combinations, not just a list of exact phrases.

    Require full vocabulary coverage and an English-specific cue. Do not lower
    langid's threshold globally: names and Portuguese would also pass more often.
    """
    return (1 <= len(words) <= 12
            and all(word in KNOWN_WORDS for word in words)
            and any(word in ENGLISH_CUES for word in words))

class EnglishFilter:
    def __init__(self):
        from langid.langid import LanguageIdentifier, model
        self.identifier = LanguageIdentifier.from_modelstring(model, norm_probs=True)
        # Keep all languages, rather than forcing every message into EN or PT.
        self.cache = OrderedDict()

    def accepts(self, body):
        if not isinstance(body, str) or len(body) > 5000:
            return False
        if body in self.cache:
            self.cache.move_to_end(body)
            return self.cache[body]
        words, normalized = normalize_for_detection(body)
        if not normalized or normalized in NO_LANGUAGE or re.fullmatch(r'(?:k+|(?:ha)+|(?:he)+|(?:rs)+)',normalized):
            result = False
        elif normalized in SHORT_ENGLISH or normalized in EXTRA_PHRASES:
            result = True
        elif any(word in PORTUGUESE_CUES for word in words):
            result = False
        elif words[0] in {'hi', 'hey', 'hello'} and len(words) <= 2 and not any(
                word in {'oi', 'ola', 'olá', 'sim', 'não', 'nao', 'tudo', 'bem', 'você', 'voce', 'vc', 'obrigado', 'obrigada'} for word in words[1:]):
            result = True
        elif known_short_english(words):
            result = True
        else:
            # No minimum word or letter count: even one word reaches detection.
            language, confidence = self.identifier.classify(normalized)
            result = language == 'en' and confidence >= 0.95
        self.cache[body] = result
        while len(self.cache)>300: self.cache.popitem(last=False)
        return result
