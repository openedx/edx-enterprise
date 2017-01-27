# -*- coding: utf-8 -*-
"""
Fake responses for course catalog api.
"""

from __future__ import absolute_import, unicode_literals

from six.moves import reduce as six_reduce

FAKE_PROGRAM_RESPONSE1 = {
    "uuid": "40782a06-1c37-4779-86aa-0a081f014d4d",
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
            "course_runs": [
                {
                    "key": "course-v1:Organization+DNDv2+T1",
                    "uuid": "076cb917-06d6-4713-8a6c-c1712ce2e421",
                    "title": "Drag and Drop Demos",
                    "image": {},  # skipped
                    "short_description": None,
                    "marketing_url": None,
                    "start": "2015-01-01T00:00:00Z",
                }
            ],
            "owners": [
                {
                    "uuid": "cd13a803-c524-4719-ba2c-c1c452b18244",
                    "key": "Organization",
                    "name": ""
                }
            ],
            "image": None
        },
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
            "key": "course-v1:Organization+ENT-1+T1",
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
            "key": "course-v1:Organization+ENT-1+T1",
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
