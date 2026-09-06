from io import BytesIO
import unittest

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from localization.tools.extend_font_subset import extend, sha, glyph_state


def font(character, units=1000):
    builder=FontBuilder(units,isTTF=True)
    order=['.notdef','sample'];builder.setupGlyphOrder(order)
    pen=TTGlyphPen(None);pen.moveTo((50,0));pen.lineTo((450,0));pen.lineTo((250,600));pen.closePath()
    builder.setupGlyf({'.notdef':TTGlyphPen(None).glyph(),'sample':pen.glyph()})
    builder.setupHorizontalMetrics({name:(500,50) for name in order})
    builder.setupHorizontalHeader(ascent=800,descent=-200)
    builder.setupCharacterMap({ord(character):'sample'})
    builder.setupNameTable({'familyName':'Synthetic','styleName':'Regular','psName':'Synthetic-Regular'})
    builder.setupOS2();builder.setupPost();builder.setupMaxp()
    stream=BytesIO();builder.save(stream);return stream.getvalue()


class FontExtensionTests(unittest.TestCase):
    def test_addition_retains_old_outline_metrics_and_glyph_id(self):
        base,donor=font('A'),font('中')
        output,report=extend(base,donor,'中',sha(base),sha(donor))
        old=TTFont(BytesIO(base));new=TTFont(BytesIO(output));source=TTFont(BytesIO(donor))
        self.assertEqual(glyph_state(old,old.getBestCmap()[65]),glyph_state(new,new.getBestCmap()[65]))
        self.assertEqual(1,new.getGlyphID(new.getBestCmap()[65]))
        self.assertEqual(glyph_state(source,source.getBestCmap()[ord('中')]),glyph_state(new,new.getBestCmap()[ord('中')]))
        self.assertEqual(3,report['new_glyph_count'])

    def test_does_not_overwrite_existing_character(self):
        base,donor=font('A'),font('A')
        with self.assertRaisesRegex(ValueError,'absent'):
            extend(base,donor,'A',sha(base),sha(donor))

    def test_rejects_changed_font_hash_missing_character_or_wrong_scale(self):
        base,donor=font('A'),font('中')
        with self.assertRaisesRegex(ValueError,'hash'):
            extend(base,donor,'中','0'*64,sha(donor))
        with self.assertRaisesRegex(ValueError,'missing'):
            extend(base,donor,'文',sha(base),sha(donor))
        donor=font('中',2048)
        with self.assertRaisesRegex(ValueError,'units'):
            extend(base,donor,'中',sha(base),sha(donor))


if __name__=='__main__':unittest.main()
