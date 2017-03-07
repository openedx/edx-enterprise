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

    def transmit(self, payload):
        """
        Send a course data import call to SAP SuccessFactors using the client.

        Args:
            payload (SapCourseExporter): The OCN course exporter object to send to SAP SuccessFactors
        """
        serialized_payload = payload.get_serialized_data()
        LOGGER.info(serialized_payload)

        try:
            code, body = self.client.send_course_import(serialized_payload)
            LOGGER.debug('Successfully sent course metadata for Enterprise Customer {}'.
                         format(self.enterprise_configuration.enterprise_customer.name))
        except RequestException as request_exception:
            code = 500
            body = str(request_exception)
            LOGGER.error('Failed to send course metadata for Enterprise Customer {}\nError Message {}'.
                         format(self.enterprise_configuration.enterprise_customer.name, body))

        error_message = body if code >= 400 else ''

        CatalogTransmissionAudit = apps.get_model(  # pylint: disable=invalid-name
            app_label='sap_success_factors',
            model_name='CatalogTransmissionAudit'
        )

        catalog_transmission_audit = CatalogTransmissionAudit(
            enterprise_customer_uuid=self.enterprise_configuration.enterprise_customer.uuid,
            total_courses=len(payload.courses),
            status=str(code),
            error_message=error_message
        )

        catalog_transmission_audit.save()
        return catalog_transmission_audit
