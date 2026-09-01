#!/usr/bin/env python3
"""Fail CI when the public Git tree violates repository boundaries."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_TOP_LEVEL = (
    ".imagegen-venv/",
    ".playwright-cli/",
    ".venv-imagegen/",
    ".venv/",
    "archive/",
    "chapters/",
    "dist/",
    "glossary/",
    "local-internal/",
    "output/",
    "outputs/",
    "patch-sources/",
    "release/",
    "release_v",
    "release-notes/",
    "review/",
    "screenshots/",
    "standards/",
    "tests/",
    "tools/",
    "work/",
    "work_archive_",
    "workspace_full_copy_",
)
TEXT_SUFFIXES = {
    ".c", ".csv", ".def", ".h", ".json", ".md", ".ps1", ".py", ".s",
    ".toml", ".tsv", ".txt", ".yaml", ".yml",
}
ALLOWED_EXTENSIONLESS = {".gitattributes", ".gitignore", "LICENSE"}
REQUIRED = {
    "README.md", "docs/en/README.md", "docs/project/CONTRIBUTING.md",
    "docs/project/ROADMAP.md", "LICENSE", "docs/legal/NOTICE.md",
    "docs/legal/THIRD_PARTY.md", "localization/README.md",
    "AGE2/README.md", "rUGP/README.md", "AGE2/requirements.txt",
    "rUGP/requirements.txt", "rUGP/runtime/README.md",
    "localization/requirements.txt",
    "docs/player/README.md", "docs/en/player-guide.md", "docs/README.md",
    "docs/research/repository-architecture.md", "docs/research/README.md",
    "docs/en/research-index.md",
    "docs/player/release-index.json",
    ".github/scripts/tests/test_verify_repository.py",
    ".github/scripts/tests/test_public_cli_help.py",
    "localization/new-locale.md",
    "localization/tools/verify_steam_depot_manifest.py",
    "AGE2/tools/text/build_review_ledger.py",
    "AGE2/docs/postmortems/loose-overlay-boundary.md",
    "AGE2/docs/postmortems/structural-empty-records.md",
    "AGE2/docs/postmortems/font-glyph-substitution-retired.md",
    "AGE2/docs/postmortems/public-snapshot-release-alignment.md",
    "AGE2/evidence/text-review-ledger-v1/pending.csv",
    "AGE2/evidence/text-review-ledger-v1/manifest.json",
    "AGE2/games/imperial-capital-burns/images/copy/source-image-lock.v2.json",
    "rUGP/tools/images/decode_record.py",
    "rUGP/packaging/steam_locale_preflight.py",
    "rUGP/docs/postmortems/ici-resize-metadata.md",
    "rUGP/docs/postmortems/image-transport-runtime.md",
    "rUGP/evidence/photon-image-routes-v1/routes_1490.v1.json",
    "rUGP/evidence/photon-reviewed-text-v1/manifest.json",
}
ABSOLUTE_WORKSTATION_PATH = re.compile(
    r"(?i)(?:[a-z]:[\\/](?:users|steam|steamlibrary|chromedownloads)[\\/]"
    r"|[\\/]\.codex[\\/]worktrees[\\/])"
)
ABSOLUTE_PATH_EXCEPTIONS = {
    # Deliberately malicious input used to prove the package path guard.
    "rUGP/tests/packaging/test_build_photon_cn_beta01.py",
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
FENCED_CODE = re.compile(
    r"^```.*?^```[ \t]*$|^~~~.*?^~~~[ \t]*$", re.MULTILINE | re.DOTALL
)
INLINE_CODE = re.compile(r"`[^`\n]*`")
SHA256 = re.compile(r"^[0-9A-F]{64}$")
SAFE_RELEASE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")
SAFE_RELEASE_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
EXPECTED_PLAYER_GAMES = {
    "tda00", "tda01", "tda02", "tda03", "imperial-capital-burns"
}
EXPECTED_DISTRIBUTION_FINDINGS = {
    "historical-player-zips-bundle-font-files-without-license-notices",
    "some-historical-player-zips-bundle-byte-identical-official-ui-fallbacks",
    "photon-images-v6-includes-19-byte-identical-official-source-images",
}
EXPECTED_OBSOLETE_RELEASES = {
    "tda01-beta0.1": "tda01-beta0.2.2",
    "tda01-beta0.2": "tda01-beta0.2.2",
    "tda01-beta0.2.1": "tda01-beta0.2.2",
    "tda03-beta0.1": "tda03-beta0.1.6",
}
SECRET_PATTERNS = (
    (
        "private-key material",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    (
        "GitHub fine-grained token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,255}\b"),
    ),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
)


def public_worktree_files() -> list[str]:
    """Return tracked plus not-ignored new files that exist in the worktree.

    Including new files makes the command useful before a commit, while filtering
    missing paths lets an intentional tracked deletion be validated before it is
    staged.  CI sees the same set as the committed tree.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(
        {
            item.decode("utf-8")
            for item in result.stdout.split(b"\0")
            if item
            and (
                (ROOT / item.decode("utf-8")).is_file()
                or (ROOT / item.decode("utf-8")).is_symlink()
            )
        }
    )


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_links(path: Path, relative: str, text: str, errors: list[str]) -> None:
    for raw in MARKDOWN_LINK.findall(text):
        target = raw.strip().split(maxsplit=1)[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = unquote(target.split("#", 1)[0])
        resolved = (path.parent / target).resolve(strict=False)
        try:
            resolved.relative_to(ROOT)
        except ValueError:
            fail(errors, f"{relative}: local link escapes repository: {raw}")
            continue
        if not resolved.exists():
            fail(errors, f"{relative}: broken local link: {raw}")


def markdown_link_targets(text: str) -> set[str]:
    """Return actual Markdown href targets, excluding link-label substrings."""

    visible = HTML_COMMENT.sub("", text)
    visible = FENCED_CODE.sub("", visible)
    visible = INLINE_CODE.sub("", visible)
    return {
        raw.strip().split(maxsplit=1)[0].strip("<>")
        for raw in MARKDOWN_LINK.findall(visible)
    }


def is_allowed_public_path(path: Path) -> bool:
    return (
        path.suffix.casefold() in TEXT_SUFFIXES
        or path.name in ALLOWED_EXTENSIONLESS
    )


def is_forbidden_public_path(relative: str) -> bool:
    return relative.casefold().startswith(FORBIDDEN_TOP_LEVEL)


def secret_marker_labels(text: str) -> list[str]:
    return [label for label, pattern in SECRET_PATTERNS if pattern.search(text)]


def check_release_index(errors: list[str]) -> None:
    relative = "docs/player/release-index.json"
    path = ROOT / relative
    if not path.is_file():
        return
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(errors, f"{relative}: invalid UTF-8 JSON: {exc}")
        return

    if document.get("schema") != "muvluv-community-release-index/v1":
        fail(errors, f"{relative}: unsupported schema")
    if document.get("scope") != "current-listed-player-packages-and-research-assets":
        fail(errors, f"{relative}: release-index scope is missing or ambiguous")
    distribution_review = document.get("distribution_review")
    if not isinstance(distribution_review, dict):
        fail(errors, f"{relative}: distribution review is missing")
    else:
        if distribution_review.get("status") != "pending-remediation":
            fail(errors, f"{relative}: distribution review status is not pending-remediation")
        findings = distribution_review.get("blocking_findings")
        if not isinstance(findings, list) or set(findings) != EXPECTED_DISTRIBUTION_FINDINGS:
            fail(errors, f"{relative}: distribution review findings differ from the audited set")
        if distribution_review.get("policy") != "docs/project/asset-and-release-policy.md":
            fail(errors, f"{relative}: distribution review policy link is invalid")
    packages = document.get("player_packages")
    obsolete_releases = document.get("obsolete_releases")
    research_assets = document.get("research_assets")
    if (
        not isinstance(packages, list)
        or not isinstance(obsolete_releases, list)
        or not isinstance(research_assets, list)
    ):
        fail(errors, f"{relative}: package arrays are missing")
        return

    game_ids: set[str] = set()
    tags: set[str] = set()
    urls: set[str] = set()
    readme_links = [
        markdown_link_targets((ROOT / name).read_text(encoding="utf-8-sig"))
        for name in ("README.md", "docs/en/README.md")
    ]
    for index, package in enumerate(packages):
        label = f"{relative}: player_packages[{index}]"
        if not isinstance(package, dict):
            fail(errors, f"{label}: entry is not an object")
            continue
        game_id = package.get("game_id")
        tag = package.get("release_tag")
        name = package.get("asset_name")
        url = package.get("asset_url")
        sha256 = package.get("asset_sha256")
        overlay = package.get("overlay_root")
        caveats = package.get("historical_caveats")
        if not isinstance(game_id, str) or game_id in game_ids:
            fail(errors, f"{label}: missing or duplicate game_id")
        else:
            game_ids.add(game_id)
        if (
            not isinstance(tag, str)
            or not SAFE_RELEASE_TAG.fullmatch(tag)
            or tag in tags
        ):
            fail(errors, f"{label}: missing or duplicate release_tag")
        else:
            tags.add(tag)
        if (
            not isinstance(name, str)
            or not SAFE_RELEASE_COMPONENT.fullmatch(name)
            or not name.casefold().endswith(".zip")
        ):
            fail(errors, f"{label}: invalid ZIP asset_name")
        expected_url = (
            "https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/"
            f"releases/download/{tag}/{name}"
        )
        if url != expected_url or url in urls:
            fail(errors, f"{label}: invalid or duplicate asset_url")
        elif isinstance(url, str):
            urls.add(url)
        if not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
            fail(errors, f"{label}: asset_sha256 is not uppercase SHA-256")
        if not isinstance(package.get("asset_bytes"), int) or package["asset_bytes"] <= 0:
            fail(errors, f"{label}: asset_bytes must be positive")
        if package.get("engine") != "age2" or package.get("locale") != "zh-Hans":
            fail(errors, f"{label}: unexpected engine or locale")
        if package.get("status") != "historical-prerelease-rights-review-pending":
            fail(errors, f"{label}: historical rights-review status is missing")
        if package.get("player_installable") is not True:
            fail(errors, f"{label}: player package is not marked installable")
        if package.get("recommended_for_download") is not False:
            fail(errors, f"{label}: rights-pending package is marked recommended")
        if package.get("distribution_approved") is not False:
            fail(errors, f"{label}: rights-pending package is marked distribution-approved")
        if not isinstance(overlay, str) or not re.fullmatch(
            r"%LOCALAPPDATA%\\ancr\\[^\\]+\\data\\root", overlay
        ):
            fail(errors, f"{label}: invalid LocalAppData overlay_root")
        if not isinstance(caveats, list) or not caveats:
            fail(errors, f"{label}: historical caveats are missing")
        if isinstance(url, str) and not all(url in links for links in readme_links):
            fail(errors, f"{label}: direct asset URL is not a Markdown link in both root READMEs")

    if game_ids != EXPECTED_PLAYER_GAMES:
        fail(
            errors,
            f"{relative}: player game set differs: "
            f"{sorted(game_ids)} != {sorted(EXPECTED_PLAYER_GAMES)}",
        )

    player_tags = set(tags)
    observed_obsolete: dict[str, str] = {}
    for index, release in enumerate(obsolete_releases):
        label = f"{relative}: obsolete_releases[{index}]"
        if not isinstance(release, dict):
            fail(errors, f"{label}: entry is not an object")
            continue
        game_id = release.get("game_id")
        tag = release.get("release_tag")
        replacement = release.get("replacement_tag")
        reason = release.get("reason")
        if game_id not in EXPECTED_PLAYER_GAMES:
            fail(errors, f"{label}: unknown game_id")
        if (
            not isinstance(tag, str)
            or not SAFE_RELEASE_TAG.fullmatch(tag)
            or tag in observed_obsolete
            or tag in player_tags
        ):
            fail(errors, f"{label}: invalid, duplicate, or current release_tag")
        elif isinstance(replacement, str):
            observed_obsolete[tag] = replacement
        if replacement not in player_tags:
            fail(errors, f"{label}: replacement_tag is not a current player package")
        if not isinstance(reason, str) or not SAFE_RELEASE_TAG.fullmatch(reason):
            fail(errors, f"{label}: invalid reason")
    if observed_obsolete != EXPECTED_OBSOLETE_RELEASES:
        fail(errors, f"{relative}: obsolete release set differs from the audited set")

    for index, asset in enumerate(research_assets):
        label = f"{relative}: research_assets[{index}]"
        if not isinstance(asset, dict):
            fail(errors, f"{label}: entry is not an object")
            continue
        tag = asset.get("release_tag")
        name = asset.get("asset_name")
        url = asset.get("asset_url")
        sha256 = asset.get("asset_sha256")
        if asset.get("player_installable") is not False:
            fail(errors, f"{label}: research asset must not be player-installable")
        if asset.get("recommended_for_download") is not False:
            fail(errors, f"{label}: rights-pending research asset is marked recommended")
        if asset.get("distribution_approved") is not False:
            fail(errors, f"{label}: rights-pending research asset is marked distribution-approved")
        if asset.get("status") != "reviewed-research-asset-rights-review-pending":
            fail(errors, f"{label}: research-asset rights-review status is missing")
        if (
            not isinstance(tag, str)
            or not SAFE_RELEASE_TAG.fullmatch(tag)
            or tag in tags
        ):
            fail(errors, f"{label}: missing or duplicate release_tag")
        else:
            tags.add(tag)
        if (
            not isinstance(name, str)
            or not SAFE_RELEASE_COMPONENT.fullmatch(name)
            or not name.casefold().endswith(".zip")
        ):
            fail(errors, f"{label}: invalid ZIP asset_name")
        expected_url = (
            "https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/"
            f"releases/download/{tag}/{name}"
        )
        if url != expected_url or url in urls:
            fail(errors, f"{label}: invalid or duplicate asset_url")
        elif isinstance(url, str):
            urls.add(url)
        if not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
            fail(errors, f"{label}: asset_sha256 is not uppercase SHA-256")
        if not isinstance(asset.get("asset_bytes"), int) or asset["asset_bytes"] <= 0:
            fail(errors, f"{label}: asset_bytes must be positive")
        if asset.get("engine") != "rugp" or asset.get("locale") != "zh-Hans":
            fail(errors, f"{label}: unexpected engine or locale")
        if not isinstance(asset.get("asset_id"), str) or not SAFE_RELEASE_TAG.fullmatch(
            asset["asset_id"]
        ):
            fail(errors, f"{label}: invalid asset_id")
        if not isinstance(asset.get("reviewed_images"), int) or asset["reviewed_images"] <= 0:
            fail(errors, f"{label}: reviewed_images must be positive")
        manifest_name = asset.get("manifest_name")
        if (
            not isinstance(manifest_name, str)
            or not SAFE_RELEASE_COMPONENT.fullmatch(manifest_name)
            or not manifest_name.casefold().endswith(".json")
        ):
            fail(errors, f"{label}: invalid manifest_name")
        if not isinstance(asset.get("manifest_sha256"), str) or not SHA256.fullmatch(
            asset["manifest_sha256"]
        ):
            fail(errors, f"{label}: manifest_sha256 is not uppercase SHA-256")
        if not isinstance(asset.get("warning"), str) or not asset["warning"]:
            fail(errors, f"{label}: non-installer warning is missing")


def main() -> int:
    files = public_worktree_files()
    present = set(files)
    errors: list[str] = []

    check_release_index(errors)

    for required in sorted(REQUIRED - present):
        fail(errors, f"missing required public file: {required}")

    for relative in files:
        if is_forbidden_public_path(relative):
            fail(errors, f"legacy top-level path is tracked: {relative}")
        path = ROOT / relative
        if path.is_symlink():
            fail(errors, f"symbolic link is not allowed in the public tree: {relative}")
        suffix = path.suffix.casefold()
        if not is_allowed_public_path(path):
            fail(errors, f"unapproved public file type: {relative}")
        if path.name.casefold() == "pack.bin" or re.search(
            r"(?i)\.rio\.\d{3}\Z", path.name
        ):
            fail(errors, f"original game container is tracked: {relative}")
        if path.is_file() and path.stat().st_size > 10 * 1024 * 1024:
            fail(errors, f"tracked file exceeds 10 MiB policy: {relative}")

        if not is_allowed_public_path(path):
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            fail(errors, f"tracked text is not UTF-8: {relative}")
            continue
        if (
            relative not in ABSOLUTE_PATH_EXCEPTIONS
            and ABSOLUTE_WORKSTATION_PATH.search(text)
        ):
            fail(errors, f"workstation-specific absolute path in public text: {relative}")
        for label in secret_marker_labels(text):
            fail(errors, f"possible {label} in public text: {relative}")
        if relative.startswith("AGE2/") and re.search(
            r"(?m)^\s*(?:from\s+rUGP\b|import\s+rUGP\b)", text
        ):
            fail(errors, f"AGE2 imports rUGP: {relative}")
        if relative.startswith("rUGP/") and re.search(
            r"(?m)^\s*(?:from\s+AGE2\b|import\s+AGE2\b)", text
        ):
            fail(errors, f"rUGP imports AGE2: {relative}")
        if suffix == ".md":
            check_links(path, relative, text, errors)

    if errors:
        print("Repository policy violations:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Repository policy passed for {len(files)} public worktree files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
