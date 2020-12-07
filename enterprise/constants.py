# -*- coding: utf-8 -*-
"""
Enterprise Django application constants.
"""

import json

from django.utils.translation import ugettext_lazy as _

# We listen to the User post_save signal in order to associate new users
# with an EnterpriseCustomer when applicable. This it the unique identifier
# used to ensure that signal receiver is only called once.
USER_POST_SAVE_DISPATCH_UID = "user_post_save_upgrade_pending_enterprise_customer_user"

# Data sharing consent messages
CONSENT_REQUEST_PROMPT = _(
    'To log in using this SSO identity provider and access special course offers, you must first '
    'consent to share your learning achievements with {enterprise_customer_name}.'
)
CONFIRMATION_ALERT_PROMPT = _(
    'In order to sign in and access special offers, you must consent to share your '
    'course data with {enterprise_customer_name}.'
)
CONFIRMATION_ALERT_PROMPT_WARNING = _(
    'If you do not consent to share your course data, that information may be shared with '
    '{enterprise_customer_name}.'
)
WELCOME_TEXT = _('Welcome to {platform_name}.')
ENTERPRISE_WELCOME_TEXT = _(
    u'You have left the {strong_start}{enterprise_customer_name}{strong_end} website and are now on the '
    '{platform_name} site. {enterprise_customer_name} has partnered with {platform_name} to offer you '
    'high-quality, always available learning programs to help you advance your knowledge and career. '
    '{line_break}Please note that {platform_name} has a different {privacy_policy_link_start}Privacy Policy '
    '{privacy_policy_link_end} from {enterprise_customer_name}.'
)

COURSE_KEY_URL_PATTERN = r'(?P<course_key>[^/+]+(/|\+)[^/+]+)'


class DefaultColors:
    """
    Class to group the default branding color codes.
    These color codes originated in the Enterprise Learner Portal.
    """
    PRIMARY = '#00262B'
    SECONDARY = '#EFF8FA'
    TERTIARY = '#0A7DA3'


class CourseModes:
    """
    Class to group modes that a course might have.
    """

    AUDIT = 'audit'
    CREDIT = 'credit'
    HONOR = 'honor'
    NO_ID_PROFESSIONAL = 'no-id-professional'
    PROFESSIONAL = 'professional'
    VERIFIED = 'verified'


# Course mode sorting based on slug
COURSE_MODE_SORT_ORDER = [
    CourseModes.VERIFIED,
    CourseModes.PROFESSIONAL,
    CourseModes.NO_ID_PROFESSIONAL,
    CourseModes.AUDIT,
    CourseModes.HONOR,
]

# Course modes that should not be displayed to users.
EXCLUDED_COURSE_MODES = [CourseModes.CREDIT]

# Number of records to display in each paginated set.
PAGE_SIZE = 25

PROGRAM_TYPE_DESCRIPTION = {
    'MicroMasters Certificate': _(
        'A series of Master’s-level courses to advance your career, '
        'created by top universities and recognized by companies. '
        'MicroMasters Programs are credit-eligible, provide in-demand '
        'knowledge and may be applied to accelerate a Master’s Degree.'
    ),
    'Professional Certificate': _(
        'Designed by industry leaders and top universities to enhance '
        'professional skills, Professional Certificates develop the '
        'proficiency and expertise that employers are looking for with '
        'specialized training and professional education.'
    ),
    'XSeries Certificate': _(
        'Created by world-renowned experts and top universities, XSeries '
        'are designed to provide a deep understanding of key subjects '
        'through a series of courses. Complete the series to earn a valuable '
        'XSeries Certificate that illustrates your achievement.'
    ),
}

ALLOWED_TAGS = [
    u'a', u'abbr', u'acronym', u'b', u'blockquote', u'em', u'i',
    u'li', u'ol', u'strong', u'ul', u'p', u'h1', u'h2',
]

DEFAULT_CATALOG_CONTENT_FILTER = {
    'content_type': 'course',
    'partner': 'edx',
    'level_type': [
        'Introductory',
        'Intermediate',
        'Advanced'
    ],
    'availability': [
        'Current',
        'Starting Soon',
        'Upcoming'
    ],
    'status': 'published'
}

# Django groups specific to granting permission to enterprise admins.
ENTERPRISE_DATA_API_ACCESS_GROUP = 'enterprise_data_api_access'
ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP = 'enterprise_enrollment_api_access'
ENTERPRISE_PERMISSION_GROUPS = [
    ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
    ENTERPRISE_DATA_API_ACCESS_GROUP,
]

ENTERPRISE_LEARNER_ROLE = 'enterprise_learner'
ENTERPRISE_ADMIN_ROLE = 'enterprise_admin'
ENTERPRISE_OPERATOR_ROLE = 'enterprise_openedx_operator'
SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE = 'enterprise_catalog_admin'

ENTERPRISE_DASHBOARD_ADMIN_ROLE = 'dashboard_admin'
ENTERPRISE_CATALOG_ADMIN_ROLE = 'catalog_admin'
ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE = 'enrollment_api_admin'
ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE = 'reporting_config_admin'

# context to give access to all resources
ALL_ACCESS_CONTEXT = '*'

# this constant should not be used anymore as it is marked for removal
ENTERPRISE_ROLE_BASED_ACCESS_CONTROL_SWITCH = 'enterprise_role_based_access_control'

OAUTH2_PROVIDER_APPLICATION_MODEL = 'oauth2_provider.Application'

EDX_ORG_NAME = 'edX, Inc'

# Waffle flag used to switch over edx-enterprise's usage of the enterprise catalog service
USE_ENTERPRISE_CATALOG = 'use_enterprise_catalog'

# ContentFilter field types for validation.
CONTENT_FILTER_FIELD_TYPES = {
    'key': {'type': list, 'subtype': str},
    'first_enrollable_paid_seat_price__lte': {'type': str}
}


def json_serialized_course_modes():
    """
    :return: serialized course modes.
    """
    return json.dumps(COURSE_MODE_SORT_ORDER)


AVAILABLE_LANGUAGES = [
    ('en', u'English'),
    ('es-419', u'Español (Latinoamérica)'),  # Spanish (Latin America)
]
