# -*- coding: utf-8 -*-
"""
Utility functions for interfacing with the Django messages framework.
"""
from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.utils.translation import ugettext as _

try:
    from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
except ImportError:
    configuration_helpers = None


def add_consent_declined_message(request, enterprise_customer, course_details):
    """
    Add a message to the Django messages store indicating that the user has declined data sharing consent.

    Arguments:
        request (HttpRequest): The current request.
        enterprise_customer (EnterpriseCustomer): The EnterpriseCustomer associated with this request.
        course_details (dict): A dictionary containing information about the course the user had declined consent for.
    """
    messages.warning(
        request,
        _(
            '{strong_start}We could not enroll you in {em_start}{course_name}{em_end}.{strong_end} '
            '{span_start}If you have questions or concerns about sharing your data, please contact your learning '
            'manager at {enterprise_customer_name}, or contact {link_start}{platform_name} support{link_end}.{span_end}'
        ).format(
            course_name=course_details.get('name'),
            em_start='<em>',
            em_end='</em>',
            enterprise_customer_name=enterprise_customer.name,
            link_start='<a href="{support_link}" target="_blank">'.format(
                support_link=configuration_helpers.get_value('ENTERPRISE_SUPPORT_URL')
            ),
            platform_name=configuration_helpers.get_value('PLATFORM_NAME'),
            link_end='</a>',
            span_start='<span>',
            span_end='</span>',
            strong_start='<strong>',
            strong_end='</strong>',
        )
    )
