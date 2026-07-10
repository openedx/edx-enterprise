#!/usr/bin/env python
"""
Merge openedx-platform's pinned package versions into [tool.uv].constraint-dependencies.

edx-enterprise runs as a plugin inside edx-platform, so its tests should only
run against package versions that edx-platform actually deploys in production.
This fetches edx-platform's own compiled requirements, extracts the pins, and
merges them into pyproject.toml's [tool.uv].constraint-dependencies -- run this
*after* `edx_lint write_uv_constraints` (which owns/overwrites that same list)
so the platform pins layer on top of it, and before `uv lock --upgrade`.

Repo-specific overrides in [tool.edx_lint].uv_constraints always win over a
platform pin for the same package -- see the precedence comment on
[tool.uv].constraint-dependencies in pyproject.toml.
"""
import re
import sys
import urllib.request

import tomlkit

PLATFORM_BASE_REQS = "https://raw.githubusercontent.com/openedx/openedx-platform/master/requirements/edx/base.txt"
PYPROJECT_PATH = "pyproject.toml"
SELF_PACKAGE = "edx-enterprise"

# Packages where a platform pin is a *global* uv constraint (applies to every
# dependency-group, unlike a plain pip -c file which only constrains packages
# actually pulled in per-environment) but genuinely conflicts with a package
# only edx-enterprise's own tooling needs -- so we deliberately don't import
# the platform's pin for these. Add a package here (with why) if `uv lock`
# reports it as unsatisfiable after a `make upgrade`.
SKIP_PACKAGES = {
    # jasmine (js_test dependency-group) hard-pins pyyaml==3.10; the platform's
    # newer pin would make the whole lock unsatisfiable.
    "pyyaml",
}


def fetch_platform_pins():
    """Download edx-platform's base.txt and yield (pkg, pin) for each pinned package."""
    with urllib.request.urlopen(PLATFORM_BASE_REQS) as response:  # noqa: S310
        lines = response.read().decode("utf-8").splitlines()

    for line in lines:
        if line.startswith("-e"):
            continue
        if line.rstrip().endswith("via edx-enterprise"):
            # Only pulled into edx-platform's own lock because edx-enterprise itself
            # requires it -- pinning it back against ourselves would be circular.
            continue
        # Package name, optional extras (e.g. "lxml[html-clean]"), then the pin.
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]*\])?==([^\s;]+)", line)
        if not match:
            continue
        pkg = match.group(1)
        if pkg.lower() == SELF_PACKAGE:
            # edx-platform pins edx-enterprise itself -- pinning ourselves is circular
            # and uv rejects a self-constraint outright.
            continue
        if pkg.lower() in SKIP_PACKAGES:
            continue
        yield pkg, match.group(2)


def main():
    """Merge openedx-platform's pins into pyproject.toml's constraint-dependencies."""
    with open(PYPROJECT_PATH, encoding="utf-8") as f:
        doc = tomlkit.load(f)

    existing = list(doc["tool"]["uv"]["constraint-dependencies"])
    pinned_packages = {re.match(r"^[A-Za-z0-9_.-]+", c).group(0).lower() for c in existing}

    added = []
    for pkg, version in fetch_platform_pins():
        if pkg.lower() in pinned_packages:
            continue
        existing.append(f"{pkg}=={version}")
        pinned_packages.add(pkg.lower())
        added.append(pkg)

    new_list = tomlkit.array()
    new_list.extend(existing)
    new_list.multiline(True)
    doc["tool"]["uv"]["constraint-dependencies"] = new_list

    with open(PYPROJECT_PATH, "w", encoding="utf-8") as f:
        tomlkit.dump(doc, f)

    print(f"Merged {len(added)} openedx-platform pins into [tool.uv].constraint-dependencies.")


if __name__ == "__main__":
    sys.exit(main())
