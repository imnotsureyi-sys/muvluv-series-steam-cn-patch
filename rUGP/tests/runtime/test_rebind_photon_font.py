import struct
import unittest

from rUGP.tests.runtime.test_build import synthetic_pe
from rUGP.tools.runtime.rebind_photon_font import rebind, sha


def fixture(flags=0x40000040):
    data=bytearray(synthetic_pe())
    struct.pack_into('<I',data,0x80+24+0xE0+36,flags)
    data[0x300:0x341]=b'A'*64+b'\0'
    return bytes(data)


class FontPinTests(unittest.TestCase):
    def test_only_existing_read_only_digest_bytes_change(self):
        old=fixture();new,report=rebind(old,sha(old),'A'*64,'B'*64)
        self.assertEqual(old[:0x300],new[:0x300])
        self.assertEqual(old[0x340:],new[0x340:])
        self.assertEqual(b'B'*64,new[0x300:0x340])
        self.assertTrue(report['exact_guard_retained'])

    def test_rejects_unrecognized_runtime_duplicate_pin_and_wrong_old_pin(self):
        data=fixture()
        with self.assertRaisesRegex(ValueError,'hash'):
            rebind(data,'0'*64,'A'*64,'B'*64)
        with self.assertRaisesRegex(ValueError,'exactly one'):
            rebind(data,sha(data),'C'*64,'B'*64)
        duplicate=data+b'A'*64+b'\0'
        with self.assertRaisesRegex(ValueError,'exactly one'):
            rebind(duplicate,sha(duplicate),'A'*64,'B'*64)

    def test_never_changes_executable_or_writable_sections(self):
        for flags in [0x60000020,0xC0000040]:
            data=fixture(flags)
            with self.assertRaisesRegex(ValueError,'read-only'):
                rebind(data,sha(data),'A'*64,'B'*64)


if __name__=='__main__':unittest.main()
