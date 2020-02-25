# -*- coding: utf-8 -*-
"""
Admin utilities.
"""
from __future__ import absolute_import, unicode_literals

import unicodecsv

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from enterprise.admin.paginator import CustomPaginator
from enterprise.models import EnterpriseCustomerUser

DOT = '.'
PAGES_ON_EACH_SIDE = 3
PAGES_ON_ENDS = 2


class UrlNames:
    """
    Collection on URL names used in admin
    """
    URL_PREFIX = "enterprise_"
    MANAGE_LEARNERS = URL_PREFIX + "manage_learners"
    TRANSMIT_COURSES_METADATA = URL_PREFIX + "transmit_courses_metadata"
    PREVIEW_EMAIL_TEMPLATE = URL_PREFIX + "preview_email_template"


class ValidationMessages:
    """
    Namespace class for validation messages.
    """

    # Keep this alphabetically sorted
    BOTH_FIELDS_SPECIFIED = _(
        "Either \"Email or Username\" or \"CSV bulk upload\" must be specified, "
        "but both were.")
    BULK_LINK_FAILED = _(
        "Error: Learners could not be added. Correct the following errors.")
    COURSE_MODE_INVALID_FOR_COURSE = _(
        "Enrollment track {course_mode} is not available for course {course_id}.")
    COURSE_WITHOUT_COURSE_MODE = _(
        "Select a course enrollment track for the given course.")
    INVALID_COURSE_ID = _(
        "Could not retrieve details for the course ID {course_id}. Specify "
        "a valid ID.")
    INVALID_EMAIL = _(
        "{argument} does not appear to be a valid email address.")
    INVALID_EMAIL_OR_USERNAME = _(
        "{argument} does not appear to be a valid email address or known "
        "username")
    MISSING_EXPECTED_COLUMNS = _(
        "Expected a CSV file with [{expected_columns}] columns, but found "
        "[{actual_columns}] columns instead."
    )
    MISSING_REASON = _(
        "Reason field is required but was not filled."
    )
    NO_FIELDS_SPECIFIED = _(
        "Either \"Email or Username\" or \"CSV bulk upload\" must be "
        "specified, but neither were.")
    PENDING_USER_ALREADY_LINKED = _(
        "Pending user with email address {user_email} is already linked with another Enterprise {ec_name}, "
        "you will be able to add the learner once the user creates account or other enterprise "
        "deletes the pending user")
    USER_ALREADY_REGISTERED = _(
        "User with email address {email} is already registered with Enterprise "
        "Customer {ec_name}")
    INVALID_CHANNEL_WORKER = _(
        'Enterprise channel worker user with the username "{channel_worker_username}" was not found.'
    )
    INVALID_ENCODING = _(
        "Unable to parse CSV file. Please make sure it is a CSV 'utf-8' encoded file."
    )
    INVALID_DISCOUNT = _(
        'Discount percentage should be from 0 to 100.'
    )


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
    try:
        reader = unicodecsv.DictReader(file_stream, encoding="utf-8")
        reader_fieldnames = reader.fieldnames
    except (unicodecsv.Error, UnicodeDecodeError):
        raise ValidationError(ValidationMessages.INVALID_ENCODING)

    if expected_columns and set(expected_columns) - set(reader_fieldnames):
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


def get_idiff_list(list_a, list_b):
    """
    Returns a list containing lower case difference of list_b and list_a after case insensitive comparison.

    Args:
        list_a: list of strings
        list_b: list of string

    Returns:
        List of unique lower case strings computed by subtracting list_b from list_a.
    """
    lower_list_a = [element.lower() for element in list_a]
    lower_list_b = [element.lower() for element in list_b]
    return list(set(lower_list_a) - set(lower_list_b))


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


def split_usernames_and_emails(email_field):
    """
    Split the contents of the email field into a list.

    In some cases, a user could enter a comma-separated value inline in the
    Manage Learners form. We should check to see if that's the case, and
    provide a list of email addresses or usernames if it is.
    """
    return [name.strip() for name in email_field.split(',')]


# pylint: disable=range-builtin-not-iterating
def paginated_list(object_list, page, page_size=25):
    """
    Returns paginated list.

    Arguments:
        object_list (QuerySet): A list of records to be paginated.
        page (int): Current page number.
        page_size (int): Number of records displayed in each paginated set.
        show_all (bool): Whether to show all records.

    Adopted from django/contrib/admin/templatetags/admin_list.py
    https://github.com/django/django/blob/1.11.1/django/contrib/admin/templatetags/admin_list.py#L50
    """
    paginator = CustomPaginator(object_list, page_size)
    try:
        object_list = paginator.page(page)
    except PageNotAnInteger:
        object_list = paginator.page(1)
    except EmptyPage:
        object_list = paginator.page(paginator.num_pages)

    page_range = []
    page_num = object_list.number

    # If there are 10 or fewer pages, display links to every page.
    # Otherwise, do some fancy
    if paginator.num_pages <= 10:
        page_range = range(paginator.num_pages)
    else:
        # Insert "smart" pagination links, so that there are always ON_ENDS
        # links at either end of the list of pages, and there are always
        # ON_EACH_SIDE links at either end of the "current page" link.
        if page_num > (PAGES_ON_EACH_SIDE + PAGES_ON_ENDS + 1):
            page_range.extend(range(1, PAGES_ON_ENDS + 1))
            page_range.append(DOT)
            page_range.extend(range(page_num - PAGES_ON_EACH_SIDE, page_num + 1))
        else:
            page_range.extend(range(1, page_num + 1))
        if page_num < (paginator.num_pages - PAGES_ON_EACH_SIDE - PAGES_ON_ENDS):
            page_range.extend(range(page_num + 1, page_num + PAGES_ON_EACH_SIDE + 1))
            page_range.append(DOT)
            page_range.extend(range(paginator.num_pages + 1 - PAGES_ON_ENDS, paginator.num_pages + 1))
        else:
            page_range.extend(range(page_num + 1, paginator.num_pages + 1))

        # Override page range to implement custom smart links.
        object_list.paginator.page_range = page_range

    return object_list
