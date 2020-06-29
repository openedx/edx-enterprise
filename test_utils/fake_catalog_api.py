# -*- coding: utf-8 -*-
"""
Fake responses for course catalog api.
"""

import copy

import mock
from six.moves import reduce as six_reduce

from test_utils import FAKE_UUIDS

FAKE_COURSE_RUN = {
    'key': 'course-v1:edX+DemoX+Demo_Course',
    'uuid': '785b11f5-fad5-4ce1-9233-e1a3ed31aadb',
    'title': 'edX Demonstration Course',
    'image': {
        'description': None,
        'height': None,
        'src': 'http://edx.devstack.lms:18000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg',
        'width': None
    },
    'short_description': 'This course demonstrates many features of the edX platform.',
    'marketing_url': 'course/demo-course?utm_=test_enterprise&utm_medium=enterprise',
    'seats': [
        {
            'type': 'audit',
            'price': '0.00',
            'currency': 'USD',
            'upgrade_deadline': None,
            'credit_provider': None,
            'credit_hours': None,
            'sku': '68EFFFF'
        },
        {
            'type': 'verified',
            'price': '149.00',
            'currency': 'USD',
            'upgrade_deadline': '2018-08-03T16:44:26.595896Z',
            'credit_provider': None,
            'credit_hours': None,
            'sku': '8CF08E5'
        }
    ],
    'start': '2013-02-05T05:00:00Z',
    'end': '3000-12-31T18:00:00Z',
    'enrollment_start': None,
    'enrollment_end': None,
    'pacing_type': 'instructor_paced',
    'type': 'verified',
    'status': 'published',
    'course': 'edX+DemoX',
    'full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
    'announcement': None,
    'video': None,
    'content_language': None,
    'transcript_languages': [],
    'instructors': [],
    'staff': [
        {
            'uuid': '51df1077-1b8d-4f86-8305-8adbc82b72e9',
            'given_name': 'Anant',
            'family_name': 'Agarwal',
            'bio': "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            'profile_image_url': 'https://www.edx.org/sites/default/files/executive/photo/anant-agarwal.jpg',
            'slug': 'anant-agarwal',
            'position': {
                'title': 'CEO',
                'organization_name': 'edX'
            },
            'profile_image': {},
            'works': [],
            'urls': {
                'twitter': None,
                'facebook': None,
                'blog': None
            },
            'email': None
        }
    ],
    'min_effort': 5,
    'max_effort': 6,
    'weeks_to_complete': 10,
    'modified': '2017-08-18T00:32:33.754662Z',
    'level_type': 'Type 1',
    'availability': 'Current',
    'mobile_available': False,
    'hidden': False,
    'reporting_type': 'mooc',
    'eligible_for_financial_aid': True,
    'content_type': 'courserun',
    'has_enrollable_seats': True
}
FAKE_COURSE_RUN2 = copy.deepcopy(FAKE_COURSE_RUN)
FAKE_COURSE_RUN2['key'] = 'course-v1:edX+DemoX+Demo_Course2'

FAKE_COURSE = {
    'key': 'edX+DemoX',
    'uuid': 'a9e8bb52-0c8d-4579-8496-1a8becb0a79c',
    'title': 'edX Demonstration Course',
    'course_runs': [FAKE_COURSE_RUN],
    'owners': [
        {
            'uuid': '2bd367cf-c58e-400c-ac99-fb175405f7fa',
            'key': 'edX',
            'name': 'edX',
            'certificate_logo_image_url': None,
            'description': '',
            'homepage_url': None,
            'tags': [],
            'logo_image_url': 'https://foo.com/bar.png',
            'marketing_url': None
        }
    ],
    'image': None,
    'short_description': 'This course demonstrates many features of the edX platform.',
    'full_description': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
    'level_type': None,
    'subjects': [],
    'prerequisites': [],
    'expected_learning_items': [
        'XBlocks',
        'Peer Assessment'
    ],
    'video': None,
    'sponsors': [],
    'modified': '2017-08-18T00:23:21.111991Z',
    'marketing_url': None,
    'content_type': 'course',
    'programs': []
}

