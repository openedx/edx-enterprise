# -*- coding: utf-8 -*-
"""
Utility functions for interfacing with the Django messages framework.
"""

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
                support_link=get_configuration_value('ENTERPRISE_SUPPORT_URL', settings.ENTERPRISE_SUPPORT_URL),
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
                support_link=get_configuration_value('ENTERPRISE_SUPPORT_URL', settings.ENTERPRISE_SUPPORT_URL),
            ),
            platform_name=get_configuration_value('PLATFORM_NAME', settings.PLATFORM_NAME),
            link_end='</a>',
            span_start='<span>',
            span_end='</span>',
            strong_start='<strong>',
            strong_end='</strong>',
        )
    )


def add_unenrollable_item_message(request, item):
    """
    Add a message to the Django message store indicating that the item (i.e. course run, program) is unenrollable.

    :param request: The current request.
    :param item: The item that is unenrollable (i.e. a course run).
    """
    messages.info(
        request,
        _(
            '{strong_start}Something happened.{strong_end} '
            '{span_start}This {item} is not currently open to new learners. Please start over and select a different '
            '{item}.{span_end}'
        ).format(
            item=item,
            strong_start='<strong>',
            strong_end='</strong>',
            span_start='<span>',
            span_end='</span>',
        )
    )


def add_generic_error_message_with_code(request, error_code):
    """
    Add message to request indicating that there was an issue processing request.

    Arguments:
        request: The current request.
        error_code: A string error code to be used to point devs to the spot in
                    the code where this error occurred.

    """
    messages.error(
        request,
        _(
            '{strong_start}Something happened.{strong_end} '
            '{span_start}Please reach out to your learning administrator with '
            'the following error code and they will be able to help you out.{span_end}'
            '{span_start}Error code: {error_code}{span_end}'
            '{span_start}Username: {username}{span_end}'
        ).format(
            error_code=error_code,
            username=request.user.username,
            strong_start='<strong>',
            strong_end='</strong>',
            span_start='<span>',
            span_end='</span>',
        )
    )
