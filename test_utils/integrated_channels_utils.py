# -*- coding: utf-8 -*-
"""
Miscellaneous utils for tests.
"""

import copy


def merge_dicts(dict1, dict2):
    """
    Merge dict1 and dict2 and returns merged dict.

    If dict2 has a key with value set to `undefined` it removes that key from dict1
    """
    merged_dict = copy.deepcopy(dict1)
    if dict2:
        for key, val in dict2.items():
            if val == 'undefined' and key in merged_dict:
                del merged_dict[key]
            else:
                merged_dict.update(dict2)
    return merged_dict
