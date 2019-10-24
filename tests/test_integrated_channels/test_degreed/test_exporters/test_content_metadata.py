# -*- coding: utf-8 -*-
"""
Tests for Degreed content metadata exporters.
"""

from __future__ import absolute_import, unicode_literals, with_statement

import unittest

import ddt
import mock
import responses
from pytest import mark

from integrated_channels.degreed.exporters.content_metadata import DegreedContentMetadataExporter
from test_utils import FAKE_UUIDS, factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestDegreedContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``DegreedContentMetadataExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer_catalog = factories.EnterpriseCustomerCatalogFactory()

        # Need a non-abstract config.
        self.config = factories.DegreedEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer_catalog.enterprise_customer,
        )

        # Mocks
        self.mock_enterprise_customer_catalogs(str(self.enterprise_customer_catalog.uuid))
        jwt_builder = mock.patch('enterprise.api_client.lms.JwtBuilder', mock.Mock())
        self.jwt_builder = jwt_builder.start()
        self.addCleanup(jwt_builder.stop)
        super(TestDegreedContentMetadataExporter, self).setUp()

    @responses.activate
    def test_content_exporter_export(self):
        """
        ``DegreedContentMetadataExporter``'s ``export`` produces the expected export.
        """
        exporter = DegreedContentMetadataExporter('fake-user', self.config)
        content_items = exporter.export()
        assert sorted(list(content_items.keys())) == sorted([
            'edX+DemoX',
            'course-v1:edX+DemoX+Demo_Course',
            FAKE_UUIDS[3],
        ])

    @ddt.data(
        (
            {
                'aggregation_key': 'course:edX+DemoX',
                'title': 'edX Demonstration Course',
                'key': 'edX+DemoX',
                'content_type': 'course',
                'image_url': 'https://edx.devstack.lms:18000/'
                             'asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
            },
            'https://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg'
        ),
        (
            {
                'number': 'DemoX',
                'org': 'edX',
                'seat_types': ['verified', 'audit'],
                'key': 'course-v1:edX+DemoX+Demo_Course',
                'availability': 'Current',
                'title': 'edX Demonstration Course',
                'content_type': 'courserun',
                'image_url': 'https://edx.devstack.lms:18000/'
                             'asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
            },
            'https://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg'
        ),
        (
            {

                'uuid': '5742ec8d-25ce-43b7-a158-6dad82034ca2',
                'title': 'edX Demonstration program',
                'published': True,
                'language': [],
                'type': 'Verified Certificate',
                'status': 'active',
                'content_type': 'program',
                'card_image_url': 'https://edx.devstack.discovery/'
                                  'media/programs/banner_images/5742ec8d-25ce-43b7-a158-6dad82034ca2.jpg',
            },
            'https://edx.devstack.discovery/media/programs/banner_images/5742ec8d-25ce-43b7-a158-6dad82034ca2.jpg',
        ),
        (
            {
                'title': 'INVALID COURSE',
                'content_type': 'INVALID-CONTENT_TYPE',
            },
            '',
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_image(self, content_metadata_item, expected_thumbnail_url):
        """
        Transforming a image gives back the thumbnail URI by checking the
        content type of the provided `content_metadata_item`.
        """
        exporter = DegreedContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_image(content_metadata_item) == expected_thumbnail_url

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
        exporter = DegreedContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_description(content_metadata_item) == expected_description
