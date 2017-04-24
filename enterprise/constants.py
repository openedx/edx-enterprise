# -*- coding: utf-8 -*-
"""
Enterprise Django application constants.
"""

from __future__ import absolute_import, unicode_literals

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
