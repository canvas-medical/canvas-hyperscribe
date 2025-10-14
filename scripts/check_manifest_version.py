#!/usr/bin/env python3
"""Check that plugin_version matches branch naming convention.

For branches starting with 'next-' or 'next/', the plugin_version in
CANVAS_MANIFEST.json must start with 'next-'.
"""

import json
import subprocess
import sys
from pathlib import Path


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    """Check manifest version against branch name."""
    try:
        branch = get_current_branch()
    except subprocess.CalledProcessError:
        print("⚠️  WARNING: Could not determine current branch")
        return 0

    # Check if this is a "next" branch
    is_next_branch = branch.startswith("next-") or branch.startswith("next/")

    if not is_next_branch:
        # Not a next branch, no check needed
        return 0

    # Read CANVAS_MANIFEST.json
    manifest_path = Path("hyperscribe/CANVAS_MANIFEST.json")
    if not manifest_path.exists():
        print(f"❌ ERROR: {manifest_path} not found")
        return 1

    with open(manifest_path) as f:
        manifest = json.load(f)

    version = manifest.get("plugin_version", "")

    if not version.startswith("next-"):
        print(f"⚠️  WARNING: Branch '{branch}' should have plugin_version starting with 'next-'")
        print(f"   Current version: '{version}'")
        print(f"   Expected format: 'next-X.Y.Z' (e.g., 'next-0.1.128')")
        print()
        print("   Please update the plugin_version in hyperscribe/CANVAS_MANIFEST.json")
        print()
        print("   To override this check, use: git commit --no-verify")
        return 1

    # All checks passed
    print(f"✅ Plugin version '{version}' matches branch '{branch}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
