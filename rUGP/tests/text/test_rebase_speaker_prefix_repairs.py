import unittest
from rUGP.tools.text.rebase_speaker_prefix_repairs import rebase_delimiters


class RebaseSpeakerTests(unittest.TestCase):
    def test_current_layout_survives_bracket_repair(self):
        self.assertEqual(rebase_delimiters('\x05纯夏【你好，\n小武。】', '\x05纯夏【你好，\x03小武。】',
                                          '\x05【纯夏】「你好，\x03小武。」'), '\x05【纯夏】「你好，\n小武。」')

    def test_missing_prefix_preserves_layout_and_terminal_contract(self):
        self.assertEqual(rebase_delimiters('算了。\n下次再说。\x01', '算了。下次再说。\x01',
                                          '【武】「算了。下次再说。」\x01'), '【武】「算了。\n下次再说。」\x01')

    def test_already_repaired_is_not_overwritten(self):
        current = '【武】「你好，\n纯夏。」\x01'
        self.assertEqual(rebase_delimiters(current, '武【你好，纯夏。】\x01', '【武】「你好，纯夏。」\x01'), current)

    def test_new_wording_requires_review(self):
        with self.assertRaisesRegex(ValueError, 'wording'):
            rebase_delimiters('武【再见。】\x01', '武【你好。】\x01', '【武】「你好。」\x01')


if __name__ == '__main__':
    unittest.main()
