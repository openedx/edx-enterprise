# -*- coding: utf-8 -*-
"""
Enterprise Django application constants.
"""

from __future__ import absolute_import, unicode_literals

# We listen to the User post_save signal in order to associate new users
# with an EnterpriseCustomer when applicable. This it the unique identifier
# used to ensure that signal receiver is only called once.
USER_POST_SAVE_DISPATCH_UID = "user_post_save_upgrade_pending_enterprise_customer_user"
