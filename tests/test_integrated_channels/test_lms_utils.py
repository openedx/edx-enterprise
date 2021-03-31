# -*- coding: utf-8 -*-
"""
Tests for the lms_utils used by integration channels.
"""

import unittest

import mock
import pytest
from opaque_keys import InvalidKeyError

from integrated_channels.lms_utils import get_course_certificate, get_single_user_grade
from test_utils import factories

A_GOOD_COURSE_ID = "edX/DemoX/Demo_Course"
A_BAD_COURSE_ID = "this_shall_not_pass"
A_LMS_USER = "a_lms_user"


@pytest.mark.django_db
class TestLMSUtils(unittest.TestCase):
    """
    Tests for lms_utils
    """

    def setUp(self):
        self.username = A_LMS_USER
        self.user = factories.UserFactory(username=self.username)
        super().setUp()

    @mock.patch('integrated_channels.lms_utils.get_certificate_for_user')
    def test_get_course_certificate_success(self, mock_get_course_certificate):
        a_cert = {
            "username": A_LMS_USER,
            "grade": "0.98",
        }
        mock_get_course_certificate.return_value = a_cert
        cert = get_course_certificate(A_GOOD_COURSE_ID, self.user)
        assert cert == a_cert
        assert mock_get_course_certificate.call_count == 1

    @mock.patch('integrated_channels.lms_utils.get_certificate_for_user')
    def test_get_course_certificate_bad_course_id_throws(self, mock_get_course_certificate):
        with pytest.raises(InvalidKeyError):
            get_course_certificate(A_BAD_COURSE_ID, self.user)
            assert mock_get_course_certificate.call_count == 0

    @mock.patch('integrated_channels.lms_utils.CourseGradeFactory')
    def test_get_single_user_grade_success(self, mock_course_grade_factory):
        expected_grade = "0.8"
        mock_course_grade_factory.return_value.read.return_value = expected_grade
        single_user_grade = get_single_user_grade(A_GOOD_COURSE_ID, self.user)
        assert single_user_grade == expected_grade

    @mock.patch('integrated_channels.lms_utils.CourseGradeFactory')
    def test_get_single_user_grade_bad_course_id_throws(self, mock_course_grade_factory):
        with pytest.raises(InvalidKeyError):
            get_single_user_grade(A_BAD_COURSE_ID, self.user)
            assert mock_course_grade_factory.call_count == 0
