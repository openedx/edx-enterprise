# -*- coding: utf-8 -*-
"""
Tests for Canvas learner data transmissions.
"""
import unittest

import mock
from pytest import mark

from integrated_channels.canvas.models import (
    CanvasLearnerAssessmentDataTransmissionAudit,
    CanvasLearnerDataTransmissionAudit,
)
from integrated_channels.canvas.transmitters import learner_data
from test_utils import factories


@mark.django_db
class TestCanvasLearnerDataTransmitter(unittest.TestCase):
    """
    Test CanvasLearnerDataTransmitter
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
        self.enterprise_config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            canvas_base_url='foobar',
            # canvas_account_id=2,
        )
        self.completion_payload = CanvasLearnerDataTransmissionAudit(
            canvas_user_email=self.enterprise_customer.contact_email,
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            course_id='course-v1:edX+DemoX+DemoCourse',
            course_completed=True,
            completed_timestamp=1486855998,
            grade=.9,
        )
        self.completion_exporter = lambda payloads=self.completion_payload: mock.MagicMock(
            export=mock.MagicMock(return_value=iter(payloads))
        )

        self.assessment_payload = CanvasLearnerAssessmentDataTransmissionAudit(
            canvas_user_email=self.enterprise_customer.contact_email,
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            course_id='course-v1:edX+DemoX+DemoCourse',
            subsection_id='section:1+testX+introduction',
            grade_point_score=1.0,
            grade_points_possible=1.0,
            grade=1.0,
            subsection_name='introduction'
        )
        self.assessment_exporter = lambda payloads=self.assessment_payload: mock.MagicMock(
            bulk_assessment_level_export=mock.MagicMock(return_value=iter(payloads))
        )
        self.single_assessment_exporter = lambda payloads=self.assessment_payload: mock.MagicMock(
            single_assessment_level_export=mock.MagicMock(return_value=iter(payloads))
        )

        self.transmitter = learner_data.CanvasLearnerTransmitter(self.enterprise_config)

        # Mocks
        assessment_reporting_mock = mock.patch(
            'integrated_channels.canvas.client.CanvasAPIClient.create_assessment_reporting'
        )
        self.assessment_reporting_mock = assessment_reporting_mock.start()
        self.addCleanup(assessment_reporting_mock.stop)

        create_course_completion_mock = mock.patch(
            'integrated_channels.canvas.client.CanvasAPIClient.create_course_completion'
        )
        self.create_course_completion_mock = create_course_completion_mock.start()
        self.addCleanup(create_course_completion_mock.stop)

        self.create_course_completion_mock = create_course_completion_mock.start()
        self.addCleanup(create_course_completion_mock.stop)

    def test_transmit_success(self):
        """
        Learner data completion transmission is successful and the payload is saved with the appropriate data.
        """
        self.create_course_completion_mock.return_value = 200, '{"success":"true"}'

        self.transmitter.transmit(self.completion_exporter([self.completion_payload]))
        self.create_course_completion_mock.assert_called_with(
            self.completion_payload.canvas_user_email,
            self.completion_payload.serialize()
        )
        assert self.completion_payload.status == '200'
        assert self.completion_payload.error_message == ''

    def test_assessment_level_transmit_success(self):
        """
        Learner data assessment level transmission is successful and the payload is saved with the appropriate data.
        """
        self.assessment_reporting_mock.return_value = 200, '{"success":"true"}'

        self.transmitter.assessment_level_transmit(self.assessment_exporter([self.assessment_payload]))
        self.assessment_reporting_mock.assert_called_with(
            self.assessment_payload.canvas_user_email,
            self.assessment_payload.serialize()
        )
        assert self.assessment_payload.status == '200'
        assert self.assessment_payload.error_message == ''

    def test_single_learner_assessment_level_transmit_success(self):
        """
        Single learner data assessment level transmission is successful and the payload is saved with the
        appropriate data.
        """
        self.assessment_reporting_mock.return_value = 200, '{"success":"true"}'

        self.transmitter.single_learner_assessment_grade_transmit(self.single_assessment_exporter(
            [self.assessment_payload]
        ))
        self.assessment_reporting_mock.assert_called_with(
            self.assessment_payload.canvas_user_email,
            self.assessment_payload.serialize()
        )
        assert self.assessment_payload.status == '200'
        assert self.assessment_payload.error_message == ''
