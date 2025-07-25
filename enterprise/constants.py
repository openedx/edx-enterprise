"""
Enterprise Django application constants.
"""
from django.utils.translation import gettext_lazy as _

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
    'You have left the {strong_start}{enterprise_customer_name}{strong_end} website and are now on the '
    '{platform_name} site. {enterprise_customer_name} has partnered with {platform_name} to offer you '
    'high-quality, always available learning programs to help you advance your knowledge and career. '
    '{line_break}Please note that {platform_name} has a different {privacy_policy_link_start}Privacy Policy '
    '{privacy_policy_link_end} from {enterprise_customer_name}.'
)

COURSE_KEY_URL_PATTERN = r'(?P<course_key>[^/+]+(/|\+)[^/+]+)'

DEFAULT_USERNAME_ATTR = 'urn:oid:0.9.2342.19200300.100.1.1'

MAX_INVITE_KEYS = 100


class DefaultColors:
    """
    Class to group the default branding color codes.
    These color codes originated in the Enterprise Learner Portal.
    """
    PRIMARY = '#2D494E'
    SECONDARY = '#F2F0EF'
    TERTIARY = '#D23228'


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
    UNPAID_EXECUTIVE_EDUCATION = 'unpaid-executive-education'


# Course mode sorting based on slug
COURSE_MODE_SORT_ORDER = [
    CourseModes.VERIFIED,
    CourseModes.PROFESSIONAL,
    CourseModes.NO_ID_PROFESSIONAL,
    CourseModes.AUDIT,
    CourseModes.HONOR,
    CourseModes.UNPAID_EXECUTIVE_EDUCATION,
]

EXEC_ED_COURSE_TYPE = "executive-education-2u"
PRODUCT_SOURCE_2U = "2u"
EXEC_ED_CONTENT_DESCRIPTION_TAG = ("This instructor-led Executive Education course is "
                                   "presented by GetSmarter, an edX partner. ")

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
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'em', 'i',
    'li', 'ol', 'strong', 'ul', 'p', 'h1', 'h2',
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
SYSTEM_ENTERPRISE_PROVISIONING_ADMIN_ROLE = 'enterprise_provisioning_admin'

ENTERPRISE_DASHBOARD_ADMIN_ROLE = 'dashboard_admin'
ENTERPRISE_CATALOG_ADMIN_ROLE = 'catalog_admin'
ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE = 'enrollment_api_admin'
ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE = 'reporting_config_admin'
ENTERPRISE_FULFILLMENT_OPERATOR_ROLE = 'fulfillment_operator'
ENTERPRISE_SSO_ORCHESTRATOR_OPERATOR_ROLE = 'sso_orchestrator_operator'

# Default enterprise enrollment roles/permissions
DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_ROLE = 'default_enterprise_enrollment_intentions_learner'
DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION = 'enterprise.can_view_default_enterprise_enrollment_intentions'

# Provisioning admins roles:
PROVISIONING_ENTERPRISE_CUSTOMER_ADMIN_ROLE = 'provisioning_enterprise_customer_admin'
PROVISIONING_PENDING_ENTERPRISE_CUSTOMER_ADMIN_ROLE = 'provisioning_pending_enterprise_customer_users_admin'
# Provisioning admins permissions:
ENTERPRISE_CUSTOMER_PROVISIONING_ADMIN_ACCESS_PERMISSION = 'provisioning.has_enterprise_customer_admin_access'
PENDING_ENT_CUSTOMER_ADMIN_PROVISIONING_ADMIN_ACCESS_PERMISSION = \
    'provisioning.has_pending_enterprise_customer_admin_access'

# Tracking related
PATHWAY_CUSTOMER_ADMIN_ENROLLMENT = 'customer-admin-enrollment'

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

# FEATURE flag that indicates if deletion of EnterpriseCourseEnrollment records via
# the Django Admin site is allowed.
ALLOW_ADMIN_ENTERPRISE_COURSE_ENROLLMENT_DELETION = 'ALLOW_ADMIN_ENTERPRISE_COURSE_ENROLLMENT_DELETION'


def json_serialized_course_modes():
    """
    :return: serialized course modes.
    """
    return COURSE_MODE_SORT_ORDER


