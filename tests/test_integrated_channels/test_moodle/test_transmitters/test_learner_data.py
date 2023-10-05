"""
Tests for Moodle learner data transmissions.
"""
import datetime
import unittest
from unittest import mock

from pytest import mark

from integrated_channels.moodle.models import MoodleLearnerDataTransmissionAudit
from integrated_channels.moodle.transmitters import learner_data
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
            decrypted_username='username',
            decrypted_password='password',
            decrypted_token='token',
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
