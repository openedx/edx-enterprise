# -*- coding: utf-8 -*-
"""
Utility functions for interfacing with the Django messages framework.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib import messages
from django.utils.translation import ugettext as _

from enterprise.utils import get_configuration_value


def add_consent_declined_message(request, enterprise_customer, item):
    """
    Add a message to the Django messages store indicating that the user has declined data sharing consent.

    Arguments:
        request (HttpRequest): The current request.
        enterprise_customer (EnterpriseCustomer): The EnterpriseCustomer associated with this request.
        item (str): A string containing information about the item for which consent was declined.
    """
    messages.warning(
        request,
        _(
            '{strong_start}We could not enroll you in {em_start}{item}{em_end}.{strong_end} '
            '{span_start}If you have questions or concerns about sharing your data, please contact your learning '
            'manager at {enterprise_customer_name}, or contact {link_start}{platform_name} support{link_end}.{span_end}'
        ).format(
            item=item,
            em_start='<em>',
            em_end='</em>',
            enterprise_customer_name=enterprise_customer.name,
            link_start='<a href="{support_link}" target="_blank">'.format(
                support_link=get_configuration_value(
                    'ENTERPRISE_SUPPORT_URL',
                    getattr(settings, 'ENTERPRISE_SUPPORT_URL', '')  # Remove the `getattr` when setting is upstreamed.
                ),
            ),
            platform_name=get_configuration_value('PLATFORM_NAME', settings.PLATFORM_NAME),
            link_end='</a>',
            span_start='<span>',
            span_end='</span>',
            strong_start='<strong>',
            strong_end='</strong>',
        )
    )


def add_missing_price_information_message(request, item):
    """
    Add a message to the Django messages store indicating that we failed to retrieve price information about an item.

    :param request: The current request.
    :param item: The item for which price information is missing. Example: a program title, or a course.
    """
    messages.warning(
        request,
        _(
            '{strong_start}We could not gather price information for {em_start}{item}{em_end}.{strong_end} '
            '{span_start}If you continue to have these issues, please contact '
            '{link_start}{platform_name} support{link_end}.{span_end}'
        ).format(
            item=item,
            em_start='<em>',
            em_end='</em>',
            link_start='<a href="{support_link}" target="_blank">'.format(
                support_link=get_configuration_value(
                    'ENTERPRISE_SUPPORT_URL',
                    getattr(settings, 'ENTERPRISE_SUPPORT_URL', '')  # Remove the `getattr` when setting is upstreamed.
                ),
            ),
            platform_name=get_configuration_value('PLATFORM_NAME', settings.PLATFORM_NAME),
            link_end='</a>',
            span_start='<span>',
            span_end='</span>',
            strong_start='<strong>',
            strong_end='</strong>',
        )
    )


def add_not_one_click_purchasable_message(request, enterprise_customer, program_title):
    """
    Add a message to the Django message store indicating that the program is not one-click purchasable.

    Only one-click purchasable programs should be available for enrollment through the Enterprise landing page flow.

    :param request: The current request.
    :param enterprise_customer: The Enterprise Customer to which the program is associated.
    :param program_title: The title of the program that is not one-click purchasable.
    """
    messages.warning(
        request,
        _(
            '{strong_start}We could not load the program titled {em_start}{program_title}{em_end} through '
            '{enterprise_customer_name}.{strong_end} '
            '{span_start}If you have any questions, please contact your learning manager at '
            '{enterprise_customer_name}, or contact {link_start}{platform_name} support{link_end}.{span_end}'
        ).format(
            program_title=program_title,
            enterprise_customer_name=enterprise_customer.name,
            em_start='<em>',
            em_end='</em>',
            link_start='<a href="{support_link}" target="_blank">'.format(
                support_link=get_configuration_value(
                    'ENTERPRISE_SUPPORT_URL',
                    getattr(settings, 'ENTERPRISE_SUPPORT_URL', '')  # Remove the `getattr` when setting is upstreamed.
                ),
            ),
            platform_name=get_configuration_value('PLATFORM_NAME', settings.PLATFORM_NAME),
            link_end='</a>',
            span_start='<span>',
            span_end='</span>',
            strong_start='<strong>',
            strong_end='</strong>',
        )
    )
