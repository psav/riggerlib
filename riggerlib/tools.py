# -*- coding: utf-8 -*-
from collections import Mapping


def recursive_update(orig_dict, updates):
    """
    Update dict objects with recursive merge.

    Args:
        orig_dict: The original dict.
        updates: The updates to merge with the dictionary.
    """
    for key, val in updates.iteritems():
        # If the item with update is a mapping, let's go deeper
        if isinstance(val, Mapping):
            orig_dict[key] = recursive_update(orig_dict.get(key, {}), val)
        # If the thing updated is a list and the update is also a list, then just extend it
        elif isinstance(val, list) and isinstance(orig_dict.get(key, None), list):
            # lists are treated as leaves of the update functions.
            # Things would get waaay to complicated.
            orig_dict[key].extend(val)
        # Otherwise if we are updating a dictionary and no previous branch matched, just set it.
        elif isinstance(orig_dict, Mapping):
            orig_dict[key] = updates[key]
        else:
            orig_dict = {key: updates[key]}
    return orig_dict
