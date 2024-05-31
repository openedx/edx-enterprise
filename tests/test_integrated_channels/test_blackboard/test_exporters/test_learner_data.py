"""
Tests for Blackboard learner data exporters.
"""

import unittest
from unittest import mock

from pytest import mark

from django.db.utils import IntegrityError

from integrated_channels.blackboard.exporters.learner_data import BlackboardLearnerExporter
from integrated_channels.blackboard.models import BlackboardLearnerDataTransmissionAudit
from test_utils import factories


@mark.django_db
class TestBlackboardLearnerDataExporter(unittest.TestCase):
    """
    Test BlackboardLearnerDataExporter
    """

    def setUp(self):
        super().setUp()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            enterprise_customer=self.enterprise_customer,
        )
        self.course_id = 'course-v1:edX+DemoX+DemoCourse'
        self.course_key = 'edX+DemoX'
        self.config = factories.BlackboardEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            blackboard_base_url='foobar',
            decrypted_client_id='client_id',
            decrypted_client_secret='client_secret',
            refresh_token='token',
        )

    def test_unique_enrollment_id_course_id_constraint(self):
        """
        Ensure that the unique constraint on enterprise_course_enrollment_id and course_id is enforced.
        """
        BlackboardLearnerDataTransmissionAudit.objects.create(
            enterprise_course_enrollment_id=5,
            course_id=self.course_id,
            course_completed=True,
            blackboard_completed_timestamp=1486855998,
        )
        with self.assertRaises(IntegrityError):
            BlackboardLearnerDataTransmissionAudit.objects.create(
                enterprise_course_enrollment_id=5,
                course_id=self.course_id,
                course_completed=True,
                blackboard_completed_timestamp=1486855998,
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
        exporter = BlackboardLearnerExporter('fake-user', self.config)
        learner_data_records_1 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_1.save()
        learner_data_records_2 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_2.save()

        assert learner_data_records_1.id == learner_data_records_2.id
