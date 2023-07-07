"""
Tests for SAPSF content metadata exporters.
"""

import unittest

import ddt
import responses
from pytest import mark

from enterprise.constants import IC_DELETE_ACTION
from enterprise.utils import parse_lms_api_datetime
from integrated_channels.sap_success_factors.exporters.content_metadata import SapSuccessFactorsContentMetadataExporter
from integrated_channels.utils import parse_datetime_to_epoch_millis
from test_utils import factories
from test_utils.fake_enterprise_api import EnterpriseMockMixin


@mark.django_db
@ddt.ddt
class TestSapSuccessFactorsContentMetadataExporter(unittest.TestCase, EnterpriseMockMixin):
    """
    Tests for the ``SapSuccessFactorsContentMetadataExporter`` class.
    """

    def setUp(self):
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.config = factories.SAPSuccessFactorsEnterpriseCustomerConfigurationFactory(
            enterprise_customer=self.enterprise_customer
        )

        super().setUp()

    def test_exporter_delete_transform(self):
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        # pylint: disable=protected-access
        transformed_delete_metadata = exporter._transform_item({
            "aggregation_key": "course:NYIF+BOPC.4x",
            "content_type": "course",
            "full_description": "ayylmao",
            "key": 'ayylmao',
            "title": "Brokerage Operations Professional Certificate Examination",
            "course_runs": [
                {
                    "key": "course-v1:NYIF+BOPC.4x+3T2017",
                    "uuid": "69b38e2f-e041-4634-b537-fc8d8e12c87e",
                    "title": "Brokerage Operations Professional Certificate Examination",
                    "short_description": "ayylmao",
                    "availability": "Archived",
                    "pacing_type": "self_paced",
                    "seats": [
                        {
                            "type": "professional",
                            "price": "500.00",
                            "currency": "USD",
                            "upgrade_deadline": None,
                            "upgrade_deadline_override": None,
                            "credit_provider": None,
                            "credit_hours": None,
                            "sku": "0C1BF31",
                            "bulk_sku": "668527E"
                        }
                    ],
                    "start": "2017-09-07T00:00:00Z",
                    # A none value here will cause the sanitization to remove the schedule blob
                    "end": None,
                }
            ],
            "uuid": "bbbf059e-b9fb-4ad7-a53e-4c6f85f47f4e",
            "end_date": "2019-09-07T00:00:00Z",
            "course_ends": "Future",
            "entitlements": [],
            "modified": "2023-07-10T04:29:38.934204Z",
            "additional_information": None,
            "course_run_keys": [
                "course-v1:NYIF+BOPC.4x+3T2017",
                "course-v1:NYIF+BOPC.4x+1T2017"
            ],
            "enrollment_url": "https://foobar.com"
        }, action=IC_DELETE_ACTION)
        assert transformed_delete_metadata['status'] == 'INACTIVE'
        assert transformed_delete_metadata['schedule'] == []

    @ddt.data(
        (
            # advertised course run has price, use it
            {
                "advertised_course_run_uuid": "dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f",
                "course_runs": [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'title': 'edX Demonstration Course',
                        'first_enrollable_paid_seat_price': 100,
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True
                    },
                    {
                        'uuid': '28e2d4c2-a020-4959-b461-6f879bbe1391',
                        'title': 'edX Demonstration Course',
                        'first_enrollable_paid_seat_price': 50,
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True
                    }
                ]
            },
            100,
            True,
        ),
        (
            # advertised course run has no price, fall back to another active course
            {
                "advertised_course_run_uuid": "dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f",
                "course_runs": [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'title': 'edX Demonstration Course',
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True
                    },
                    {
                        'uuid': '28e2d4c2-a020-4959-b461-6f879bbe1391',
                        'title': 'edX Demonstration Course',
                        'first_enrollable_paid_seat_price': 50,
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True
                    }
                ]
            },
            50,
            True,
        ),
        (
            # no advertised course run, use active course run
            {
                "course_runs": [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'title': 'edX Demonstration Course',
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True,
                        'first_enrollable_paid_seat_price': 100
                    }
                ]
            },
            100,
            True
        ),
        (
            # no advertised course run and no active course run, return 0
            {
                'course_runs': [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'title': 'edX Demonstration Course',
                        'status': 'unpublished',
                        'is_enrollable': False,
                        'is_marketable': False,
                        'first_enrollable_paid_seat_price': 100
                    }
                ]
            },
            0.0,
            True
        ),
        (
            # show_course_price false, return 0
            {
                'advertised_course_run_uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                'course_runs': [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'title': 'edX Demonstration Course',
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True,
                        'first_enrollable_paid_seat_price': 100
                    }
                ]
            },
            0.0,
            False
        ),
        (
            # no price data, return 0
            {
                'advertised_course_run_uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                'course_runs': [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'title': 'edX Demonstration Course',
                        'status': 'published',
                        'is_enrollable': True,
                        'is_marketable': True
                    }
                ]
            },
            0.0,
            True
        ),
        (
            # no course run data, return 0
            {'course_runs': []},
            0.0,
            True
        )
    )
    @responses.activate
    @ddt.unpack
    def test_transform_price(self, course_run, expected_price, show_price):
        """
        Transforming a price of a current course run.
        """
        self.config.show_course_price = show_price
        self.config.save()
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_price(course_run) == [
            {
                'currency': 'USD',
                'value': expected_price
            }
        ]

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'English',
            'status': 'published'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'pacing_type': 'self_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'English',
            'status': 'published'
        }
    )
    @responses.activate
    def test_transform_courserun_title_includes_start(self, course_run):
        """
        Transforming a title gives back the title with start date for course
        run of type `instructor-paced` or `self-paced`.
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        expected_title = '{course_run_title} (Starts: {start_date})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y')
        )
        assert exporter.transform_courserun_title(course_run) == \
            [{
                'locale': 'English',
                'value': expected_title
            }]

    @responses.activate
    def test_transform_courserun_title_excludes_start(self):
        """
        Transforming a title gives back just the title if there is not start date.
        """
        course_run = {
            'start': None,
            'pacing_type': 'self_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'en'
        }
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_courserun_title(course_run) == \
            [{
                'locale': 'English',
                'value': course_run['title']
            }]

    @ddt.data(
        (
            {
                'content_type': 'courserun',
                'start': '2013-02-05T05:00:00Z',
                'end': '2013-05-05T05:00:00Z',
            },
            [{
                'startDate': parse_datetime_to_epoch_millis('2013-02-05T05:00:00Z'),
                'endDate': parse_datetime_to_epoch_millis('2013-05-05T05:00:00Z'),
                'active': False,
                'duration': '89 days',
            }]
        ),
        (
            {
                "content_type": "course",
                "key": "CatalystX+IL-BSL.S1x",
                "title": "Cómo Convertirse en un Líder Exitoso (Entrenamiento de Liderazgo Inclusivo)",
                "course_runs": [
                    {
                        "key": "course-v1:CatalystX+IL-BSL.S1x+2T2017",
                        "start": "2017-05-16T16:00:00Z",
                        "end": "2017-06-30T23:59:00Z",
                    },
                    {
                        "key": "course-v1:CatalystX+IL-BSL.S1x+2T2018",
                        "start": "2018-05-16T16:00:00Z",
                        "end": "2018-06-30T23:59:00Z",
                    }
                ],
            },
            [{
                'startDate': parse_datetime_to_epoch_millis('2018-05-16T16:00:00Z'),
                'endDate': parse_datetime_to_epoch_millis('2018-06-30T23:59:00Z'),
                'active': False,
                'duration': '45 days',
            }]
        ),
        (
            {
                "content_type": "course",
                "key": "CatalystX+IL-BSL.S1x",
                "title": "Cómo Convertirse en un Líder Exitoso (Entrenamiento de Liderazgo Inclusivo)",
                "course_runs": [
                    {
                        "key": "course-v1:CatalystX+IL-BSL.S1x+2T2017",
                        "start": "2017-05-16T16:00:00Z",
                        "end": "",
                    }
                ],
            },
            []
        ),
        (
            {},
            []
        )
    )
    @ddt.unpack
    def test_transform_schedule_course_run(self, metadata, expected_schedules):
        """
        Transforming a course run returns an array with one courserun element, for schedule
        or the most recent courserun, if procesing a course
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_schedule(metadata) == expected_schedules

    @ddt.data(
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': None,
            'pacing_type': 'instructor_paced',
            'availability': 'Archived',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': None,
            'availability': 'Archived',
            'pacing_type': 'self_paced',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': None,
            'enrollment_end': '2012-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': 'Current',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
        {
            'start': '2013-02-05T05:00:00Z',
            'enrollment_start': '2014-02-05T05:00:00Z',
            'enrollment_end': '2015-02-05T05:00:00Z',
            'pacing_type': 'instructor_paced',
            'availability': 'Upcoming',
            'title': 'edX Demonstration Course',
            'content_language': 'English'
        },
    )
    @responses.activate
    def test_transform_courserun_title_includes_enrollment_closed(self, course_run):
        """
        Transforming a title gives back the title with start date and
        `enrollment closed` message for course run with availability set to
        `Archived`.
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        expected_title = '{course_run_title} ({start_date} - {enrollment_closed})'.format(
            course_run_title=course_run['title'],
            start_date=parse_lms_api_datetime(course_run['start']).strftime('%B %Y'),
            enrollment_closed='Enrollment Closed'
        )
        assert exporter.transform_courserun_title(course_run) == \
            [{
                'locale': 'English',
                'value': expected_title
            }]

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
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_image(content_metadata_item) == expected_thumbnail_url

    @responses.activate
    def test_transform_launch_points(self):
        """
        Transforming launch points generates list containing a dict that we expect
        """
        content_metadata_item = {
            'enrollment_url': 'http://some/enrollment/url/',
            'aggregation_key': 'course:edX+DemoX',
            'title': 'edX Demonstration Course',
            'key': 'edX+DemoX',
            'content_type': 'course',
            'card_image_url': 'https://edx.devstack.lms:18000/'
                              'asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
            'short_description': 'Some short description.',
            'full_description': 'Detailed description of edx demo course.',
        }
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        launch_points = exporter.transform_launch_points(content_metadata_item)

        assert launch_points[0]['providerID'] == 'EDX'
        assert launch_points[0]['launchURL'] == content_metadata_item['enrollment_url']
        assert launch_points[0]['contentTitle'] == content_metadata_item['title']
        assert launch_points[0]['contentID'] == 'edX+DemoX'
        assert launch_points[0]['launchType'] == 3
        assert launch_points[0]['mobileEnabled'] is True
        assert launch_points[0]['mobileLaunchURL'] == content_metadata_item['enrollment_url']

    @ddt.data(
        (
            # active course
            {
                'title': 'Hippity Hop',
                'course_runs': [
                    {
                        'start': '2014-02-05T05:00:00Z',
                        'end': '2050-12-31T18:00:00Z',
                        'pacing_type': 'instructor_paced',
                        'availability': 'Current',
                        'status': 'published',
                    }
                ],
                'short_description': 'Watch the rabbits roam.',
                'full_description': 'Rabbits explore their new garden home.',
            },
            'Pacing: Instructor-Paced. Starts: February 2014, Ends: December 2050. Rabbits explore their new '
            'garden home.',
        ),
        (
            # enrollment closed, no full description
            {
                'title': 'Happy Bunny Course',
                'course_runs': [
                    {
                        'start': '2115-02-05T05:00:00Z',
                        'end': '2151-12-31T18:00:00Z',
                        'pacing_type': 'self_paced',
                        'availability': 'Archived',
                        'status': 'published'
                    }
                ],
                'short_description': 'The bunnies are delighted.',
            },
            'Pacing: Self-Paced. Starts: February 2115, Ends: December 2151. Enrollment is closed. The bunnies are '
            'delighted.',
        ),
        (
            # archived course, no dates provided
            {
                'title': 'Rabbit Care',
                'course_runs': [
                    {
                        'pacing_type': 'instructor_paced',
                        'availability': 'Archived',
                        'status': 'published',
                    }
                ],
                'full_description': 'In depth discussion of rabbit care and feeding.',
            },
            'Pacing: Instructor-Paced. Enrollment is closed. In depth discussion of rabbit care and feeding.',
        ),
        (
            # no end date provided
            {
                'title': 'Acres of Carrots',
                'course_runs': [
                    {
                        'start': '2216-02-05T05:00:00Z',
                        'pacing_type': 'instructor_paced',
                        'availability': 'Current',
                        'status': 'published'
                    }
                ],
                'short_description': 'Learn to grow this colorful veggie.',
                'full_description': 'Carrots are great. Rabbits love them. Come learn about growing carrots.',
            },
            'Pacing: Instructor-Paced. Starts: February 2216. Carrots are great. Rabbits love them. Come learn about '
            'growing carrots.',
        ),
        (
            # no start date provided
            {
                'title': 'Bunnies are cute',
                'course_runs': [
                    {
                        'end': '2317-02-05T05:00:00Z',
                        'pacing_type': 'instructor_paced',
                        'availability': 'Current',
                        'status': 'published'
                    }
                ],
                'short_description': 'Yep.',
            },
            'Pacing: Instructor-Paced. Ends: February 2317. Yep.',
        ),
        (
            # advertised course run provided
            {
                'title': 'Acres of Carrots',
                'course_runs': [
                    {
                        'uuid': 'dd7bb3e4-56e9-4639-9296-ea9c2fb99c7f',
                        'start': '2019-02-05T05:00:00Z',
                        'end': '2020-02-05T05:00:00Z',
                        'availability': 'Archived',
                        'pacing_type': 'instructor_paced',
                        'status': 'published'
                    },
                    {
                        'uuid': '28e2d4c2-a020-4959-b461-6f879bbe1391',
                        'start': '2017-02-05T05:00:00Z',
                        'availability': 'Current',
                        'pacing_type': 'instructor_paced',
                        'status': 'published'
                    },
                ],
                'short_description': 'Learn to grow this colorful veggie.',
                'full_description': 'Carrots are great. Rabbits love them. Come learn about growing carrots.',
                'advertised_course_run_uuid': '28e2d4c2-a020-4959-b461-6f879bbe1391',
            },
            'Pacing: Instructor-Paced. Starts: February 2017. Carrots are great. Rabbits love them. Come learn about '
            'growing carrots.',
        ),
        (
            {
            },
            '',
        ),
    )
    @responses.activate
    @ddt.unpack
    def test_transform_course_description(self, course, expected_description):
        """
        Transforming a course description includes the pacing and start date.
        """
        exporter = SapSuccessFactorsContentMetadataExporter('fake-user', self.config)
        assert exporter.transform_description(course) == [
            {
                'locale': 'English',
                'value': expected_description
            }
        ]
