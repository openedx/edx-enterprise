# -*- coding: utf-8 -*-
"""
Tests for the utils of the enterprise_learner_portal app.
"""

from datetime import datetime

import ddt
from pytest import mark
from pytz import UTC

from django.test import TestCase

from enterprise_learner_portal.utils import CourseRunProgressStatuses, get_course_run_status
from test_utils import factories


@mark.django_db
@ddt.ddt
class TestUtils(TestCase):
    """
    Tests for enterprise_learner_portal utils.
    """

    @ddt.data(
        {
            'course_overview': {'has_started': False, 'has_ended': False},
            'certificate_info': {'is_passing': False},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.UPCOMING,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': False},
            'certificate_info': {'is_passing': False},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.IN_PROGRESS,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': False},
            'certificate_info': {'is_passing': True},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.COMPLETED,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': True},
            'certificate_info': {'is_passing': False},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.COMPLETED,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': True},
            'certificate_info': {'is_passing': True},
            'saved_for_later': False,
            'expected_status': CourseRunProgressStatuses.COMPLETED,
        },
        {
            'course_overview': {'has_started': True, 'has_ended': False},
            'certificate_info': {'is_passing': False},
            'saved_for_later': True,
            'expected_status': CourseRunProgressStatuses.SAVED_FOR_LATER,
        },
    )
    @ddt.unpack
    def test_get_course_run_status(
            self,
            course_overview,
            certificate_info,
            saved_for_later,
            expected_status,
    ):
        """
        Assert get_course_run_status returns the proper results based on input parameters
        """
        enterprise_enrollment = factories.EnterpriseCourseEnrollmentFactory.create(saved_for_later=saved_for_later)
        actual = get_course_run_status(
            course_overview,
            certificate_info,
            enterprise_enrollment
        )
        assert actual == expected
