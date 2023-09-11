# -*- coding: utf-8 -*-
"""
Tests for Degreed Learner Data exporters.
"""

import datetime
import unittest

import ddt
import mock
from freezegun import freeze_time
from mock.mock import MagicMock
from pytest import mark

from integrated_channels.degreed2.exporters.learner_data import Degreed2LearnerExporter
from test_utils import factories
from test_utils.fake_catalog_api import setup_course_catalog_api_client_mock


@mark.django_db
@ddt.ddt
class TestDegreed2LearnerExporter(unittest.TestCase):
    """
    Tests of DegreedLearnerExporter class.
    """

    NOW = datetime.datetime(2017, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    NOW_TIMESTAMP = 1483326245000

    def setUp(self):
        self.user = factories.UserFactory(username='C3PO', id=1, email='degreed@email.com')
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
        self.config = factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer,
            active=True,
        )
        self.idp = factories.EnterpriseCustomerIdentityProviderFactory(
            enterprise_customer=self.enterprise_customer
        )
        tpa_client_mock = mock.patch('enterprise.models.ThirdPartyAuthApiClient')
        self.tpa_client = tpa_client_mock.start()
        self.tpa_client.return_value.get_remote_id.return_value = 'fake-remote-id'
        self.addCleanup(tpa_client_mock.stop)

        course_catalog_api_client_mock = mock.patch('enterprise.api_client.discovery.CourseCatalogApiServiceClient')
        self.course_catalog_client = course_catalog_api_client_mock.start()
        setup_course_catalog_api_client_mock(self.course_catalog_client)
        self.addCleanup(course_catalog_api_client_mock.stop)
        super().setUp()

    @ddt.data(
        (None, None,),
        (NOW, .83),
    )
    @ddt.unpack
    @freeze_time(NOW)
    def test_get_learner_data_record(self, completed_date, grade_percent):
        """
        The base ``get_learner_data_record`` method returns a ``LearnerDataTransmissionAudit`` with appropriate values.
        """
        enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=self.course_id,
        )
        exporter = Degreed2LearnerExporter('fake-user', self.config)
        learner_data_records = exporter.get_learner_data_records(
            enterprise_course_enrollment,
            completed_date=completed_date,
            grade_percent=grade_percent,
        )
        assert len(learner_data_records) == 2
        assert learner_data_records[0].course_id == self.course_key
        assert learner_data_records[1].course_id == self.course_id

        for learner_data_record in learner_data_records:
            assert learner_data_record.enterprise_course_enrollment_id == enterprise_course_enrollment.id
            assert learner_data_record.degreed_user_email == 'degreed@email.com'
            assert learner_data_record.degreed_completed_timestamp == (
                self.NOW.strftime('%Y-%m-%dT%H:%M:%S') if completed_date is not None else None
            )
            assert learner_data_record.grade == (grade_percent * 100 if grade_percent else None)

    def test_no_remote_id(self):
        """
        If the TPA API Client returns no remote user ID, nothing is returned.
        """
        self.tpa_client.return_value.get_remote_id.return_value = None
        exporter = Degreed2LearnerExporter('fake-user', self.config)
        assert exporter.get_learner_data_records(factories.EnterpriseCourseEnrollmentFactory()) is None

    @mock.patch('integrated_channels.degreed.exporters.learner_data.get_course_id_for_enrollment')
    def test_get_remote_id_called_with_idp_id(self, mock_get_course_id_for_enrollment):
        mock_get_course_id_for_enrollment.return_value = 'test:id'
        enterprise_configuration = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=factories.EnterpriseCustomerFactory(),
            idp_id='test-id'
        )
        enterprise_customer_user = factories.EnterpriseCustomerUserFactory()
        enterprise_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user
        )
        enterprise_enrollment.enterprise_customer_user.get_remote_id = MagicMock()
        exporter = Degreed2LearnerExporter(factories.UserFactory(), enterprise_configuration)

        exporter.get_learner_data_records(enterprise_enrollment)
        enterprise_enrollment.enterprise_customer_user.get_remote_id.assert_called_once_with(
            enterprise_configuration.idp_id
        )
