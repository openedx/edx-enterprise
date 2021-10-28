# -*- coding: utf-8 -*-
"""
Tests for Degreed2 content metadata exporters.
"""

import unittest

import ddt
import mock
import responses
from pytest import mark

from integrated_channels.degreed2.exporters.content_metadata import Degreed2ContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_catalog_api import get_fake_catalog, get_fake_content_metadata
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestDegreed2ContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``DegreedContentMetadataExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()
        # Need a non-abstract config.
        self.config = factories.Degreed2EnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )
        super().setUp()

    @ddt.data(
        (
            {
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    },
                    {
                        'start': '2017-02-05T05:00:00Z',
                        'min_effort': 9,
                        'max_effort': 10,
                        'weeks_to_complete': 12
                    }
                ]
            },
            '2-4 hours a week for 10 weeks. Detailed description of edx demo course.',
        ),
        (
            {
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': '',
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },
            '2-4 hours a week for 10 weeks. Some short description.',
        ),
        (
            {
                'title': 'edX Demonstration Course',
                'short_description': '',
                'full_description': '',
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },
            '2-4 hours a week for 10 weeks. edX Demonstration Course',
        ),
        (
            {
                'title': '',
                'short_description': '',
                'full_description': '',
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },
            '',
        ),
        (
            {
                'title': '',
                'short_description': '',
                'full_description': '<p>This course is part of the '
                                    '<a href=\"../../../../microsoft-professional-program-certficate-data-science\">'
                                    '<em>&#8804;Professional Program Certificate in Data Science</em></a>'
                                    '&nbsp;That doesn&rsquo;t<em> '
                                    'only teach us how to build a cloud data science solution using Microsoft Azure '
                                    'Machine Learning platform',
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },

            '2-4 hours a week for 10 weeks. '
            'This course is part of the Professional Program Certificate in Data ScienceThat doesnt '
            'only teach us how to build a cloud data science solution using Microsoft Azure Machine Learning platform'
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_description(self, content_metadata_item, expected_description):
        """
        Test the transform of description on multiple use cases.
        """
        exporter = Degreed2ContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_description(content_metadata_item) == expected_description
