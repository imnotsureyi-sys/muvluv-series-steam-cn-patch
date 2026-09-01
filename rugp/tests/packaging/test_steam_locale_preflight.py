from __future__ import annotations

from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest

from rugp.packaging.steam_locale_preflight import (
    LocalePreflightError,
    PAIR_SCHEMA,
    main,
    parse_keyvalues,
    preflight_game_locale,
    preflight_photon_pair,
    revalidate_locale_observation,
    write_preflight_report,
)


def acf(appid: str, *, user: str = "english", mounted: str = "english") -> str:
    return (
        '"AppState"\n{\n'
        f'  "appid" "{appid}"\n'
        '  "UserConfig"\n  {\n'
        f'    "language" "{user}"\n  }}\n'
        '  "MountedConfig"\n  {\n'
        f'    "language" "{mounted}"\n  }}\n'
        '}\n'
    )


class SteamLocalePreflightTests(unittest.TestCase):
    def write_manifest(
        self, root: Path, appid: str, *, user: str = "english", mounted: str = "english"
    ) -> Path:
        path = root / f"appmanifest_{appid}.acf"
        path.write_text(acf(appid, user=user, mounted=mounted), encoding="utf-8")
        return path

    def test_confirmed_pf_and_pm_policies_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pf = self.write_manifest(root, "889700")
            pm = self.write_manifest(root, "889710")
            pf_result = preflight_game_locale(game="photonflowers", appmanifest_path=pf)
            pair = preflight_photon_pair(pf_appmanifest=pf, pm_appmanifest=pm)
        self.assertEqual(pf_result.public_report()["expected_locale"], "english")
        self.assertEqual(pair.public_report()["status"], "PASS_PREFLIGHT")
        self.assertFalse(pair.public_report()["production_write_authorization_granted"])

    def test_game_root_derives_only_its_steamapps_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            steamapps = Path(temporary) / "steamapps"
            game = steamapps / "common" / "Photon Flowers"
            game.mkdir(parents=True)
            self.write_manifest(steamapps, "889700")
            result = preflight_game_locale(game="pf", game_root=game)
        self.assertEqual(result.public_report()["appmanifest"]["path_source"], "derived")

    def test_wrong_appid_or_either_locale_fails_closed(self) -> None:
        cases = (
            ("000000", "english", "english", "appid mismatch"),
            ("889700", "japanese", "japanese", "Steam locale mismatch"),
            ("889700", "english", "japanese", "between UserConfig"),
        )
        for appid, user, mounted, message in cases:
            with self.subTest(appid=appid, user=user, mounted=mounted):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    path = root / "appmanifest_889700.acf"
                    path.write_text(acf(appid, user=user, mounted=mounted), encoding="utf-8")
                    with self.assertRaisesRegex(LocalePreflightError, message):
                        preflight_game_locale(game="pf", appmanifest_path=path)

    def test_unconfirmed_games_are_not_inferred_from_photon(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.write_manifest(Path(temporary), "889700")
            for game in ("muv-luv", "alternative", "unknown"):
                with self.subTest(game=game):
                    with self.assertRaisesRegex(LocalePreflightError, "unconfirmed"):
                        preflight_game_locale(game=game, appmanifest_path=manifest)

    def test_parser_rejects_duplicate_case_collision_and_malformed_tokens(self) -> None:
        duplicate = '"AppState" { "appid" "1" "AppID" "1" }'
        with self.assertRaisesRegex(LocalePreflightError, "duplicate/case-colliding"):
            parse_keyvalues(duplicate)
        for malformed in ('AppState { }', '"AppState" { "appid" }', '"AppState" {'):
            with self.subTest(text=malformed):
                with self.assertRaises(LocalePreflightError):
                    parse_keyvalues(malformed)

    def test_apply_time_revalidation_detects_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = self.write_manifest(Path(temporary), "889700")
            observation = preflight_game_locale(game="pf", appmanifest_path=manifest)
            revalidate_locale_observation(observation)
            manifest.write_text(acf("889700") + "// changed\n", encoding="utf-8")
            with self.assertRaisesRegex(LocalePreflightError, "changed after"):
                revalidate_locale_observation(observation)

    def test_report_is_path_redacted_atomic_and_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.write_manifest(root, "889700")
            observation = preflight_game_locale(game="pf", appmanifest_path=manifest)
            output = root / "preflight.json"
            write_preflight_report(observation, output)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn(str(root), json.dumps(report))
            self.assertEqual(report["writes_performed"], 0)
            with self.assertRaisesRegex(LocalePreflightError, "already exists"):
                write_preflight_report(observation, output)
            with self.assertRaisesRegex(LocalePreflightError, "aliases an input"):
                write_preflight_report(observation, manifest)

    def test_pair_cli_failure_uses_the_pair_schema(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = main(["photon-pair"])
        self.assertEqual(result, 2)
        report = json.loads(errors.getvalue())
        self.assertEqual(report["schema"], PAIR_SCHEMA)
        self.assertEqual(report["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
