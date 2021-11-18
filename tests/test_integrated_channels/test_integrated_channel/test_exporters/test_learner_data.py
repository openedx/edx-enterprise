# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` learner_data export classes.
"""
import datetime
import unittest

import ddt
import mock
from freezegun import freeze_time
from mock.mock import MagicMock
from pytest import mark

from django.utils import timezone

from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.models import LearnerDataTransmissionAudit
from test_utils import factories
from test_utils.integrated_channels_utils import mock_course_overview, mock_single_learner_grade


def create_ent_enrollment_mock(is_audit=True):
    '''
    creates a magicmock instance for enterprise enrollment
    '''
    enterprise_enrollment = MagicMock()
    enterprise_enrollment.enterprise_customer_user = MagicMock()
    enterprise_enrollment.enterprise_customer_user.user_id = 1
    enterprise_enrollment.enterprise_customer_user.enterprise_customer = MagicMock()
    enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid = 'abc'
    enterprise_enrollment.is_audit_enrollment = MagicMock(return_value=is_audit)
    return enterprise_enrollment


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
        self.user_2 = factories.UserFactory(username='R2D2', id=2)
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.course_id_2 = 'course-v2:edX+Much+Wow+Very+Test'
        self.course_key = 'edX+DemoX'
        self.enterprise_customer = factories.EnterpriseCustomerFactory(
            enable_audit_enrollment=True,
            enable_audit_data_reporting=True
        )
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_customer_user_2 = factories.EnterpriseCustomerUserFactory(
            user_id=self.user_2.id,
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
        super().setUp()

    def test_default_channel_settings(self):
        """
        If you add any settings to the ChannelSettingsMixin, add a test here for the common default value
        """
        assert LearnerExporter('fake-user', self.config).INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK is True

    def test_collect_learner_data_no_enrollments(self):
        learner_data = list(self.exporter.export())
        assert not learner_data

    @ddt.data(
        (None,),
        (NOW,),
    )
    @ddt.unpack
    @freeze_time(NOW)
    def test_get_learner_data_record(self, completed_date):
        """
        The base ``get_learner_data_record`` method returns a ``LearnerDataTransmissionAudit`` with appropriate values.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        expected_course_completed = True
        exporter = LearnerExporter('fake-user', self.config)
        learner_data_records = exporter.get_learner_data_records(
            enterprise_course_enrollment,
            completed_date=completed_date,
            grade='A+',
            course_completed=expected_course_completed,
        )

        learner_data_record = learner_data_records[0]
        assert learner_data_record.enterprise_course_enrollment_id == enterprise_course_enrollment.id
        assert learner_data_record.course_id == enterprise_course_enrollment.course_id
        assert learner_data_record.course_completed == expected_course_completed
        assert learner_data_record.completed_timestamp == (self.NOW_TIMESTAMP if completed_date is not None else None)
        assert learner_data_record.grade == 'A+'

    def test_get_learner_subsection_data_records(self):
        """
        Test that the base learner subsection data exporter generates appropriate learner records from assessment grade
        data.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        exporter = LearnerExporter('fake-user', self.config)

        assessment_grade_data = {
            'subsection_1': {
                'grade': 0.9,
                'subsection_id': 'sub_1'
            },
            'subsection_2': {
                'grade': 1.0,
                'subsection_id': 'sub_2'
            }
        }

        learner_subsection_data_records = exporter.get_learner_assessment_data_records(
            enterprise_course_enrollment,
            assessment_grade_data
        )

        for subsection_record in learner_subsection_data_records:
            if subsection_record.subsection_id == 'sub_1':
                assert subsection_record.grade == 0.9
            else:
                assert subsection_record.grade == 1.0

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    def test_collect_learner_data_without_consent(self, mock_get_course_details, mock_grades_api, mock_enrollment_api):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        self.data_sharing_consent.granted = False
        self.data_sharing_consent.save()

        # Return random course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='self'
        )

        # Return enrollment mode data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.export())
        assert not learner_data
        assert mock_grades_api.call_count == 0

        learner_assessment_data = list(self.exporter.bulk_assessment_level_export())
        assert not learner_assessment_data
        assert mock_grades_api.call_count == 0

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    def test_collect_learner_data_no_course_details(self, mock_get_course_details, mock_enrollment_api):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        # Return no course details
        mock_get_course_details.return_value = None

        # Return empty enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {}

        learner_data = list(self.exporter.export())
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    def test_learner_data_instructor_paced_no_certificate(
            self,
            mock_get_course_certificate,
            mock_course_catalog_api,
            mock_get_course_details,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_course_certificate.return_value = None

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
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

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    def test_learner_data_instructor_paced_no_certificate_null_sso_id(
            self, mock_get_course_certificate, mock_get_course_details, mock_enrollment_api
    ):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        # No SSO user attached
        self.tpa_client.get_remote_id.return_value = None

        # no certificate found
        mock_get_course_certificate.return_value = None

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='instructor',
        )

        # Return enrollment mode data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode="verified"
        )

        learner_data = list(self.exporter.export())
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_instructor_paced_with_certificate(
            self,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_certificate,
            mock_get_course_details,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}
        mock_is_course_completed.return_value = True

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
        mock_get_course_certificate.return_value = certificate

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
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

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_self_paced_no_grades(
            self,
            mock_course_catalog_api,
            mock_get_course_details,
            mock_get_single_user_grade,
            mock_enrollment_api,
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        # Return self-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='self',
        )

        # Mock grades data not found
        mock_get_single_user_grade.return_value = None

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
        (True, None, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified'),
        # passing grade with course end date in past
        (True, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified'),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified'),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'audit'),
        # non-passing grade with no course end date
        (False, None, None, LearnerExporter.GRADE_INCOMPLETE, 'verified'),
        # non-passing grade with course end date in past
        (False, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_FAILING, 'verified'),
        # non-passing grade with course end date in past
        (False, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_AUDIT, 'audit'),
        # non-passing grade with course end date in future
        (False, TOMORROW, None, LearnerExporter.GRADE_INCOMPLETE, 'verified'),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_self_paced_course(
            self,
            passing,
            end_date,
            expected_completion,
            expected_grade,
            course_enrollment_mode,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_details,
            mock_get_single_user_grade,
            mock_course_enrollment_class
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}

        mock_is_course_completed.return_value = True

        # Mock self-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='self',
            end=end_date if end_date else None,
        )

        # Mock grades data
        mock_get_single_user_grade.return_value = mock_single_learner_grade(
            passing=passing,
        )

        # Mock enrollment data
        mock_course_enrollment_class.objects.get.return_value.mode = course_enrollment_mode
        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.export())

        assert len(learner_data) == 2
        assert learner_data[0].course_id == self.course_key
        assert learner_data[1].course_id == self.course_id

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert report.course_completed
            assert report.completed_timestamp == expected_completion
            assert report.grade == expected_grade

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_assessment_data_export(
            self,
            mock_course_catalog_api,
            mock_grades_api,
            mock_enrollment_api
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        mock_enrollment_api.return_value.get_course_enrollment.return_value = dict(
            mode='verified',
        )

        # Mock grades data
        assessment_grade_data = [dict(
            attempted=True,
            subsection_name='subsection_1',
            category='subsection_category',
            percent=1.0,
            label='subsection_label',
            score_earned=10,
            score_possible=10,
            module_id='subsection_id_1'
        )]

        mock_grades_api.return_value.get_course_assessment_grades.return_value = assessment_grade_data

        learner_data = list(self.exporter.bulk_assessment_level_export())

        assert learner_data[0].course_id == self.course_id
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].grade == 1.0
        assert learner_data[0].subsection_id == 'subsection_id_1'

    @ddt.data(
        ('self', LearnerExporter.GRADE_PASSING),
        ('instructor', LearnerExporter.GRADE_PASSING),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_multiple_courses(
            self,
            pacing,
            grade,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_details,
            mock_get_single_user_grade,
            mock_get_course_certificate,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}
        mock_is_course_completed.return_value = True

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
                user_id=self.user_2.id,
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

        def get_course_details(course_key):  # pylint: disable=unused-argument
            """
            Mock course details - set course_id to match input
            """
            return mock_course_overview(
                pacing=pacing,
            )
        mock_get_course_details.side_effect = get_course_details

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
            return None
        mock_get_course_certificate.side_effect = get_course_certificate

        def get_course_grade(course_id, username):  # pylint: disable=unused-argument
            """
            Mock grades data - set passed depending on course_id
            """
            return mock_single_learner_grade(
                passing='2' in course_id,
                percent=100.0,
            )
        mock_get_single_user_grade.side_effect = get_course_grade

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
        # note: the course_completed is a function of the mock_is_course_completed mock
        for report1 in learner_data[0:1]:
            assert report1.enterprise_course_enrollment_id == enrollment1.id
            assert report1.course_completed
            assert report1.completed_timestamp is None
            assert report1.grade == LearnerExporter.GRADE_INCOMPLETE

        assert learner_data[2].course_id == self.course_key
        assert learner_data[3].course_id == course_id2
        for report2 in learner_data[2:3]:
            assert report2.enterprise_course_enrollment_id == enrollment2.id
            assert report2.course_completed
            assert report2.completed_timestamp == self.NOW_TIMESTAMP
            assert report2.grade == grade
        assert learner_data[4].course_id == self.course_key
        assert learner_data[5].course_id == self.course_id
        for report3 in learner_data[4:5]:
            assert report3.enterprise_course_enrollment_id == enrollment3.id
            assert report3.course_completed
            assert report3.completed_timestamp is None
            assert report3.grade == LearnerExporter.GRADE_INCOMPLETE

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
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_audit_data_reporting(
            self,
            enable_audit_enrollment,
            enable_reporting,
            mode,
            expected_data_len,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_details,
            mock_get_single_user_grade,
            mock_course_enrollment_class
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}

        mock_is_course_completed.return_value = True

        # Set the audit track data passback configuration
        self.enterprise_customer.enable_audit_enrollment = enable_audit_enrollment
        self.enterprise_customer.enable_audit_data_reporting = enable_reporting
        self.enterprise_customer.save()

        # Use self-paced course to get grades data
        mock_get_course_details.return_value = mock_course_overview(
            pacing='self',
        )

        # Mock grades data
        mock_get_single_user_grade.return_value = mock_single_learner_grade(
            passing=True,
        )

        # Mock enrollment data, in particular the enrollment mode
        mock_course_enrollment_class.objects.get.return_value.mode = mode

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

    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    def test_learner_exporter_with_skip_transmitted(
        self,
        mock_get_course_details,
        mock_get_single_user_grade,
        mock_course_enrollment_class
    ):
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
        learner_data = list(
            self.exporter.export(
                grade='Pass',
                TransmissionAudit=LearnerDataTransmissionAudit
            )
        )

        assert not learner_data

        # Check that LMS enrollment populated as part of model used in audit check:
        expected_result = mock_course_enrollment_class.objects.get.return_value
        self.assertEqual(expected_result, enterprise_course_enrollment.course_enrollment)
        assert mock_course_enrollment_class.objects.get.call_count == 1

        assert mock_get_course_details.call_count == 0
        assert mock_get_single_user_grade.call_count == 0

    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_id_for_enrollment')
    def test_export_unique_courses_from_enrollments(self, mock_catalog_api_service_client):
        """
        Test export_unique_courses properly selects unique course keys from a customer's enterprise enrollment.
        """
        mock_catalog_api_service_client.side_effect = [self.course_id, self.course_id, self.course_id_2]
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user_2,
            course_id=self.course_id,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id_2
        )
        exporter = LearnerExporter('fake-user', self.config)
        unique_enrollments = exporter.export_unique_courses()

        assert len(unique_enrollments) == 2
        assert self.course_id in unique_enrollments
        assert self.course_id_2 in unique_enrollments

    def test_grades_summary_for_completed_audit_has_autofilled_date(self):
        '''
        We will insert a current date time stamp for audit enrollment,
        if it's completed, and if the grades api returns no completion date
        '''
        exporter = LearnerExporter('fake-user', self.config)
        course_details = mock_course_overview()
        enterprise_enrollment = create_ent_enrollment_mock()
        incomplete_count = 0

        exporter.collect_grades_data = MagicMock(return_value=(None, None, None, None, ))
        completed_date_from_api, _, _, _ = exporter.get_grades_summary(
            course_details,
            enterprise_enrollment,
            'test-channel',
            incomplete_count
        )
        # if we autofill the date, then this shouldn't be None since collect_grades_data is set to
        # return a None value for completed_date
        assert completed_date_from_api is not None
        exporter.collect_grades_data.assert_called_once()

    def test_grades_summary_for_incompleted_audit_honors_existing_date(self):
        '''
        If there is a completed_date from the api called by collect_grades_data
        still honor it rather than override using now, just as a safety measure
        '''
        exporter = LearnerExporter('fake-user', self.config)
        course_details = mock_course_overview()
        enterprise_enrollment = create_ent_enrollment_mock()
        incomplete_count = 0

        a_date = timezone.now()
        exporter.collect_grades_data = MagicMock(return_value=(a_date, None, None, None, ))
        completed_date_from_api, _, _, _ = exporter.get_grades_summary(
            course_details,
            enterprise_enrollment,
            'test-channel',
            incomplete_count
        )
        assert completed_date_from_api is a_date
        exporter.collect_grades_data.assert_called_once()
