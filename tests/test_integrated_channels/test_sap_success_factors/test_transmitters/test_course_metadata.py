# -*- coding: utf-8 -*-
"""
Tests for SAPSF course metadata transmissions.
"""

from __future__ import absolute_import, unicode_literals

import datetime
import json
import unittest

import ddt
import mock
from integrated_channels.integrated_channel.models import CatalogTransmissionAudit
from integrated_channels.sap_success_factors.transmitters import course_metadata
from pytest import mark
from requests import RequestException

from test_utils import factories


@mark.django_db
@ddt.ddt
class TestSapSuccessFactorsCourseTransmitter(unittest.TestCase):
    """
    Tests for the class ``SapSuccessFactorsCourseTransmitter``.
    """

    def setUp(self):
        super(TestSapSuccessFactorsCourseTransmitter, self).setUp()
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret",
        )
        self.global_config = factories.SAPSuccessFactorsGlobalConfigurationFactory()
        self.payload = [{'course1': 'test1'}, {'course2': 'test2'}]
        self.json_dump = json.dumps(self.payload)

        # Mocks
        get_oauth_access_token_mock = mock.patch(
            'integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token'
        )
        self.get_oauth_access_token_mock = get_oauth_access_token_mock.start()
        self.get_oauth_access_token_mock.return_value = "token", datetime.datetime.utcnow()
        self.addCleanup(get_oauth_access_token_mock.stop)
        create_course_content_mock = mock.patch(
            'integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_course_content'
        )
        self.create_course_content_mock = create_course_content_mock.start()
        self.addCleanup(create_course_content_mock.stop)

    @ddt.data(
        (
            (200, '{"success":"true"}'),
            '200',
            '',
            {},
            False
        ),
        (
            RequestException('error occurred'),
            '500',
            'error occurred',
            {},
            False
        ),
        (
            (200, '{"success":"true"}'),
            '200',
            '',
            {
                'test_course': {
                    'in_catalog': True,
                    'status': 'ACTIVE',
                }
            },
            True
        ),
    )
    @ddt.unpack
    def test_transmit_success(
            self,
            expected_transmit_result,
            expected_status,
            expected_error_message,
            audit_summary,
            has_previous_transmission
    ):
        """
        The catalog data transmission audit that gets saved after the transmission completes contains appropriate data.
        """
        if has_previous_transmission:
            transmission_audit = CatalogTransmissionAudit(
                enterprise_customer_uuid=self.enterprise_config.enterprise_customer.uuid,
                total_courses=2,
                status='200',
                error_message='',
                audit_summary=json.dumps(audit_summary),
                channel=self.enterprise_config.provider_id,
            )
            transmission_audit.save()

        if isinstance(expected_transmit_result, tuple):
            self.create_course_content_mock.return_value = expected_transmit_result
        else:
            self.create_course_content_mock.side_effect = expected_transmit_result

        course_exporter_mock = mock.MagicMock(courses=self.payload)
        course_exporter_mock.export.return_value = [(self.json_dump, 'POST')]
        course_exporter_mock.resolve_removed_courses.return_value = {}

        transmitter = course_metadata.SapSuccessFactorsCourseTransmitter(self.enterprise_config)
        transmitter.transmit(course_exporter_mock)

        self.create_course_content_mock.assert_called_with(self.json_dump)
        course_exporter_mock.resolve_removed_courses.assert_called_with(audit_summary)
        course_exporter_mock.export.assert_called()

        catalog_transmission_audit = CatalogTransmissionAudit.objects.filter(
            enterprise_customer_uuid=self.enterprise_config.enterprise_customer.uuid,
            channel=self.enterprise_config.provider_id,
        ).latest('created')
        assert catalog_transmission_audit.enterprise_customer_uuid == self.enterprise_config.enterprise_customer.uuid
        assert catalog_transmission_audit.total_courses == len(self.payload)
        assert catalog_transmission_audit.status == expected_status
        assert catalog_transmission_audit.error_message == expected_error_message
