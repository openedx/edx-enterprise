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

from enterprise.api_client.lms import parse_lms_api_datetime
from enterprise.models import EnterpriseCustomerUser


class ProgramStatuses(object):
    """
    Namespace class for program statuses.
    """
    UNPUBLISHED = "unpublished"
    ACTIVE = "active"
    RETIRED = "retired"
    DELETED = "deleted"


class UrlNames(object):
    """
    Collection on URL names used in admin
    """
    URL_PREFIX = "enterprise_"
    MANAGE_LEARNERS = URL_PREFIX + "manage_learners"
    MANAGE_ADMINS = URL_PREFIX + "manage_admins"
    MANAGE_ADMIN_USER_PERMISSIONS = URL_PREFIX + "manage_admin_user_permissions"
    PREVIEW_EMAIL_TEMPLATE = URL_PREFIX + "preview_email_template"


class ValidationMessages(object):
    """
    Namespace class for validation messages.
    """

    # Keep this alphabetically sorted
    BOTH_FIELDS_SPECIFIED = _(
        "Either \"Email or Username\" or \"CSV bulk upload\" must be specified, "
        "but both were.")
    BULK_LINK_FAILED = _(
        "Error: Learners could not be added. Correct the following errors.")
    COURSE_AND_PROGRAM_ERROR = _(
        "Either \"Course ID\" or \"Program ID\" can be specified, but both were.")
    COURSE_MODE_INVALID_FOR_COURSE = _(
        "Enrollment track {course_mode} is not available for course {course_id}.")
    COURSE_MODE_NOT_AVAILABLE = _(
        "Enrollment track {mode} is not available for all courses in program "
        "{program_title}. The available enrollment tracks are {modes}.")
    COURSE_WITHOUT_COURSE_MODE = _(
        "Select a course enrollment track for the given course or program.")
    FAILED_TO_OBTAIN_COURSE_MODES = _(
        "Failed to obtain available course enrollment tracks for "
        "program {program_title}")
    INVALID_COURSE_ID = _(
        "Could not retrieve details for the course ID {course_id}. Specify "
        "a valid ID.")
    INVALID_EMAIL = _(
        "{argument} does not appear to be a valid email address.")
    INVALID_EMAIL_OR_USERNAME = _(
        "{argument} does not appear to be a valid email address or known "
        "username")
    INVALID_PROGRAM_ID = _(
        "Could not retrieve details for the program {program_id}. Specify a "
        "valid program ID or program name."
    )
    MISSING_EXPECTED_COLUMNS = _(
        "Expected a CSV file with [{expected_columns}] columns, but found "
        "[{actual_columns}] columns instead."
    )
    MULTIPLE_PROGRAM_MATCH = _(
        "Searching programs by title returned {program_count} programs. "
        "Try using program UUID"
    )
    NO_FIELDS_SPECIFIED = _(
        "Either \"Email or Username\" or \"CSV bulk upload\" must be "
        "specified, but neither were.")
    PROGRAM_IS_INACTIVE = _(
        "Enrollment in program {program_id} is closed because it is in "
        "{status} status.")
    USER_ALREADY_REGISTERED = _(
        "User with email address {email} is already registered with Enterprise "
        "Customer {ec_name}")


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
    return existing_record or False


def get_course_runs_from_program(program):
    """
    Return course runs from program data.

    Arguments:
        program(dict): Program data from Course Catalog API

    Returns:
        set: course runs in given program
    """
    course_runs = set()
    for course in program.get("courses", []):
        for run in course.get("course_runs", []):
            if "key" in run and run["key"]:
                course_runs.add(run["key"])

    return course_runs


def get_earliest_start_date_from_program(program):
    """
    Get the earliest date that one of the courses in the program was available.
    For the sake of emails to new learners, we treat this as the program start date.

    Arguemnts:
        program (dict): Program data from Course Catalog API

    returns:
        datetime.datetime: The date and time at which the first course started
    """
    start_dates = []
    for course in program.get('courses', []):
        for run in course.get('course_runs', []):
            if run.get('start'):
                start_dates.append(parse_lms_api_datetime(run['start']))
    if not start_dates:
        return None
    return min(start_dates)


def split_usernames_and_emails(email_field):
    """
    Split the contents of the email field into a list.

    In some cases, a user could enter a comma-separated value inline in the
    Manage Learners form. We should check to see if that's the case, and
    provide a list of email addresses or usernames if it is.
    """
    return [name.strip() for name in email_field.split(',')]
