# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utility functions.
"""

import re
import unittest

from pytest import mark, raises

from django.core.exceptions import ValidationError

from enterprise.admin.utils import ValidationMessages, email_or_username__to__email, parse_csv
from test_utils.factories import FAKER, UserFactory
from test_utils.file_helpers import MakeCsvStreamContextManager  # pylint: disable=ungrouped-imports


class TestParseCSV(unittest.TestCase):
    """
    Test parse_csv method.
    """

    @staticmethod
    def _make_expected_result(header, contents):
        """
        Generates :method:`parse_csv` output from header and contents.

        Arguments:
            header (Iterable): Column headers.
            contents (Iterable): CSV contents - each item represents a line.

        Returns:
            list: Expected :method:`parse_csv` output
        """
        return [
            dict(zip(header, column_values))
            for column_values in contents
        ]

    def test_parse_csv_normal(self):
        header = ("key1", "key2")
        contents = (
            ("QWERTY", "UIOP"),
            ("ASDFGH", "JKL:")
        )

        with MakeCsvStreamContextManager(header, contents) as stream:
            expected_result = self._make_expected_result(header, contents)

            actual_result = list(parse_csv(stream))
            assert actual_result == expected_result

    def test_parse_csv_check_columns_normal(self):
        header = ("Name", "MainCaliber")
        contents = (
            ("Bismarck", "4 x 2 - 380"),
            ("Yamato", "3 x 3 - 460")
        )

        with MakeCsvStreamContextManager(header, contents) as stream:
            expected_result = self._make_expected_result(header, contents)

            actual_result = list(parse_csv(stream, expected_columns=set(header)))
            assert actual_result == expected_result

    def test_parse_csv_check_columns_mismatch(self):
        header = ("Name", "MainCaliber", "Std Displacement")
        expected_columns = {"Name", "Email"}
        contents = (
            ("Bismarck", "4 x 2 - 380", "41700"),
            ("Yamato", "3 x 3 - 460", "63200")
        )

        with MakeCsvStreamContextManager(header, contents) as stream:
            expected_error_message = ValidationMessages.MISSING_EXPECTED_COLUMNS.format(
                expected_columns=", ".join(expected_columns), actual_columns=", ".join(header)
            )

            with raises(ValidationError, match=re.escape(expected_error_message)):
                list(parse_csv(stream, expected_columns={"Name", "Email"}))

    def test_parse_csv_check_with_wrong_encoding(self):
        header = ("email",)
        contents = (
            "honor@example.com",
            "staff@example.com",
        )

        with MakeCsvStreamContextManager(header, contents, 'utf-16') as stream:
            expected_error_message = ValidationMessages.INVALID_ENCODING

            with raises(ValidationError, match=expected_error_message):
                list(parse_csv(stream, expected_columns={"email"}))


@mark.django_db
class TestEmailConversion(unittest.TestCase):
    """
    Tests for :method:`email_or_username__to__email`.
    """

    def test_email_or_username__to__email_username(self):
        user = UserFactory()
        email_or_username = user.username

        assert email_or_username__to__email(email_or_username) == user.email

    def test_email_or_username__to__email_something_else(self):
        email_or_username = FAKER.email()  # pylint: disable=no-member

        assert email_or_username__to__email(email_or_username) == email_or_username
