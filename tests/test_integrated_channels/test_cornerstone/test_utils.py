"""
Tests for the utilities used by Cornerstone integration channel.
"""

import unittest

import ddt
from pytest import mark

from django.test import RequestFactory

from integrated_channels.cornerstone.models import (
    CornerstoneEnterpriseCustomerConfiguration,
    CornerstoneLearnerDataTransmissionAudit,
)
from integrated_channels.cornerstone.utils import create_cornerstone_learner_data
from test_utils.factories import EnterpriseCustomerCatalogFactory, EnterpriseCustomerFactory, UserFactory


@ddt.ddt
class TestCornerstoneUtils(unittest.TestCase):
    """
    Test utility functions used by Cornerstone integration channel.
    """
    def setUp(self):
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_customer_catalog = EnterpriseCustomerCatalogFactory(
            enterprise_customer=self.enterprise_customer
        )
        self.config = CornerstoneEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            catalogs_to_transmit=str(self.enterprise_customer_catalog.uuid),
            active=True,
            cornerstone_base_url='https://dummy_subdomain.csod.com'
        )
        self.config.save()
        self.config2 = CornerstoneEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            catalogs_to_transmit=str(self.enterprise_customer_catalog.uuid),
            active=True,
            cornerstone_base_url='https://edx-two.csod.com'
        )
        self.config2.save()

        super().setUp()

    @staticmethod
    def _assert_learner_data_transmission_audit(transmission_audit, user, course_id, querystring):
        """ Asserts CornerstoneLearnerDataTransmissionAudit values"""
        assert transmission_audit.user == user
        assert transmission_audit.course_id == course_id
        assert transmission_audit.user_guid == querystring['userGuid']
        assert transmission_audit.session_token == querystring['sessionToken']
        assert transmission_audit.callback_url == querystring['callbackUrl']
        assert transmission_audit.subdomain == querystring['subdomain']

    @staticmethod
    def _get_request(querystring, user=None):
        """ returns mocked request """
        request = RequestFactory().get(path='/', data=querystring)
        request.user = user if user else UserFactory()
        return request

    @ddt.data(
        (
            {
                'userGuid': 'dummy_id',
                'sessionToken': 'dummySessionToken',
                'callbackUrl': 'dummy_callbackUrl',
                'subdomain': 'dummy_subdomain',
            },
            'dummy_courseId',
            True,
        ),
        (
            {
                'callbackUrl': 'dummy_callbackUrl',
                'subdomain': 'dummy_subdomain',
            },
            'dummy_courseId',
            False,
        ),
        (
            {},
            None,
            False,
        ),
    )
    @ddt.unpack
    @mark.django_db
    def test_update_cornerstone_learner_data_transmission_audit(self, querystring, course_id, expected_result):
        """ test creating records """
        request = self._get_request(querystring)
        create_cornerstone_learner_data(request, self.config, course_id)
        actual_result = request.user.cornerstone_transmission_audit.filter(course_id=course_id).exists()
        assert actual_result == expected_result
        if expected_result:
            record = request.user.cornerstone_transmission_audit.filter(course_id=course_id).first()
            assert record.enterprise_customer_uuid == self.enterprise_customer.uuid
            assert record.plugin_configuration_id == self.config.id

    @mark.django_db
    def test_update_cornerstone_learner_data_transmission_audit_with_existing_data(self):
        """ test updating audit records """
        user = UserFactory()
        course_id = 'dummy_courseId'
        querystring = {
            'userGuid': 'dummy_id',
            'sessionToken': 'dummy_session_token',
            'callbackUrl': 'dummy_callbackUrl',
            'subdomain': 'dummy_subdomain',
        }

        # creating data for first time
        request = self._get_request(querystring, user)
        create_cornerstone_learner_data(request, self.config, course_id)
        records = CornerstoneLearnerDataTransmissionAudit.objects.all()
        assert records.count() == 1
        self._assert_learner_data_transmission_audit(records.first(), user, course_id, querystring)

        # Updating just sessionToken Should NOT create new records, instead update old one.
        querystring['sessionToken'] = 'updated_dummy_session_token'
        request = self._get_request(querystring, user)
        create_cornerstone_learner_data(request, self.config, course_id)
        records = CornerstoneLearnerDataTransmissionAudit.objects.all()
        assert records.count() == 1
        self._assert_learner_data_transmission_audit(records.first(), user, course_id, querystring)

        # But updating courseId Should create fresh record.
        course_id = 'updated_dummy_courseId'
        request = self._get_request(querystring, user)
        create_cornerstone_learner_data(request, self.config, course_id)
        records = CornerstoneLearnerDataTransmissionAudit.objects.all()
        assert records.count() == 2
        self._assert_learner_data_transmission_audit(records[1], user, course_id, querystring)
