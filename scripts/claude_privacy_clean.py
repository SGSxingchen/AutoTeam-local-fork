#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


LEVEL1_KEYS = [
    "userID",
    "anonymousId",
    "firstStartTime",
    "claudeCodeFirstTokenDate",
]

LEVEL2_PATHS = [
    ".claude/telemetry",
    ".claude/statsig",
    ".claude/stats-cache.json",
]

LEVEL3_PATHS = [
    ".claude/history.jsonl",
    ".claude/sessions",
    ".claude/paste-cache",
    ".claude/shell-snapshots",
    ".claude/session-env",
    ".claude/file-history",
    ".claude/debug",
]

NON_HISTORY_TRACE_PATHS = [
    ".claude/paste-cache",
    ".claude/shell-snapshots",
    ".claude/session-env",
    ".claude/file-history",
    ".claude/debug",
]

LEVEL4_KEYS = [
    "oauthAccount",
    "s1mAccessCache",
    "groveConfigCache",
    "passesEligibilityCache",
    "clientDataCache",
    "cachedExtraUsageDisabledReason",
    "githubRepoPaths",
]

MACOS_KEYCHAIN_SERVICES = [
    "claude-code",
    "claude-code-credentials",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean Claude Code local tracking data. Default mode removes most local traces, "
            "preserves history/session records, and disables nonessential traffic."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply the cleanup. Without this flag the script only prints a dry-run plan.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--safe",
        action="store_true",
        help="Only remove device IDs and telemetry caches (levels 1 and 2).",
    )
    mode_group.add_argument(
        "--include-history",
        action="store_true",
        help="Also delete local history/session traces from ~/.claude (level 3).",
    )
    mode_group.add_argument(
        "--aggressive-preserve-history",
        action="store_true",
        help="Default mode: delete most local traces while preserving ~/.claude/history.jsonl, ~/.claude/sessions, and ~/.claude/projects.",
    )
    parser.add_argument(
        "--include-oauth",
        action="store_true",
        help="Also clear OAuth account linkage from ~/.claude.json and macOS Keychain (level 4). Useful with --safe.",
    )
    traffic_group = parser.add_mutually_exclusive_group()
    traffic_group.add_argument(
        "--disable-nonessential-traffic",
        dest="disable_nonessential_traffic",
        action="store_true",
        help="Default behavior: set CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 in ~/.claude/settings.json.",
    )
    traffic_group.add_argument(
        "--keep-nonessential-traffic",
        dest="disable_nonessential_traffic",
        action="store_false",
        help="Do not write CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backups before modifying files or deleting paths.",
    )
    parser.set_defaults(disable_nonessential_traffic=True)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    tmp_path.replace(path)


def format_home_relative(path: Path, home: Path) -> str:
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def expand_targets(home: Path, raw_paths: list[str]) -> list[Path]:
    return [home / raw_path for raw_path in raw_paths]


def backup_destination(path: Path, home: Path, backup_dir: Path) -> Path:
    try:
        relative = path.relative_to(home)
        return backup_dir / relative
    except ValueError:
        return backup_dir / path.name