FAKE_PROGRAM_RESPONSE1 = {
    "uuid": FAKE_UUIDS[2],
    "title": "Program1",
    "subtitle": "",
    "type": "All types",
    "status": "active",
    "marketing_slug": "program1",
    "marketing_url": "all types/program1",
    "banner_image": {},  # skipped
    "courses": [
        {
            "key": "Organization+DNDv2",
            "uuid": "7fe4f68a-abd0-433f-ac9e-1559c12b96e7",
            "title": "Drag and Drop Demos",
            "course_runs": [{"key": "course-v1:Organization+DNDv2+Run1"}],
        },
        {
            "key": "Organization+VD1",
            "uuid": "6d681f1d-856d-4955-8786-a9f3fed6a48f",
            "title": "VectorDraw",
            "course_runs": [{"key": "course-v1:Organization+VD1+Run1"}],
        },
        {
            "key": "Organization+ENT-1",
            "uuid": "7f27580c-f475-413b-851a-529ac90f0bb8",
            "title": "Enterprise Tests",
            "course_runs": [{"key": "course-v1:Organization+ENT-1+Run1"}],
        }
    ],
    "authoring_organizations": [
        {
            "uuid": "12de950c-6fae-49f7-aaa9-778c2fbdae56",
            "key": "edX",
            "name": "",
            "certificate_logo_image_url": None,
            "description": None,
            "homepage_url": None,
            "tags": [],
            "logo_image_url": None,
            "marketing_url": None
        }
    ],
    "card_image_url": "http://wowslider.com/sliders/demo-10/data/images/dock.jpg",
    "is_program_eligible_for_one_click_purchase": False,
    "overview": "This is a test Program.",
    "min_hours_effort_per_week": 5,
    "max_hours_effort_per_week": 10,
    "video": {
        "src": "http://www.youtube.com/watch?v=3_yD_cEKoCk",
        "description": None,
        "image": None
    },
    "expected_learning_items": [],
    "faq": [],
    "credit_backing_organizations": [
        {
            "uuid": "12de950c-6fae-49f7-aaa9-778c2fbdae56",
            "key": "edX",
            "name": "",
            "certificate_logo_image_url": None,
            "description": None,
            "homepage_url": None,
            "tags": [],
            "logo_image_url": None,
            "marketing_url": None
        }
    ],
    "corporate_endorsements": [],
    "job_outlook_items": [],
    "individual_endorsements": [],
    "languages": [
        "en-us"
    ],
    "transcript_languages": [
        "en-us"
    ],
    "subjects": [],
    "price_ranges": [],
    "staff": [],
    "credit_redemption_overview": "This is a test Program.",
    "applicable_seat_types": [
        "audit"
    ],
}

FAKE_PROGRAM_RESPONSE2 = {
    "uuid": "40732b09-2345-6789-10bc-9e03f9304cdc",
    "title": "Program2",
    "subtitle": "",
    "type": "Prof only",
    "status": "active",
    "marketing_slug": "program2",
    "marketing_url": "prof only/program2",
    "banner_image": {},  # skipped
    "courses": [
        {
            "key": "Organization+VD1",
            "uuid": "6d681f1d-856d-4955-8786-a9f3fed6a48f",
            "title": "VectorDraw",
            "course_runs": [
                {
                    "key": "course-v1:Organization+VD1+VD1",
                    "uuid": "5b949fc1-aa05-42b0-8c9f-8e6114848ae9",
                    "title": "VectorDraw",
                    "image": {},  # skipped
                    "short_description": None,
                    "marketing_url": None,
                    "start": "2030-01-01T00:00:00Z",
                }
            ],
        },
        {
            "key": "Organization+ENT-1",
            "uuid": "7f27580c-f475-413b-851a-529ac90f0bb8",
            "title": "Enterprise Tests",
            "course_runs": [
                {
                    "key": "course-v1:Organization+ENT-1+T1",
                    "uuid": "a2128a84-6e20-4fce-958e-80d9461ef835",
                    "title": "Enterprise Tests",
                    "image": {},  # skipped
                    "short_description": "",
                    "marketing_url": None
                }
            ],
        }
    ],
}

FAKE_PROGRAM_RESPONSE3 = {
    "uuid": "52ad909b-c57d-4ff1-bab3-999813a2479b",
    "title": "Program Title 1",
    "subtitle": "Program Subtitle 1",
    "type": "Professional Certificate",
    "status": "active",
    "marketing_slug": "marketingslug1",
    "marketing_url": "verified-certificate/marketingslug1",
    "courses": [
        {
            "key": 'course-v1:edX+DemoX+Demo_Course',
            "uuid": "a312ec52-74ef-434b-b848-f110eb90b672",
            "title": "edX Demonstration Course",
            "course_runs": [
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course',
                    "uuid": "a276c25f-c640-4943-98dd-6c9ad8c71bb9",
                    "title": "edX Demonstration Course",
                    "short_description": "",
                    "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                    "seats": [],
                    "start": "2016-01-01T00:00:00Z",
                    "end": "2018-01-01T00:00:00Z",
                    "enrollment_start": None,
                    "enrollment_end": None,
                    "pacing_type": "self_paced",
                    "type": None,
                    "status": "published",
                },
            ],
        },
        {
            "key": 'course-v1:edX+DemoX+Demo_Course2',
            "uuid": "b312ec52-74ef-434b-b848-f110eb90b672",
            "title": "edX Demonstration Course 2",
            "course_runs": [
                {
                    "key": 'course-v1:edX+DemoX+Demo_Course2',
                    "uuid": "b276c25f-c640-4943-98dd-6c9ad8c71bb9",
                    "title": "edX Demonstration Course 2",
                    "short_description": "",
                    "marketing_url": "course/edxdemo?utm_medium=affiliate_partner&utm_source=staff",
                    "seats": [],
                    "start": "2016-01-01T00:00:00Z",
                    "end": "2018-01-01T00:00:00Z",
                    "enrollment_start": None,
                    "enrollment_end": None,
                    "pacing_type": "self_paced",
                    "type": None,
                    "status": "published",
                },
            ],
        },
    ],
    "authoring_organizations": [
        {
            "uuid": "12de950c-6fae-49f7-aaa9-778c2fbdae56",
            "key": "edX",
            "name": "Authoring Organization",
            "certificate_logo_image_url": 'awesome/certificate/logo/url.jpg',
            "description": 'Such author, much authoring',
            "homepage_url": 'homepage.com/url',
            "logo_image_url": 'images/logo_image_url.jpg',
            "marketing_url": 'marketing/url',
        },
    ],
    "expected_learning_items": [
        "Blocks",
        "XBlocks",
        "Peer Assessment"
    ],
    'corporate_endorsements': [
        {
            "corporation_name": "Bob's Company",
            "statement": "",
            "image": {
                "src": "http://evonexus.org/wp-content/uploads/2016/01/IBM-logo-1024x576.jpg",
                "description": None,
                "height": None,
                "width": None,
            },
            "individual_endorsements": [
                {
                    "endorser": {
                        "uuid": "789aa881-e44b-4675-9377-fa103c12bbfc",
                        "given_name": "Bob",
                        "family_name": "the Builder",
                        "bio": "Working hard on a daily basis!",
                        "profile_image_url": None,
                        "slug": "bob-the-builder",
                        "position": {
                            "title": "Engineer",
                            "organization_name": "Bob's Company",
                            "organization_id": 1
                        },
                        "profile_image": {},
                        "works": [],
                        "urls": {
                            "facebook": None,
                            "twitter": None,
                            "blog": None,
                        },
                        "email": None
                    },
                    "quote": "Life is hard for us engineers. Period."
                }
            ]
        }
    ],
    "is_program_eligible_for_one_click_purchase": True,
    "overview": "This is a test Program.",
    "weeks_to_complete_min": 4,
    "weeks_to_complete_max": 6,
    "min_hours_effort_per_week": 5,
    "max_hours_effort_per_week": 10,
    "applicable_seat_types": [
        "verified",
        "professional",
        "credit",
    ],
}

