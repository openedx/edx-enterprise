"""
Tests for SAPSF learner data transmissions.
"""

import datetime
import unittest
from unittest import mock

import ddt
from pytest import mark

from integrated_channels.exceptions import ClientError
from integrated_channels.sap_success_factors.models import SapSuccessFactorsLearnerDataTransmissionAudit
from integrated_channels.sap_success_factors.transmitters import learner_data
from test_utils import factories


@ddt.ddt
@mark.django_db
class TestSapSuccessFactorsLearnerDataTransmitter(unittest.TestCase):
    """
    Test SapSuccessFactorsLearnerTransmitter.
    """

    def setUp(self):
        super().setUp()
        self.global_config = factories.SAPSuccessFactorsGlobalConfigurationFactory()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer
        )
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=5,
            enterprise_customer_user=self.enterprise_customer_user
        )
        self.enterprise_config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            decrypted_key="client_id",
            sapsf_base_url="http://test.successfactors.com/",
            sapsf_company_id="company_id",
            sapsf_user_id="user_id",
            decrypted_secret="client_secret"
        )
        self.payloads = [
            SapSuccessFactorsLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
                sapsf_user_id='sap_user',
                course_id='course-v1:edX+DemoX+DemoCourse',
                course_completed=True,
                sap_completed_timestamp=1486855998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486855998),
                instructor_name='Professor Professorson',
                grade='Passing even more',
                error_message='',
                status=200,
                enterprise_customer_uuid=self.enterprise_customer.uuid,
                plugin_configuration_id=self.enterprise_config.id,
                is_transmitted=True
            )
        ]
        self.exporter = lambda payloads=self.payloads: mock.MagicMock(
            export=mock.MagicMock(return_value=iter(payloads))
        )

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
        self.payloads[0].save()
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter())
        self.create_course_completion_mock.assert_not_called()

    def test_avoid_retransmit_on_grade_change(self):
        """
        SAPSF does not support retransmsmitting completion, so we don't do that
        if just a grade changed relative to what is already saved
        """

        self.payloads[0].save()

        # let's try to send a payload with everything same except the grade
        payload = self.payloads[0]
        payload.grade = 'a_bit_different_grade'

        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter([payload]))
        self.create_course_completion_mock.assert_not_called()

    def test_transmit_success(self):
        """
        Learner data transmission is successful and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.return_value = 200, '{"success":"true"}'
        payload = SapSuccessFactorsLearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            sap_completed_timestamp=1486755998,
            completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
            instructor_name='Professor Professorson',
            grade='Pass',
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.enterprise_config.id,
        )
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter([payload]))
        self.create_course_completion_mock.assert_called_with(payload.sapsf_user_id, payload.serialize())
        assert payload.status == '200'
        assert payload.error_message == ''
        assert payload.is_transmitted is True

    def test_transmit_failure(self):
        """
        Learner data transmission fails for some reason and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.side_effect = ClientError('error occurred')
        payload = SapSuccessFactorsLearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            sap_completed_timestamp=1486755998,
            completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
            instructor_name='Professor Professorson',
            grade='Pass',
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.enterprise_config.id,
        )
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter([payload]))
        self.create_course_completion_mock.assert_called_with(payload.sapsf_user_id, payload.serialize())
        assert payload.status == '500'
        assert payload.error_message == 'error occurred'
        assert payload.is_transmitted is False

    @ddt.data(
        ('user account is inactive', False),
        ('meh, usual network problem', True)
    )
    @ddt.unpack
    def test_transmit_failure_user_inactive(self, content, ecu_active_expectation):
        """Learner data transmission fails because the user is inactive on the SAPSF side, so we mark them inactive
        internally."""
        self.create_course_completion_mock.side_effect = ClientError(content)
        payload = SapSuccessFactorsLearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            sapsf_user_id='sap_user',
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            sap_completed_timestamp=1486755998,
            completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
            instructor_name='Professor Professorson',
            grade='Pass',
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            plugin_configuration_id=self.enterprise_config.id,
        )
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter([payload]))
        self.create_course_completion_mock.assert_called_with(payload.sapsf_user_id, payload.serialize())
        self.enterprise_customer_user.refresh_from_db()
        assert self.enterprise_customer_user.active == ecu_active_expectation
        assert payload.status == '500'
        assert payload.error_message == content

    def test_transmit_by_course_key_success(self):
        """
        This tests the case where the transmission with the course key succeeds, and as a result
        the transmission with the course run id does not get attempted.
        """
        self.create_course_completion_mock.return_value = 200, '{"success":"true"}'
        payloads = [
            SapSuccessFactorsLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
                sapsf_user_id='sap_user',
                course_id='edX+DemoX',
                course_completed=True,
                sap_completed_timestamp=1486755998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
                instructor_name='Professor Professorson',
                grade='Pass',
                enterprise_customer_uuid=self.enterprise_customer.uuid,
                plugin_configuration_id=self.enterprise_config.id,
            ),
            SapSuccessFactorsLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
                sapsf_user_id='sap_user',
                course_id='course-v1:edX+DemoX+DemoCourse',
                course_completed=True,
                sap_completed_timestamp=1486755998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
                instructor_name='Professor Professorson',
                grade='Pass',
                enterprise_customer_uuid=self.enterprise_customer.uuid,
                plugin_configuration_id=self.enterprise_config.id,
            )
        ]
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter(payloads))
        self.create_course_completion_mock.assert_called_once()
        self.create_course_completion_mock.assert_called_with(payloads[0].sapsf_user_id, payloads[0].serialize())

        assert payloads[0].status == '200'
        assert payloads[0].error_message == ''
        assert not payloads[1].status

    def test_transmit_by_course_id_success(self):
        """
        This tests the case where the transmission with the course key fails, and as a result
        the transmission with the course run id is sent as well and succeeds.
        """
        self.create_course_completion_mock.side_effect = [
            ClientError('error occurred'),
            (200, '{"success":"true"}')
        ]
        payloads = [
            SapSuccessFactorsLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
                sapsf_user_id='sap_user',
                course_id='edX+DemoX',
                course_completed=True,
                sap_completed_timestamp=1486755998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
                instructor_name='Professor Professorson',
                grade='Pass',
                enterprise_customer_uuid=self.enterprise_customer.uuid,
                plugin_configuration_id=self.enterprise_config.id,
            ),
            SapSuccessFactorsLearnerDataTransmissionAudit(
                enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
                sapsf_user_id='sap_user',
                course_id='course-v1:edX+DemoX+DemoCourse',
                course_completed=True,
                sap_completed_timestamp=1486755998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486755998),
                instructor_name='Professor Professorson',
                grade='Pass',
                enterprise_customer_uuid=self.enterprise_customer.uuid,
                plugin_configuration_id=self.enterprise_config.id,
            )
        ]
        transmitter = learner_data.SapSuccessFactorsLearnerTransmitter(self.enterprise_config)
        transmitter.transmit(self.exporter(payloads))
        expected_calls = [
            mock.call(payloads[0].sapsf_user_id, payloads[0].serialize()),
            mock.call(payloads[1].sapsf_user_id, payloads[1].serialize()),
        ]
        self.create_course_completion_mock.assert_has_calls(expected_calls)

        assert payloads[0].status == '500'
        assert payloads[0].error_message == 'error occurred'
        assert payloads[1].status == '200'
        assert payloads[1].error_message == ''

    def test_override_channel_settings(self):
        """
        If you add any settings to the ChannelSettingsMixin, add a test here for the common default value
        """
        assert learner_data.SapSuccessFactorsLearnerTransmitter(
            self.enterprise_config
        ).INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK is False
