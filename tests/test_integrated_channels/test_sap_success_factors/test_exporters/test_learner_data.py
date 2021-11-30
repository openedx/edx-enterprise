# -*- coding: utf-8 -*-
"""
Tests for SAPSF learner data exporters.
"""

import unittest

import ddt
import mock
from mock.mock import MagicMock
from pytest import mark

from integrated_channels.sap_success_factors.exporters.learner_data import SapSuccessFactorsLearnerExporter
from test_utils.factories import (
    EnterpriseCourseEnrollmentFactory,
    EnterpriseCustomerFactory,
    EnterpriseCustomerUserFactory,
    SAPSuccessFactorsEnterpriseCustomerConfigurationFactory,
    UserFactory,
)


@mark.django_db
@ddt.ddt
class TestSAPSuccessFactorLearnerDataExporter(unittest.TestCase):
    """
    Tests for the ``SapSuccessFactorsLearnerDataExporter`` class.
    """

    @mock.patch('integrated_channels.sap_success_factors.exporters.learner_data.get_course_id_for_enrollment')
    @mock.patch('integrated_channels.sap_success_factors.exporters.learner_data.get_course_run_for_enrollment')
    def test_call_get_remote_id(self, mock_get_course_run_for_enrollment, mock_get_course_id_for_enrollment):
        mock_get_course_run_for_enrollment.return_value = MagicMock()
        mock_get_course_id_for_enrollment.return_value = 'test:id'
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory()
        enterprise_configuration = SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            idp_id='test-id'
        )
        completed_date = None
        grade = 'Pass'
        course_completed = False
        enterprise_customer_user = EnterpriseCustomerUserFactory()
        enterprise_enrollment = EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user
        )
        enterprise_enrollment.enterprise_customer_user.get_remote_id = MagicMock()
        exporter = SapSuccessFactorsLearnerExporter(user, enterprise_configuration)

        exporter.get_learner_data_records(
            enterprise_enrollment,
            completed_date,
            grade,
            course_completed
        )
        enterprise_enrollment.enterprise_customer_user.get_remote_id.assert_called_once_with(
            enterprise_configuration.idp_id
        )

    def test_override_of_default_channel_settings(self):
        """
        If you override any settings to the ChannelSettingsMixin, add a test here for those
        """
        user = UserFactory()
        enterprise_customer = EnterpriseCustomerFactory()
        enterprise_configuration = SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=enterprise_customer,
            idp_id='test-id'
        )
        assert SapSuccessFactorsLearnerExporter(
            user,
            enterprise_configuration
        ).INCLUDE_GRADE_FOR_COMPLETION_AUDIT_CHECK is False
