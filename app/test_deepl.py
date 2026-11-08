import json
import unittest
from io import BytesIO
from urllib.error import HTTPError
from deepl_api import DeepLEngine, NeedsAttention

class Response:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps(self.data).encode()
class Opener:
    def __init__(self):self.requests=[];self.status=None
    def open(self,req,timeout):
        self.requests.append(req)
        if self.status:raise HTTPError(req.full_url,self.status,'error',{},BytesIO())
        return Response({'character_count':12,'character_limit':1000000} if req.full_url.endswith('/usage') else {'translations':[{'text':'Olá!'}]})
class Tests(unittest.TestCase):
    def setUp(self):
        self.events=[];self.engine=DeepLEngine(self.events.append);self.engine.opener=Opener()
    def test_auth_and_usage(self):
        self.engine.configure('example-secret')
        req=self.engine.opener.requests[0]
        self.assertEqual(req.full_url,'https://api.deepl.com/v2/usage')
        self.assertEqual(req.get_header('Authorization'),'DeepL-Auth-Key example-secret')
        self.assertFalse(self.engine.blocked)
        self.assertNotIn('example-secret',str(self.events))
    def test_free_endpoint(self):
        self.engine.configure('test:fx')
        self.assertTrue(self.engine.opener.requests[0].full_url.startswith('https://api-free.deepl.com/'))
    def test_text_preserved_and_cache(self):
        self.engine.configure('example')
        text="u there? don't change my words"
        self.assertEqual(self.engine.translate(text,'en_pt'),'Olá!')
        req=self.engine.opener.requests[-1];data=json.loads(req.data)
        self.assertEqual(data,{'text':[text],'target_lang':'PT-BR','source_lang':'EN'})
        count=len(self.engine.opener.requests)
        self.engine.translate(text,'en_pt')
        self.assertEqual(len(self.engine.opener.requests),count)
        self.engine.translate('olá','pt_en')
        self.assertEqual(json.loads(self.engine.opener.requests[-1].data)['source_lang'],'PT')
    def test_quota_and_bad_key_pause_without_retry(self):
        for code in (403,429,456):
            self.engine.key='example';self.engine.blocked=False;self.engine.opener.status=code
            count=len(self.engine.opener.requests)
            with self.assertRaises(NeedsAttention):self.engine.translate('new text','en_pt')
            self.assertTrue(self.engine.blocked)
            self.assertEqual(len(self.engine.opener.requests),count+1)
            with self.assertRaises(NeedsAttention):self.engine.translate('new text','en_pt')
            self.assertEqual(len(self.engine.opener.requests),count+1)
    def test_key_not_saved_in_preferences(self):
        import tempfile
        from pathlib import Path
        import engine
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder, patch.object(engine,'DATA',Path(folder)):
            engine.save_settings({'layout':'Lateral','folder':'example'})
            self.assertNotIn('key',engine.load_settings())
        self.engine.configure('example');self.engine.close()
        self.assertEqual(self.engine.key,'')

if __name__=='__main__':unittest.main()