def backup_path(path: Path, home: Path, backup_dir: Path) -> None:
    destination = backup_destination(path, home, backup_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.is_dir() and not path.is_symlink():
        shutil.copytree(path, destination, dirs_exist_ok=True)
        return
    shutil.copy2(path, destination)


def delete_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def print_section(title: str, items: list[str]) -> None:
    print(f"{title}:")
    if not items:
        print("  - none")
        return
    for item in items:
        print(f"  - {item}")


def main() -> int:
    args = parse_args()
    home = Path.home()
    claude_dir = home / ".claude"
    claude_json = home / ".claude.json"
    settings_json = claude_dir / "settings.json"
    aggressive_preserve_history = not args.safe and not args.include_history

    keys_to_remove = list(LEVEL1_KEYS)
    if args.include_oauth or aggressive_preserve_history:
        keys_to_remove.extend(LEVEL4_KEYS)

    delete_targets = expand_targets(home, LEVEL2_PATHS)
    if args.include_history:
        delete_targets.extend(expand_targets(home, LEVEL3_PATHS))
    elif aggressive_preserve_history:
        delete_targets.extend(expand_targets(home, NON_HISTORY_TRACE_PATHS))

    existing_delete_targets = [path for path in delete_targets if path.exists()]
    preserved_targets = [
        home / ".claude/history.jsonl",
        home / ".claude/sessions",
        home / ".claude/projects",
    ]
    if args.include_history:
        preserved_targets = [home / ".claude/projects"]

    config_data: dict | None = None
    existing_config_keys: list[str] = []
    if claude_json.exists():
        try:
            config_data = load_json(claude_json)
        except json.JSONDecodeError as exc:
            print(f"error: failed to parse {claude_json}: {exc}", file=sys.stderr)
            return 1
        existing_config_keys = [key for key in keys_to_remove if key in config_data]

    settings_data: dict | None = None
    settings_change_needed = False
    if args.disable_nonessential_traffic:
        if settings_json.exists():
            try:
                settings_data = load_json(settings_json)
            except json.JSONDecodeError as exc:
                print(f"error: failed to parse {settings_json}: {exc}", file=sys.stderr)
                return 1
        else:
            settings_data = {}
        current_value = settings_data.get("env", {}).get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")
        settings_change_needed = current_value != "1"

    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"Home: {home}")
    print(f"Preserve history: {'no' if args.include_history else 'yes'}")
    print(f"Aggressive preserve-history mode: {'yes' if aggressive_preserve_history else 'no'}")
    print(f"Clear OAuth linkage: {'yes' if (args.include_oauth or aggressive_preserve_history) else 'no'}")
    print_section(
        "JSON keys that will be removed",
        existing_config_keys,
    )
    print_section(
        "Paths that will be deleted",
        [format_home_relative(path, home) for path in existing_delete_targets],
    )
    print_section(
        "Paths that will be preserved",
        [format_home_relative(path, home) for path in preserved_targets],
    )
    if args.disable_nonessential_traffic:
        print(
            "Traffic setting: "
            + (
                "will write CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"
                if settings_change_needed
                else "already set"
            )
        )

    if not args.apply:
        print("")
        print("Dry-run only. Re-run with --apply to make changes.")
        return 0

    backup_dir: Path | None = None
    if not args.no_backup:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = claude_dir / "backups" / f"cc-privacy-clean-{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up_items: list[str] = []
    if backup_dir is not None:
        if claude_json.exists():
            backup_path(claude_json, home, backup_dir)
            backed_up_items.append(format_home_relative(claude_json, home))
        if settings_change_needed and settings_json.exists():
            backup_path(settings_json, home, backup_dir)
            backed_up_items.append(format_home_relative(settings_json, home))
        for path in existing_delete_targets:
            backup_path(path, home, backup_dir)
            backed_up_items.append(format_home_relative(path, home))

    removed_keys: list[str] = []
    if config_data is not None:
        for key in keys_to_remove:
            if key in config_data:
                removed_keys.append(key)
                del config_data[key]
        if removed_keys:
            write_json(claude_json, config_data)

    deleted_paths: list[str] = []
    for path in existing_delete_targets:
        delete_path(path)
        deleted_paths.append(format_home_relative(path, home))

    if args.disable_nonessential_traffic:
        assert settings_data is not None
        env = settings_data.setdefault("env", {})
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        write_json(settings_json, settings_data)

    keychain_results: list[str] = []
    if args.include_oauth or aggressive_preserve_history:
        if platform.system() == "Darwin" and shutil.which("security"):
            for service in MACOS_KEYCHAIN_SERVICES:
                result = subprocess.run(
                    ["security", "delete-generic-password", "-s", service],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    keychain_results.append(f"removed Keychain entry: {service}")
                else:
                    keychain_results.append(f"Keychain entry not removed or missing: {service}")
        else:
            keychain_results.append("skipped Keychain cleanup (not macOS or `security` not available)")

    print("")
    print("Cleanup complete.")
    if backup_dir is not None:
        print(f"Backup directory: {backup_dir}")
        print_section("Backed up items", backed_up_items)
    print_section("Removed JSON keys", removed_keys)
    print_section("Deleted paths", deleted_paths)
    if args.disable_nonessential_traffic:
        print(
            "Traffic setting: "
            + (
                "updated"
                if settings_change_needed
                else "already enabled"
            )
        )
    if keychain_results:
        print_section("OAuth token cleanup", keychain_results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
