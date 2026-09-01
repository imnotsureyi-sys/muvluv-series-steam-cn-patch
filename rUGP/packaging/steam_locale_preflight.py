#!/usr/bin/env python3
"""Fail-closed Steam locale preflight for future PF/PM packages.

The check is deliberately read-only.  It parses one Steam appmanifest using a
strict Valve KeyValues subset, verifies the app ID and both effective language
fields, and retains an in-memory file seal for compare-and-swap revalidation
immediately before an installer performs its first write.

Only the PF/PM policies that this project has independently observed are
encoded.  Muv-Luv and Muv-Luv Alternative are rejected instead of inheriting a
policy from a superficially similar rUGP title.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Mapping

from localization.tools.safe_output import OutputSafetyError, write_new_files


SCHEMA = "rugp-steam-locale-preflight/v1"
PAIR_SCHEMA = "rugp-photon-steam-locale-preflight/v1"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024


class LocalePreflightError(RuntimeError):
    """The manifest or requested game policy could not be proved exactly."""


@dataclass(frozen=True)
class GameLocalePolicy:
    """One manually confirmed, narrow Steam appmanifest policy."""

    key: str
    title: str
    appid: str
    required_locale: str


# These are the only public locale policies established by the project's PF/PM
# Steam-manifest observations and active English-translation-route tests.  Do
# not add a game by analogy: it needs its own manifest and runtime-route audit.
CONFIRMED_GAME_POLICIES: Mapping[str, GameLocalePolicy] = {
    "pf": GameLocalePolicy(
        key="pf",
        title="Muv-Luv photonflowers*",
        appid="889700",
        required_locale="english",
    ),
    "pm": GameLocalePolicy(
        key="pm",
        title="Muv-Luv photonmelodies♬",
        appid="889710",
        required_locale="english",
    ),
}

_ALIASES = {
    "pf": "pf",
    "photonflowers": "pf",
    "photonflowers*": "pf",
    "pm": "pm",
    "photonmelodies": "pm",
}
_KNOWN_UNCONFIRMED = {
    "ml",
    "muv-luv",
    "muvluv",
    "al",
    "alternative",
    "muv-luv alternative",
    "muv-luv-alternative",
    "muvluv alternative",
}


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    offset: int


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class _ManifestSnapshot:
    # Never serialize or display this field: reports must be workstation-neutral.
    path: Path = field(repr=False)
    source: str
    identity: _FileIdentity = field(repr=False)
    byte_count: int
    sha256: str
    payload: bytes = field(repr=False, compare=False)


@dataclass(frozen=True)
class LocaleObservation:
    """A validated report plus the private seal needed for apply-time CAS."""

    policy: GameLocalePolicy
    manifest: _ManifestSnapshot = field(repr=False)
    user_locale: str
    mounted_locale: str

    def public_report(self) -> dict[str, Any]:
        """Return a JSON-safe report containing no local absolute path."""

        return {
            "schema": SCHEMA,
            "status": "PASS",
            "mode": "read-only",
            "game": self.policy.key,
            "title": self.policy.title,
            "appid": self.policy.appid,
            "expected_locale": self.policy.required_locale,
            "observed_locale": {
                "AppState.UserConfig.language": self.user_locale,
                "AppState.MountedConfig.language": self.mounted_locale,
            },
            "appmanifest": {
                "name": f"appmanifest_{self.policy.appid}.acf",
                "path_redacted": True,
                "path_source": self.manifest.source,
                "bytes": self.manifest.byte_count,
                "sha256": self.manifest.sha256,
            },
            "policy_scope": "confirmed-pf-pm-steam-locale-only",
            "writes_performed": 0,
            "production_write_authorization_granted": False,
            "apply_time_revalidation_required": True,
        }

    def input_paths(self) -> tuple[Path, ...]:
        """Private inputs used only to prevent report/input aliasing."""

        return (self.manifest.path,)


@dataclass(frozen=True)
class PhotonPairObservation:
    pf: LocaleObservation
    pm: LocaleObservation

    def public_report(self) -> dict[str, Any]:
        return {
            "schema": PAIR_SCHEMA,
            "status": "PASS_PREFLIGHT",
            "mode": "read-only",
            "games": {
                "pf": self.pf.public_report(),
                "pm": self.pm.public_report(),
            },
            "write_scope": [],
            "writes_performed": 0,
            "production_write_authorization_granted": False,
            "apply_time_revalidation_required": True,
        }

    def input_paths(self) -> tuple[Path, ...]:
        return (*self.pf.input_paths(), *self.pm.input_paths())


def _tokenize_keyvalues(text: str) -> list[_Token]:
    """Tokenize the quoted scalar/object subset used by Steam ACF files."""

    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character == "/" and index + 1 < len(text) and text[index + 1] == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if character == "{":
            tokens.append(_Token("lbrace", character, index))
            index += 1
            continue
        if character == "}":
            tokens.append(_Token("rbrace", character, index))
            index += 1
            continue
        if character != '"':
            raise LocalePreflightError(
                f"malformed appmanifest: unquoted token at character {index}"
            )

        start = index
        index += 1
        value: list[str] = []
        while index < len(text):
            character = text[index]
            if character == '"':
                index += 1
                scalar = "".join(value)
                if not scalar:
                    raise LocalePreflightError(
                        f"malformed appmanifest: empty quoted token at character {start}"
                    )
                tokens.append(_Token("string", scalar, start))
                break
            if character in "\r\n" or ord(character) < 0x20:
                raise LocalePreflightError(
                    f"malformed appmanifest: control character in string at character {start}"
                )
            if character == "\\":
                if index + 1 >= len(text):
                    raise LocalePreflightError(
                        f"malformed appmanifest: trailing escape at character {index}"
                    )
                escaped = text[index + 1]
                escape_map = {
                    '"': '"',
                    "\\": "\\",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                }
                if escaped not in escape_map:
                    raise LocalePreflightError(
                        f"malformed appmanifest: unsupported escape at character {index}"
                    )
                value.append(escape_map[escaped])
                index += 2
                continue
            value.append(character)
            index += 1
        else:
            raise LocalePreflightError(
                f"malformed appmanifest: unterminated string at character {start}"
            )
    return tokens


def parse_keyvalues(text: str) -> dict[str, Any]:
    """Parse strict Valve KeyValues and reject duplicate/case-colliding keys."""

    tokens = _tokenize_keyvalues(text)
    position = 0

    def parse_pairs(*, nested: bool) -> dict[str, Any]:
        nonlocal position
        result: dict[str, Any] = {}
        folded_keys: dict[str, str] = {}
        while position < len(tokens):
            token = tokens[position]
            if token.kind == "rbrace":
                if not nested:
                    raise LocalePreflightError(
                        f"malformed appmanifest: unmatched closing brace at {token.offset}"
                    )
                position += 1
                return result
            if token.kind != "string":
                raise LocalePreflightError(
                    f"malformed appmanifest: expected quoted key at {token.offset}"
                )
            key = token.value
            folded = key.casefold()
            if folded in folded_keys:
                raise LocalePreflightError(
                    "ambiguous appmanifest: duplicate/case-colliding key "
                    f"{key!r} conflicts with {folded_keys[folded]!r}"
                )
            folded_keys[folded] = key
            position += 1
            if position >= len(tokens):
                raise LocalePreflightError(
                    f"malformed appmanifest: key {key!r} has no value"
                )
            value_token = tokens[position]
            if value_token.kind == "string":
                value: Any = value_token.value
                position += 1
            elif value_token.kind == "lbrace":
                position += 1
                value = parse_pairs(nested=True)
            else:
                raise LocalePreflightError(
                    f"malformed appmanifest: key {key!r} has an invalid value"
                )
            result[key] = value
        if nested:
            raise LocalePreflightError("malformed appmanifest: unclosed object")
        return result

    parsed = parse_pairs(nested=False)
    if position != len(tokens):
        raise LocalePreflightError("malformed appmanifest: trailing tokens")
    return parsed


def _casefold_get(mapping: Mapping[str, Any], key: str, *, context: str) -> Any:
    matches = [
        value for candidate, value in mapping.items() if candidate.casefold() == key.casefold()
    ]
    if len(matches) != 1:
        qualifier = "missing" if not matches else "ambiguous"
        raise LocalePreflightError(f"{qualifier} {context}.{key}")
    return matches[0]


def _required_object(
    mapping: Mapping[str, Any], key: str, *, context: str
) -> Mapping[str, Any]:
    value = _casefold_get(mapping, key, context=context)
    if not isinstance(value, Mapping):
        raise LocalePreflightError(f"{context}.{key} must be an object")
    return value


def _required_scalar(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = _casefold_get(mapping, key, context=context)
    if not isinstance(value, str) or not value.strip():
        raise LocalePreflightError(f"{context}.{key} must be a non-empty quoted scalar")
    return value


def _file_identity(value: os.stat_result) -> _FileIdentity:
    return _FileIdentity(
        device=value.st_dev,
        inode=value.st_ino,
        size=value.st_size,
        mtime_ns=value.st_mtime_ns,
    )


def _snapshot_manifest(path: Path, *, source: str) -> _ManifestSnapshot:
    """Read one stable regular file without exposing its absolute path."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    try:
        before_path = absolute.stat(follow_symlinks=False)
    except OSError as exc:
        raise LocalePreflightError("appmanifest is missing or inaccessible") from exc
    if stat.S_ISLNK(before_path.st_mode):
        raise LocalePreflightError("appmanifest symlinks are not accepted")
    if not stat.S_ISREG(before_path.st_mode):
        raise LocalePreflightError("appmanifest is not a regular file")
    if before_path.st_size <= 0 or before_path.st_size > MAX_MANIFEST_BYTES:
        raise LocalePreflightError("appmanifest size is outside the accepted bound")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise LocalePreflightError("appmanifest cannot be opened safely") from exc
    try:
        with os.fdopen(descriptor, "rb") as stream:
            before_handle = os.fstat(stream.fileno())
            if not stat.S_ISREG(before_handle.st_mode):
                raise LocalePreflightError("appmanifest is not a regular file")
            if _file_identity(before_handle) != _file_identity(before_path):
                raise LocalePreflightError("appmanifest changed before it was read")
            payload = stream.read(MAX_MANIFEST_BYTES + 1)
            after_handle = os.fstat(stream.fileno())
    except OSError as exc:
        raise LocalePreflightError("appmanifest could not be read completely") from exc

    try:
        after_path = absolute.stat(follow_symlinks=False)
    except OSError as exc:
        raise LocalePreflightError("appmanifest changed while it was read") from exc
    identity = _file_identity(before_handle)
    if identity != _file_identity(after_handle) or identity != _file_identity(after_path):
        raise LocalePreflightError("appmanifest changed while it was read")
    if len(payload) != identity.size or len(payload) > MAX_MANIFEST_BYTES:
        raise LocalePreflightError("appmanifest read length differs from its stable size")

    return _ManifestSnapshot(
        path=absolute,
        source=source,
        identity=identity,
        byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest().upper(),
        payload=payload,
    )


