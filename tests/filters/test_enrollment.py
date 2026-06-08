"""
Tests for enterprise.filters.enrollment pipeline step.
"""
import uuid
from unittest.mock import MagicMock, patch

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

    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_returns_unchanged_args_for_non_enterprise_user(
        self,
        mock_enterprise_client,
        mock_consent_client,
    ):
        """
        When the user is not linked to an enterprise customer, return the
        arguments unchanged without calling any API clients.
        """
        user = UserFactory.create(username="regular-user")
        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            linked_enterprise=None,
            has_api_key_permissions=True,
        )
        self.assertEqual(
            result,
            {
                "user": user,
                "course_key": course_key,
                "linked_enterprise": None,
                "has_api_key_permissions": True,
            },
        )

        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_not_called()
        mock_consent_client.return_value.provide_consent.assert_not_called()

    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_returns_unchanged_args_for_no_api_permissions(
        self,
        mock_enterprise_client,
        mock_consent_client,
    ):
        """
        When the user request is sent without proper api key permissions, return the
        arguments unchanged without calling any API clients.
        """
        user = UserFactory.create(username="regular-user")
        enterprise_uuid = uuid.uuid4()

        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            linked_enterprise=enterprise_uuid,
            has_api_key_permissions=False,
        )
        self.assertEqual(
            result,
            {
                "user": user,
                "course_key": course_key,
                "linked_enterprise": enterprise_uuid,
                "has_api_key_permissions": False,
            },
        )

        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_not_called()
        mock_consent_client.return_value.provide_consent.assert_not_called()

    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_calls_api_clients_for_enterprise_user(
        self,
        mock_enterprise_client,
        mock_consent_client,
    ):
        """
        When the user is linked to an enterprise customer, call both
        EnterpriseApiServiceClient and ConsentApiServiceClient.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()

        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            linked_enterprise=enterprise_uuid,
            has_api_key_permissions=True,
        )
        self.assertEqual(
            result,
            {
                "user": user,
                "course_key": course_key,
                "linked_enterprise": enterprise_uuid,
                "has_api_key_permissions": True,
            },
        )

        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_called_once_with(
            "enterprise-learner",
            "course-v1:org+course+run",
        )
        mock_consent_client.return_value.provide_consent.assert_called_once_with(
            username="enterprise-learner",
            course_id="course-v1:org+course+run",
            enterprise_customer_uuid=str(enterprise_uuid),
        )

    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_logs_exception_when_enterprise_api_call_fails(
        self,
        mock_enterprise_client,
        mock_consent_client,
    ):
        """
        When the enterprise API client raises an exception, it is logged and
        execution continues to the consent API call.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()

        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"

        # Something goes wrong in the enterprise client
        mock_enterprise_client.return_value.post_enterprise_course_enrollment.side_effect = Exception(
            "boom"
        )

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            linked_enterprise=enterprise_uuid,
            has_api_key_permissions=True,
        )
        self.assertEqual(
            result,
            {
                "user": user,
                "course_key": course_key,
                "linked_enterprise": enterprise_uuid,
                "has_api_key_permissions": True,
            },
        )

        # Consent API should still be called despite enrollment API failure
        mock_consent_client.return_value.provide_consent.assert_called_once()

    @patch("enterprise.filters.enrollment.ConsentApiServiceClient")
    @patch("enterprise.filters.enrollment.EnterpriseApiServiceClient")
    def test_logs_exception_when_consent_api_call_fails(
        self,
        mock_enterprise_client,
        mock_consent_client,
    ):
        """
        When the consent API client raises an exception, it is logged and
        the filter still returns the original arguments.
        """
        user = UserFactory.create(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()

        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"

        # Something goes wrong in the consent client
        mock_consent_client.return_value.provide_consent.side_effect = Exception(
            "consent-boom"
        )

        step = self._make_step()
        result = step.run_filter(
            user=user,
            course_key=course_key,
            linked_enterprise=enterprise_uuid,
            has_api_key_permissions=True,
        )
        self.assertEqual(
            result,
            {
                "user": user,
                "course_key": course_key,
                "linked_enterprise": enterprise_uuid,
                "has_api_key_permissions": True,
            },
        )

        # Enterprise API should still be called despite consent API failure
        mock_enterprise_client.return_value.post_enterprise_course_enrollment.assert_called_once()