AVAILABLE_LANGUAGES = [
    ('en', 'English'),
    ('es-419', 'Español (Latinoamérica)'),  # Spanish (Latin America)
    ('ar', 'العربية'),  # Arabic
    ('zh-cn', '中文 (简体)'),  # Chinese (China)
    ('fr-ca', 'français (Canada)'),  # French (Canada)
    ('da', 'dansk'),  # Danish
    ('de-de', 'Deutsch (Deutschland)'),  # German (Germany)
    ('el', 'Ελληνικά'),  # Greek
    ('he', 'עברית'),  # Hebrew
    ('hi', 'हिन्दी'),  # Hindi
    ('id', 'Bahasa Indonesia'),  # Indonesian
    ('it-it', 'Italiano (Italia)'),  # Italian (Italy)
    ('pt-br', 'Português (Brasil)'),  # Portuguese (Brazil)
    ('pt-pt', 'Português (Portugal)'),  # Portuguese (Portugal)
    ('ru', 'Русский'),  # Russian
    ('es-es', 'Español (España)'),  # Spanish (Spain)
    ('sw', 'Kiswahili'),  # Swahili
    ('te', 'తెలుగు'),  # Telugu
    ('th', 'ไทย'),  # Thai
    ('tr-tr', 'Türkçe (Türkiye)'),  # Turkish (Turkey)
    ('uk', 'українська'),  # Ukrainian
]

LMS_API_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
LMS_API_DATETIME_FORMAT_WITHOUT_TIMEZONE = '%Y-%m-%dT%H:%M:%S'

TRANSMISSION_MARK_CREATE = 'create'
TRANSMISSION_MARK_UPDATE = 'update'
TRANSMISSION_MARK_DELETE = 'delete'

HTTP_STATUS_STRINGS = {
    400: 'The request was invalid, check the fields you entered are correct.',
    401: 'The request was unauthorized, check your credentials.',
    403: 'The request was rejected because it did not have the rights to access the content.',
    404: 'The requested resource was not found.',
    408: 'The request timed out.',
    429: 'The user has sent too many requests.',
    500: 'An internal problem on our side interfered.',
    503: 'The server is temporarily unavailable.',
}

IC_CREATE_ACTION = 'create'
IC_UPDATE_ACTION = 'update'
IC_DELETE_ACTION = 'delete'


class FulfillmentTypes:
    LICENSE = 'license'
    LEARNER_CREDIT = 'learner_credit'
    COUPON_CODE = 'coupon_code'
    CHOICES = [(choice, choice.capitalize().replace('_', ' ')) for choice in (LICENSE, LEARNER_CREDIT, COUPON_CODE)]


SSO_BRAZE_CAMPAIGN_ID = 'a5f10d46-8093-4ce1-bab7-6df018d03660'

# The maximum length of a text field in the database.
MAX_ALLOWED_TEXT_LENGTH = 16_000_000

GROUP_MEMBERSHIP_PENDING_STATUS = 'pending'
GROUP_MEMBERSHIP_REMOVED_STATUS = 'removed'
GROUP_MEMBERSHIP_ACCEPTED_STATUS = 'accepted'
GROUP_MEMBERSHIP_INTERNAL_API_ERROR_STATUS = 'internal_api_error'
GROUP_MEMBERSHIP_EMAIL_ERROR_STATUS = 'email_error'
GROUP_MEMBERSHIP_STATUS_CHOICES = (
    (GROUP_MEMBERSHIP_REMOVED_STATUS, 'Removed'),
    (GROUP_MEMBERSHIP_ACCEPTED_STATUS, 'Accepted'),
    (GROUP_MEMBERSHIP_PENDING_STATUS, 'Pending'),
    (GROUP_MEMBERSHIP_INTERNAL_API_ERROR_STATUS, 'Internal API error'),
    (GROUP_MEMBERSHIP_EMAIL_ERROR_STATUS, 'Email error')
)
GROUP_TYPE_BUDGET = 'budget'
GROUP_TYPE_FLEX = 'flex'
GROUP_TYPE_CHOICES = (
    (GROUP_TYPE_BUDGET, 'Budget'),
    (GROUP_TYPE_FLEX, 'Flex')
)

ENTITY_ID_REGEX = r"<(\w+:)?EntityDescriptor.*?entityID=['\"](.*?)['\"].*?>"

# Max learners included in the Admin Manage Learners page
DJANGO_ADMIN_MANAGE_LEARNERS_LIMIT = 10000
