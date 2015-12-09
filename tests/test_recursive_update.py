# -*- coding: utf-8 -*-
import pytest

from riggerlib.tools import recursive_update


@pytest.mark.parametrize(("orig", "update", "result"), [
    ({}, {}, {}),
    ({}, {"a": 1}, {"a": 1}),
    ({"a": 1}, {"a": "foo"}, {"a": "foo"}),
    ({"a": {"b": 1}}, {"a": {"c": 2}}, {"a": {"b": 1, "c": 2}}),
    ({"a": 1}, {"b": 2}, {"a": 1, "b": 2}),
    ({"a": [1, 2, 3]}, {"a": [4, 5, 6]}, {"a": [1, 2, 3, 4, 5, 6]}),
    ({"a": {"b": [1, 2, 3]}}, {"a": {"b": [4, 5, 6]}}, {"a": {"b": [1, 2, 3, 4, 5, 6]}}),
    (
        {
            "a": {"b": 2},
            "b": [1, 3, 5],
            "c": {"d": [1], "e": "lol"},
            "f": "hello world!",
            "g": 1,
        },
        {
            "a": {"bb": "hey"},
            "b": [2, 4, 6],
            "c": {"d": [2], "e": "hey"},
            "f": {"new": True},
            "g": None,
        },
        {
            "a": {"b": 2, "bb": "hey"},
            "b": [1, 3, 5, 2, 4, 6],
            "c": {"d": [1, 2], "e": "hey"},
            "f": {"new": True},
            "g": None,
        })
])
def test_update_works(orig, update, result):
    assert recursive_update(orig, update) == result