FAKE_PROGRAM_TYPE = {
    "name": "Professional Certificate",
    "logo_image": {
        "small": {
            "height": 64,
            "width": 64,
            "url": "http://localhost:18381/media/media/program_types/logo_images/professional-certificate.small.png"
        },
        "medium": {
            "height": 128,
            "width": 128,
            "url": "http://localhost:18381/media/media/program_types/logo_images/professional-certificate.medium.png"
        },
        "large": {
            "height": 256,
            "width": 256,
            "url": "http://localhost:18381/media/media/program_types/logo_images/professional-certificate.large.png"
        },
        "x-small": {
            "height": 32,
            "width": 32,
            "url": "http://localhost:18381/media/media/program_types/logo_images/professional-certificate.x-small.png"
        }
    },
    "applicable_seat_types": [
        "verified",
        "professional",
        "credit"
    ],
    "slug": "professional-certificate"
}

FAKE_COURSE_RUNS_RESPONSE = [
    {
        "key": "course-v1:edX+DemoX+Demo_Course",
        "uuid": "9f9093b0-58e9-480c-a619-5af5000507bb",
        "title": "edX Demonstration Course",
        "course": "edX+DemoX",
        "start": "2013-02-05T05:00:00Z",
        "end": None,
        "seats": [
            {
                "type": "professional",
                "price": "1000.00",
                "currency": "EUR",
                "upgrade_deadline": "2018-01-13T11:19:02Z",
                "credit_provider": "",
                "credit_hours": None
            },
            {
                "type": "audit",
                "price": "0.00",
                "currency": "USD",
                "upgrade_deadline": None,
                "credit_provider": "",
                "credit_hours": None
            }
        ],
        "programs": []
    },
    {
        "key": "course-v1:Organization+DNDv2+T1",
        "uuid": "076cb917-06d6-4713-8a6c-c1712ce2e421",
        "title": "Drag and Drop Demos",
        "course": "Organization+DNDv2",
        "start": "2015-01-01T00:00:00Z",
        "end": None,
        "video": None,
        "seats": [],
        "programs": [
            {
                "uuid": "40782a06-1c37-4779-86aa-0a081f014d4d",
                "title": "Program1",
                "type": "Prof only",
                "marketing_slug": "program1",
                "marketing_url": "prof only/program1"
            }
        ]
    },
    {
        "key": "course-v1:Organization+ENT-1+T1",
        "uuid": "a2128a84-6e20-4fce-958e-80d9461ef835",
        "title": "Enterprise Tests",
        "course": "course-v1:Organization+ENT-1+T1",
        "start": None,
        "end": None,
        "seats": [
            {
                "type": "professional",
                "price": "0.00",
                "currency": "AZN",
                "upgrade_deadline": None,
                "credit_provider": "",
                "credit_hours": None
            },
            {
                "type": "audit",
                "price": "0.00",
                "currency": "AED",
                "upgrade_deadline": None,
                "credit_provider": "",
                "credit_hours": None
            }
        ],
        "programs": [
            {
                "uuid": "40782a06-1c37-4779-86aa-0a081f014d4d",
                "title": "Program1",
                "type": "Prof only",
                "marketing_slug": "program1",
                "marketing_url": "prof only/program1"
            }
        ]
    },
    {
        "key": "course-v1:Organization+VD1+VD1",
        "uuid": "5b949fc1-aa05-42b0-8c9f-8e6114848ae9",
        "title": "VectorDraw",
        "course": "Organization+VD1",
        "start": "2030-01-01T00:00:00Z",
        "end": None,
        "seats": [
            {
                "type": "professional",
                "price": "12.00",
                "currency": "BOB",
                "upgrade_deadline": None,
                "credit_provider": "",
                "credit_hours": None
            }
        ],
        "programs": [
            {
                "uuid": "40782a06-1c37-4779-86aa-0a081f014d4d",
                "title": "Program1",
                "type": "Prof only",
                "marketing_slug": "program1",
                "marketing_url": "prof only/program1"
            }
        ]
    }
]

