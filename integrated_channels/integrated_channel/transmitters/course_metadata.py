# -*- coding: utf-8 -*-
"""
Generic course metadata transmitter for integrated channels.
"""

from __future__ import absolute_import, unicode_literals

import json
import logging

from integrated_channels.integrated_channel.client import IntegratedChannelApiClient
from integrated_channels.integrated_channel.transmitters import Transmitter
from requests import RequestException

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist

LOGGER = logging.getLogger(__name__)


class CourseTransmitter(Transmitter):
    """
    A generic course metadata transmitter.

    It may be subclassed by specific integrated channel course metadata transmitters for
    each integrated channel's particular course metadata transmission requirements and expectations.
    """

    def __init__(self, enterprise_configuration, client=IntegratedChannelApiClient):
        """
        By default, use the abstract integrated channel API client which raises an error when used if not subclassed.
        """
        super(CourseTransmitter, self).__init__(
            enterprise_configuration=enterprise_configuration,
            client=client
        )

    def transmit(self, payload, **kwargs):  # pylint: disable=unused-argument
        """
        Transmit the course metadata payload to the integrated channel.
        """
        total_transmitted = 0
        errors = []
        status_codes = []
        for course_metadata, method in payload.export():
            status_code, body = self.transmit_block(course_metadata, method=method)
            status_codes.append(str(status_code))
            error_message = body if status_code >= 400 else ''
            if error_message:
                errors.append(error_message)
            else:
                total_transmitted += len(course_metadata)

        error_message = ', '.join(errors) if errors else ''
        code_string = ', '.join(status_codes)

        # pylint: disable=invalid-name
        CatalogTransmissionAudit = apps.get_model('integrated_channel', 'CatalogTransmissionAudit')
        try:
            last_catalog_transmission = CatalogTransmissionAudit.objects.filter(
                error_message='',
                enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
                channel=self.enterprise_configuration.provider_id,
            ).latest('created')
            last_audit_summary = json.loads(last_catalog_transmission.audit_summary)
        except ObjectDoesNotExist:
            last_audit_summary = {}

        CatalogTransmissionAudit(
            enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
            total_courses=len(payload.courses),
            status=code_string,
            error_message=error_message,
            audit_summary=json.dumps(payload.resolve_removed_courses(last_audit_summary)),
            channel=self.enterprise_configuration.provider_id,
        ).save()

    def transmit_block(self, course_metadata, method='POST'):
        """
        Transmit a block of course metadata to the integrated channel.

        Handle any request errors and logging requirements.

        Args:
            course_metadata (bytes): A set of bytes containing a page's worth of course metadata
            method (str): One of ``POST`` or ``DELETE``, deciding which action the client should take
                          for this course run.

        Returns:
            status_code (int): An integer status for the HTTP request
            body (str): The server's response body
        """
        LOGGER.info(course_metadata)

        if method == 'POST':
            method = self.client.create_course_content
        elif method == 'DELETE':
            method = self.client.delete_course_content
        else:
            raise ValueError('Invalid method provided for the transmission of this course block: {}'.format(method))

        try:
            status_code, body = method(course_metadata)
        except RequestException as request_exception:
            status_code = 500
            body = str(request_exception)

        if status_code >= 400:
            LOGGER.error('Failed to send course metadata for Enterprise Customer {}\nError Message {}'.
                         format(self.enterprise_configuration.enterprise_customer.name, body))
        else:
            LOGGER.debug('Successfully sent course metadata for Enterprise Customer {}'.
                         format(self.enterprise_configuration.enterprise_customer.name))

        return status_code, body
