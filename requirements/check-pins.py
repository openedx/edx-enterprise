#!/usr/bin/env python
#
# Compare two pip pin files.  Everything in the first one should match one
# in the second one.

import re
import sys

def pins(lines):
    for line in lines:
        line = line.strip()
        content = re.sub(r"(^|\s+)#.*$", "", line)
        if not content:
            continue
        pin = content.split("==")
        if len(pin) == 2:
            yield pin[0], (pin[1], line)

def read_pin_dict(filename):
    with open(filename) as f:
        return dict(pins(f))


def check_pins(our_file, their_file):
    ours = read_pin_dict(our_file)
    theirs = read_pin_dict(their_file)
    for pkg in ours:
        us = ours[pkg][0]
        try:
            them = theirs[pkg][0]
        except KeyError:
            print("*** Pinned, but not in {}:".format(their_file))
            print(ours[pkg][1])
            print("")
        else:
            if us != them:
                print("*** Pins disagree:")
                print(ours[pkg][1])
                print(theirs[pkg][1])
                print("")

check_pins(*sys.argv[1:])
