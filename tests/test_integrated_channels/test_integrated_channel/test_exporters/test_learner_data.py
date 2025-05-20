"""
Tests for the `edx-enterprise` learner_data export classes.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from unittest.mock import MagicMock

import ddt
from freezegun import freeze_time
from pytest import mark
from requests.exceptions import HTTPError

from integrated_channels.integrated_channel.exporters.learner_data import LearnerExporter
from integrated_channels.integrated_channel.models import GenericLearnerDataTransmissionAudit
from test_utils import factories
from test_utils.integrated_channels_utils import (
    mock_course_overview,
    mock_persistent_course_grade,
    mock_single_learner_grade,
)


def create_ent_enrollment_mock(is_audit=True):
    '''
    creates a magicmock instance for enterprise enrollment
    '''
    enterprise_enrollment = MagicMock()
    enterprise_enrollment.enterprise_customer_user = MagicMock()
    enterprise_enrollment.enterprise_customer_user.user_id = 1
    enterprise_enrollment.enterprise_customer_user.enterprise_customer = MagicMock()
    enterprise_enrollment.enterprise_customer_user.enterprise_customer.uuid = 'abc'
    enterprise_enrollment.is_audit_enrollment = is_audit
    return enterprise_enrollment


@mark.django_db
@ddt.ddt
class TestLearnerExporter(unittest.TestCase):
    """
    Tests of LearnerExporter class.
    """

    # Use these tz-aware datetimes in tests
    NOW = datetime(2017, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    NOW_TIMESTAMP = 1483326245000
    TOMORROW = NOW + timedelta(days=1)
    YESTERDAY = NOW + timedelta(days=-1)
    YESTERDAY_TIMESTAMP = NOW_TIMESTAMP - 24 * 60 * 60 * 1000

    def setUp(self):
        self.user = factories.UserFactory(username='C3PO', id=1, email='burneremail@example.com')
        self.user_2 = factories.UserFactory(username='R2D2', id=2, email='burneremail2@example.com')
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
        self.config = factories.GenericEnterpriseCustomerPluginConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
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
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_get_learner_data_record(self, completed_date, mock_course_catalog_api):
        """
        The base ``get_learner_data_record`` method returns a ``GenericLearnerDataTransmissionAudit``
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
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
        assert learner_data_record.course_id == self.course_key
        assert learner_data_record.course_completed == expected_course_completed
        assert learner_data_record.completed_timestamp == (self.NOW_TIMESTAMP if completed_date is not None else None)
        assert learner_data_record.grade == 'A+'

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_retrieve_same_learner_data_record(self, mock_course_catalog_api):
        """
        If a learner data record already exists for the enrollment, it should be retrieved instead of created.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        expected_course_completed = True
        exporter = LearnerExporter('fake-user', self.config)
        learner_data_records_1 = exporter.get_learner_data_records(
            enterprise_course_enrollment,
            course_completed=expected_course_completed,
            progress_status='Passed'
        )[0]
        learner_data_records_1.save()
        learner_data_records_2 = exporter.get_learner_data_records(
            enterprise_course_enrollment,
            course_completed=expected_course_completed,
            progress_status='Passed'
        )[0]
        learner_data_records_2.save()

        assert learner_data_records_1.id == learner_data_records_2.id

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
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "verified"
        }

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
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    def test_learner_data_instructor_paced_no_certificate(
            self,
            mock_get_single_user_grade,
            mock_get_persistent_grade,
            mock_get_course_certificate,
            mock_course_catalog_api,
            mock_get_course_details,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_course_certificate.return_value = None
        mock_get_persistent_grade.return_value = None
        mock_get_single_user_grade.return_value = None

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='instructor',
        )

        # Return enrollment mode data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "verified"
        }

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 1
        assert learner_data[0].course_id == self.course_key

        assert learner_data[0].user_email == self.user.email
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert not learner_data[0].course_completed
        assert learner_data[0].completed_timestamp is None
        assert learner_data[0].grade == LearnerExporter.GRADE_INCOMPLETE

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    def test_learner_data_instructor_paced_no_certificate_null_sso_id(
            self,
            mock_get_course_certificate,
            mock_get_course_details,
            mock_get_single_user_grade,
            mock_enrollment_api
    ):
        # SSO/SAP-specific behaviour and the Generic config doesnt depend on it
        self.config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            sapsf_base_url='enterprise.successfactors.com',
            decrypted_key='key',
            decrypted_secret='secret',
            active=True,
        )
        self.exporter = self.config.get_learner_data_exporter('dummy-user')

        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        # No SSO user attached
        self.tpa_client.get_remote_id.return_value = None

        # no certificate found
        mock_get_course_certificate.return_value = None

        # no grade found
        mock_get_single_user_grade.return_value = None

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='instructor',
        )

        # Return enrollment mode data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "audit"
        }

        learner_data = list(self.exporter.export())
        assert not learner_data

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_instructor_paced_with_certificate_created_date(
            self,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_certificate,
            mock_get_persistent_grade,
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

        mock_get_persistent_grade.return_value = None

        # Return a mock certificate a created_date
        certificate = {
            'username': self.user,
            'course_id': self.course_id,
            'certificate_type': 'professional',
            'created_date': self.NOW.isoformat(),
            'status': 'downloadable',
            'is_passing': True,
            'grade': 'A-',
        }
        mock_get_course_certificate.return_value = certificate

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='instructor',
            display_name='Dogs and Cats: Star Crossed Lovers or Fated Foes'
        )

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "verified"
        }

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 1
        assert learner_data[0].course_id == self.course_key
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].course_completed
        assert learner_data[0].completed_timestamp == self.NOW_TIMESTAMP
        assert learner_data[0].grade == LearnerExporter.GRADE_PASSING
        assert learner_data[0].progress_status == 'Passed'
        assert learner_data[0].content_title == 'Dogs and Cats: Star Crossed Lovers or Fated Foes'

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_instructor_paced_with_certificate_created(
            self,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_certificate,
            mock_get_persistent_grade,
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

        mock_get_persistent_grade.return_value = None

        # Return a mock certificate with a created field (formatted)
        certificate = {
            "username": self.user,
            "course_id": self.course_id,
            "certificate_type": "professional",
            "created": self.NOW.isoformat(),
            "status": "downloadable",
            "is_passing": True,
            "grade": "A-",
        }
        mock_get_course_certificate.return_value = certificate

        # Return instructor-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='instructor',
        )

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "verified"
        }

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 1
        assert learner_data[0].course_id == self.course_key
        assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
        assert learner_data[0].course_completed
        assert learner_data[0].completed_timestamp == self.NOW_TIMESTAMP
        assert learner_data[0].grade == LearnerExporter.GRADE_PASSING

    @mock.patch('enterprise.models.EnrollmentApiClient')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_self_paced_no_grades(
            self,
            mock_course_catalog_api,
            mock_get_course_details,
            mock_get_single_user_grade,
            mock_get_course_certificate,
            mock_enrollment_api,
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_course_certificate.return_value = None

        # Return self-paced course details
        mock_get_course_details.return_value = mock_course_overview(
            pacing='self',
        )

        # Mock grades data not found
        mock_get_single_user_grade.return_value = None

        # Mock enrollment data
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "verified"
        }

        learner_data = list(self.exporter.export())
        assert len(learner_data) == 1
        assert learner_data[0].course_id == self.course_key

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert not report.course_completed
            assert report.completed_timestamp is None
            assert report.grade is LearnerExporter.GRADE_INCOMPLETE
            assert report.progress_status == 'In Progress'

    @ddt.data(
        # passing grade with no course end date
        (True, None, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified', 'Passed'),
        # passing grade with course end date in past
        (True, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified', 'Passed'),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified', 'Passed'),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'audit', 'Passed'),
        # non-passing grade with no course end date
        (False, None, None, LearnerExporter.GRADE_INCOMPLETE, 'verified', 'In Progress'),
        # non-passing grade with course end date in past
        (False, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_FAILING, 'verified', 'Failed'),
        # non-passing grade with course end date in past
        (False, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_AUDIT, 'audit', 'Failed'),
        # non-passing grade with course end date in future
        (False, TOMORROW, None, LearnerExporter.GRADE_INCOMPLETE, 'verified', 'In Progress'),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
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
            progress_status,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_details,
            mock_get_persistent_grade,
            mock_get_single_user_grade,
            mock_get_course_certificate,
            mock_course_enrollment_class
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}

        mock_is_course_completed.return_value = True
        mock_get_course_certificate.return_value = None
        mock_get_persistent_grade.return_value = mock_persistent_course_grade(
            user_id='a-user-id',
            course_id=self.course_id,
            passed_timestamp=expected_completion,
        )

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

        assert len(learner_data) == 1
        assert learner_data[0].course_id == self.course_key

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert report.progress_status == progress_status
            assert report.course_completed
            assert report.completed_timestamp == expected_completion
            assert report.grade == expected_grade

    @ddt.data(
        # passing grade with no course end date
        (True, None, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified'),
        # passing grade with course end date in past
        (True, YESTERDAY, YESTERDAY_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified'),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'verified'),
        # passing grade with course end date in future
        (True, TOMORROW, NOW_TIMESTAMP, LearnerExporter.GRADE_PASSING, 'audit'),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_self_paced_course_with_funky_certificate(
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
            mock_get_persistent_grade,
            mock_get_single_user_grade,
            mock_get_course_certificate,
            mock_course_enrollment_class
    ):
        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}

        mock_is_course_completed.return_value = True

        # Return a mock certificate with a blank created field (funky)
        # Should use passing timestamp instead
        certificate = {
            'username': self.user,
            'course_id': self.course_id,
            'certificate_type': 'professional',
            'status': 'downloadable',
            'is_passing': True,
            'grade': 'A-',
        }
        mock_get_course_certificate.return_value = certificate

        mock_get_persistent_grade.return_value = mock_persistent_course_grade(
            user_id='a-user-id',
            course_id=self.course_id,
            passed_timestamp=expected_completion,
        )

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

        assert len(learner_data) == 1
        assert learner_data[0].course_id == self.course_key

        for report in learner_data:
            assert report.enterprise_course_enrollment_id == enrollment.id
            assert report.course_completed
            assert report.completed_timestamp == expected_completion
            assert report.grade == expected_grade

    @ddt.data(
        ('A-', None),
        ('0.72', 72.0),
    )
    @ddt.unpack
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_completion_summary')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.is_course_completed')
    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_learner_data_grade_typing(
            self,
            grade_value,
            expected_grade,
            mock_course_catalog_api,
            mock_is_course_completed,
            mock_get_completion_summary,
            mock_get_course_details,
            mock_get_persistent_grade,
            mock_get_single_user_grade,
            mock_get_course_certificate,
            mock_course_enrollment_class
    ):
        factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        # Return a mock certificate with a grade value to be transformed by the exporter
        certificate = {
            'username': self.user,
            'course_id': self.course_id,
            'certificate_type': 'professional',
            'status': 'downloadable',
            'is_passing': True,
            'grade': grade_value,
        }

        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}
        mock_is_course_completed.return_value = True
        mock_get_course_certificate.return_value = certificate
        mock_get_persistent_grade.return_value = mock_persistent_course_grade(
            user_id='a-user-id',
            course_id=self.course_id,
            passed_timestamp=self.NOW_TIMESTAMP,
        )
        mock_get_course_details.return_value = mock_course_overview(pacing='self', end=None)
        mock_get_single_user_grade.return_value = mock_single_learner_grade(
            passing=True,
        )
        mock_course_enrollment_class.objects.get.return_value.mode = 'verified'

        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            self.config = factories.Degreed2EnterpriseCustomerConfigurationFactory(
                enterprise_customer=self.enterprise_customer,
            )
            self.exporter = self.config.get_learner_data_exporter('test')
            learner_data = list(self.exporter.export())

        assert learner_data[0].grade == expected_grade

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

        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            'mode': 'verified',
        }

        # Mock grades data
        assessment_grade_data = [{
            'attempted': True,
            'subsection_name': 'subsection_1',
            'category': 'subsection_category',
            'percent': 1.0,
            'label': 'subsection_label',
            'score_earned': 10,
            'score_possible': 10,
            'module_id': 'subsection_id_1'
        }]

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
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
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
            mock_get_persistent_grade,
            mock_enrollment_api
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}
        mock_is_course_completed.return_value = True
        mock_get_persistent_grade.return_value = None

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
                return {
                    'username': username,
                    'is_passing': True,
                    'grade': grade,
                }
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
        mock_enrollment_api.return_value.get_course_enrollment.return_value = {
            "mode": "verified"
        }

        # Collect the learner data, with time set to NOW
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.export())

        assert len(learner_data) == 3

        assert learner_data[0].course_id == self.course_key
        # note: the course_completed is a function of the mock_is_course_completed mock
        assert learner_data[0].enterprise_course_enrollment_id == enrollment1.id
        assert learner_data[0].course_completed
        assert learner_data[0].completed_timestamp is None
        assert learner_data[0].grade == LearnerExporter.GRADE_INCOMPLETE

        assert learner_data[1].course_id == self.course_key
        assert learner_data[1].enterprise_course_enrollment_id == enrollment2.id
        assert learner_data[1].course_completed
        assert learner_data[1].completed_timestamp == self.NOW_TIMESTAMP
        assert learner_data[1].grade == grade

        assert learner_data[2].course_id == self.course_key
        assert learner_data[2].enterprise_course_enrollment_id == enrollment3.id
        assert learner_data[2].course_completed
        assert learner_data[2].completed_timestamp is None
        assert learner_data[2].grade == LearnerExporter.GRADE_INCOMPLETE

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
    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_persistent_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_certificate')
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
            mock_get_course_certificate,
            mock_get_persistent_grade,
            mock_course_enrollment_class
    ):
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key

        enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )

        mock_get_completion_summary.return_value = {'complete_count': 1, 'incomplete_count': 0, 'locked_count': 0}

        mock_is_course_completed.return_value = True
        mock_get_course_certificate.return_value = None

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

        mock_get_persistent_grade.return_value = mock_persistent_course_grade(
            user_id='a-user-id',
            course_id=self.course_key,
            passed_timestamp=self.YESTERDAY_TIMESTAMP,
        )

        # Collect the learner data
        with freeze_time(self.NOW):
            learner_data = list(self.exporter.export())

        assert len(learner_data) == expected_data_len

        if expected_data_len == 1:
            assert learner_data[0].course_id == self.course_key
            assert learner_data[0].enterprise_course_enrollment_id == enrollment.id
            assert learner_data[0].course_completed
            assert learner_data[0].grade == LearnerExporter.GRADE_PASSING

    @mock.patch('enterprise.models.CourseEnrollment')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_single_user_grade')
    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.get_course_details')
    # @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    # mock_course_catalog_api,
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
        mock_get_course_details.return_value = mock_course_overview(
            pacing='self'
        )
        transmission_audit = GenericLearnerDataTransmissionAudit(
            plugin_configuration_id=self.config.id,
            enterprise_customer_uuid=self.enterprise_customer.uuid,
            enterprise_course_enrollment_id=enterprise_course_enrollment.id,
            course_id=self.course_id,
            course_completed=True,
            completed_timestamp=datetime.fromtimestamp(1568877047),
            grade=1.0,
            status='200',
            error_message='',
            created=datetime.fromtimestamp(1568877047),
            modified=datetime.fromtimestamp(1568877047),
            is_transmitted=True
        )
        transmission_audit.save()
        learner_data = list(
            self.exporter.export(
                grade=1,
                TransmissionAudit=GenericLearnerDataTransmissionAudit
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

        exporter.collect_grades_data = MagicMock(return_value=(None, None, None, None, None))
        completed_date_from_api, _, _, _, _ = exporter.get_grades_summary(
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

        a_date = datetime.now(timezone.utc)
        exporter.collect_grades_data = MagicMock(return_value=(a_date, None, None, None, None))
        completed_date_from_api, _, _, _, _ = exporter.get_grades_summary(
            course_details,
            enterprise_enrollment,
            'test-channel',
            incomplete_count
        )
        assert completed_date_from_api is a_date
        exporter.collect_grades_data.assert_called_once()

    def test_audit_enrollment_does_not_check_cert(self):
        '''
        If cert data available, use it prefentially for reporting learner data
        Else use grades data if available
        '''
        exporter = LearnerExporter('fake-user', self.config)
        a_date = datetime.now(timezone.utc)
        course_details = mock_course_overview()
        enterprise_enrollment_audit_track = create_ent_enrollment_mock()
        incomplete_count = 0

        # audit enrollment should not call cert api
        exporter.collect_grades_data = MagicMock(return_value=(a_date, None, None, None, None))
        exporter.collect_certificate_data = MagicMock(return_value=())
        completed_date_from_api, _, _, _, _ = exporter.get_grades_summary(
            course_details,
            enterprise_enrollment_audit_track,
            'test-channel',
            incomplete_count
        )
        assert completed_date_from_api is a_date
        exporter.collect_grades_data.assert_called_once()
        exporter.collect_certificate_data.assert_not_called()

        exporter.collect_grades_data.reset_mock()
        exporter.collect_certificate_data.reset_mock()

    def test_nonnaudit_enrollment_checks_cert(self):
        '''
        If cert data available, use it prefentially for reporting learner data
        Else use grades data if available
        '''
        exporter = LearnerExporter('fake-user', self.config)
        a_date = datetime.now(timezone.utc)
        course_details = mock_course_overview()
        enterprise_enrollment_verified_track = create_ent_enrollment_mock(False)
        incomplete_count = 0

        # non audit enrollment should call cert api
        exporter.collect_grades_data = MagicMock(return_value=('2022-09-09', None, False, None, self.NOW_TIMESTAMP))
        exporter.collect_certificate_data = MagicMock(return_value=(a_date, None, True, 0.12, self.NOW_TIMESTAMP))
        completed_date_from_api, _, _, _, _ = exporter.get_grades_summary(
            course_details,
            enterprise_enrollment_verified_track,
            'test-channel',
            incomplete_count
        )
        assert completed_date_from_api is a_date
        exporter.collect_grades_data.assert_not_called()
        exporter.collect_certificate_data.assert_called_once()

    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    def test_collect_assessment_grades_data_404(self, mock_grades_api):
        """
        Test _collect_assessment_grades_data returns empty dict if assessment_grades_data not found.
        """
        exporter = LearnerExporter('fake-user', self.config)
        get_course_assessment_grades_mock = mock_grades_api.return_value.get_course_assessment_grades
        response_mock = mock.Mock()
        response_mock.status_code = 404
        get_course_assessment_grades_mock.side_effect = HTTPError(response=response_mock)

        result = exporter._collect_assessment_grades_data(mock.Mock())  # pylint: disable=protected-access
        assert isinstance(result, dict)
        assert not result

    @mock.patch('integrated_channels.integrated_channel.exporters.learner_data.GradesApiClient')
    def test_collect_assessment_grades_data_error(self, mock_grades_api):
        """
        Test _collect_assessment_grades_data rises error.
        """
        exporter = LearnerExporter('fake-user', self.config)
        get_course_assessment_grades_mock = mock_grades_api.return_value.get_course_assessment_grades
        response_mock = mock.Mock()
        response_mock.status_code = 400
        get_course_assessment_grades_mock.side_effect = HTTPError(response=response_mock)

        with self.assertRaises(HTTPError):
            exporter._collect_assessment_grades_data(mock.Mock())  # pylint: disable=protected-access
