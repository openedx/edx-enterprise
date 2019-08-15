# -*- coding: utf-8 -*-
"""
Tests for the utils of the enterprise_learner_portal app.
"""
from __future__ import absolute_import, unicode_literals

from datetime import datetime

import ddt
from pytz import UTC

from django.test import TestCase

from enterprise_learner_portal.utils import CourseRunProgressStatuses, get_course_run_status


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
            CourseRunProgressStatuses.UPCOMING,
        ),
    )
    @ddt.unpack
    def test_get_course_run_status(
            self,
            course_overview,
            certificate_info,
            expected,
    ):
        """
        get_course_run_status should return the proper results
        based on input parameters
        """
        actual = get_course_run_status(
            course_overview,
            certificate_info,
        )
        assert actual == expected
