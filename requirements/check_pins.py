#!/usr/bin/env python
"""
Compare two pip requirements files.  Everything in the first one should match
one in the second one.
"""

import re
import sys

def pins(lines):
    """Parse lines from a requirements file.

    Yields (pkg, content), where `pkg` is the name of the package, and
    `content` is the specification of what to install.
    """
    for line in lines:
        line = line.strip()
        content = re.sub(r"(^|\s+)#.*$", "", line)
        if not content:
            continue
        pin = content.split("==")
        if len(pin) == 2:
            pkg, _ = pin
            if pkg.startswith("git+https:"):
                pkg = pkg.partition("#egg=")[-1]
            elif "[" in pkg:
                pkg = pkg.partition("[")[0]
            yield pkg, content


def read_pin_dict(filename):
    """Read a requirements file, and return a dict mapping package name to spec."""
    with open(filename) as f:
        return dict(pins(f))


def check_pins(our_file, their_file):
    """Check that all the pins in `our_file` match the corresponding line in `their_file`."""
    ours = read_pin_dict(our_file)
    theirs = read_pin_dict(their_file)
    for pkg in ours:
        our_pkg = ours[pkg]
        try:
            their_pkg = theirs[pkg]
        except KeyError:
            print(f"*** Pinned, but not in {their_file}:")
            print(our_pkg)
            print("")
        else:
            if our_pkg != their_pkg:
                print("*** Pins disagree:")
                print(our_pkg)
                print(their_pkg)
                print("")

check_pins(*sys.argv[1:])  # pylint: disable=too-many-function-args
