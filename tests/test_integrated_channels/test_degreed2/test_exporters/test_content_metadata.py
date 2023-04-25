# -*- coding: utf-8 -*-
"""
Tests for Degreed2 content metadata exporters.
"""

import unittest

import ddt
import responses
from pytest import mark

from integrated_channels.degreed2.exporters.content_metadata import Degreed2ContentMetadataExporter
from test_utils import factories
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
            # full description under length limit
            {
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
                'owners': [
                    {
                        'name': 'edX'
                    }
                ],
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

            '[edX]: 2-4 hours a week for 10 weeks. Detailed description of edx demo course.',
        ),
        (
            # no owners
            {
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
                'owners': [],
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
            # multiple owners
            {
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': 'Detailed description of edx demo course.',
                'owners': [
                    {
                        'name': 'edX'
                    },
                    {
                        'name': 'MIT'
                    }
                ],
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

            '[edX, MIT]: 2-4 hours a week for 10 weeks. Detailed description of edx demo course.',
        ),
        (
            # empty full description
            {
                'title': 'edX Demonstration Course',
                'short_description': 'Some short description.',
                'full_description': '',
                'owners': [
                    {
                        'name': 'edX'
                    }
                ],
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },
            '[edX]: 2-4 hours a week for 10 weeks. Some short description.',
        ),
        (
            # empty full and short description
            {
                'title': 'edX Demonstration Course',
                'short_description': '',
                'full_description': '',
                'owners': [
                    {
                        'name': 'edX'
                    }
                ],
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },
            '[edX]: 2-4 hours a week for 10 weeks. edX Demonstration Course',
        ),
        (
            # empty everything
            {
                'title': '',
                'short_description': '',
                'full_description': '',
                'owners': [
                    {
                        'name': 'edX'
                    }
                ],
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
            # full_description over limit, with tags
            {
                'title': '',
                'short_description': '',
                'full_description': '<p>This description is very long and over the long string limit. This course is '
                                    'part of the '
                                    '<a href=\"../../../../microsoft-professional-program-certficate-data-science\">'
                                    '<em>&#8804;Professional Program Certificate in Data Science</em></a>'
                                    '&nbsp;That doesn&rsquo;t<em> '
                                    'only teach us how to build a cloud data science solution using Microsoft Azure '
                                    'Machine Learning platform'
                                    'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nunc vel blandit est. '
                                    'Sed a justo maximus, hendrerit tortor quis, dictum purus. Morbi rutrum vitae '
                                    'neque at suscipit. Vestibulum sollicitudin porttitor neque sit amet sodales. '
                                    'Integer egestas elit sagittis interdum euismod. Maecenas tincidunt, urna ut '
                                    'vehicula egestas, urna nisl ultricies felis, sed dignissim orci nisl vel turpis. '
                                    'Vivamus efficitur tempus auctor. Nunc mattis, nisi quis gravida vehicula,'
                                    'massa nisi gravida sapien, vitae interdum sapien erat nec eros. Proin augue elit,'
                                    'placerat quis sapien eu, gravida auctor orci. Phasellus et mollis neque, congue'
                                    'tempor ipsum. Morbi dignissim venenatis est. Integer lobortis massa vel aliquet'
                                    'aliquam. Fusce a lectus mi. Vivamus non commodo libero. Sed bibendum commodo ex'
                                    'sodales facilisis. Aliquam ac euismod elit, a fringilla enim. Suspendisse ante'
                                    'erat, malesuada non libero ut, iaculis fermentum nisl. Proin non quam in risus'
                                    'feugiat facilisis. Pellentesque habitant morbi tristique senectus et netus et'
                                    'malesuada fames ac turpis egestas. Nulla ac leo massa. Nulla faucibus diam quis'
                                    'arcu euismod, vel volutpat nulla blandit. In vel consectetur ipsum, in congue'
                                    'nibh. Mauris fringilla commodo justo. Nullam et placerat velit. Sed in commodo'
                                    'sapien. Nam non risus congue, rhoncus neque ac, facilisis tortor. Aenean nulla'
                                    'lacus, pharetra non felis porttitor, scelerisque sagittis magna. Cras tristique,'
                                    'ante a ultricies gravida, purus orci pulvinar nisi, quis fermentum libero metus'
                                    'nec mauris. Praesent lectus lectus, condimentum eget augue nec, volutpat rutrum'
                                    'lacus. Vivamus eget tincidunto',
                'owners': [
                    {
                        'name': 'edX'
                    }
                ],
                'course_runs': [
                    {
                        'start': '2018-02-05T05:00:00Z',
                        'min_effort': 2,
                        'max_effort': 4,
                        'weeks_to_complete': 10
                    }
                ]
            },

            '[edX]: 2-4 hours a week for 10 weeks. '
            'This description is very long and over the long string limit. '
            'This course is part of the Professional Program Certificate in Data ScienceThat doesnt '
            'only teach us how to build a cloud data science solution using Microsoft Azure Machine Learning platform'
            'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nunc vel blandit est. '
            'Sed a justo maximus, hendrerit tortor quis, dictum purus. Morbi rutrum vitae '
            'neque at suscipit. Vestibulum sollicitudin porttitor neque sit amet sodales. '
            'Integer egestas elit sagittis interdum euismod. Maecenas tincidunt, urna ut '
            'vehicula egestas, urna nisl ultricies felis, sed dignissim orci nisl vel turpis. '
            'Vivamus efficitur tempus auctor. Nunc mattis, nisi quis gravida vehicula,'
            'massa nisi gravida sapien, vitae interdum sapien erat nec eros. Proin augue elit,'
            'placerat quis sapien eu, gravida auctor orci. Phasellus et mollis neque, congue'
            'tempor ipsum. Morbi dignissim venenatis est. Integer lobortis massa vel aliquet'
            'aliquam. Fusce a lectus mi. Vivamus non commodo libero. Sed bibendum commodo ex'
            'sodales facilisis. Aliquam ac euismod elit, a fringilla enim. Suspendisse ante'
            'erat, malesuada non libero ut, iaculis fermentum nisl. Proin non quam in risus'
            'feugiat facilisis. Pellentesque habitant morbi tristique senectus et netus et'
            'malesuada fames ac turpis egestas. Nulla ac leo massa. Nulla faucibus diam quis'
            'arcu euismod, vel volutpat nulla blandit. In vel consectetur ipsum, in congue'
            'nibh. Mauris fringilla commodo justo. Nullam et placerat velit. Sed in commodo'
            'sapien. Nam non risus congue, rhoncus neque ac, facilisis tortor. Aenean nulla'
            'lacus, pharetra non felis porttitor, scelerisque sagittis magna. Cras tristique,'
            'ante a ultricies gravida, purus orci pulvinar nisi, quis fermentum libero metus'
            'nec mauris. Praesent lectus lectus, condimentum eget augue nec, volutpat rutrum'
            'lacus. Vivamus eget tinci...'
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

    def test_transform_duration_course(self):
        exporter = Degreed2ContentMetadataExporter('fake-user', self.config)
        content_metadata_item = {
            "aggregation_key": "course:edX+0089786",
            "content_type": "course",
            "full_description": "<p>sdf</p>",
            "key": "edX+0089786",
            "short_description": "<p>ssdf</p>",
            "title": "using exporter to set participation type",
            "course_runs": [
                {
                    "key": "course-v1:edX+0089786+3T2021",
                    "start": "2021-10-01T16:00:00Z",
                    "end": "2022-01-01T17:00:00Z",
                    "uuid": "7d238cc5-88e4-4831-a28e-4193ae4b2618",
                    "min_effort": 2,
                    "max_effort": 4,
                    "weeks_to_complete": 10,
                },
                {
                    "key": "course-v1:edX+0087786+3T2021",
                    "start": "2019-10-01T16:00:00Z",
                    "end": "2022-01-02T17:00:00Z",
                    "uuid": "7d238cc5-88e4-4931-a28e-4193ae4b2618",
                    "min_effort": 2,
                    "max_effort": 4,
                    "weeks_to_complete": 10,
                }
            ],
            "uuid": "3580463a-6f9c-48ed-ae8d-b5a012860d75",
            "advertised_course_run_uuid": "7d238cc5-88e4-4831-a28e-4193ae4b2618",
        }
        assert exporter.transform_duration_type(content_metadata_item) == 'Hours'
        assert exporter.transform_duration(content_metadata_item) == 30

    def test_transform_duration_course_run(self):
        exporter = Degreed2ContentMetadataExporter('fake-user', self.config)
        content_metadata_item = {
            "content_type": "courserun",
            "key": "course-v1:edX+0089786+3T2021",
            "start": "2021-10-01T16:00:00Z",
            "end": "2022-01-01T17:00:00Z",
            "uuid": "7d238cc5-88e4-4831-a28e-4193ae4b2618",
            "min_effort": 2,
            "max_effort": 4,
            "weeks_to_complete": 10,
        }
        assert exporter.transform_duration_type(content_metadata_item) == 'Hours'
        assert exporter.transform_duration(content_metadata_item) == 30

    def test_transform_duration_with_invalid_dates(self):
        """
        want to return 0 instead of fail with missing information
        """
        exporter = Degreed2ContentMetadataExporter('fake-user', self.config)
        content_metadata_item = {
            "content_type": "courserun",
            "key": "course-v1:edX+0089786+3T2021",
            "start": "2021-10-01T16:00:00Z",
            "end": None,
            "uuid": "7d238cc5-88e4-4831-a28e-4193ae4b2618",
            "min_effort": 2,
            "max_effort": 4,
            "weeks_to_complete": None,
        }
        assert exporter.transform_duration(content_metadata_item) == 0

        content_metadata_item = {
            "content_type": "courserun",
            "key": "course-v1:edX+0089786+3T2021",
            "start": "00:00Z",
            "end": None,
            "uuid": "7d238cc5-88e4-4831-a28e-4193ae4b2618",
        }
        assert exporter.transform_duration(content_metadata_item) == 0

        content_metadata_item = {
            "content_type": "courserun",
            "key": "course-v1:edX+0089786+3T2021",
            "start": None,
            "end": "2021-10-01T16:00:00Z",
            "uuid": "7d238cc5-88e4-4831-a28e-4193ae4b2618",
            "min_effort": None,
            "max_effort": 4,
            "weeks_to_complete": 10,
        }
        assert exporter.transform_duration(content_metadata_item) == 0
