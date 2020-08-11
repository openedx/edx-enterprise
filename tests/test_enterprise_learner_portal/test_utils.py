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
    NOW = datetime.now(UTC)

    @ddt.data(
        (
            {
                'pacing': 'instructor',
                'has_ended': True,
                'has_started': False,
            },
            {
                'is_passing': True,
                'created': NOW,
            },
            False,
            CourseRunProgressStatuses.COMPLETED,
        ),
        (
            {
                'pacing': 'instructor',
                'has_ended': False,
                'has_started': True,
            },
            {
                'is_passing': True,
                'created': NOW,
            },
            False,
            CourseRunProgressStatuses.IN_PROGRESS,
        ),
        (
            {
                'pacing': 'instructor',
                'has_ended': False,
                'has_started': False,
            },
            {
                'is_passing': True,
                'created': NOW,
            },
            False,
            CourseRunProgressStatuses.UPCOMING,
        ),
        (
            {
                'pacing': 'self',
                'has_ended': True,
                'has_started': False,
            },
            {
                'is_passing': True,
                'created': NOW,
            },
            False,
            CourseRunProgressStatuses.COMPLETED,
        ),
        (
            {
                'pacing': 'self',
                'has_ended': False,
                'has_started': True,
            },
            {
                'is_passing': False,
                'created': NOW,
            },
            False,
            CourseRunProgressStatuses.IN_PROGRESS,
        ),
        (
            {
                'pacing': 'self',
                'has_ended': False,
                'has_started': False,
            },
            {
                'is_passing': False,
                'created': NOW,
            },
            False,
            CourseRunProgressStatuses.UPCOMING,
        ),
        (
            {
                'pacing': 'instructor',
                'has_ended': False,
                'has_started': True,
            },
            {
                'is_passing': False,
                'created': NOW,
            },
            True,
            CourseRunProgressStatuses.SAVED_FOR_LATER,
        ),
    )
    @ddt.unpack
    def test_get_course_run_status(
            self,
            course_overview,
            certificate_info,
            saved_for_later,
            expected,
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