def _steamapps_candidates(game_root: Path) -> list[Path]:
    try:
        resolved = game_root.resolve(strict=True)
    except OSError as exc:
        raise LocalePreflightError("game root is missing or inaccessible") from exc
    if not resolved.is_dir():
        raise LocalePreflightError("game root is not a directory")
    candidates = [
        ancestor.parent
        for ancestor in (resolved, *resolved.parents)
        if ancestor.name.casefold() == "common"
        and ancestor.parent.name.casefold() == "steamapps"
    ]
    return list(dict.fromkeys(candidate.resolve() for candidate in candidates))


def _resolve_manifest_path(
    *, policy: GameLocalePolicy, game_root: Path | None, explicit_path: Path | None
) -> tuple[Path, str]:
    expected_name = f"appmanifest_{policy.appid}.acf"
    steamapps: list[Path] = []
    if game_root is not None:
        steamapps = _steamapps_candidates(game_root)
        if len(steamapps) > 1:
            raise LocalePreflightError("game root has ambiguous Steam library ancestry")

    if explicit_path is not None:
        if explicit_path.name.casefold() != expected_name.casefold():
            raise LocalePreflightError(
                f"explicit appmanifest basename must be {expected_name}"
            )
        explicit_absolute = Path(os.path.abspath(os.fspath(explicit_path)))
        if steamapps:
            derived = steamapps[0] / expected_name
            if explicit_absolute.resolve(strict=False) != derived.resolve(strict=False):
                raise LocalePreflightError(
                    "explicit appmanifest conflicts with the game-root manifest"
                )
        return explicit_absolute, "explicit"

    if game_root is None:
        raise LocalePreflightError("provide a game root or explicit appmanifest")
    if len(steamapps) != 1:
        raise LocalePreflightError(
            "game root is not under exactly one steamapps/common directory"
        )
    return steamapps[0] / expected_name, "derived"


