"""
Tests for enterprise.filters.enrollment pipeline step.
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseEnrollmentViewStarted
from requests.exceptions import HTTPError

from django.test import TestCase

from enterprise.filters.enrollment import EnterpriseEnrollmentViewProcessor
from test_utils.factories import UserFactory


class TestEnterpriseEnrollmentViewProcessor(TestCase):
    """
    Tests for EnterpriseEnrollmentViewProcessor pipeline step.
    """

    def _make_step(self):
        return EnterpriseEnrollmentViewProcessor(
            "org.openedx.learning.course.enrollment.view.started.v1",
            [],
        )

    @patch('enterprise.filters.enrollment.get_current_request')
    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_returns_unchanged_args_for_non_enterprise_user(
        self,
        mock_enterprise_client,
        mock_consent_client,
        mock_get_current_request,
    ):
        """
        When the user is not linked to an enterprise customer, return the
        arguments unchanged without calling any API clients.
        """
        user = UserFactory.create(username="regular-user")
        course_key = CourseKey.from_string("course-v1:org+course+run")

        mock_request = MagicMock()
        mock_request.data = {}
        mock_get_current_request.return_value = mock_request

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            requester_is_backend_service=True,
        )
        assert result == {
            "user": user,
            "course_key": course_key,
            "requester_is_backend_service": True,
        }

        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_not_called()
        mock_consent_client.return_value.provide_consent.assert_not_called()

    @patch('enterprise.filters.enrollment.get_current_request')
    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_returns_unchanged_args_for_no_api_permissions(
        self,
        mock_enterprise_client,
        mock_consent_client,
        mock_get_current_request,
    ):
        """
        When the user request is sent without proper api key permissions, return the
        arguments unchanged without calling any API clients.
        """
        user = UserFactory.create(username="regular-user")
        enterprise_uuid = uuid.uuid4()
        mock_request = MagicMock()
        mock_request.data = {"linked_enterprise_customer": str(enterprise_uuid)}
        mock_get_current_request.return_value = mock_request

        course_key = CourseKey.from_string("course-v1:org+course+run")

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            requester_is_backend_service=False,
        )
        assert result == {
            "user": user,
            "course_key": course_key,
            "requester_is_backend_service": False,
        }

        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_not_called()
        mock_consent_client.return_value.provide_consent.assert_not_called()

    @patch('enterprise.filters.enrollment.get_current_request')
    @patch('enterprise.filters.enrollment.EnterpriseApiException')
    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_calls_api_clients_for_enterprise_user(
        self,
        mock_enterprise_client,
        mock_consent_client,
        mock_enterprise_api_exception,  # pylint: disable=unused-argument
        mock_get_current_request,
    ):
        """
        When the user is linked to an enterprise customer, call both
        EnterpriseApiServiceClient and ConsentApiServiceClient.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()
        mock_request = MagicMock()
        mock_request.data = {"linked_enterprise_customer": str(enterprise_uuid)}
        mock_get_current_request.return_value = mock_request

        course_key = CourseKey.from_string("course-v1:org+course+run")

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            requester_is_backend_service=True,
        )
        assert result == {
            "user": user,
            "course_key": course_key,
            "requester_is_backend_service": True,
        }

        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_called_once_with(
            "enterprise-learner",
            "course-v1:org+course+run",
        )
        mock_consent_client.return_value.provide_consent.assert_called_once_with(
            username="enterprise-learner",
            course_id="course-v1:org+course+run",
            enterprise_customer_uuid=str(enterprise_uuid),
        )

    @patch('enterprise.filters.enrollment.get_current_request')
    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiException", Exception)
    def test_raises_prevent_enrollment_when_enterprise_api_call_fails(
        self,
        mock_enterprise_client,
        mock_consent_client,
        mock_get_current_request,
    ):
        """
        When the enterprise API client raises, the step raises PreventEnrollment
        and does not proceed to the consent API call.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()
        mock_request = MagicMock()
        mock_request.data = {"linked_enterprise_customer": str(enterprise_uuid)}
        mock_get_current_request.return_value = mock_request

        course_key = CourseKey.from_string("course-v1:org+course+run")

        # Something goes wrong in the enterprise client
        mock_enterprise_client.return_value.post_enterprise_course_enrollment.side_effect = Exception("boom")

        step = self._make_step()
        with pytest.raises(CourseEnrollmentViewStarted.PreventEnrollment):
            step.run_filter(
                user=user,
                course_key=course_key,
                requester_is_backend_service=True,
            )

        # Consent API must NOT be reached once the enterprise post has failed
        mock_consent_client.return_value.provide_consent.assert_not_called()

    @patch('enterprise.filters.enrollment.get_current_request')
    @patch('enterprise.filters.enrollment.EnterpriseApiException')
    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_raises_prevent_enrollment_when_consent_api_call_fails(
        self,
        mock_enterprise_client,
        mock_consent_client,
        mock_enterprise_api_exception,  # pylint: disable=unused-argument
        mock_get_current_request,
    ):
        """
        When the consent API client raises, the step raises PreventEnrollment
        after the enterprise enrollment post has already happened.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()
        mock_request = MagicMock()
        mock_request.data = {"linked_enterprise_customer": str(enterprise_uuid)}
        mock_get_current_request.return_value = mock_request

        course_key = CourseKey.from_string("course-v1:org+course+run")

        # Something goes wrong in the consent client
        mock_consent_client.return_value.provide_consent.side_effect = HTTPError(
            "consent-boom"
        )

        step = self._make_step()
        with pytest.raises(CourseEnrollmentViewStarted.PreventEnrollment):
            step.run_filter(
                user=user,
                course_key=course_key,
                requester_is_backend_service=True,
            )

        # Enterprise post happens before consent, so it is still called once
        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_called_once()

    @patch('enterprise.filters.enrollment.get_current_request')
    @patch("enterprise.filters.enrollment.ConsentApiServiceClient", new=None)
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient", new=None)
    @patch("enterprise.filters.enrollment.EnterpriseApiException", new=None)
    def test_skips_enrollment_when_enterprise_api_unavailable(
        self,
        mock_get_current_request,
    ):
        """
        When enterprise_support.api is unavailable (imports fail), the step logs
        a warning and returns arguments unchanged without attempting API calls.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()
        mock_request = MagicMock()
        mock_request.data = {"linked_enterprise_customer": str(enterprise_uuid)}
        mock_get_current_request.return_value = mock_request

        course_key = CourseKey.from_string("course-v1:org+course+run")

        step = self._make_step()
        with patch('enterprise.filters.enrollment.log') as mock_log:
            result = step.run_filter(
                user=user,
                course_key=course_key,
                requester_is_backend_service=True,
            )
            assert result == {
                "user": user,
                "course_key": course_key,
                "requester_is_backend_service": True,
            }

            mock_log.warning.assert_called_once_with(
                'enterprise_support.api is unavailable: skipping enterprise enrollment side effects'
            )
