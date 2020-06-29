# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` utility functions.
"""

import re
import unittest

import ddt
from pytest import mark, raises

from django.core.exceptions import ValidationError

from enterprise.admin.utils import (
    ValidationMessages,
    email_or_username__to__email,
    get_idiff_list,
    parse_csv,
    validate_email_to_link,
)
from enterprise.models import EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from test_utils.factories import FAKER, EnterpriseCustomerUserFactory, PendingEnterpriseCustomerUserFactory, UserFactory
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


@mark.django_db
@ddt.ddt
class TestGetDifferenceList(unittest.TestCase):
    """
    Tests for :method:`get_idiff_list`.
    """

    @ddt.unpack
    @ddt.data(
        (
            [],
            [],
            []
        ),
        (
            ['DUMMY1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
            ['dummy1@example.com', 'DUMMY3@EXAMPLE.COM'],
            ['dummy2@example.com']
        ),
        (
            ['dummy1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
            [],
            ['dummy1@example.com', 'dummy2@example.com', 'dummy3@example.com'],
        )
    )
    def test_get_idiff_list_method(self, all_emails, registered_emails, unregistered_emails):
        emails = get_idiff_list(all_emails, registered_emails)
        self.assertEqual(sorted(emails), sorted(unregistered_emails))


@mark.django_db
@ddt.ddt
class TestValidateEmailToLink(unittest.TestCase):
    """
    Tests for :method:`validate_email_to_link`.
    """

    def test_validate_email_to_link_normal(self):
        email = FAKER.email()  # pylint: disable=no-member
        assert PendingEnterpriseCustomerUser.objects.filter(user_email=email).count() == 0, \
            "Precondition check - should not have PendingEnterpriseCustomerUser"
        assert EnterpriseCustomerUser.objects.count() == 0, \
            "Precondition check - should not have EnterpriseCustomerUser"

        exists = validate_email_to_link(email)  # should not raise any Exceptions
        assert exists is False

    @ddt.unpack
    @ddt.data(
        ("something", "something", ValidationMessages.INVALID_EMAIL),
        ("something_again@", "something_else", ValidationMessages.INVALID_EMAIL)
    )
    def test_validate_email_to_link_invalid_email(self, email, raw_email, msg_template):
        assert EnterpriseCustomerUser.objects.get_link_by_email(email) is None, \
            "Precondition check - should not have EnterpriseCustomerUser or PendingEnterpriseCustomerUser"

        expected_message = msg_template.format(argument=raw_email)

        with raises(ValidationError, match=expected_message):
            validate_email_to_link(email, raw_email)

    @ddt.data(True, False)
    def test_validate_email_to_link_existing_user_record(self, ignore_existing):
        user = UserFactory()
        email = user.email
        existing_record = EnterpriseCustomerUserFactory(user_id=user.id)
        assert not PendingEnterpriseCustomerUser.objects.exists(), \
            "Precondition check - should not have PendingEnterpriseCustomerUser"
        assert EnterpriseCustomerUser.objects.get(user_id=user.id) == existing_record, \
            "Precondition check - should have EnterpriseCustomerUser"

        if ignore_existing:
            exists = validate_email_to_link(email, ignore_existing=True)
            assert exists
        else:
            expected_message = ValidationMessages.USER_ALREADY_REGISTERED.format(
                email=email, ec_name=existing_record.enterprise_customer.name
            )

            with raises(ValidationError, match=expected_message):
                validate_email_to_link(email)

    @ddt.data(True, False)
    def test_validate_email_to_link_existing_pending_record(self, ignore_existing):
        email = FAKER.email()  # pylint: disable=no-member
        existing_record = PendingEnterpriseCustomerUserFactory(user_email=email)
        assert PendingEnterpriseCustomerUser.objects.get(user_email=email) == existing_record, \
            "Precondition check - should have PendingEnterpriseCustomerUser"
        assert not EnterpriseCustomerUser.objects.exists(), \
            "Precondition check - should not have EnterpriseCustomerUser"

        if ignore_existing:
            exists = validate_email_to_link(email, ignore_existing=True)
            assert exists
        else:
            expected_message = ValidationMessages.USER_ALREADY_REGISTERED.format(
                email=email, ec_name=existing_record.enterprise_customer.name
            )

            with raises(ValidationError, match=expected_message):
                exists = validate_email_to_link(email)
