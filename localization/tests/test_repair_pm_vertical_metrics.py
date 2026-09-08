from io import BytesIO
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable

from localization.tools.extend_font_subset import sha
from localization.tools.repair_pm_vertical_metrics import repair


def fixture():
    b = FontBuilder(1000, isTTF=True)
    names = ['.notdef'] + [f'original{i}' for i in range(1, 4715)] + [f'uni{c:04X}' for c in range(0xE100, 0xE1E3)]
    b.setupGlyphOrder(names)
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0)); pen.lineTo((450, 0)); pen.lineTo((250, 600)); pen.closePath()
    glyph = pen.glyph()
    b.setupGlyf({name: deepcopy(glyph) for name in names})
    b.setupHorizontalMetrics({name: (500, 50) for name in names})
    b.setupHorizontalHeader(ascent=800, descent=-200)
    b.setupVerticalMetrics({name: (1000, 280) for name in names})
    b.setupVerticalHeader(ascent=880, descent=-120)
    b.setupCharacterMap({c: f'uni{c:04X}' for c in range(0xE100, 0xE1E3)})
    b.setupNameTable({'familyName': 'Synthetic', 'styleName': 'Regular'})
    b.setupOS2(); b.setupPost(); b.setupMaxp()
    stream = BytesIO(); b.save(stream)
    font = TTFont(BytesIO(stream.getvalue()), recalcTimestamp=False)
    for tag, data in {'vhea': font.getTableData('vhea')[:-2] + struct.pack('>H', 4715),
                      'vmtx': struct.pack('>Hh', 1000, 280) * 4715}.items():
        table = DefaultTable(tag); table.data = data; font[tag] = table
    out = BytesIO(); font.save(out)
    return out.getvalue()


class PMVerticalMetricsTests(unittest.TestCase):
    def test_only_missing_pua_metrics_are_added(self):
        data = fixture()
        with patch('localization.tools.repair_pm_vertical_metrics.PM_SHA256', sha(data)):
            output, report = repair(data)
        a = TTFont(BytesIO(data), lazy=True); b = TTFont(BytesIO(output))
        self.assertEqual(4942, len(b['vmtx'].metrics))
        self.assertEqual(227, len(report['added_vertical_metrics']))
        self.assertEqual(a.reader['vmtx'], b.reader['vmtx'][:18860])
        self.assertEqual(a.getTableData('hmtx'), b.getTableData('hmtx'))
        self.assertEqual(a.getTableData('glyf'), b.getTableData('glyf'))
        self.assertEqual((1000, 280), b['vmtx']['uniE100'])

    def test_unknown_font_is_rejected_before_parsing(self):
        with self.assertRaisesRegex(ValueError, 'reviewed PM font hash'):
            repair(b'not a reviewed font')

    def test_valid_but_unexpected_structure_is_rejected(self):
        data = fixture()
        with patch('localization.tools.repair_pm_vertical_metrics.PM_SHA256', sha(data)):
            fixed, _ = repair(data)
        with patch('localization.tools.repair_pm_vertical_metrics.PM_SHA256', sha(fixed)):
            with self.assertRaisesRegex(ValueError, 'structure'):
                repair(fixed)
