import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import key_store

class KeyStoreTests(unittest.TestCase):
    def test_save_load_forget_with_mocked_windows_crypto(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(key_store,'KEY_FILE',Path(folder)/'key.dpapi'):
            self.assertEqual(key_store.load_key(),'')
            with patch.object(key_store,'_crypt',return_value=b'protected bytes'):
                key_store.save_key('secret')
            self.assertNotIn(b'secret',key_store.KEY_FILE.read_bytes())
            with patch.object(key_store,'_crypt',return_value=b'secret'):
                self.assertEqual(key_store.load_key(),'secret')
            key_store.forget_key()
            self.assertFalse(key_store.KEY_FILE.exists())
    def test_encryption_failure_never_writes_plaintext(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(key_store,'KEY_FILE',Path(folder)/'key.dpapi'), patch.object(key_store,'_crypt',side_effect=OSError('failed')):
            with self.assertRaises(OSError):key_store.save_key('secret')
            self.assertEqual(list(Path(folder).iterdir()),[])
    @unittest.skipUnless(key_store.os.name=='nt','DPAPI real exige Windows')
    def test_real_windows_crypto(self):
        text=b'test credential, not a real API key'
        encrypted=key_store._crypt(text)
        self.assertNotEqual(encrypted,text)
        self.assertEqual(key_store._crypt(encrypted,decrypt=True),text)
