# -*- coding: utf-8 -*-
"""
Enterprise Django application constants.
"""

from __future__ import absolute_import, unicode_literals

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

COURSE_KEY_URL_PATTERN = r'(?P<course_key>[^/+]+(/|\+)[^/+]+)'

# Course mode sorting based on slug
COURSE_MODE_SORT_ORDER = ['verified', 'professional', 'no-id-professional', 'audit', 'honor']

# Course modes that should not be displayed to users.
EXCLUDED_COURSE_MODES = ['credit']


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


def json_serialized_course_modes():
    """
    :return: serialized course modes.
    """
    return json.dumps(COURSE_MODE_SORT_ORDER)