FAKE_PROGRAM_RESPONSES = {
    FAKE_PROGRAM_RESPONSE1["uuid"]: FAKE_PROGRAM_RESPONSE1,
    FAKE_PROGRAM_RESPONSE2["uuid"]: FAKE_PROGRAM_RESPONSE2,
}

FAKE_CATALOG_COURSES_RESPONSE = {
    1: [
        {
            "key": "edX+DemoX",
            "uuid": "cf8f5cce-1370-46aa-8162-31fdff55dc7e",
            "title": "Fancy Course",
            "course_runs": [],
            "owners": [
                {
                    "uuid": "366e7739-fb3a-42d0-8351-8c3dbab3e339",
                    "key": "edX",
                    "name": "",
                    "certificate_logo_image_url": None,
                    "description": None,
                    "homepage_url": None,
                    "tags": [],
                    "logo_image_url": None,
                    "marketing_url": None
                }
            ],
            "image": None,
            "short_description": None,
            "full_description": None,
            "level_type": None,
            "subjects": [],
            "prerequisites": [],
            "expected_learning_items": [],
            "video": None,
            "sponsors": [],
            "modified": "2017-01-16T14:07:47.327605Z",
            "marketing_url": "http://lms.example.com/course/edxdemox?utm_source=admin&utm_medium=affiliate_partner"
        },
        {
            "key": "foobar+fb1",
            "uuid": "c08c1e43-307c-444b-acc7-aea4a7b9f8f6",
            "title": "FooBar Ventures",
            "course_runs": [],
            "owners": [
                {
                    "uuid": "8d920bc3-a1b2-44db-9380-1d3ca728c275",
                    "key": "foobar",
                    "name": "",
                    "certificate_logo_image_url": None,
                    "description": None,
                    "homepage_url": None,
                    "tags": [],
                    "logo_image_url": None,
                    "marketing_url": None
                }
            ],
            "image": {
                "src": "",
                "height": None,
                "width": None,
                "description": None
            },
            "short_description": "",
            "full_description": "This is a really cool course.",
            "level_type": None,
            "subjects": [],
            "prerequisites": [],
            "expected_learning_items": [],
            "video": None,
            "sponsors": [],
            "modified": "2017-03-07T18:37:45.238722Z",
            "marketing_url": "http://lms.example.com/course/foobarfb1?utm_source=admin&utm_medium=affiliate_partner"
        },
        {
            "key": "test+course3",
            "uuid": "c08c1e43-307c-444b-acc7-aea4a7b9f8f7",
            "title": "Test Course for unexpected data",
            "course_runs": [],
            "owners": [
                {
                    "uuid": "8d920bc3-a1b2-44db-9380-1d3ca728c275",
                    "key": "foobar",
                    "name": "",
                    "certificate_logo_image_url": None,
                    "description": None,
                    "homepage_url": None,
                    "tags": [],
                    "logo_image_url": None,
                    "marketing_url": None
                }
            ],
            "image": None,
            "short_description": "",
            "full_description": "This is a really cool course.",
            "level_type": None,
            "subjects": [],
            "prerequisites": [],
            "expected_learning_items": [],
            "video": None,
            "sponsors": [],
            "modified": "2017-03-07T18:37:45.238722Z",
            "marketing_url": "http://lms.example.com/course/testcourse3?utm_source=admin&utm_medium=affiliate_partner"
        },
    ]
}

