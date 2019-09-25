# -*- coding: utf-8 -*-
"""
Tests for the `integrated_channels.cornerstone.models` models module.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import mock
from freezegun import freeze_time
from pytest import mark

from django.utils import timezone

from integrated_channels.cornerstone.models import CornerstoneEnterpriseCustomerConfiguration
from integrated_channels.integrated_channel.tasks import transmit_single_learner_data
from test_utils.factories import EnterpriseCustomerFactory, UserFactory

NOW = timezone.now()


@mark.django_db
class TestCornerstoneEnterpriseCustomerConfiguration(unittest.TestCase):
    """
    Tests of the ``CornerstoneEnterpriseCustomerConfiguration`` model.
    """

    def setUp(self):
        self.enterprise_customer = EnterpriseCustomerFactory()
        self.config = CornerstoneEnterpriseCustomerConfiguration(
            enterprise_customer=self.enterprise_customer,
            active=True
        )
        self.config.save()
        self.user = UserFactory()
        self.demo_course_run_id = 'course-v1:edX+DemoX+Demo_Course_1'

        super(TestCornerstoneEnterpriseCustomerConfiguration, self).setUp()

    @freeze_time(NOW)
    @mock.patch(
        'integrated_channels.cornerstone.models.CornerstoneEnterpriseCustomerConfiguration.get_learner_data_exporter'
    )
    def test_transmit_single_learner_data(self, mock_learner_exporter):
        """
        The transmit_single_learner_data is called and passes kwargs to underlying transmitter.
        """
        kwargs = {
            'learner_to_transmit': self.user,
            'course_run_id': self.demo_course_run_id,
            'completed_date': NOW,
            'grade': 'Pass',
            'is_passing': True,
        }
        mock_learner_exporter.return_value = 'mock_learner_exporter'
        with mock.patch(
            'integrated_channels.cornerstone.models.CornerstoneEnterpriseCustomerConfiguration'
            '.get_learner_data_transmitter'
        ) as mock_transmitter:
            transmit_single_learner_data(self.user.username, self.demo_course_run_id)
            mock_transmitter.return_value.transmit.assert_called_once_with('mock_learner_exporter', **kwargs)
