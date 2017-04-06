"""
Module tests classes responsible for transmitting data to integrated channels.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import json
import unittest

import mock
from integrated_channels.sap_success_factors.models import (LearnerDataTransmissionAudit,
                                                            SAPSuccessFactorsEnterpriseCustomerConfiguration,
                                                            SAPSuccessFactorsGlobalConfiguration)
from integrated_channels.sap_success_factors.transmitters import courses, learner_data
from pytest import mark
from requests import RequestException

from test_utils.factories import EnterpriseCustomerFactory


class TestSuccessFactorsCourseTransmitter(unittest.TestCase):
    """
    Test SuccessFactorsCourseTransmitter.
    """

    @mark.django_db
    def setUp(self):
        super(TestSuccessFactorsCourseTransmitter, self).setUp()
        SAPSuccessFactorsGlobalConfiguration.objects.create(
            completion_status_api_path="",
            course_api_path="",
            oauth_api_path=""
        )

        enterprise_customer = EnterpriseCustomerFactory(
            name='Starfleet Academy',
        )

        self.enterprise_config = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=enterprise_customer,
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret"
        )

        self.payload = [{'course1': 'test1'}, {'course2': 'test2'}]

    @mark.django_db
    @mock.patch('integrated_channels.sap_success_factors.utils.reverse')
    @mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient')
    def test_transmit_success(self, client_mock, track_selection_reverse_mock):
        client_mock.get_oauth_access_token.return_value = "token", datetime.datetime.utcnow()
        client_mock_instance = client_mock.return_value
        client_mock_instance.send_course_import.return_value = 200, '{"success":"true"}'
        track_selection_reverse_mock.return_value = '/course_modes/choose/course-v1:edX+DemoX+Demo_Course/'

        payload_mock = mock.MagicMock(courses=self.payload)
        payload_mock.get_serialized_data_blocks.return_value = [(json.dumps(self.payload), 2)]

        transmitter = courses.SuccessFactorsCourseTransmitter(self.enterprise_config)
        assert transmitter.__class__.__bases__[0].__name__ == 'SuccessFactorsTransmitterBase'

        catalog_transmission_audit = transmitter.transmit(payload_mock)

        client_mock_instance.send_course_import.assert_called_with(json.dumps(self.payload))
        payload_mock.get_serialized_data_blocks.assert_called()
        assert catalog_transmission_audit.enterprise_customer_uuid == self.enterprise_config.enterprise_customer.uuid
        assert catalog_transmission_audit.total_courses == len(self.payload)
        assert catalog_transmission_audit.status == '200'
        assert catalog_transmission_audit.error_message == ''

    @mark.django_db
    @mock.patch('integrated_channels.sap_success_factors.utils.reverse')
    @mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient')
    def test_transmit_failure(self, client_mock, track_selection_reverse_mock):
        client_mock.get_oauth_access_token.return_value = "token", datetime.datetime.utcnow()
        client_mock_instance = client_mock.return_value
        client_mock_instance.send_course_import.side_effect = RequestException('error occurred')
        track_selection_reverse_mock.return_value = '/course_modes/choose/course-v1:edX+DemoX+Demo_Course/'

        payload_mock = mock.MagicMock(courses=self.payload)
        payload_mock.get_serialized_data_blocks.return_value = [(json.dumps(self.payload), 2)]

        transmitter = courses.SuccessFactorsCourseTransmitter(self.enterprise_config)

        catalog_transmission_audit = transmitter.transmit(payload_mock)

        client_mock_instance.send_course_import.assert_called_with(json.dumps(self.payload))
        payload_mock.get_serialized_data_blocks.assert_called()
        assert catalog_transmission_audit.enterprise_customer_uuid == self.enterprise_config.enterprise_customer.uuid
        assert catalog_transmission_audit.total_courses == len(self.payload)
        assert catalog_transmission_audit.status == '500'
        assert catalog_transmission_audit.error_message == 'error occurred'


class TestSuccessFactorsLearnerDataTransmitter(unittest.TestCase):
    """
    Test SuccessFactorsLearnerDataTransmitter.
    """

    @mark.django_db
    def setUp(self):
        super(TestSuccessFactorsLearnerDataTransmitter, self).setUp()
        SAPSuccessFactorsGlobalConfiguration.objects.create(
            completion_status_api_path="",
            course_api_path="",
            oauth_api_path=""
        )

        self.enterprise_config = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            secret="client_secret"
        )

    @mark.django_db
    @mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient')
    def test_transmit_already_sent(self, client_mock):
        client_mock.get_oauth_access_token.return_value = "token", datetime.datetime.utcnow()
        client_mock_instance = client_mock.return_value

        payload = LearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486755998,
            instructor_name='Professor Professorson',
            grade='Pass',
            error_message='',
        )
        payload.save()

        transmitter = learner_data.SuccessFactorsLearnerDataTransmitter(self.enterprise_config)
        response = transmitter.transmit(payload)
        assert response is None
        client_mock_instance.send_completion_status.assert_not_called()

    @mark.django_db
    @mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient')
    def test_transmit_success(self, client_mock):
        client_mock.get_oauth_access_token.return_value = "token", datetime.datetime.utcnow()
        client_mock_instance = client_mock.return_value
        client_mock_instance.send_completion_status.return_value = 200, '{"success":"true"}'

        payload = LearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486755998,
            instructor_name='Professor Professorson',
            grade='Pass',
        )
        transmitter = learner_data.SuccessFactorsLearnerDataTransmitter(self.enterprise_config)

        transmission_audit = transmitter.transmit(payload)
        client_mock_instance.send_completion_status.assert_called_with(
            payload.sapsf_user_id, payload.serialize()
        )
        assert transmission_audit.status == '200'
        assert transmission_audit.error_message == ''

    @mark.django_db
    @mock.patch('integrated_channels.sap_success_factors.transmitters.SAPSuccessFactorsAPIClient')
    def test_transmit_failure(self, client_mock):
        client_mock.get_oauth_access_token.return_value = "token", datetime.datetime.utcnow()
        client_mock_instance = client_mock.return_value
        client_mock_instance.send_completion_status.side_effect = RequestException('error occurred')

        payload = LearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=5,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486755998,
            instructor_name='Professor Professorson',
            grade='Pass',
        )
        transmitter = learner_data.SuccessFactorsLearnerDataTransmitter(self.enterprise_config)

        transmission_audit = transmitter.transmit(payload)
        client_mock_instance.send_completion_status.assert_called_with(
            payload.sapsf_user_id, payload.serialize()
        )
        assert transmission_audit.status == '500'
        assert transmission_audit.error_message == 'error occurred'