FAKE_CATALOG_COURSE_DETAILS_RESPONSES = {
    'edX+DemoX': {
        "key": "edX+DemoX",
        "uuid": "cf8f5cce-1370-46aa-8162-31fdff55dc7e",
        "title": "Fancy Course",
        "course_runs": [
            {
                "key": "course-v1:edX+DemoX+Demo_Course",
                "uuid": "0a25b789-86d0-43bd-972b-3858a985462e",
                "title": "edX Demonstration Course",
                "image": {
                    "src": (
                        "http://192.168.1.187:8000/asset-v1:edX+DemoX+Demo_"
                        "Course+type@asset+block@images_course_image.jpg"
                    ),
                    "height": None,
                    "width": None,
                    "description": None
                },
                "short_description": None,
                "marketing_url": None,
                "start": "2013-02-05T05:00:00Z",
                "end": None,
                "enrollment_start": None,
                "enrollment_end": None,
                "pacing_type": "instructor_paced",
                "type": "audit",
                "course": "edX+DemoX",
                "full_description": None,
                "announcement": None,
                "video": None,
                "seats": [
                    {
                        "type": "audit",
                        "price": "0.00",
                        "currency": "USD",
                        "upgrade_deadline": None,
                        "credit_provider": "",
                        "credit_hours": None,
                        "sku": ""
                    }
                ],
                "content_language": 'en-us',
                "transcript_languages": [],
                "instructors": [],
                "staff": [],
                "min_effort": None,
                "max_effort": None,
                "modified": "2017-03-07T18:37:43.992494Z",
                "level_type": None,
                "availability": "Upcoming",
                "mobile_available": False,
                "hidden": False,
                "reporting_type": "mooc"
            },
        ],
        "owners": [
            {
                "uuid": "366e7739-fb3a-42d0-8351-8c3dbab3e339",
                "key": "edX",
                "name": "",
                "certificate_logo_image_url": None,
                "description": None,
                "homepage_url": None,
                "tags": [],
                "logo_image_url": None,
                "marketing_url": None
            }
        ],
        "image": None,
        "short_description": None,
        "full_description": None,
        "level_type": None,
        "subjects": [],
        "prerequisites": [],
        "expected_learning_items": [],
        "video": None,
        "sponsors": [],
        "modified": "2017-01-16T14:07:47.327605Z",
        "marketing_url": "http://lms.example.com/course/edxdemox?utm_source=admin&utm_medium=affiliate_partner",
        "programs": [
            {
                "uuid": "643b89e6-04bc-4367-b292-9d3991d86b8e",
                "title": "My Cool Program",
                "type": "SuperAwesome",
                "marketing_slug": "coolstuff",
                "marketing_url": "http://lms.example.com/coolstuff"
            }
        ]
    },
    'foobar+fb1': {
        "key": "foobar+fb1",
        "uuid": "c08c1e43-307c-444b-acc7-aea4a7b9f8f6",
        "title": "FooBar Ventures",
        "course_runs": [
            {
                "key": "course-v1:foobar+fb1+fbv1",
                "uuid": "3550853f-e65a-492e-8781-d0eaa16dd538",
                "title": "Other Course Name",
                "image": {
                    "src": (
                        "http://192.168.1.187:8000/asset-v1:foobar+fb1+fbv1"
                        "+type@asset+block@images_course_image.jpg"
                    ),
                    "height": None,
                    "width": None,
                    "description": None
                },
                "short_description": "",
                "marketing_url": None,
                "start": "2015-01-01T00:00:00Z",
                "end": None,
                "enrollment_start": None,
                "enrollment_end": None,
                "pacing_type": "instructor_paced",
                "type": None,
                "course": "foobar+fb1",
                "full_description": "This is a really cool course. Like, we promise.",
                "announcement": None,
                "video": None,
                "seats": [],
                "content_language": None,
                "transcript_languages": [],
                "instructors": [],
                "staff": [],
                "min_effort": None,
                "max_effort": None,
                "modified": "2017-03-07T18:37:45.082681Z",
                "level_type": None,
                "availability": "Upcoming",
                "mobile_available": False,
                "hidden": False,
                "reporting_type": "mooc"
            }
        ],
        "owners": [
            {
                "uuid": "8d920bc3-a1b2-44db-9380-1d3ca728c275",
                "key": "foobar",
                "name": "",
                "certificate_logo_image_url": None,
                "description": None,
                "homepage_url": None,
                "tags": [],
                "logo_image_url": None,
                "marketing_url": None
            }
        ],
        "image": {
            "src": "",
            "height": None,
            "width": None,
            "description": None
        },
        "short_description": "",
        "full_description": "This is a really cool course.",
        "level_type": None,
        "subjects": [],
        "prerequisites": [],
        "expected_learning_items": [],
        "video": None,
        "sponsors": [],
        "modified": "2017-03-07T18:37:45.238722Z",
        "marketing_url": "http://lms.example.com/course/foobarfb1?utm_source=admin&utm_medium=affiliate_partner",
        "programs": []
    },
    'test+course3': {
        "key": "test+course3",
        "uuid": "c08c1e43-307c-444b-acc7-aea4a7b9f8f6",
        "title": "Test Course with unexpected data",
        "course_runs": [
            {
                "key": "course-v1:test+course3+fbv1",
                "uuid": "3550853f-e65a-492e-8781-d0eaa16dd538",
                "title": "Other Course Name",
                "image": None,
                "short_description": "",
                "marketing_url": None,
                "start": "2015-01-01T00:00:00Z",
                "end": None,
                "enrollment_start": None,
                "enrollment_end": None,
                "pacing_type": "instructor_paced",
                "type": None,
                "course": "foobar+fb1",
                "full_description": "This is a really cool course. Like, we promise.",
                "announcement": None,
                "video": None,
                "seats": [],
                "content_language": None,
                "transcript_languages": [],
                "instructors": [],
                "staff": [],
                "min_effort": None,
                "max_effort": None,
                "modified": "2017-03-07T18:37:45.082681Z",
                "level_type": None,
                "availability": "Upcoming",
                "mobile_available": False,
                "hidden": False,
                "reporting_type": "mooc"
            }
        ],
        "owners": [
            {
                "uuid": "8d920bc3-a1b2-44db-9380-1d3ca728c275",
                "key": "foobar",
                "name": "",
                "certificate_logo_image_url": None,
                "description": None,
                "homepage_url": None,
                "tags": [],
                "logo_image_url": None,
                "marketing_url": None
            }
        ],
        "image": None,
        "short_description": "",
        "full_description": "This is a really cool course.",
        "level_type": None,
        "subjects": [],
        "prerequisites": [],
        "expected_learning_items": [],
        "video": None,
        "sponsors": [],
        "modified": "2017-03-07T18:37:45.238722Z",
        "marketing_url": "http://lms.example.com/course/test+course3?utm_source=admin&utm_medium=affiliate_partner",
        "programs": []
    }
}

