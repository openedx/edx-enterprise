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
from pytest import mark
from slumber.exceptions import HttpNotFoundError

from django.utils import timezone

from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.models import LearnerDataTransmissionAudit
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestLearnerExporter(unittest.TestCase):
    """
    Tests of LearnerExporter class.
    """

    # Use these tz-aware datetimes in tests
    NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    NOW_TIMESTAMP = 1483326245000
    TOMORROW = NOW + datetime.timedelta(days=1)
    YESTERDAY = NOW + datetime.timedelta(days=-1)
    YESTERDAY_TIMESTAMP = NOW_TIMESTAMP - 24 * 60 * 60 * 1000

    def setUp(self):
        self.user = factories.UserFactory(username='C3PO', id=1)
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.course_key = 'edX+DemoX'
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.data_sharing_consent = factories.DataSharingConsentFactory(
            username=self.user.username,
            course_id=self.course_id,
            enterprise_customer=self.enterprise_customer,
            granted=True,
        )
        self.config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='enterprise.successfactors.com',
            key='key',
            secret='secret',
            active=True,
        )
        self.idp = factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer
        )
        tpa_client_mock = mock.patch('enterprise.models.ThirdPartyAuthApiClient')
        self.tpa_client = tpa_client_mock.start().return_value
        # Default remote ID
        self.tpa_client.get_remote_id.return_value = 'fake-remote-id'
        self.addCleanup(tpa_client_mock.stop)
        self.exporter = self.config.get_learner_data_exporter('dummy-user')
        assert isinstance(self.exporter, LearnerExporter)
        super(TestLearnerExporter, self).setUp()

    def test_collect_learner_data_no_enrollments(self):
        learner_data = list(self.exporter.export())
        assert not learner_data

    @ddt.data(
        (None, False),
        (None, True),
        (NOW, False),
        (NOW, True),
    )
    @ddt.unpack
    @freeze_time(NOW)
    def test_get_learner_data_record(self, completed_date, is_passing):
        """
        The base ``get_learner_data_record`` method returns a ``LearnerDataTransmissionAudit`` with appropriate values.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        exporter = LearnerExporter('fake-user', self.config)
        learner_data_records = exporter.get_learner_data_records(
            enterprise_course_enrollment,
            completed_date=completed_date,
            grade='A+',
            is_passing=is_passing,
        )

        learner_data_record = learner_data_records[0]
        assert learner_data_record.enterprise_course_enrollment_id == enterprise_course_enrollment.id
        assert learner_data_record.course_id == enterprise_course_enrollment.course_id
        assert learner_data_record.course_completed == (completed_date is not None and is_passing)
        assert learner_data_record.completed_timestamp == (self.NOW_TIMESTAMP if completed_date is not None else None)
        assert learner_data_record.grade == 'A+'

    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    def test_collect_learner_data_without_consent(self, mock_course_api, mock_grades_api, mock_enrollment_api):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
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

        learner_data = list(self.exporter.export())
        assert not learner_data
        assert mock_grades_api.call_count == 0

    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    def test_collect_learner_data_no_course_details(self, mock_course_api):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        # Return no course details
        mock_course_api.return_value.get_course_details.return_value = None

        learner_data = list(self.exporter.export())
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CertificatesApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_instructor_paced_no_certificate(
            self, mock_course_catalog_api, mock_certificate_api, mock_course_api, mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
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

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 2
        assert learner_data[0].course_id == self.course_key
        assert learner_data[1].course_id == self.course_id

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert not report.course_completed
            assert report.completed_timestamp is None
            assert report.grade == LearnerExporter.GRADE_INCOMPLETE

    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CertificatesApiClient')
    def test_learner_data_instructor_paced_no_certificate_null_sso_id(
            self, mock_certificate_api, mock_course_api, mock_enrollment_api
    ):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        # No SSO user attached
        self.tpa_client.get_remote_id.return_value = None

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

        learner_data = list(self.exporter.export())
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CertificatesApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_instructor_paced_with_certificate(
            self, mock_course_catalog_api, mock_certificate_api, mock_course_api, mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
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

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 2
        assert learner_data[0].course_id == self.course_key
        assert learner_data[1].course_id == self.course_id

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert report.course_completed
            assert report.completed_timestamp == self.NOW_TIMESTAMP
            assert report.grade == LearnerExporter.GRADE_PASSING

    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_self_paced_no_grades(
            self,
            mock_course_catalog_api,
            mock_course_api,
            mock_grades_api,
            mock_enrollment_api,
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        # Return self-paced course details
        mock_course_api.return_value.get_course_details.return_value = {
            'pacing': 'self',
        }

        # Mock grades data not found
        mock_grades_api.return_value.get_course_grade.side_effect = HttpNotFoundError(
            'No grade record found for course={}, username={}'.format(self.course_id, self.user.username)
        )

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 2
        assert learner_data[0].course_id == self.course_key
        assert learner_data[1].course_id == self.course_id

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert not report.course_completed
            assert report.completed_timestamp is None
            assert report.grade is None

    @ddt.data(
        # passing grade with no course end date
        (True, None, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING),
        # passing grade with course end date in past
        (True, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_PASSING),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING),
        # non-passing grade with no course end date
        (False, None, None, LearnerExporter.GRADE_INCOMPLETE),
        # non-passing grade with course end date in past
        (False, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_FAILING),
        # non-passing grade with course end date in future
        (False, TOMORROW, None, LearnerExporter.GRADE_INCOMPLETE),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_self_paced_course(
            self,
            passing,
            end_date,
            expected_completion,
            expected_grade,
            mock_course_catalog_api,
            mock_course_api,
            mock_grades_api,
            mock_enrollment_api
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

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
            learner_data = list(self.exporter.export())

        assert len(learner_data) == 2
        assert learner_data[0].course_id == self.course_key
        assert learner_data[1].course_id == self.course_id

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert report.course_completed == (passing and expected_completion is not None)
            assert report.completed_timestamp == expected_completion
            assert report.grade == expected_grade

    @ddt.data(
        ('self', LearnerExporter.GRADE_PASSING),
        ('instructor', LearnerExporter.GRADE_PASSING),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CertificatesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_multiple_courses(
            self,
            pacing,
            grade,
            mock_course_catalog_api,
            mock_course_api,
            mock_grades_api,
            mock_certificate_api,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment1 = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        course_id2 = 'course-v1:edX+DemoX+DemoCourse2'
        enrollment2 = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_id2,
        )
        factories.DataSharingConsentFactory(
            username=self.enterprise_customer_user.username,
            course_id=course_id2,
            enterprise_customer=self.enterprise_customer,
            granted=True
        )

        enrollment3 = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=factories.EnterpriseCustomerUserFactory(
                user_id=factories.UserFactory(username='R2D2', id=2).id,
                enterprise_customer=self.enterprise_customer,
            ),
            course_id=self.course_id,
        )
        factories.DataSharingConsentFactory(
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
            learner_data = list(self.exporter.export())

        assert len(learner_data) == 6

        assert learner_data[0].course_id == self.course_key
        assert learner_data[1].course_id == self.course_id
        for report1 in learner_data[0:1]:
            assert report1.enterprise_course_enrollment_id == enrollment1.id
            assert not report1.course_completed
            assert report1.completed_timestamp is None
            assert report1.grade == LearnerExporter.GRADE_INCOMPLETE

        assert learner_data[2].course_id == self.course_key
        assert learner_data[3].course_id == self.course_id
        for report2 in learner_data[2:3]:
            assert report2.enterprise_course_enrollment_id == enrollment3.id
            assert not report2.course_completed
            assert report2.completed_timestamp is None
            assert report2.grade == LearnerExporter.GRADE_INCOMPLETE

        assert learner_data[4].course_id == self.course_key
        assert learner_data[5].course_id == course_id2
        for report3 in learner_data[4:5]:
            assert report3.enterprise_course_enrollment_id == enrollment2.id
            # assert report3.course_id == course_id2
            assert report3.course_completed
            assert report3.completed_timestamp == self.NOW_TIMESTAMP
            assert report3.grade == grade

    @ddt.data(
        (True, True, 'audit', 2),
        (True, False, 'audit', 0),
        (False, True, 'audit', 0),
        (False, False, 'audit', 0),
        (True, True, 'verified', 2),
        (True, False, 'verified', 2),
        (False, True, 'verified', 2),
        (False, False, 'verified', 2),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_audit_data_reporting(
            self,
            enable_audit_enrollment,
            enable_reporting,
            mode,
            expected_data_len,
            mock_course_catalog_api,
            mock_course_api,
            mock_grades_api,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
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
            learner_data = list(self.exporter.export())

        assert len(learner_data) == expected_data_len

        if expected_data_len == 2:
            assert learner_data[0].course_id == self.course_key
            assert learner_data[1].course_id == self.course_id
            for report in learner_data:
                assert report.enterprise_course_enrollment_id == enrollment.id
                assert report.course_completed
                assert report.grade == LearnerExporter.GRADE_PASSING

    @mock.patch('enterprise.models.EnrollmentApiClientJwt')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.CourseApiClient')
    def test_learner_exporter_with_skip_transmitted(self, mock_course_api, mock_grades_api, mock_enrollment_api):
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        transmission_audit = LearnerDataTransmissionAudit(
            enterprise_course_enrollment_id=enterprise_course_enrollment.id,
            course_id=self.course_id,
            course_completed=True,
            completed_timestamp=1568877047181,
            grade='Pass',
        )
        transmission_audit.save()
        learner_data = list(self.exporter.export(TransmissionAudit=LearnerDataTransmissionAudit))

        assert not learner_data
        assert mock_enrollment_api.call_count == 0
        assert mock_course_api.call_count == 0
        assert mock_grades_api.call_count == 0
