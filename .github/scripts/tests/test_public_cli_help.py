from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]

SCRIPT_COMMANDS = (
    "age2/tools/fpd/fpd_codec.py",
    "age2/tools/fpd/extract_fpd.py",
    "age2/tools/egpack/extract_egpack_manifest.py",
    "age2/tools/egpack/build_changes.py",
    "age2/tools/egpack/repack_egpack.py",
    "age2/tools/egpack/verify_egpack.py",
    "age2/tools/text/export_portable_translation.py",
    "age2/tools/uistring/patch_uistring.py",
    "age2/games/imperial-capital-burns/tools/build_phase1.py",
    "rugp/packaging/build_photon_cn_beta01.py",
    "rugp/runtime/build.py",
    "rugp/tools/images/verify_route_closure.py",
    "rugp/tools/provenance/verify_photon_images_v6.py",
    "rugp/tools/provenance/export_portable_photon_snapshot.py",
    "rugp/tools/provenance/audit_photon_locale_bindings.py",
)

MODULE_COMMANDS = (
    "localization.tools.font_coverage",
    "localization.tools.images.build_deterministic_textless_background",
    "localization.tools.images.render_deterministic_localized_text",
    "localization.tools.images.verify_localized_image_invariants",
    "localization.tools.images.verify_localized_group_consistency",
    "localization.tools.verify_steam_depot_manifest",
    "localization.tools.create_locale_template",
    "rugp.packaging.steam_locale_preflight",
    "rugp.tools.catalog.rio_inventory",
    "rugp.tools.images.decode_record",
    "rugp.tools.text.export_reviewed_translation",
    "rugp.tools.text.split_reviewed_translation",
    "rugp.tools.text.extract_crsa_text",
)


class PublicCliHelpTests(unittest.TestCase):
    def assert_help_works(self, command: list[str]) -> None:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=(
                f"public CLI help failed: {command!r}\n"
                f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            ),
        )
        self.assertIn("usage:", (completed.stdout + completed.stderr).casefold())

    def test_documented_script_entry_points_import_and_show_help(self) -> None:
        for relative in SCRIPT_COMMANDS:
            with self.subTest(script=relative):
                self.assert_help_works([sys.executable, relative, "--help"])

    def test_documented_module_entry_points_import_and_show_help(self) -> None:
        for module in MODULE_COMMANDS:
            with self.subTest(module=module):
                self.assert_help_works([sys.executable, "-m", module, "--help"])


if __name__ == "__main__":
    unittest.main()
