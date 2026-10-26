"""
Tests for consent.filters.courseware pipeline steps.
"""
from unittest.mock import patch

import ddt
import pytest
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CoursewareAccessChecksRequested, CoursewareViewStarted

from django.test import RequestFactory, TestCase

from consent.filters.courseware import DataSharingConsentCourseAccessStep, DataSharingConsentRedirectStep
from test_utils.factories import UserFactory


@ddt.ddt
class TestDataSharingConsentRedirectStep(TestCase):
    """Tests for DataSharingConsentRedirectStep."""

    def _make_step(self):
        return DataSharingConsentRedirectStep(
            "org.openedx.learning.courseware.view.started.v1", []
        )

    @ddt.data(
        {
            "consent_url_return_value": "/consent/",
            "expected_raises": CoursewareViewStarted.RedirectToUrl,
            "expected_redirect_url": "/consent/",
        },
        {
            "consent_url_return_value": None,
            "expected_raises": None,
            "expected_redirect_url": None,
        },
    )
    @ddt.unpack
    @patch('consent.filters.courseware.get_enterprise_consent_url')
    @patch('consent.filters.courseware.get_current_request')
    def test_run_filter(
        self,
        mock_get_request,
        mock_get_url,
        consent_url_return_value,
        expected_raises,
        expected_redirect_url,
    ):
        """Raises RedirectToUrl when consent is required, otherwise returns passthrough."""
        user = UserFactory.create()
        request = RequestFactory().get('/')
        request.user = user
        mock_get_request.return_value = request
        mock_get_url.return_value = consent_url_return_value
        step = self._make_step()
        course_key = CourseKey.from_string("course-v1:org+course+run")
        view_name = "test_view"
        if expected_raises is not None:
            with pytest.raises(expected_raises) as exc_info:
                step.run_filter(course_key=course_key, view_name=view_name)
            assert exc_info.value.redirect_to == expected_redirect_url
        else:
            result = step.run_filter(course_key=course_key, view_name=view_name)
            assert result == {"course_key": course_key, "view_name": view_name}
        mock_get_url.assert_called_once_with(
            request=request,
            course_id='course-v1:org+course+run',
            enrollment_exists=True,
            source=view_name,
        )

    @patch('consent.filters.courseware.get_current_request', return_value=None)
    def test_passthrough_when_no_request(self, _mock_get_request):
        """No exception and passthrough dict when there is no current request available."""
        step = self._make_step()
        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        view_name = "test_view"
        result = step.run_filter(course_key=course_key, view_name=view_name)
        assert result == {"course_key": course_key, "view_name": view_name}


@ddt.ddt
class TestDataSharingConsentCourseAccessStep(TestCase):
    """Tests for DataSharingConsentCourseAccessStep."""

    def _make_step(self):
        return DataSharingConsentCourseAccessStep(
            "org.openedx.learning.courseware.access_checks.requested.v1", [],
        )

    @ddt.data(
        {
            "consent_url_return_value": "/consent/",
            "expected_raises": CoursewareAccessChecksRequested.PreventCoursewareAccess,
            "expected_developer_message": "/consent/",
        },
        {
            "consent_url_return_value": None,
            "expected_raises": None,
            "expected_developer_message": None,
        },
    )
    @ddt.unpack
    @patch('consent.filters.courseware.get_enterprise_consent_url')
    @patch('consent.filters.courseware.get_current_request')
    def test_run_filter(
        self,
        mock_get_request,
        mock_get_url,
        consent_url_return_value,
        expected_raises,
        expected_developer_message,
    ):
        """Raises PreventCoursewareAccess when consent is required, otherwise returns passthrough."""
        user = UserFactory.create()
        request = RequestFactory().get('/')
        request.user = user
        mock_get_request.return_value = request
        mock_get_url.return_value = consent_url_return_value
        step = self._make_step()
        course_key = CourseKey.from_string("course-v1:org+course+run")
        if expected_raises is not None:
            with pytest.raises(expected_raises) as exc_info:
                step.run_filter(user=user, course_key=course_key)
            assert exc_info.value.error_code == 'data_sharing_access_required'
            assert exc_info.value.developer_message == expected_developer_message
        else:
            result = step.run_filter(user=user, course_key=course_key)
            assert result == {"user": user, "course_key": course_key}
        mock_get_url.assert_called_once_with(
            request=request,
            course_id='course-v1:org+course+run',
            user=user,
            return_to="courseware",
            enrollment_exists=True,
            source="CoursewareAccess",
        )

    @patch('consent.filters.courseware.get_current_request', return_value=None)
    def test_passthrough_when_no_request(self, _mock_get_request):
        """No exception when there is no current request available."""
        step = self._make_step()
        user = UserFactory.create()
        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        result = step.run_filter(user=user, course_key=course_key)
        assert result == {"user": user, "course_key": course_key}
