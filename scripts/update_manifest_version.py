#!/usr/bin/env python3
"""Automatically manage plugin_version and tags in CANVAS_MANIFEST.json.

This script ensures that the manifest has proper version tracking:
- tags.version_date: Current date in ISO format
- tags.version_branch: Current git branch name
- tags.version_semantic: Semantic version (e.g., "0.1.127")
- plugin_version: Formatted string combining all version info
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_git_branch() -> str:
    """Get current git branch name.

    In GitHub Actions CI/CD, checks GITHUB_HEAD_REF first (for pull requests).
    Falls back to git rev-parse for local development.
    """
    # Check GitHub Actions environment variable first
    github_branch = os.environ.get("GITHUB_HEAD_REF")
    if github_branch:
        return github_branch[:20]

    # Fall back to git command for local development
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        return branch[:20]
    except subprocess.CalledProcessError as e:
        print(f"❌ ERROR: Could not get git branch: {e}")
        sys.exit(1)


def get_canvas_sdk_version() -> str | None:
    """Get the installed Canvas SDK version from uv run canvas --version."""
    try:
        result = subprocess.run(
            ["uv", "run", "canvas", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        # Parse "canvas_cli Version: 0.64.0" -> "0.64.0"
        match = re.search(r"Version:\s*(\d+\.\d+\.\d+)", output)
        if match:
            return match.group(1)
        return None
    except subprocess.CalledProcessError:
        return None


def parse_semantic_version(plugin_version: str) -> str | None:
    """Parse semantic version from plugin_version string.

    Examples:
        "0.1.127" -> "0.1.127"
        "2024-10-13 v0.1.127 (next)" -> "0.1.127"
    """
    # Try direct semantic version pattern
    match = re.search(r"\bv?(\d+\.\d+\.\d+)\b", plugin_version)
    if match:
        return match.group(1)
    return None


def compare_versions(version1: str, version2: str) -> int:
    """Compare two semantic versions.

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2
    """

    def parse_version(v: str) -> tuple[int, int, int]:
        parts = v.split(".")
        return (int(parts[0]), int(parts[1]), int(parts[2]))

    v1 = parse_version(version1)
    v2 = parse_version(version2)

    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0


def main() -> int:
    """Update manifest version information."""
    manifest_path = Path("hyperscribe/CANVAS_MANIFEST.json")

    if not manifest_path.exists():
        print(f"❌ ERROR: {manifest_path.as_posix()} not found")
        return 1

    # Read current manifest
    with manifest_path.open("r") as f:
        manifest = json.load(f)

    # Get git branch
    branch = get_git_branch()

    # Get Canvas SDK version
    sdk_version = get_canvas_sdk_version()
    current_sdk_version = manifest.get("sdk_version", "")

    if sdk_version:
        if not current_sdk_version:
            # No current version, set it
            manifest["sdk_version"] = sdk_version
            print(f"📦 Set sdk_version: {sdk_version}")
        else:
            comparison = compare_versions(sdk_version, current_sdk_version)
            if comparison > 0:
                # Detected version is higher, update
                manifest["sdk_version"] = sdk_version
                print(f"📦 Updated sdk_version: {current_sdk_version} → {sdk_version}")
            elif comparison == 0:
                # Same version
                print(f"✓ sdk_version is up-to-date: {sdk_version}")
            else:
                # Detected version is lower, don't downgrade
                print(
                    f"⚠️  WARNING: Detected Canvas SDK version ({sdk_version}) is lower "
                    f"than manifest ({current_sdk_version})"
                )
                print(f"   Not downgrading. Please update your Canvas SDK: uv sync")
    else:
        print(f"⚠️  WARNING: Could not determine Canvas SDK version from 'uv run canvas --version'")

    # Ensure tags exists
    if "tags" not in manifest:
        manifest["tags"] = {}

    # Get or parse semantic version
    current_plugin_version = manifest.get("plugin_version", "")
    version_semantic = manifest["tags"].get("version_semantic")

    if not version_semantic:
        # Try to parse from current plugin_version
        version_semantic = parse_semantic_version(current_plugin_version)
        if not version_semantic:
            print(f"❌ ERROR: Could not determine semantic version")
            print(f"   Current plugin_version: '{current_plugin_version}'")
            print(f"   Please set tags.version_semantic manually (e.g., '0.1.128')")
            return 1

    # Update tags
    version_date = datetime.now().date().isoformat()
    manifest["tags"]["version_date"] = version_date
    manifest["tags"]["version_branch"] = branch
    manifest["tags"]["version_semantic"] = version_semantic

    # Construct plugin_version
    new_plugin_version = f"{version_date} v{version_semantic} ({branch})"
    manifest["plugin_version"] = new_plugin_version

    # Write back to file
    with manifest_path.open("w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")  # Add trailing newline

    print(f"✅ Updated manifest:")
    print(f"   plugin_version: {new_plugin_version}")
    print(f"   tags.version_semantic: {version_semantic}")
    print(f"   tags.version_branch: {branch}")
    print(f"   tags.version_date: {version_date}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
