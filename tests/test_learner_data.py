# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` learner_data export classes.
"""
from __future__ import absolute_import, unicode_literals

import datetime
import unittest

import ddt
import mock
from freezegun import freeze_time
from integrated_channels.integrated_channel.learner_data import BaseLearnerExporter
from integrated_channels.sap_success_factors.models import SAPSuccessFactorsEnterpriseCustomerConfiguration
from pytest import mark
from slumber.exceptions import HttpNotFoundError

from django.utils import timezone

from test_utils.factories import (EnterpriseCourseEnrollmentFactory, EnterpriseCustomerFactory,
                                  EnterpriseCustomerUserFactory, UserFactory)


@mark.django_db
@ddt.ddt
class TestBaseLearnerExporter(unittest.TestCase):
    """
    Tests of BaseLearnerExporter class.
    """

    # Use these tz-aware datetimes in tests
    NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    NOW_TIMESTAMP = 1483326245000
    TOMORROW = NOW + datetime.timedelta(days=1)
    YESTERDAY = NOW + datetime.timedelta(days=-1)
    YESTERDAY_TIMESTAMP = NOW_TIMESTAMP - 24*60*60*1000

    def setUp(self):
        self.user = UserFactory(username='C3PO')
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.enterprise_customer_user = EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        config = SAPSuccessFactorsEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret',
            active=True,
        )
        self.exporter = config.get_learner_data_exporter('dummy-user')
        assert isinstance(self.exporter, BaseLearnerExporter)
        super(TestBaseLearnerExporter, self).setUp()

    def test_collect_learner_data_no_enrollments(self):
        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 0

    def test_collect_learner_data_without_consent(self):
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=False,
        )
        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 0

    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_collect_learner_data_no_course_details(self, mock_course_api):
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )

        # Return no course details
        mock_course_api.return_value.get_course_details.return_value = None

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 0

    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CertificatesApiClient')
    def test_learner_data_instructor_paced_no_certificate(self, mock_certificate_api, mock_course_api):
        enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )

        # Raise 404 - no certificate found
        mock_certificate_api.return_value.get_course_certificate.side_effect = HttpNotFoundError

        # Return instructor-paced course details
        mock_course_api.return_value.get_course_details.return_value = dict(
            pacing='instructor',
        )

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 1
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].course_id == self.course_id
        assert not learner_data[0].course_completed
        assert learner_data[0].completed_timestamp is None
        assert learner_data[0].grade == BaseLearnerExporter.GRADE_INCOMPLETE

    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CertificatesApiClient')
    def test_learner_data_instructor_paced_w_certificate(self, mock_certificate_api, mock_course_api):
        enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )

        # Return a mock certificate
        certificate = dict(
            username=self.user,
            course_id=self.course_id,
            certificate_type='professional',
            created_date=self.NOW.isoformat(),
            status="downloadable",
            is_passing=True,
            grade='A-',
        )
        mock_certificate_api.return_value.get_course_certificate.return_value = certificate

        # Return instructor-paced course details
        mock_course_api.return_value.get_course_details.return_value = dict(
            pacing='instructor',
        )

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 1
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].course_id == self.course_id
        assert learner_data[0].course_completed
        assert learner_data[0].completed_timestamp == self.NOW_TIMESTAMP
        assert learner_data[0].grade == BaseLearnerExporter.GRADE_PASSING

    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_self_paced_no_grades(self, mock_course_api, mock_grades_api):
        enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )

        # Return instructor-paced course details
        mock_course_api.return_value.get_course_details.return_value = dict(
            pacing='self',
        )

        # Mock grades data not found
        mock_grades_api.return_value.get_course_grade.side_effect = HttpNotFoundError

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 1
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].course_id == self.course_id
        assert not learner_data[0].course_completed
        assert learner_data[0].completed_timestamp is None
        assert learner_data[0].grade is None

    @ddt.data(
        # passing grade with no course end date
        (True, None, NOW_TIMESTAMP, BaseLearnerExporter.GRADE_PASSING),
        # passing grade with course end date in past
        (True, YESTERDAY, YESTERDAY_TIMESTAMP, BaseLearnerExporter.GRADE_PASSING),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, BaseLearnerExporter.GRADE_PASSING),
        # non-passing grade with no course end date
        (False, None, None, BaseLearnerExporter.GRADE_INCOMPLETE),
        # non-passing grade with course end date in past
        (False, YESTERDAY, YESTERDAY_TIMESTAMP, BaseLearnerExporter.GRADE_FAILING),
        # non-passing grade with course end date in future
        (False, TOMORROW, None, BaseLearnerExporter.GRADE_INCOMPLETE),
    )
    @ddt.unpack
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_self_paced_course(self, passing, end_date, expected_completion, expected_grade,
                                            mock_course_api, mock_grades_api):
        enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )

        # Mock self-paced course details
        mock_course_api.return_value.get_course_details.return_value = dict(
            pacing='self',
            end=end_date.isoformat() if end_date else None,
        )

        # Mock grades data
        mock_grades_api.return_value.get_course_grade.return_value = dict(
            passed=passing,
        )

        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.collect_learner_data())

        assert len(learner_data) == 1
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].course_id == self.course_id
        assert learner_data[0].course_completed == (passing and expected_completion is not None)
        assert learner_data[0].completed_timestamp == expected_completion
        assert learner_data[0].grade == expected_grade

    @ddt.data(
        ('self', BaseLearnerExporter.GRADE_PASSING),
        ('instructor', BaseLearnerExporter.GRADE_PASSING),
    )
    @ddt.unpack
    @mock.patch('integrated_channels.integrated_channel.learner_data.CertificatesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_multiple_courses(self, pacing, grade, mock_course_api, mock_grades_api, mock_certificate_api):
        enrollment1 = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )
        course_id2 = 'course-v1:edX+DemoX+DemoCourse2'
        enrollment2 = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_id2,
            consent_granted=True,
        )
        enrollment3 = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=EnterpriseCustomerUserFactory(
                user_id=UserFactory(username='R2D2').id,
                enterprise_customer=self.enterprise_customer,
            ),
            course_id=self.course_id,
            consent_granted=True,
        )

        def get_course_details(course_id):
            """
            Mock course details - set course_id to match input
            """
            return dict(
                pacing=pacing,
                course_id=course_id
            )
        mock_course_api.return_value.get_course_details.side_effect = get_course_details

        def get_course_certificate(course_id, username):
            """
            Mock certificate data - return depending on course_id
            """
            if '2' in course_id:
                return dict(
                    username=username,
                    is_passing=True,
                    grade=grade,
                )
            else:
                raise HttpNotFoundError
        mock_certificate_api.return_value.get_course_certificate.side_effect = get_course_certificate

        def get_course_grade(course_id, username):
            """
            Mock grades data - set passed depending on course_id
            """
            return dict(
                passed='2' in course_id,
                course_key=course_id,
                username=username,
            )
        mock_grades_api.return_value.get_course_grade.side_effect = get_course_grade

        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.collect_learner_data())

        assert len(learner_data) == 3
        assert learner_data[0].enterprise_course_enrollment_id == enrollment1.id
        assert learner_data[0].course_id == self.course_id
        assert not learner_data[0].course_completed
        assert learner_data[0].completed_timestamp is None
        assert learner_data[0].grade == BaseLearnerExporter.GRADE_INCOMPLETE

        assert learner_data[1].enterprise_course_enrollment_id == enrollment3.id
        assert learner_data[1].course_id == self.course_id
        assert not learner_data[1].course_completed
        assert learner_data[1].completed_timestamp is None
        assert learner_data[1].grade == BaseLearnerExporter.GRADE_INCOMPLETE

        assert learner_data[2].enterprise_course_enrollment_id == enrollment2.id
        assert learner_data[2].course_id == course_id2
        assert learner_data[2].course_completed
        assert learner_data[2].completed_timestamp == self.NOW_TIMESTAMP
        assert learner_data[2].grade == grade
