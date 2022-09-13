"""
Admin utilities.
"""

import unicodecsv

from django.contrib import auth
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger

from enterprise.admin.paginator import CustomPaginator
from enterprise.utils import ValidationMessages

DOT = '.'
PAGES_ON_EACH_SIDE = 3
PAGES_ON_ENDS = 2
User = auth.get_user_model()


class UrlNames:
    """
    Collection on URL names used in admin
    """
    URL_PREFIX = "enterprise_"
    MANAGE_LEARNERS = URL_PREFIX + "manage_learners"
    MANAGE_LEARNERS_DSC = URL_PREFIX + "manage_learners_data_sharing_consent"
    TRANSMIT_COURSES_METADATA = URL_PREFIX + "transmit_courses_metadata"
    PREVIEW_EMAIL_TEMPLATE = URL_PREFIX + "preview_email_template"
    PREVIEW_QUERY_RESULT = URL_PREFIX + "preview_query_result"


def validate_csv(file_stream, expected_columns=None):
    """
    Validate csv file for encoding and expected header.

    Args:
        file_stream: input file
        expected_columns: list of column names that are expected to be present in csv

    Returns:
       reader: an iterable for csv datat if csv passes the validation

    Raises:
        ValidationError
    """
    try:
        reader = unicodecsv.DictReader(file_stream, encoding="utf-8-sig")
        reader_fieldnames = reader.fieldnames
    except (unicodecsv.Error, UnicodeDecodeError) as error:
        raise ValidationError(ValidationMessages.INVALID_ENCODING) from error

    if expected_columns and set(expected_columns) - set(reader_fieldnames):
        raise ValidationError(ValidationMessages.MISSING_EXPECTED_COLUMNS.format(
            expected_columns=", ".join(expected_columns), actual_columns=", ".join(reader.fieldnames)
        ))

    return reader


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
    reader = validate_csv(file_stream, expected_columns)
    yield from reader


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


def split_usernames_and_emails(email_field):
    """
    Split the contents of the email field into a list.

    In some cases, a user could enter a comma-separated value inline in the
    Manage Learners form. We should check to see if that's the case, and
    provide a list of email addresses or usernames if it is.
    """
    return [name.strip() for name in email_field.split(',')]


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
