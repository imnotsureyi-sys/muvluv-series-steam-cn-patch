import struct
import unittest

from rUGP.packaging.build_photon_player import BACKLOG_ACTION, BACKLOG_SITES, verify_backlog_actions
from rUGP.tests.catalog.test_rio_inventory import class_ref
from rUGP.tests.formats.rio.test_crsa_vm_stream import archive, common


def fixture(game, text=BACKLOG_ACTION, *, wrong_callee=False, omit_last=False):
    _, _, orders, callee = BACKLOG_SITES[game]
    commands = []
    for order in range(1, max(orders)+1):
        if order not in orders or (omit_last and order == max(orders)):
            commands.append(class_ref('CVmRet', 21)+common())
            continue
        resource = class_ref('CRsa', 5)+struct.pack('<HIIHB', 0xC108, callee+int(wrong_callee), 0, 0, 0)
        fields = struct.pack('<I', 1)+b'\0'
        fields += struct.pack('<I', 1)+b'\xff\xfe\xff'+bytes((len(text),))+text.encode('utf-16le')
        fields += (struct.pack('<I', 1)+b'\0')*7
        preload = b'\0' if order == min(orders) else b''
        commands.append(class_ref('CVmCall', 21)+common()+preload+resource+struct.pack('<H', 9)+fields+b'\0')
    return archive(b''.join(commands), len(commands))


class BacklogActionTests(unittest.TestCase):
    def test_native_action_survives_both_game_bindings(self):
        for game in BACKLOG_SITES:
            verify_backlog_actions(fixture(game), game)

    def test_translation_padding_and_missing_or_wrong_binding_are_rejected(self):
        for game in BACKLOG_SITES:
            for options in ({'text': r'\A关闭回看'}, {'text': BACKLOG_ACTION+'\u2060'},
                            {'wrong_callee': True}, {'omit_last': True}):
                with self.subTest(game=game, options=options), self.assertRaisesRegex(ValueError, 'backlog'):
                    verify_backlog_actions(fixture(game, **options), game)


if __name__ == '__main__':
    unittest.main()
