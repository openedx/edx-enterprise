"""
Tests for Moodle learner data exporters.
"""

import datetime
import unittest
from unittest import mock

from pytest import mark

from django.db.utils import IntegrityError

from integrated_channels.moodle.exporters.learner_data import MoodleLearnerExporter
from integrated_channels.moodle.models import MoodleLearnerDataTransmissionAudit
from test_utils import factories


@mark.django_db
class TestMoodleLearnerDataExporter(unittest.TestCase):
    """
    Test MoodleLearnerDataExporter
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.course_key = 'edX+DemoX'
        self.config = factories.MoodleEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            moodle_base_url='foobar',
            service_short_name='shortname',
            category_id=1,
            decrypted_username='username',
            decrypted_password='password',
            decrypted_token='token',
        )

    def test_unique_enrollment_id_course_id_constraint(self):
        """
        Ensure that the unique constraint on enterprise_course_enrollment_id and course_id is enforced.
        """
        MoodleLearnerDataTransmissionAudit.objects.create(
            moodle_user_email=self.enterprise_customer.contact_email,
            enterprise_course_enrollment_id=5,
            course_id=self.course_id,
            course_completed=True,
            moodle_completed_timestamp=1486855998,
            completed_timestamp=datetime.datetime.fromtimestamp(1486855998),
            total_hours=1.0,
            grade=.9,
        )
        with self.assertRaises(IntegrityError):
            MoodleLearnerDataTransmissionAudit.objects.create(
                moodle_user_email=self.enterprise_customer.contact_email,
                enterprise_course_enrollment_id=5,
                course_id=self.course_id,
                course_completed=True,
                moodle_completed_timestamp=1486855998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486855998),
                total_hours=2.0,
                grade=.9,
            )

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_retrieve_same_learner_data_record(self, mock_course_catalog_api):
        """
        If a learner data record already exists for the enrollment, it should be retrieved instead of created.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            course_id=self.course_id,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        exporter = MoodleLearnerExporter('fake-user', self.config)
        learner_data_records_1 = exporter.get_learner_data_records(
            enterprise_course_enrollment,
            progress_status='In Progress'
        )[0]
        learner_data_records_1.save()
        learner_data_records_2 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_2.save()

        assert learner_data_records_1.id == learner_data_records_2.id
