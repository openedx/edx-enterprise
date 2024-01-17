"""
Tests for Moodle learner data exporters.
"""

import unittest
from unittest import mock

from pytest import mark

from integrated_channels.moodle.exporters.learner_data import MoodleLearnerExporter
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
        learner_data_records_1 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_1.save()
        learner_data_records_2 = exporter.get_learner_data_records(enterprise_course_enrollment)[0]
        learner_data_records_2.save()

        assert learner_data_records_1.id == learner_data_records_2.id
