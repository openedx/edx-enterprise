"""
Tests for Moodle learner data transmissions.
"""
import datetime
import unittest
from unittest import mock
from unittest.mock import Mock

from pytest import mark

from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter, LearnerExporterUtility
from integrated_channels.integrated_channel.transmitters.learner_data import LearnerTransmitter
from integrated_channels.moodle.models import MoodleLearnerDataTransmissionAudit
from integrated_channels.moodle.transmitters import learner_data
from integrated_channels.utils import encode_data_for_logging, generate_formatted_log
from test_utils import factories


@mark.django_db
class TestMoodleLearnerDataTransmitter(unittest.TestCase):
    """
    Test MoodleLearnerDataTransmitter
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=5,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        self.enterprise_config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            moodle_base_url='foobar',
            service_short_name='shortname',
            category_id=1,
            username='username',
            password='password',
            token='token',
        )
        self.payload = MoodleLearnerDataTransmissionAudit(
            moodle_user_email=self.enterprise_customer.contact_email,
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            moodle_completed_timestamp=1486855998,
            completed_timestamp=datetime.datetime.fromtimestamp(1486855998),
            total_hours=1.0,
            grade=.9,
        )
        self.exporter = lambda payloads=self.payload: mock.MagicMock(
            export=mock.MagicMock(return_value=iter(payloads))
        )
        # Mocks
        create_course_completion_mock = mock.patch(
            'integrated_channels.moodle.client.MoodleAPIClient.create_course_completion'
        )

        self.create_course_completion_mock = create_course_completion_mock.start()
        self.addCleanup(create_course_completion_mock.stop)

        self.learner_transmitter = LearnerTransmitter(self.enterprise_config)

    def test_transmit_success(self):
        """
        Learner data transmission is successful and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.return_value = 200, '{"success":"true"}'

        transmitter = learner_data.MoodleLearnerTransmitter(self.enterprise_config)

        transmitter.transmit(self.exporter([self.payload]))
        self.create_course_completion_mock.assert_called_with(self.payload.moodle_user_email, self.payload.serialize())
        assert self.payload.status == '200'
        assert self.payload.error_message == ''

    @mock.patch("integrated_channels.integrated_channel.models.LearnerDataTransmissionAudit")
    @mock.patch('integrated_channels.integrated_channel.transmitters.'
                'learner_data.LOGGER', autospec=True)
    def test_incomplete_progress_learner_data_transmission(self, mock_logger, learner_data_transmission_audit_mock):
        """
        Test that a customer's configuration can run in enable incomplete progress transmission mode
        """
        # Set boolean flag to true
        self.enterprise_config.enable_incomplete_progress_transmission = True

        self.learner_transmitter.client.create_course_completion = Mock(return_value=(200, 'success'))

        LearnerExporterMock = LearnerExporter

        learner_data_transmission_audit_mock.serialize = Mock(return_value='serialized data')
        learner_data_transmission_audit_mock.user_id = 1
        learner_data_transmission_audit_mock.enterprise_course_enrollment_id = 1
        learner_data_transmission_audit_mock.course_completed = False
        learner_data_transmission_audit_mock.course_id = 'course_id'
        LearnerExporterMock.export = Mock(return_value=[learner_data_transmission_audit_mock])
        lms_user_id = LearnerExporterUtility.lms_user_id_for_ent_course_enrollment_id(
            learner_data_transmission_audit_mock.enterprise_course_enrollment_id
        )
        serialized_payload = learner_data_transmission_audit_mock.serialize(
            enterprise_configuration=self.enterprise_config
        )
        encoded_serialized_payload = encode_data_for_logging(serialized_payload)
        self.learner_transmitter.transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        # with enable_incomplete_progress_transmission = True we should be able to call this method
        assert self.learner_transmitter.client.create_course_completion.called

        # Set boolean flag to false
        self.enterprise_config.enable_incomplete_progress_transmission = False
        self.learner_transmitter.transmit(
            LearnerExporterMock,
            remote_user_id='user_id'
        )
        mock_logger.info.assert_called_with(generate_formatted_log(
            self.enterprise_config.channel_code(),
            self.enterprise_config.enterprise_customer.uuid or None,
            lms_user_id,
            learner_data_transmission_audit_mock.course_id,
            'Skipping in-progress enterprise enrollment record '
            f'integrated_channel_remote_user_id={learner_data_transmission_audit_mock.user_id}, '
            f'integrated_channel_serialized_payload_base64={encoded_serialized_payload}'
        ))
