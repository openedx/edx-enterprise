# -*- coding: utf-8 -*-
"""
Tests for the SAP SuccessFactors content metadata transmitter.
"""

from __future__ import absolute_import, unicode_literals

import logging
import unittest

import mock
import responses
from pytest import mark
from testfixtures import LogCapture

from integrated_channels.exceptions import ClientError
from integrated_channels.integrated_channel.exporters.content_metadata import ContentMetadataItemExport
from integrated_channels.integrated_channel.models import ContentMetadataItemTransmission
from integrated_channels.sap_success_factors.transmitters.content_metadata import (
    SapSuccessFactorsContentMetadataTransmitter,
)
from test_utils import factories


@mark.django_db
class TestSapSuccessFactorsContentMetadataTransmitter(unittest.TestCase):
    """
    Tests for the class ``SapSuccessFactorsContentMetadataTransmitter``.
    """

    def setUp(self):
        super(TestSapSuccessFactorsContentMetadataTransmitter, self).setUp()
        self.url_base = 'http://test.successfactors.com/'
        self.oauth_api_path = 'learning/oauth-api/rest/v1/token'
        self.completion_status_api_path = 'learning/odatav4/public/admin/ocn/v1/current-user/item/learning-event'
        self.course_api_path = 'learning/odatav4/public/admin/ocn/v1/OcnCourses'
        self.expires_in = 1800
        self.access_token = 'access_token'
        self.expected_token_response_body = {'expires_in': self.expires_in, 'access_token': self.access_token}
        enterprise_customer = factories.EnterpriseCustomerFactory(name='Starfleet Academy')
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            key='client_id',
            sapsf_base_url=self.url_base,
            sapsf_company_id='company_id',
            sapsf_user_id='user_id',
            secret='client_secret',
        )
        factories.SAPSuccessFactorsGlobalConfiguration.objects.create(
            completion_status_api_path=self.completion_status_api_path,
            course_api_path=self.course_api_path,
            oauth_api_path=self.oauth_api_path
        )

    @responses.activate
    @mock.patch('integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.update_content_metadata')
    def test_transmit_create_failure(self, update_content_metadata_mock):
        """
        Test unsuccessful creation of content metadata during transmission.
        """
        content_id = 'course:DemoX'
        update_content_metadata_mock.side_effect = ClientError('error occurred')
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )

        with LogCapture(level=logging.ERROR) as log_capture:
            transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
            transmitter.transmit({
                content_id: ContentMetadataItemExport(
                    {'key': content_id, 'content_type': 'course'},
                    {'courseID': content_id, 'update': True}
                )
            })
            assert len(log_capture.records) == 2
            assert 'Failed to update [1] content metadata items' in log_capture.records[0].getMessage()
            assert not ContentMetadataItemTransmission.objects.filter(
                enterprise_customer=self.enterprise_config.enterprise_customer,
                integrated_channel_code=self.enterprise_config.channel_code(),
                content_id=content_id,
            ).exists()

    @responses.activate
    def test_prepare_items_for_delete(self):
        """
        Test items to be deleted are updated with a status of INACTIVE.
        """
        responses.add(
            responses.POST,
            self.url_base + self.oauth_api_path,
            json=self.expected_token_response_body,
            status=200
        )
        transmitter = SapSuccessFactorsContentMetadataTransmitter(self.enterprise_config)
        items_to_delete = {'test': {}}
        transmitter._prepare_items_for_delete(items_to_delete)  # pylint: disable=protected-access
        assert items_to_delete['test']['status'] == 'INACTIVE'
