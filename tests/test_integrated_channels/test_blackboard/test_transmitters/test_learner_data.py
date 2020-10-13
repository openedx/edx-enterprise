# -*- coding: utf-8 -*-
"""
Tests for Moodle learner data transmissions.
"""
import unittest

import mock
from pytest import mark

from integrated_channels.blackboard.models import BlackboardLearnerDataTransmissionAudit
from integrated_channels.blackboard.transmitters import learner_data
from test_utils import factories


@mark.django_db
class TestBlackboardLearnerDataTransmitter(unittest.TestCase):
    """
    Test MoodleLearnerDataTransmitter
    """

    def setUp(self):
        super(TestBlackboardLearnerDataTransmitter, self).setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=5,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        self.enterprise_config = factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            blackboard_base_url='foobar',
            client_id='client_id',
            client_secret='client_secret',
            refresh_token='token',
        )
        self.payload = BlackboardLearnerDataTransmissionAudit(
            blackboard_user_email=self.enterprise_customer.contact_email,
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486855998,
            total_hours=1.0,
            grade=.9,
        )
        self.exporter = lambda payloads=self.payload: mock.MagicMock(
            export=mock.MagicMock(return_value=iter(payloads))
        )
        # Mocks
        create_course_completion_mock = mock.patch(
            'integrated_channels.blackboard.client.BlackboardAPIClient.create_course_completion'
        )
        self.create_course_completion_mock = create_course_completion_mock.start()
        self.addCleanup(create_course_completion_mock.stop)

        self.create_course_completion_mock = create_course_completion_mock.start()
        self.addCleanup(create_course_completion_mock.stop)

    def test_transmit_success(self):
        """
        Learner data transmission is successful and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.return_value = 200, '{"success":"true"}'

        transmitter = learner_data.BlackboardLearnerTransmitter(self.enterprise_config)

        transmitter.transmit(self.exporter([self.payload]))
        self.create_course_completion_mock.assert_called_with(self.payload.blackboard_user_email, self.payload.serialize())
        assert self.payload.status == '200'
        assert self.payload.error_message == ''