FAKE_CATALOG_COURSE_PAGINATED_RESPONSE = {
    'count': 3,
    'next': 'http://testserver/api/v1/catalogs/1/courses?page=3',
    'previous': 'http://testserver/api/v1/catalogs/1/courses?page=1',
    'results': [
        {
            'owners': [
                {
                    'description': None,
                    'tags': [],
                    'name': '',
                    'homepage_url': None,
                    'key': 'edX',
                    'certificate_logo_image_url': None,
                    'marketing_url': None,
                    'logo_image_url': None,
                    'uuid': FAKE_UUIDS[1]
                }
            ],
            'uuid': FAKE_UUIDS[2],
            'title': 'edX Demonstration Course',
            'prerequisites': [],
            'image': None,
            'expected_learning_items': [],
            'sponsors': [],
            'modified': '2017-03-03T07:34:19.322916Z',
            'full_description': None,
            'subjects': [],
            'video': None,
            'key': 'edX+DemoX',
            'short_description': None,
            'marketing_url': None,
            'level_type': None,
            'course_runs': []
        }
    ]
}

FAKE_SEARCH_ALL_COURSE_RESULT = {
    "title": "edX Demonstration Course",
    "min_effort": None,
    "marketing_url": "course/course-v1:edX+DemoX+Demo_Course/about",
    "image_url": "https://business.sandbox.edx.org/asset-v1:edX+DemoX+Demo_Course+type"
                 "@asset+block@images_course_image.jpg",
    "pacing_type": "instructor_paced",
    "short_description": None,
    "subject_uuids": [],
    "transcript_languages": [],
    "course_runs": [],
    "full_description": None,
    "seat_types": [
        "audit",
        "verified"
    ],
    "mobile_available": False,
    "end": None,
    "partner": "edx",
    "max_effort": None,
    "start": "2013-02-05T05:00:00",
    "weeks_to_complete": None,
    "published": True,
    "content_type": "courserun",
    "has_enrollable_seats": True,
    "authoring_organization_uuids": [
        "12de950c-6fae-49f7-aaa9-778c2fbdae56"
    ],
    "enrollment_start": None,
    "staff_uuids": [],
    "language": None,
    "number": "DemoX",
    "type": "verified",
    "key": "course-v1:edX+DemoX+Demo_Course",
    "org": "edX",
    "level_type": None,
    "program_types": [],
    "aggregation_key": "courserun:edX+DemoX",
    "logo_image_urls": [
        None
    ],
    "enrollment_end": None,
    "availability": "Upcoming"
}

FAKE_SEARCH_ALL_SHORT_COURSE_RESULT = {
    "title": "edX Demonstration Course",
    "full_description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
    "key": "edX+DemoX",
    "short_description": None,
    "aggregation_key": "course:edX+DemoX",
    "content_type": "course",
    "course_runs": [],
}

FAKE_SEARCH_ALL_SHORT_COURSE_RESULT_LIST = [
    {
        "title": "edX Demonstration Course 2",
        "full_description": None,
        "key": "edX+DemoX+2",
        "short_description": None,
        "aggregation_key": "course:edX+DemoX",
        "content_type": "course",
        "course_runs": [],
    },
    {
        "title": "edX Demonstration Course 3",
        "full_description": None,
        "key": "edX+DemoX+3",
        "short_description": None,
        "aggregation_key": "course:edX+DemoX",
        "content_type": "course",
        "course_runs": [],
    },
]

FAKE_SEARCH_ALL_PROGRAM_RESULT_1 = {
    "title": "Program Title 1",
    "marketing_url": "professional-certificate/marketingslug1",
    "content_type": "program",
    "card_image_url": "http://wowslider.com/sliders/demo-10/data/images/dock.jpg",
    "min_hours_effort_per_week": 5,
    "authoring_organization_uuids": [
        "12de950c-6fae-49f7-aaa9-778c2fbdae56"
    ],
    "hidden": False,
    "authoring_organizations": [
        {
            "marketing_url": None,
            "homepage_url": None,
            "tags": [],
            "certificate_logo_image_url": None,
            "name": "",
            "key": "edX",
            "description": None,
            "uuid": "12de950c-6fae-49f7-aaa9-778c2fbdae56",
            "logo_image_url": None
        }
    ],
    "staff_uuids": [],
    "published": True,
    "uuid": FAKE_UUIDS[3],
    "max_hours_effort_per_week": 10,
    "subject_uuids": [],
    "weeks_to_complete_min": None,
    "type": "Professional Certificate",
    "language": [
        "English"
    ],
    "partner": "edx",
    "subtitle": "Program Subtitle 1",
    "status": "active",
    "weeks_to_complete_max": None,
    "aggregation_key": "program:" + FAKE_UUIDS[3],
    "is_program_eligible_for_one_click_purchase": True
}

