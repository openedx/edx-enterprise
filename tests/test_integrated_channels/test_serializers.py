"""
Test suite for Enterprise Integrated Channels serializers. 
"""

import unittest

import ddt
from pytest import mark
import uuid

from integrated_channels.integrated_channel.exporters.learner_data import get_learner_data_records
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestLearnerSyncStatusSerializer(unittest.TestCase):
    """
    Tests for LearnerSyncStatusSerializer
    """

    def setUp(self):
      customer_uuid_1 = uuid.uuid4()
      # self.enterprise_customer = factories.EnterpriseCustomerFactory(
      #       uuid=customer_uuid_1,
      #   )
      # self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
      #       user_id=self.user.id,
      #       enterprise_customer=self.enterprise_customer,
      # )
      cornerstone_learner_audit = factories.CornerstoneLearnerDataTransmissionAuditFactory(
          id=1,
          enterprise_customer_uuid=customer_uuid_1,
          course_id='course-v1:edX+DemoX+DemoCourse',
          plugin_configuration_id='1',
          status='404',
          completed_timestamp=1486855998,
      )
      degreed_learner_audit = factories.DegreedLearnerDataTransmissionAuditFactory(
          id=1,
          enterprise_customer_uuid=customer_uuid_1,
          course_id='course-v1:edX+DemoX+DemoCourse',
          plugin_configuration_id='1',
          status='202',
          completed_timestamp=1586855998,
      )
      sap_learner_audit = factories.SapSuccessFactorsLearnerDataTransmissionAuditFactory(
          id=1,
          enterprise_customer_uuid=customer_uuid_1,
          course_id='course-v1:edX+DemoX+DemoCourse',
          plugin_configuration_id='2',
          status='200',
          completed_timestamp=1668465843, 
      )
      super().setUp()

    def test_learner_serializer(self):
      # enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
      #   enterprise_customer_user=self.enterprise_customer_user,
      #   course_id='course-v1:edX+DemoX+DemoCourse',
      # )
      # exporter = LearnerExporter('fake-user', self.config)
      # learner_data_records = get_learner_data_records(
      #     enterprise_course_enrollment,
      # )

class TestContentSyncStatusSerializer(unittest.TestCase):
    """
    Tests for LearnerSyncStatusSerializer
    """

    def setUp(self):
      customer_uuid_1 = uuid.uuid4()
      self.enterprise_customer = factories.EnterpriseCustomerFactory(
        uuid=customer_uuid_1,
      )
      canvas_transmission = factories.ContentMetadataItemTransmissionFactory(
          integrated_channel_code='CANVAS',
          enterprise_customer=self.enterprise_customer,
          plugin_configuration_id=1,
          api_response_status_code=200,
          content_last_changed='2019-01-16T15:11:10.521611Z',
          remote_created_at='2019-07-16T15:11:10.521611Z',
          remote_updated_at='2019-12-16T15:11:10.521611Z',
          remote_deleted_at=None,
      )
      moodle_transmission = factories.ContentMetadataItemTransmissionFactory(
          integrated_channel_code='MOODLE',
          enterprise_customer=self.enterprise_customer,
          plugin_configuration_id=1,
          api_response_status_code=200,
          content_last_changed='2019-02-16T15:11:10.521611Z',
          remote_created_at='2019-01-16T15:11:10.521611Z',
          remote_deleted_at=None,
      )
      blackboard_transmission = factories.ContentMetadataItemTransmissionFactory(
          integrated_channel_code='BLACKBOARD',
          enterprise_customer=self.enterprise_customer,
          plugin_configuration_id=1,
          api_response_status_code=400,
          content_last_changed='2021-07-17T15:11:10.521611Z',
          remote_created_at='2021-07-16T15:11:10.521611Z',
          remote_deleted_at='2021-07-17T15:11:10.521611Z',
      )


