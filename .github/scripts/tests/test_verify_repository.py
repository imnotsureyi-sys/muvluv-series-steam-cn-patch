from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "verify_repository.py"
SPEC = importlib.util.spec_from_file_location("verify_repository", SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import machinery failure
    raise RuntimeError("could not load repository verifier")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RepositoryPolicyHelperTests(unittest.TestCase):
    def test_only_visible_markdown_links_count_as_release_links(self) -> None:
        visible = "[download](https://example.invalid/patch.zip)"
        hidden = (
            "<!-- [hidden](https://example.invalid/comment.zip) -->\n"
            "```markdown\n[code](https://example.invalid/code.zip)\n```\n"
            "`[inline](https://example.invalid/inline.zip)`"
        )
        self.assertEqual(
            MODULE.markdown_link_targets(visible + "\n" + hidden),
            {"https://example.invalid/patch.zip"},
        )

    def test_release_components_cannot_escape_the_expected_url(self) -> None:
        for value in ("../other", "owner/release", ".", "tag with spaces"):
            with self.subTest(value=value):
                self.assertIsNone(MODULE.SAFE_RELEASE_TAG.fullmatch(value))
        self.assertIsNotNone(MODULE.SAFE_RELEASE_TAG.fullmatch("tda01-beta0.2.2"))
        self.assertIsNotNone(
            MODULE.SAFE_RELEASE_COMPONENT.fullmatch("MuvLuv_TDA01_Patch.zip")
        )

    def test_public_tree_is_text_allowlisted_not_binary_blacklisted(self) -> None:
        for name in (
            "payload.bin",
            "runtime.so",
            "video.mp4",
            "font.woff2",
            "database.sqlite",
            ".env",
            "id_rsa",
        ):
            with self.subTest(name=name):
                self.assertFalse(MODULE.is_allowed_public_path(Path(name)))
        for name in ("tool.py", "table.csv", "README.md", ".gitignore", "LICENSE"):
            with self.subTest(name=name):
                self.assertTrue(MODULE.is_allowed_public_path(Path(name)))

    def test_generated_and_private_roots_stay_forbidden_when_force_added(self) -> None:
        for relative in (
            "outputs/leak.json",
            "output/report.txt",
            "archive/source.csv",
            "local-internal/handoff.md",
            "release_v9/package.txt",
            "workspace_full_copy_1/data.json",
        ):
            with self.subTest(relative=relative):
                self.assertTrue(MODULE.is_forbidden_public_path(relative))
        self.assertFalse(MODULE.is_forbidden_public_path("rUGP/tools/README.md"))

    def test_high_confidence_secret_markers_are_detected(self) -> None:
        samples = {
            "private-key material": "-----BEGIN " + "PRIVATE KEY-----",
            "GitHub token": "gh" + "p_" + "A" * 40,
            "GitHub fine-grained token": "github_" + "pat_" + "A" * 50,
            "AWS access key": "AK" + "IA" + "A" * 16,
            "OpenAI-style API key": "s" + "k-" + "A" * 30,
        }
        for expected, sample in samples.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, MODULE.secret_marker_labels(sample))
        self.assertEqual(MODULE.secret_marker_labels("ordinary documentation"), [])


if __name__ == "__main__":
    unittest.main()