FAKE_SEARCH_ALL_PROGRAM_RESULT_2 = {
    "title": "Program Title 2",
    "marketing_url": "professional-certificate/marketingslug2",
    "content_type": "program",
    "card_image_url": "http://wowslider.com/sliders/demo-10/data/images/dock.jpg",
    "min_hours_effort_per_week": 5,
    "authoring_organization_uuids": [
        "12de950c-6fae-49f7-aaa9-778c2fbdae56"
    ],
    "hidden": False,
    "authoring_organizations": [
        {
            "marketing_url": None,
            "homepage_url": None,
            "tags": [],
            "certificate_logo_image_url": None,
            "name": "",
            "key": "edX",
            "description": None,
            "uuid": "12de950c-6fae-49f7-aaa9-778c2fbdae56",
            "logo_image_url": None
        }
    ],
    "staff_uuids": [],
    "published": True,
    "uuid": FAKE_UUIDS[2],
    "max_hours_effort_per_week": 10,
    "subject_uuids": [],
    "weeks_to_complete_min": None,
    "type": "Professional Certificate",
    "language": [
        "English"
    ],
    "partner": "edx",
    "subtitle": "Program Subtitle 1",
    "status": "active",
    "weeks_to_complete_max": None,
    "aggregation_key": "program:" + FAKE_UUIDS[3],
    "is_program_eligible_for_one_click_purchase": True
}

FAKE_SEARCH_ALL_RESULTS = {
    "count": 3,
    "next": None,
    "previous": None,
    "results": [
        FAKE_SEARCH_ALL_COURSE_RESULT,
        FAKE_SEARCH_ALL_SHORT_COURSE_RESULT,
        FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
    ]
}

FAKE_SEARCH_ALL_RESULTS_2 = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        FAKE_SEARCH_ALL_COURSE_RESULT,
        FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
    ]
}

FAKE_SEARCH_ALL_COURSE_RESULT_1 = copy.deepcopy(FAKE_SEARCH_ALL_COURSE_RESULT)
FAKE_SEARCH_ALL_COURSE_RESULT_1['marketing_url'] = None
FAKE_SEARCH_ALL_COURSE_RESULT_1['key'] = "course-v1:test+test+DemoX+Demo_Course"
FAKE_SEARCH_ALL_RESULTS_3 = {
    "count": 3,
    "next": None,
    "previous": None,
    "results": [
        FAKE_SEARCH_ALL_COURSE_RESULT_1,
        FAKE_SEARCH_ALL_SHORT_COURSE_RESULT,
        FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
    ]
}

FAKE_SEARCH_ALL_RESULTS_WITH_PAGINATION = {
    "count": 2,
    "next": "https://fake.server/api/v1/?page=1",
    "previous": "https://fake.server/api/v1/?page=2",
    "results": [
        FAKE_SEARCH_ALL_COURSE_RESULT,
        FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
    ]
}

FAKE_SEARCH_ALL_COURSE_RESULT_2 = copy.deepcopy(FAKE_SEARCH_ALL_COURSE_RESULT)
FAKE_SEARCH_ALL_COURSE_RESULT_2['has_enrollable_seats'] = False
FAKE_SEARCH_ALL_COURSE_RESULT_2["key"] = "course-v1:test+DemoX+Demo_Course"
FAKE_SEARCH_ALL_PROGRAM_RESULT_3 = copy.deepcopy(FAKE_SEARCH_ALL_PROGRAM_RESULT_2)
FAKE_SEARCH_ALL_PROGRAM_RESULT_3['is_program_eligible_for_one_click_purchase'] = False
FAKE_SEARCH_ALL_PROGRAM_RESULT_3['uuid'] = FAKE_UUIDS[1]

FAKE_SEARCH_ALL_RESULTS_WITH_PAGINATION_1 = {
    "count": 5,
    "next": "https://fake.server/api/v1/?page=1",
    "previous": "https://fake.server/api/v1/?page=4",
    "results": [
        FAKE_SEARCH_ALL_COURSE_RESULT_1,
        FAKE_SEARCH_ALL_COURSE_RESULT_2,
        FAKE_SEARCH_ALL_SHORT_COURSE_RESULT,
        FAKE_SEARCH_ALL_PROGRAM_RESULT_1,
        FAKE_SEARCH_ALL_PROGRAM_RESULT_3,
    ]
}

FAKE_SEARCH_ALL_COURSE_RESULT_3 = {
    "content_type": "course",
    "full_description": "This is full description of course",
    "aggregation_key": "course:edX+DemoX",
    "key": "edX+DemoX",
    "short_description": "This is short description of course",
    "title": "edX Demonstration Course",
    "card_image_url": "http://local:18000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg",
    "subjects": [],
    "organizations": [
        "edX: "
    ],
    "uuid": "4424529e-23aa-489b-b25a-800f52e05b66",
    "languages": [],
    "course_runs": [
        {
            "enrollment_end": None,
            "enrollment_mode": "verified",
            "key": "course-v1:edX+DemoX+Demo_Course",
            "enrollment_start": None,
            "pacing_type": "instructor_paced",
            "end": None,
            "start": "2013-02-05T05:00:00Z",
            "go_live_date": None,
            "availability": "Current"
        }
    ],
}


def get_catalog_courses(catalog_id):
    """
    Fake implementation returning catalog courses by ID.

    Arguments:
        catalog_id (int): Catalog ID

    Returns:
        list: Details of the courses included in the catalog
    """
    return FAKE_CATALOG_COURSES_RESPONSE.get(catalog_id, [])


