# -*- coding: utf-8 -*-
"""
Admin utilities.
"""
from __future__ import absolute_import, unicode_literals

import unicodecsv
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from enterprise.models import EnterpriseCustomerUser


class UrlNames(object):
    """
    Collection on URL names used in admin
    """
    URL_PREFIX = "enterprise_"
    MANAGE_LEARNERS = URL_PREFIX + "manage_learners"


class ValidationMessages(object):
    """
    Namespace class for validation messages.
    """
    BOTH_FIELDS_SPECIFIED = _("Either \"Email or Username\" or \"CSV bulk upload\" must be specified, but both were.")
    BULK_LINK_FAILED = _("Bulk operation failed - no users were linked. Please correct the errors listed below.")
    COURSE_MODE_INVALID_FOR_COURSE = _("Enrollment mode {course_mode} not available for course {course_id}.")
    COURSE_WITHOUT_COURSE_MODE = _("Please select a course enrollment mode for the given course.")
    INVALID_COURSE_ID = _("Could not retrieve details for the course ID {course_id}. Please specify a valid ID.")
    INVALID_EMAIL = _("{argument} does not appear to be a valid email")
    INVALID_EMAIL_OR_USERNAME = _("{argument} does not appear to be a valid email or known username")
    MISSING_EXPECTED_COLUMNS = _(
        "Expected a CSV file with [{expected_columns}] columns, but found [{actual_columns}] columns instead."
    )
    NO_FIELDS_SPECIFIED = _("Either \"Email or Username\" or \"CSV bulk upload\" must be specified, but neither were.")
    USER_ALREADY_REGISTERED = _("User with email {email} is already registered with Enterprise Customer {ec_name}")


def parse_csv(file_stream, expected_columns=None):
    """
    Parse csv file and return a stream of dictionaries representing each row.

    First line of CSV file must contain column headers.

    Arguments:
         file_stream: input file
         expected_columns (set[unicode]): columns that are expected to be present

    Yields:
        dict: CSV line parsed into a dictionary.
    """
    reader = unicodecsv.DictReader(file_stream, encoding="utf-8")

    if expected_columns and set(expected_columns) - set(reader.fieldnames):
        raise ValidationError(ValidationMessages.MISSING_EXPECTED_COLUMNS.format(
            expected_columns=", ".join(expected_columns), actual_columns=", ".join(reader.fieldnames)
        ))

    # "yield from reader" would be nicer, but we're on python2.7 yet.
    for row in reader:
        yield row


def email_or_username__to__email(email_or_username):
    """
    Convert email_or_username to email.

    Returns:
        str: If `email_or_username` was a username returns user's email, otherwise assumes it was an email and returns
             as is.
    """
    try:
        user = User.objects.get(username=email_or_username)
        return user.email
    except User.DoesNotExist:
        return email_or_username


def validate_email_to_link(email, raw_email=None, message_template=None, ignore_existing=False):
    """
    Validate email to be linked to Enterprise Customer.

    Performs two checks:
        * Checks that email is valid
        * Checks that it is not already linked to any Enterprise Customer

    Arguments:
        email (str): user email to link
        raw_email (str): raw value as it was passed by user - used in error message.
        message_template (str): Validation error template string.
        ignore_existing (bool): If True to skip the check for an existing Enterprise Customer

    Raises:
        ValidationError: if email is invalid or already linked to Enterprise Customer.

    Returns:
        bool: Whether or not there is an existing record with the same email address.
    """
    raw_email = raw_email if raw_email is not None else email
    message_template = message_template if message_template is not None else ValidationMessages.INVALID_EMAIL
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError(message_template.format(argument=raw_email))

    existing_record = EnterpriseCustomerUser.objects.get_link_by_email(email)
    if existing_record and not ignore_existing:
        raise ValidationError(ValidationMessages.USER_ALREADY_REGISTERED.format(
            email=email, ec_name=existing_record.enterprise_customer.name
        ))
    return bool(existing_record)
