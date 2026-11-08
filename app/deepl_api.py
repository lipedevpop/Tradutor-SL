"""Official DeepL HTTP API. Credentials stay in session memory only."""
import json
import os
from pathlib import Path
from collections import OrderedDict
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

DATA = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'TradutorIMAlchemyDeepL'
class NeedsAttention(RuntimeError): pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class DeepLEngine:
    def __init__(self, notify, stopped=None):
        self.notify, self.stopped = notify, stopped
        self.key = ''
        self.blocked = True
        self.cache = OrderedDict()
        self.opener = build_opener(NoRedirect())

    def language(self, text): return 'en'

    def configure(self, key):
        self.key = key.strip()
        self.blocked = True
        self.cache.clear()
        self.resume()

    def pause(self, message):
        self.blocked = True
        self.notify(('api_attention', message))
        raise NeedsAttention(message)

    def request(self, path, payload=None):
        if not self.key:
            self.pause('Insira sua chave DeepL nas configurações.')
        if self.stopped and self.stopped.is_set():
            raise RuntimeError('Encerrando.')
        base = 'https://api-free.deepl.com' if self.key.endswith(':fx') else 'https://api.deepl.com'
        req = Request(base + '/v2/' + path,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None,
            headers={'Authorization': 'DeepL-Auth-Key ' + self.key, 'Content-Type': 'application/json'},
            method='POST' if payload is not None else 'GET')
        try:
            with self.opener.open(req, timeout=12) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as error:
            messages = {403:'Chave recusada. Confira a chave e o plano de API no DeepL.',
                        456:'Limite de caracteres do DeepL atingido. Traduções pausadas.',
                        429:'DeepL temporariamente ocupado. Aguarde e clique em Retomar API.',
                        400:'O DeepL recusou os parâmetros desta consulta.',
                        401:'Chave DeepL inválida ou sem autorização.'}
            self.pause(messages.get(error.code, f'DeepL retornou erro HTTP {error.code}. Tente retomar mais tarde.'))
        except (URLError, TimeoutError, OSError):
            self.pause('Não foi possível conectar ao DeepL. Confira a internet e clique em Retomar API.')
        except (ValueError, UnicodeError):
            self.pause('Resposta inesperada do DeepL. Tradução pausada.')

    def usage(self):
        data = self.request('usage')
        count, limit = data.get('character_count'), data.get('character_limit')
        if not isinstance(count, int) or not isinstance(limit, int):
            self.pause('O DeepL respondeu com um formato de saldo não reconhecido.')
        self.notify(('api_usage', f'DeepL: {count:,} / {limit:,} caracteres usados.'.replace(',', '.')))
        if count >= limit:
            self.pause('Limite de caracteres da conta atingido.')
        return data

    def resume(self):
        self.usage()
        self.blocked = False

    def translate(self, text, direction):
        if direction not in ('en_pt', 'pt_en'): raise ValueError('Direção inválida.')
        if not text.strip(): return ''
        if self.blocked: raise NeedsAttention('API pausada.')
        cache_key=(direction,text)
        if cache_key in self.cache:
            self.cache.move_to_end(cache_key)
            return self.cache[cache_key]
        payload={'text':[text], 'target_lang':'PT-BR' if direction=='en_pt' else 'EN-US'}
        payload['source_lang'] = 'EN' if direction == 'en_pt' else 'PT'
        data=self.request('translate',payload)
        try:
            result=data['translations'][0]['text']
            if not isinstance(result,str) or not result.strip(): raise ValueError()
        except (KeyError, IndexError, TypeError, ValueError):
            self.pause('Não foi possível ler a tradução retornada pelo DeepL.')
        self.cache[cache_key]=result
        while len(self.cache)>100: self.cache.popitem(last=False)
        return result

    def close(self):
        self.key=''
        self.cache.clear()
