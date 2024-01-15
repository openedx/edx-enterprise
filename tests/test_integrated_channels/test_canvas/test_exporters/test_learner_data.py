"""
Tests for Canvas learner data exporters.
"""

import unittest
from unittest import mock

from pytest import mark

from integrated_channels.canvas.exporters.learner_data import CanvasLearnerExporter
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
        self.config = factories.CanvasEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            canvas_base_url='foobar',
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
        exporter = CanvasLearnerExporter('fake-user', self.config)
        learner_data_records_1 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_1.save()
        learner_data_records_2 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_2.save()

        assert learner_data_records_1.id == learner_data_records_2.id
