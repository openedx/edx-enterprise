# -*- coding: utf-8 -*-
"""
Django signal handlers.
"""
from __future__ import absolute_import, unicode_literals

from logging import getLogger

from enterprise.models import EnterpriseCustomerUser, PendingEnterpriseCustomerUser
from enterprise.utils import disable_for_loaddata

logger = getLogger(__name__)  # pylint: disable=invalid-name


@disable_for_loaddata
def handle_user_post_save(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Handle User model changes - checks if pending enterprise customer user record exists and upgrades it to actual link.
    """
    created = kwargs.get("created", False)
    user_instance = kwargs.get("instance", None)

    if user_instance is None:
        return  # should never happen, but better safe than 500 error

    try:
        pending_link_record = PendingEnterpriseCustomerUser.objects.get(user_email=user_instance.email)
    except PendingEnterpriseCustomerUser.DoesNotExist:
        return  # nothing to do in this case

    if not created:
        # existing user changed his email to match one of pending link records - try linking him to EC
        try:
            existing_record = EnterpriseCustomerUser.objects.get(user_id=user_instance.id)
            message_template = "User {user} have changed email to match pending Enterprise Customer link, " \
                               "but was already linked to Enterprise Customer {enterprise_customer} - " \
                               "deleting pending link record"
            logger.info(message_template.format(
                user=user_instance, enterprise_customer=existing_record.enterprise_customer
            ))
            pending_link_record.delete()
            return
        except EnterpriseCustomerUser.DoesNotExist:
            pass  # everything ok - current user is not linked to other ECs

    EnterpriseCustomerUser.objects.create(
        enterprise_customer=pending_link_record.enterprise_customer,
        user_id=user_instance.id
    )
    pending_link_record.delete()