def get_course_details(course_key):
    """
    Fake implementation returning course details by key.

    Arguments:
        course_key (str): The course key of the course; not the unique-per-run key.

    Returns:
        dict: Details of the course.
    """
    return FAKE_CATALOG_COURSE_DETAILS_RESPONSES.get(course_key, {}).copy()


def get_program_by_uuid(program_uuid):
    """
    Fake implementation returning program by UUID.

    Arguments:
        program_uuid(string): Program UUID in string form

    Returns:
        dict: Program data provided by Course Catalog API
    """
    return FAKE_PROGRAM_RESPONSES.get(program_uuid).copy()


def get_program_by_title(program_title):
    """
    Fake implementation returning program by title.

    Arguments:
        program_title(str): Program title as seen by students and in Course Catalog Admin

    Returns:
        dict: Program data provided by Course Catalog API
    """
    try:
        return next(response for response in FAKE_PROGRAM_RESPONSES.values() if response["title"] == program_title)
    except StopIteration:
        return None


def get_common_course_modes(course_runs):
    """
    Fake implementation returning common course modes.

    Arguments:
        course_run_ids(Iterable[str]): Target Course run IDs.

    Returns:
        set: course modes found in all given course runs
    """
    course_run_modes = [
        set(seat.get("type") for seat in course_run.get("seats"))
        for course_run in FAKE_COURSE_RUNS_RESPONSE
        if course_run.get("key") in course_runs
    ]

    return six_reduce(lambda left, right: left & right, course_run_modes)


def setup_course_catalog_api_client_mock(
        client_mock,
        course_overrides=None,
        course_run_overrides=None,
        program_overrides=None,
        program_type_overrides=None,
):
    """
    Set up the Course Catalog API client mock.

    Args:
    ----
        client_mock (Mock): The mock course catalog api client.
        course_overrides (dict): Dictionary containing overrides of the fake course metadata values.
        course_run_overrides (dict): Dictionary containing overrides of the fake course run metadata values.
        program_overrides (dict): Dictionary containing overrides of the fake program metadata values.
        program_type_overrides (dict): Dictionary containing overrides of the fake program type metadata values.
    """
    client = client_mock.return_value

    fake_course = FAKE_COURSE.copy()
    fake_course_run = FAKE_COURSE_RUN.copy()
    fake_program = FAKE_PROGRAM_RESPONSE3.copy()
    fake_program_type = FAKE_PROGRAM_TYPE.copy()
    fake_search_all_course_result = FAKE_SEARCH_ALL_COURSE_RESULT.copy()

    # Apply overrides to default fake course catalog metadata.
    if course_overrides:
        fake_course.update(course_overrides)
    if course_run_overrides:
        fake_course_run.update(course_run_overrides)
    if program_overrides:
        fake_program.update(program_overrides)
    if program_type_overrides:
        fake_program_type.update(program_type_overrides)

    # Mock course catalog api functions.
    client.get_course_details.return_value = fake_course
    client.get_course_run.return_value = fake_course_run
    client.get_course_id.return_value = fake_course['key']
    client.get_course_and_course_run.return_value = (fake_course, fake_course_run)
    client.get_program_course_keys.return_value = [course['key'] for course in fake_program['courses']]
    client.get_program_by_uuid.return_value = fake_program
    client.get_program_type_by_slug.return_value = fake_program_type
    client.get_catalog_results.return_value = {'results': [fake_search_all_course_result]}


def create_course_run_dict(start="2014-10-14T13:11:03Z", end="3000-10-13T13:11:01Z",
                           enrollment_start="2014-10-13T13:11:03Z",
                           enrollment_end="2999-10-13T13:11:04Z",
                           upgrade_deadline="3000-10-13T13:11:04Z",
                           availability='Starting Soon',
                           weeks_to_complete=1):
    """
    Return enrollable and upgradeable course run dict.
    """
    return {
        "start": start,
        "end": end,
        "enrollment_start": enrollment_start,
        "enrollment_end": enrollment_end,
        "seats": [{"type": "verified", "upgrade_deadline": upgrade_deadline}],
        "availability": availability,
        "weeks_to_complete": weeks_to_complete
    }


class CourseDiscoveryApiTestMixin:
    """
    Mixin for course discovery API test classes.
    """

    CATALOG_API_PATCH_PREFIX = "enterprise.api_client.discovery"

    def _make_catalog_api_location(self, catalog_api_member):
        """
        Return path for `catalog_api_member` to mock.
        """
        return "{}.{}".format(self.CATALOG_API_PATCH_PREFIX, catalog_api_member)

    def _make_patch(self, patch_location, new=None):
        """
        Patch `patch_location`, register the patch to stop at test cleanup and return mock object.
        """
        patch_mock = new if new is not None else mock.Mock()
        patcher = mock.patch(patch_location, patch_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        return patch_mock

    @staticmethod
    def _get_important_parameters(get_data_mock):
        """
        Return important (i.e. varying) parameters to get_edx_api_data.
        """
        args, kwargs = get_data_mock.call_args

        # This test is to make sure that all calls to get_edx_api_data are made using kwargs
        # and there is no positional argument. This is required as changes in get_edx_api_data's
        # signature are breaking edx-enterprise and using kwargs would reduce that.
        assert args == ()

        return kwargs.get('resource', None), kwargs.get('resource_id', None)
