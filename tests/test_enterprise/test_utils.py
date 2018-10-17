import unittest

from enterprise.api.utils import update_content_filters


class TestEnterpriseAPIViews(unittest.TestCase):
    """
    Tests for enterprise api utils.
    """

    def test_update_content_filters(self):
        """
        _update_content_filters should properly combine catalog filter dicts
        """
        original_filters = {
            "key1": "true",
            "key2": "cat",
            "key3": ["rock", "stick", "leaf"],
        }
        new_filters = {
            "key1": "true",
            "key2": "dog",
            "key3": ["leaf", "branch", "tree"],
            "key4": "soup",
        }
        expected = {
            "key1": "true",
            "key2": ["cat", "dog"],
            "key3": ["rock", "stick", "leaf", "branch", "tree"],
            "key4": "soup"
        }
        update_content_filters(original_filters, new_filters)
        assert original_filters["key1"] == expected["key1"]
        assert original_filters["key2"].sort() == expected["key2"].sort()
        assert original_filters["key3"].sort() == expected["key3"].sort()
        assert original_filters["key4"] == expected["key4"]
