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

from test_utils.factories import (
    DataSharingConsentFactory,
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    UserFactory,
)


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
        self.data_sharing_consent = DataSharingConsentFactory(
            username=self.user.username,
            course_id=self.course_id,
            enterprise_customer=self.enterprise_customer,
            granted=True,
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
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_collect_learner_data_without_consent(self, mock_course_api, mock_grades_api, mock_enrollment_api):
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=False,
        )

        self.data_sharing_consent.granted = False
        self.data_sharing_consent.save()

        # Return random course details
        mock_course_api.return_value.get_course_details.return_value = dict(
            pacing='self'
        )

        # Return enrollment mode data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.collect_learner_data())
        assert not learner_data
        assert mock_grades_api.call_count == 0

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
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CertificatesApiClient')
    def test_learner_data_instructor_paced_no_certificate(
            self, mock_certificate_api, mock_course_api, mock_enrollment_api
    ):
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

        # Return enrollment mode data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 1

        report = learner_data[0]
        assert report.enterprise_course_enrollment_id == enrollment.id
        assert report.course_id == self.course_id
        assert not report.course_completed
        assert report.completed_timestamp is None
        assert report.grade == BaseLearnerExporter.GRADE_INCOMPLETE

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CertificatesApiClient')
    def test_learner_data_instructor_paced_with_certificate(
            self, mock_certificate_api, mock_course_api, mock_enrollment_api
    ):
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

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 1

        report = learner_data[0]
        assert report.enterprise_course_enrollment_id == enrollment.id
        assert report.course_id == self.course_id
        assert report.course_completed
        assert report.completed_timestamp == self.NOW_TIMESTAMP
        assert report.grade == BaseLearnerExporter.GRADE_PASSING

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_self_paced_no_grades(self, mock_course_api, mock_grades_api, mock_enrollment_api):
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

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.collect_learner_data())
        assert len(learner_data) == 1

        report = learner_data[0]
        assert report.enterprise_course_enrollment_id == enrollment.id
        assert report.course_id == self.course_id
        assert not report.course_completed
        assert report.completed_timestamp is None
        assert report.grade is None

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
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_self_paced_course(self, passing, end_date, expected_completion, expected_grade,
                                            mock_course_api, mock_grades_api, mock_enrollment_api):
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

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.collect_learner_data())

        assert len(learner_data) == 1

        report = learner_data[0]
        assert report.enterprise_course_enrollment_id == enrollment.id
        assert report.course_id == self.course_id
        assert report.course_completed == (passing and expected_completion is not None)
        assert report.completed_timestamp == expected_completion
        assert report.grade == expected_grade

    @ddt.data(
        ('self', BaseLearnerExporter.GRADE_PASSING),
        ('instructor', BaseLearnerExporter.GRADE_PASSING),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CertificatesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_multiple_courses(
            self, pacing, grade, mock_course_api, mock_grades_api, mock_certificate_api, mock_enrollment_api
    ):
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
        DataSharingConsentFactory(
            username=self.enterprise_customer_user.username,
            course_id=course_id2,
            enterprise_customer=self.enterprise_customer,
            granted=True
        )

        enrollment3 = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=EnterpriseCustomerUserFactory(
                user_id=UserFactory(username='R2D2').id,
                enterprise_customer=self.enterprise_customer,
            ),
            course_id=self.course_id,
            consent_granted=True,
        )
        DataSharingConsentFactory(
            username='R2D2',
            course_id=self.course_id,
            enterprise_customer=self.enterprise_customer,
            granted=True
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

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.collect_learner_data())

        assert len(learner_data) == 3

        report1 = learner_data[0]
        assert report1.enterprise_course_enrollment_id == enrollment1.id
        assert report1.course_id == self.course_id
        assert not report1.course_completed
        assert report1.completed_timestamp is None
        assert report1.grade == BaseLearnerExporter.GRADE_INCOMPLETE

        report2 = learner_data[1]
        assert report2.enterprise_course_enrollment_id == enrollment3.id
        assert report2.course_id == self.course_id
        assert not report2.course_completed
        assert report2.completed_timestamp is None
        assert report2.grade == BaseLearnerExporter.GRADE_INCOMPLETE

        report3 = learner_data[2]
        assert report3.enterprise_course_enrollment_id == enrollment2.id
        assert report3.course_id == course_id2
        assert report3.course_completed
        assert report3.completed_timestamp == self.NOW_TIMESTAMP
        assert report3.grade == grade

    @ddt.data(
        (True, True, 'audit', 1),
        (True, False, 'audit', 0),
        (False, True, 'audit', 0),
        (False, False, 'audit', 0),
        (True, True, 'verified', 1),
        (True, False, 'verified', 1),
        (False, True, 'verified', 1),
        (False, False, 'verified', 1),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.learner_data.CourseApiClient')
    def test_learner_data_audit_data_reporting(
            self,
            enable_audit_enrollment,
            enable_reporting,
            mode,
            expected_data_len,
            mock_course_api,
            mock_grades_api,
            mock_enrollment_api
    ):
        enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
            consent_granted=True,
        )

        # Set the audit track data passback configuration
        self.enterprise_customer.enable_audit_enrollment = enable_audit_enrollment
        self.enterprise_customer.enable_audit_data_reporting = enable_reporting
        self.enterprise_customer.save()

        # Use self-paced course to get grades data
        mock_course_api.return_value.get_course_details.return_value = dict(
            pacing='self',
            course_id=self.course_id,
        )

        # Mock grades data
        mock_grades_api.return_value.get_course_grade.return_value = dict(
            passed=True,
        )

        # Mock enrollment data, in particular the enrollment mode
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode=mode
        )

        # Collect the learner data
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.collect_learner_data())

        assert len(learner_data) == expected_data_len

        if expected_data_len == 1:
            report = learner_data[0]
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert report.course_id == self.course_id
            assert report.course_completed
            assert report.grade == BaseLearnerExporter.GRADE_PASSING
