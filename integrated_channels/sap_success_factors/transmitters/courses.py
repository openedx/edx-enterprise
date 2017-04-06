"""
Class for transmitting course data to SuccessFactors.
"""
from __future__ import absolute_import, unicode_literals

import logging
from django.apps import apps

from integrated_channels.sap_success_factors.transmitters import SuccessFactorsTransmitterBase
from requests import RequestException


LOGGER = logging.getLogger(__name__)


class SuccessFactorsCourseTransmitter(SuccessFactorsTransmitterBase):
    """
    This endpoint is intended to carry out an export of course data to SuccessFactors for a given Enterprise.
    """

    def transmit_block(self, serialized_payload):
        """
        SAPSuccessFactors can only send 1000 items at a time, so this method sends one "page" at a time.

        Args:
            serialized_payload (bytes): A set of bytes containing a page's worth of data

        Returns:
            status_code (int): An integer status for the HTTP request
            body (str): The SAP SuccessFactors server's response body
        """
        LOGGER.info(serialized_payload)
        try:
            status_code, body = self.client.send_course_import(serialized_payload)
            LOGGER.debug('Successfully sent course metadata for Enterprise Customer {}'.
                         format(self.enterprise_configuration.enterprise_customer.name))
        except RequestException as request_exception:
            status_code = 500
            body = str(request_exception)
            LOGGER.error('Failed to send course metadata for Enterprise Customer {}\nError Message {}'.
                         format(self.enterprise_configuration.enterprise_customer.name, body))

        return status_code, body

    def transmit(self, payload):
        """
        Send a course data import call to SAP SuccessFactors using the client.

        Args:
            payload (SapCourseExporter): The OCN course exporter object to send to SAP SuccessFactors
        """
        total_transmitted = 0
        errors = []
        status_codes = []
        for serialized_payload, length in payload.get_serialized_data_blocks():
            status_code, body = self.transmit_block(serialized_payload)
            status_codes.append(str(status_code))
            error_message = body if status_code >= 400 else ''
            if error_message:
                errors.append(error_message)
            else:
                total_transmitted += length

        error_message = ', '.join(errors) if errors else ''
        code_string = ', '.join(status_codes)

        CatalogTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label='sap_success_factors',
            model_name='CatalogTransmissionAudit'
        )

        catalog_transmission_audit = CatalogTransmissionAudit(
            enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
            total_courses=len(payload.courses),
            status=code_string,
            error_message=error_message
        )

        catalog_transmission_audit.save()
        return catalog_transmission_audit
