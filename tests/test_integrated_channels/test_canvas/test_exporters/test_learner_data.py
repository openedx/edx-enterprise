"""
Tests for Canvas learner data exporters.
"""

import datetime
import unittest
from unittest import mock

from pytest import mark

from django.db.utils import IntegrityError

from integrated_channels.canvas.exporters.learner_data import CanvasLearnerExporter
from integrated_channels.canvas.models import CanvasLearnerDataTransmissionAudit
from test_utils import factories


@mark.django_db
class TestCanvasLearnerDataExporter(unittest.TestCase):
    """
    Test CanvasLearnerDataExporter
    """

    def setUp(self):
        super().setUp()
        self.user = factories.UserFactory(id=1, email='example@email.com')
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.course_key = 'edX+DemoX'
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            id=5,
            enterprise_customer_user=self.enterprise_customer_user,
        )
        self.config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            canvas_base_url='foobar',
        )

    def test_unique_enrollment_id_course_id_constraint(self):
        """
        Ensure that the unique constraint on enterprise_course_enrollment_id and course_id is enforced.
        """
        CanvasLearnerDataTransmissionAudit.objects.create(
            canvas_user_email=self.user.email,
            enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
            course_id=self.course_id,
            course_completed=True,
            canvas_completed_timestamp=1486855998,
            completed_timestamp=datetime.datetime.fromtimestamp(1486855998),
            total_hours=1.0,
            grade=.9,
        )
        with self.assertRaises(IntegrityError):
            CanvasLearnerDataTransmissionAudit.objects.create(
                canvas_user_email=self.user.email,
                enterprise_course_enrollment_id=self.enterprise_course_enrollment.id,
                course_id=self.course_id,
                course_completed=True,
                canvas_completed_timestamp=1486855998,
                completed_timestamp=datetime.datetime.fromtimestamp(1486855998),
                total_hours=1.0,
                grade=.9,
            )

    @mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
    def test_retrieve_same_learner_data_record(self, mock_course_catalog_api):
        """
        If a learner data record already exists for the enrollment, it should be retrieved instead of created.
        """
        mock_course_catalog_api.return_value.get_course_id.return_value = self.course_key
        exporter = CanvasLearnerExporter('fake-user', self.config)
        learner_data_records_1 = exporter.get_learner_data_records(
            self.enterprise_course_enrollment,
            progress_status='In Progress'
        )[0]
        learner_data_records_1.save()
        learner_data_records_2 = exporter.get_learner_data_records(self.enterprise_course_enrollment)[0]
        learner_data_records_2.save()

        assert learner_data_records_1.id == learner_data_records_2.id
