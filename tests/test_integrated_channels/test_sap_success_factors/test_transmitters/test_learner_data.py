# -*- coding: utf-8 -*-
"""
Tests for SAPSF learner data transmissions.
"""

from __future__ import absolute_import, unicode_literals

import datetime
import unittest

import mock
from pytest import mark
from requests import RequestException

from integrated_channels.sap_success_factors.models import SapSuccessFactorsLearnerDataTransmissionAudit
from integrated_channels.sap_success_factors.transmitters import learner_data
from test_utils import factories


@mark.django_db
class TestSapSuccessFactorsLearnerDataTransmitter(unittest.TestCase):
    """
    Test SapSuccessFactorsLearnerTransmitter.
    """

    def setUp(self):
        super(TestSapSuccessFactorsLearnerDataTransmitter, self).setUp()
        self.global_config = factories.SAPSuccessFactorsGlobalConfigurationFactory()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret"
        )
        self.payload = SapSuccessFactorsLearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486855998,
            instructor_name='Professor Professorson',
            grade='Passing even more',
            error_message='',
        )
        self.exporter = lambda payload=self.payload: mock.MagicMock(export=mock.MagicMock(return_value=iter([payload])))

        # Mocks
        get_oauth_access_token_mock = mock.patch(
            'integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.get_oauth_access_token'
        )
        self.get_oauth_access_token_mock = get_oauth_access_token_mock.start()
        self.get_oauth_access_token_mock.return_value = "token", datetime.datetime.utcnow()
        self.addCleanup(get_oauth_access_token_mock.stop)

        create_course_completion_mock = mock.patch(
            'integrated_channels.sap_success_factors.client.SAPSuccessFactorsAPIClient.create_course_completion'
        )
        self.create_course_completion_mock = create_course_completion_mock.start()
        self.addCleanup(create_course_completion_mock.stop)

    def test_transmit_already_sent(self):
        """
        If we already sent a payload (we can tell if we did if it exists), don't send again.
        """
        self.payload.save()
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter())
        self.create_course_completion_mock.assert_not_called()

    def test_transmit_success(self):
        """
        Learner data transmission is successful and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.return_value = 200, '{"success":"true"}'
        payload = SapSuccessFactorsLearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486755998,
            instructor_name='Professor Professorson',
            grade='Pass',
        )
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter(payload))
        self.create_course_completion_mock.assert_called_with(payload.sapsf_user_id, payload.serialize())
        assert payload.status == '200'
        assert payload.error_message == ''

    def test_transmit_failure(self):
        """
        Learner data fails for some reason and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.side_effect = RequestException('error occurred')
        payload = SapSuccessFactorsLearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486755998,
            instructor_name='Professor Professorson',
            grade='Pass',
        )
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter(payload))
        self.create_course_completion_mock.assert_called_with(payload.sapsf_user_id, payload.serialize())
        assert payload.status == '500'
        assert payload.error_message == 'error occurred'