def _resolve_policy(game: str) -> GameLocalePolicy:
    normalized = game.strip().casefold()
    if normalized in _KNOWN_UNCONFIRMED:
        raise LocalePreflightError(
            "unconfirmed: no public Steam locale policy exists for Muv-Luv or "
            "Muv-Luv Alternative; refusing to infer one from PF/PM"
        )
    key = _ALIASES.get(normalized)
    if key is None:
        raise LocalePreflightError(f"unknown or unconfirmed game policy: {game!r}")
    return CONFIRMED_GAME_POLICIES[key]


def _decode_manifest(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LocalePreflightError("appmanifest is not valid UTF-8/ASCII") from exc
    if "\x00" in text:
        raise LocalePreflightError("appmanifest contains NUL bytes")
    return parse_keyvalues(text)


def _validate_manifest(
    policy: GameLocalePolicy, snapshot: _ManifestSnapshot
) -> LocaleObservation:
    root = _decode_manifest(snapshot.payload)
    if len(root) != 1:
        raise LocalePreflightError(
            "ambiguous appmanifest: expected exactly one AppState root"
        )
    app_state = _required_object(root, "AppState", context="root")
    observed_appid = _required_scalar(app_state, "appid", context="AppState").strip()
    if observed_appid != policy.appid:
        raise LocalePreflightError(
            f"appid mismatch: expected {policy.appid}, observed {observed_appid}"
        )
    user_config = _required_object(app_state, "UserConfig", context="AppState")
    mounted_config = _required_object(app_state, "MountedConfig", context="AppState")
    user_locale = _required_scalar(
        user_config, "language", context="AppState.UserConfig"
    ).strip().casefold()
    mounted_locale = _required_scalar(
        mounted_config, "language", context="AppState.MountedConfig"
    ).strip().casefold()
    if user_locale != mounted_locale:
        raise LocalePreflightError(
            "Steam locale mismatch between UserConfig.language and "
            "MountedConfig.language"
        )
    if user_locale != policy.required_locale:
        raise LocalePreflightError(
            f"Steam locale mismatch for {policy.key}: expected "
            f"{policy.required_locale!r}, observed {user_locale!r}"
        )
    return LocaleObservation(
        policy=policy,
        manifest=snapshot,
        user_locale=user_locale,
        mounted_locale=mounted_locale,
    )


def preflight_game_locale(
    *,
    game: str,
    game_root: Path | None = None,
    appmanifest_path: Path | None = None,
) -> LocaleObservation:
    """Validate one confirmed PF/PM manifest and retain an in-memory seal."""

    policy = _resolve_policy(game)
    path, source = _resolve_manifest_path(
        policy=policy, game_root=game_root, explicit_path=appmanifest_path
    )
    return _validate_manifest(policy, _snapshot_manifest(path, source=source))


def preflight_photon_pair(
    *,
    pf_root: Path | None = None,
    pm_root: Path | None = None,
    pf_appmanifest: Path | None = None,
    pm_appmanifest: Path | None = None,
) -> PhotonPairObservation:
    """Validate PF and PM independently; either failure rejects the pair."""

    return PhotonPairObservation(
        pf=preflight_game_locale(
            game="pf", game_root=pf_root, appmanifest_path=pf_appmanifest
        ),
        pm=preflight_game_locale(
            game="pm", game_root=pm_root, appmanifest_path=pm_appmanifest
        ),
    )


def revalidate_locale_observation(observation: LocaleObservation) -> LocaleObservation:
    """Re-read the exact private input and require its complete seal to match."""

    if not isinstance(observation, LocaleObservation):
        raise LocalePreflightError(
            "apply-time revalidation requires the in-memory observation, not its report"
        )
    fresh = _validate_manifest(
        observation.policy,
        _snapshot_manifest(observation.manifest.path, source=observation.manifest.source),
    )
    if (
        fresh.manifest.sha256 != observation.manifest.sha256
        or fresh.manifest.byte_count != observation.manifest.byte_count
        or fresh.manifest.identity != observation.manifest.identity
    ):
        raise LocalePreflightError("appmanifest changed after locale preflight")
    return fresh


def revalidate_photon_pair(
    observation: PhotonPairObservation,
) -> PhotonPairObservation:
    """Perform the final compare-and-swap check for both Photon manifests."""

    if not isinstance(observation, PhotonPairObservation):
        raise LocalePreflightError(
            "pair revalidation requires the in-memory observation, not its report"
        )
    return PhotonPairObservation(
        pf=revalidate_locale_observation(observation.pf),
        pm=revalidate_locale_observation(observation.pm),
    )


def _json_bytes(report: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_preflight_report(
    observation: LocaleObservation | PhotonPairObservation, output: Path
) -> None:
    """Publish one path-redacted report atomically and without replacement."""

    if not isinstance(observation, (LocaleObservation, PhotonPairObservation)):
        raise LocalePreflightError("report source is not a validated locale observation")
    try:
        write_new_files(
            {output: _json_bytes(observation.public_report())},
            inputs=observation.input_paths(),
        )
    except OutputSafetyError as exc:
        raise LocalePreflightError(
            "report output aliases an input, duplicates another output, or already exists"
        ) from exc
    except OSError as exc:
        raise LocalePreflightError("could not publish the report atomically") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate one confirmed PF/PM locale")
    check.add_argument("--game", required=True, help="pf or pm")
    check.add_argument("--game-root", type=Path)
    check.add_argument("--appmanifest", type=Path)
    check.add_argument("--report", type=Path)

    pair = subparsers.add_parser("photon-pair", help="validate PF and PM together")
    pair.add_argument("--pf-root", type=Path)
    pair.add_argument("--pm-root", type=Path)
    pair.add_argument("--pf-appmanifest", type=Path)
    pair.add_argument("--pm-appmanifest", type=Path)
    pair.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "check":
            observation: LocaleObservation | PhotonPairObservation = preflight_game_locale(
                game=args.game,
                game_root=args.game_root,
                appmanifest_path=args.appmanifest,
            )
        else:
            observation = preflight_photon_pair(
                pf_root=args.pf_root,
                pm_root=args.pm_root,
                pf_appmanifest=args.pf_appmanifest,
                pm_appmanifest=args.pm_appmanifest,
            )
        if args.report is not None:
            write_preflight_report(observation, args.report)
        print(json.dumps(observation.public_report(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except LocalePreflightError as exc:
        failure_schema = PAIR_SCHEMA if args.command == "photon-pair" else SCHEMA
        print(
            json.dumps(
                {"schema": failure_schema, "status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
