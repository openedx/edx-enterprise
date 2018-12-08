# -*- coding: utf-8 -*-
"""
Helper functions for the Consent application.
"""

from __future__ import absolute_import, unicode_literals

from django.apps import apps

from consent.models import ProxyDataSharingConsent
from enterprise.api_client.discovery import CourseCatalogApiServiceClient
from enterprise.utils import get_enterprise_customer


def get_data_sharing_consent(username, enterprise_customer_uuid, course_id=None, program_uuid=None):
    """
    Get the data sharing consent object associated with a certain user, enterprise customer, and other scope.

    :param username: The user that grants consent
    :param enterprise_customer_uuid: The consent requester
    :param course_id (optional): A course ID to which consent may be related
    :param program_uuid (optional): A program to which consent may be related
    :return: The data sharing consent object, or None if the enterprise customer for the given UUID does not exist.
    """
    EnterpriseCustomer = apps.get_model('enterprise', 'EnterpriseCustomer')  # pylint: disable=invalid-name
    try:
        if course_id:
            return get_course_data_sharing_consent(username, course_id, enterprise_customer_uuid)
        return get_program_data_sharing_consent(username, program_uuid, enterprise_customer_uuid)
    except EnterpriseCustomer.DoesNotExist:
        return None


def get_course_data_sharing_consent(username, course_id, enterprise_customer_uuid):
    """
    Get the data sharing consent object associated with a certain user of a customer for a course.

    :param username: The user that grants consent.
    :param course_id: The course for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: The data sharing consent object
    """
    # Prevent circular imports.
    DataSharingConsent = apps.get_model('consent', 'DataSharingConsent')  # pylint: disable=invalid-name
    return DataSharingConsent.objects.proxied_get(
        username=username,
        course_id=course_id,
        enterprise_customer__uuid=enterprise_customer_uuid
    )


def get_program_data_sharing_consent(username, program_uuid, enterprise_customer_uuid):
    """
    Get the data sharing consent object associated with a certain user of a customer for a program.

    :param username: The user that grants consent.
    :param program_uuid: The program for which consent is granted.
    :param enterprise_customer_uuid: The consent requester.
    :return: The data sharing consent object
    """
    enterprise_customer = get_enterprise_customer(enterprise_customer_uuid)
    discovery_client = CourseCatalogApiServiceClient(enterprise_customer.site)
    course_ids = discovery_client.get_program_course_keys(program_uuid)
    child_consents = (
        get_data_sharing_consent(username, enterprise_customer_uuid, course_id=individual_course_id)
        for individual_course_id in course_ids
    )
    return ProxyDataSharingConsent.from_children(program_uuid, *child_consents)
