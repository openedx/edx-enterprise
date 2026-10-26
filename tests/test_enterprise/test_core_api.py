"""
Tests for the ``enterprise.core_api`` module.
"""
from unittest.mock import patch

import ddt
from opaque_keys.edx.keys import CourseKey
from pytest import mark

from django.test import RequestFactory, TestCase, override_settings

from enterprise.core_api import enterprise_learner_enrolled, get_active_enterprise_customer_user
from test_utils import factories


@mark.django_db
class GetActiveEnterpriseCustomerUserTest(TestCase):
    """Tests for ``enterprise.core_api.get_active_enterprise_customer_user``."""

    def setUp(self):
        super().setUp()
        self.user = factories.UserFactory()

    @override_settings(ENABLE_ENTERPRISE_INTEGRATION=False)
    def test_returns_none_when_integration_disabled(self):
        factories.EnterpriseCustomerUserFactory(user_id=self.user.id, active=True)
        assert get_active_enterprise_customer_user(self.user) is None

    @override_settings(ENABLE_ENTERPRISE_INTEGRATION=True)
    def test_returns_active_customer_user(self):
        factories.EnterpriseCustomerUserFactory(user_id=self.user.id, active=True)
        data = get_active_enterprise_customer_user(self.user)
        assert data.user.username == self.user.username
        assert data.active

    @override_settings(ENABLE_ENTERPRISE_INTEGRATION=True)
    def test_returns_none_when_no_active_user_found(self):
        assert get_active_enterprise_customer_user(self.user) is None


@mark.django_db
@ddt.ddt
class EnterpriseLearnerEnrolledTest(TestCase):
    """Tests for ``enterprise.core_api.enterprise_learner_enrolled``."""

    def _make_request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    @ddt.data(
        # Linked customer with portal enabled and matching enrollment: returns True.
        {"has_customer": True, "enable_learner_portal": True, "has_enrollment": True, "expected_result": True},
        # No linked enterprise customer: returns False.
        {"has_customer": False, "enable_learner_portal": None, "has_enrollment": False, "expected_result": False},
        # Linked customer but learner portal disabled: returns False.
        {"has_customer": True, "enable_learner_portal": False, "has_enrollment": False, "expected_result": False},
        # Linked customer with portal enabled but no EnterpriseCourseEnrollment: returns False.
        {"has_customer": True, "enable_learner_portal": True, "has_enrollment": False, "expected_result": False},
    )
    @ddt.unpack
    @patch('enterprise.core_api.enterprise_customer_from_session_or_learner_data')
    def test_returns_enrolled(
        self,
        mock_customer,
        has_customer: bool,
        enable_learner_portal: bool | None,
        has_enrollment: bool,
        expected_result: bool,
    ):
        """Returns True only when the user has an active linked customer with portal enabled and an enrollment."""
        user = factories.UserFactory()
        course_key = CourseKey.from_string("course-v1:edX+DemoX+Demo_Course")
        if has_customer:
            ec = factories.EnterpriseCustomerFactory()
            mock_customer.return_value = {'uuid': str(ec.uuid), 'enable_learner_portal': enable_learner_portal}
            if has_enrollment:
                ecu = factories.EnterpriseCustomerUserFactory(enterprise_customer=ec, user_id=user.id)
                factories.EnterpriseCourseEnrollmentFactory(enterprise_customer_user=ecu, course_id=str(course_key))
        else:
            mock_customer.return_value = None
        assert enterprise_learner_enrolled(self._make_request(user), course_key) is expected_result
