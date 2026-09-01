from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]

SCRIPT_COMMANDS = (
    "AGE2/tools/fpd/fpd_codec.py",
    "AGE2/tools/fpd/extract_fpd.py",
    "AGE2/tools/egpack/extract_egpack_manifest.py",
    "AGE2/tools/egpack/build_changes.py",
    "AGE2/tools/egpack/repack_egpack.py",
    "AGE2/tools/egpack/verify_egpack.py",
    "AGE2/tools/text/export_portable_translation.py",
    "AGE2/tools/uistring/patch_uistring.py",
    "AGE2/games/imperial-capital-burns/tools/build_phase1.py",
    "rUGP/packaging/build_photon_cn_beta01.py",
    "rUGP/runtime/build.py",
    "rUGP/tools/images/verify_route_closure.py",
    "rUGP/tools/provenance/verify_photon_images_v6.py",
    "rUGP/tools/provenance/export_portable_photon_snapshot.py",
    "rUGP/tools/provenance/audit_photon_locale_bindings.py",
)

MODULE_COMMANDS = (
    "localization.tools.font_coverage",
    "localization.tools.images.build_deterministic_textless_background",
    "localization.tools.images.render_deterministic_localized_text",
    "localization.tools.images.verify_localized_image_invariants",
    "localization.tools.images.verify_localized_group_consistency",
    "localization.tools.verify_steam_depot_manifest",
    "localization.tools.create_locale_template",
    "rUGP.packaging.steam_locale_preflight",
    "rUGP.tools.catalog.rio_inventory",
    "rUGP.tools.images.decode_record",
    "rUGP.tools.text.export_reviewed_translation",
    "rUGP.tools.text.split_reviewed_translation",
    "rUGP.tools.text.extract_crsa_text",
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
