import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rUGP.formats.rio.crsa import CRSA_PREFIX, encode_crsa_encrypted
from rUGP.tools.text.audit_crsa_display_gaps import audit


class CrsaCensusTests(unittest.TestCase):
    def test_all_six_byte_signatures_and_failures_are_accounted_for(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);rio=root/'fixture.rio';(root/'fixture.rio.ici').write_bytes(b'ICI')
            payload='\x05翻译\x00'.encode('utf-16le')
            first=CRSA_PREFIX+b'\x00'*5+encode_crsa_encrypted(payload)
            second=CRSA_PREFIX+b'\x17\x01\x42\x03\x44'+encode_crsa_encrypted(payload)
            bad=CRSA_PREFIX+bytes(13)
            raw=b'prefix'+first+b'gap'+second+bad;rio.write_bytes(raw)
            with patch('rUGP.tools.text.audit_crsa_display_gaps.build_inventory',return_value={'nodes':[]}):
                audit(root,root/'out')
            result=json.loads((root/'out/census.json').read_text())['volumes'][0]
            self.assertEqual(result['signatures'],3)
            self.assertEqual(len(result['blocks']),2)
            self.assertEqual(len(result['failures']),1)
            self.assertEqual([r['offset'] for r in result['blocks']],[6,6+len(first)+3])
            self.assertEqual(rio.read_bytes(),raw)


if __name__=='__main__':
    unittest.main()
