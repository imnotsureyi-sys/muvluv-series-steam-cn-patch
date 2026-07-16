import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "patch_uistring", ROOT / "tools" / "uistring" / "patch_uistring.py"
)
patch_uistring = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(patch_uistring)


class PatchUiStringTests(unittest.TestCase):
    def test_tsv_backslash_t_represents_an_in_field_tab(self):
        with tempfile.TemporaryDirectory() as td:
            table = Path(td) / "changes.tsv"
            table.write_text(
                "id\tjp\tzh_cn\n50002\t前半\\t後半\t中文\\t换行\n",
                encoding="utf-8",
            )

            changes = patch_uistring.load_changes(table)

            self.assertEqual(changes["50002"].expected, "前半\t後半")
            self.assertEqual(changes["50002"].replacement, "中文\t换行")

    def test_only_whitelisted_visible_field_changes(self):
        source = (
            "50002::msg_go_title::タイトル画面に戻ります。::::::\n"
            "50021::msg_autospeed::(使用していません)::::::\n"
        )
        changes = {
            "50002": patch_uistring.Change(
                expected="タイトル画面に戻ります。", replacement="返回标题画面。"
            )
        }

        result = patch_uistring.apply_changes(source, changes)

        self.assertEqual(
            result,
            "50002::msg_go_title::返回标题画面。::::::\n"
            "50021::msg_autospeed::(使用していません)::::::\n",
        )

    def test_expected_japanese_is_strict(self):
        with self.assertRaisesRegex(ValueError, "50002"):
            patch_uistring.apply_changes(
                "50002::msg_go_title::別の原文::::::\n",
                {
                    "50002": patch_uistring.Change(
                        expected="タイトル画面に戻ります。", replacement="返回标题画面。"
                    )
                },
            )

    def test_missing_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "50003"):
            patch_uistring.apply_changes(
                "50002::msg_go_title::タイトル画面に戻ります。::::::\n",
                {"50003": patch_uistring.Change(expected="ロード", replacement="读取")},
            )


if __name__ == "__main__":
    unittest.main()
