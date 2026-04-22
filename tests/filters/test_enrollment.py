"""
Tests for enterprise.filters.enrollment pipeline step.
"""
import sys
import uuid
from types import ModuleType
from unittest.mock import MagicMock, patch

from django.test import TestCase

from enterprise.filters.enrollment import EnterpriseEnrollmentPostProcessor
from test_utils.factories import UserFactory


def _make_mock_api_module():
    """
    Return a fake ``openedx.features.enterprise_support.api`` module with mock clients.
    """
    mock_enterprise_client = MagicMock()
    mock_consent_client = MagicMock()

    mock_module = ModuleType("openedx.features.enterprise_support.api")
    mock_module.EnterpriseApiServiceClient = MagicMock(return_value=mock_enterprise_client)
    mock_module.ConsentApiServiceClient = MagicMock(return_value=mock_consent_client)
    return mock_module, mock_enterprise_client, mock_consent_client


def _make_openedx_modules():
    """
    Build a minimal set of sys.modules entries for the openedx namespace.
    """
    entries = {}
    for name in (
        "openedx",
        "openedx.features",
        "openedx.features.enterprise_support",
    ):
        entries[name] = ModuleType(name)
    return entries


class TestEnterpriseEnrollmentPostProcessor(TestCase):
    """
    Tests for EnterpriseEnrollmentPostProcessor pipeline step.
    """

    def _make_step(self):
        return EnterpriseEnrollmentPostProcessor(
            "org.openedx.learning.course.enrollment.created.v1",
            [],
        )

    def test_returns_unchanged_args_for_non_enterprise_user(self):
        """
        When the user is not linked to an enterprise customer, return the
        arguments unchanged without calling any API clients.
        """
        user = UserFactory.build(username="regular-user")
        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"
        mode = "verified"

        mock_qs = MagicMock()
        mock_qs.exists.return_value = False

        mock_api_module, mock_enterprise_client, mock_consent_client = _make_mock_api_module()
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        with patch.dict(sys.modules, extra_modules), \
                patch("enterprise.filters.enrollment.EnterpriseCustomerUser.objects") as mock_objects:
            mock_objects.filter.return_value = mock_qs
            step = self._make_step()
            result = step.run_filter(user=user, course_key=course_key, mode=mode)

        assert result == {"user": user, "course_key": course_key, "mode": mode}
        mock_enterprise_client.post_enterprise_course_enrollment.assert_not_called()
        mock_consent_client.provide_consent.assert_not_called()

    def test_calls_api_clients_for_enterprise_user(self):
        """
        When the user is linked to an enterprise customer, call both
        EnterpriseApiServiceClient and ConsentApiServiceClient.
        """
        user = UserFactory.build(username="enterprise-learner")
        enterprise_uuid = uuid.uuid4()

        mock_enterprise_customer = MagicMock()
        mock_enterprise_customer.uuid = enterprise_uuid

        mock_ecu = MagicMock()
        mock_ecu.enterprise_customer = mock_enterprise_customer

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.first.return_value = mock_ecu

        course_key = MagicMock()
        course_key.__str__.return_value ="course-v1:TestOrg+course+run"
        mode = "audit"

        mock_api_module, mock_enterprise_client, mock_consent_client = _make_mock_api_module()
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        with patch.dict(sys.modules, extra_modules), \
                patch("enterprise.filters.enrollment.EnterpriseCustomerUser.objects") as mock_objects:
            mock_objects.filter.return_value = mock_qs
            step = self._make_step()
            result = step.run_filter(user=user, course_key=course_key, mode=mode)

        assert result == {"user": user, "course_key": course_key, "mode": mode}
        mock_enterprise_client.post_enterprise_course_enrollment.assert_called_once_with(
            "enterprise-learner",
            "course-v1:TestOrg+course+run",
            consent_granted=True,
        )
        mock_consent_client.provide_consent.assert_called_once_with(
            username="enterprise-learner",
            course_id="course-v1:TestOrg+course+run",
            enterprise_customer_uuid=str(enterprise_uuid),
        )

    def test_logs_exception_when_enterprise_api_call_fails(self):
        """
        When the enterprise API client raises an exception, it is logged and
        execution continues to the consent API call.
        """
        user = UserFactory.build(username="learner")
        enterprise_uuid = uuid.uuid4()

        mock_enterprise_customer = MagicMock()
        mock_enterprise_customer.uuid = enterprise_uuid

        mock_ecu = MagicMock()
        mock_ecu.enterprise_customer = mock_enterprise_customer

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.first.return_value = mock_ecu

        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"
        mode = "audit"

        mock_api_module, mock_enterprise_client, mock_consent_client = _make_mock_api_module()
        mock_enterprise_client.post_enterprise_course_enrollment.side_effect = Exception("boom")
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        with patch.dict(sys.modules, extra_modules), \
                patch("enterprise.filters.enrollment.EnterpriseCustomerUser.objects") as mock_objects, \
                patch("enterprise.filters.enrollment.log") as mock_log:
            mock_objects.filter.return_value = mock_qs
            step = self._make_step()
            result = step.run_filter(user=user, course_key=course_key, mode=mode)

        assert result == {"user": user, "course_key": course_key, "mode": mode}
        mock_log.exception.assert_any_call(
            "Failed to post enterprise course enrollment for user %s in course %s.",
            "learner",
            "course-v1:org+course+run",
        )
        # Consent API should still be called despite enrollment API failure
        mock_consent_client.provide_consent.assert_called_once()

    def test_logs_exception_when_consent_api_call_fails(self):
        """
        When the consent API client raises an exception, it is logged and
        the filter still returns the original arguments.
        """
        user = UserFactory.build(username="learner2")
        enterprise_uuid = uuid.uuid4()

        mock_enterprise_customer = MagicMock()
        mock_enterprise_customer.uuid = enterprise_uuid

        mock_ecu = MagicMock()
        mock_ecu.enterprise_customer = mock_enterprise_customer

        mock_qs = MagicMock()
        mock_qs.exists.return_value = True
        mock_qs.first.return_value = mock_ecu

        course_key = MagicMock()
        course_key.__str__.return_value = "course-v1:org+course+run"
        mode = "verified"

        mock_api_module, _mock_enterprise_client, mock_consent_client = _make_mock_api_module()
        mock_consent_client.provide_consent.side_effect = Exception("consent-boom")
        extra_modules = _make_openedx_modules()
        extra_modules["openedx.features.enterprise_support.api"] = mock_api_module

        with patch.dict(sys.modules, extra_modules), \
                patch("enterprise.filters.enrollment.EnterpriseCustomerUser.objects") as mock_objects, \
                patch("enterprise.filters.enrollment.log") as mock_log:
            mock_objects.filter.return_value = mock_qs
            step = self._make_step()
            result = step.run_filter(user=user, course_key=course_key, mode=mode)

        assert result == {"user": user, "course_key": course_key, "mode": mode}
        mock_log.exception.assert_any_call(
            "Failed to provide enterprise consent for user %s in course %s.",
            "learner2",
            "course-v1:org+course+run",
        )
