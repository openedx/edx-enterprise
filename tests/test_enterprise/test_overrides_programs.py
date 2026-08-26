"""
Tests for enterprise.overrides.programs pluggable override.
"""
import unittest
from unittest.mock import MagicMock

from pytest import mark

from enterprise.overrides.programs import enterprise_get_enterprise_course_ids
from test_utils import factories


@mark.django_db
class TestEnterpriseGetEnterpriseCourseIds(unittest.TestCase):
    """
    Tests for enterprise_get_enterprise_course_ids override function.
    """

    def setUp(self):
        super().setUp()
        self.user = factories.UserFactory()
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )

    def _call(self, user=None):
        """Call the override function for the given user and the test enterprise customer."""
        return enterprise_get_enterprise_course_ids(
            prev_fn=MagicMock(),
            enterprise_uuid=str(self.enterprise_customer.uuid),
            user=user or self.user,
        )

    def test_returns_course_ids_for_requested_customer(self):
        """
        Course IDs of the user's enrollments under the requested customer are returned.
        """
        factories.EnterpriseCourseEnrollmentFactory(
            course_id='course-v1:edX+DemoX+Demo_Course',
            enterprise_customer_user=self.enterprise_customer_user,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            course_id='course-v1:edX+SecondX+Second_Course',
            enterprise_customer_user=self.enterprise_customer_user,
        )

        result = self._call()

        assert sorted(result) == [
            'course-v1:edX+DemoX+Demo_Course',
            'course-v1:edX+SecondX+Second_Course',
        ]

    def test_excludes_enrollments_under_a_different_customer(self):
        """
        Enrollments the user has under some other enterprise customer are not returned.
        """
        factories.EnterpriseCourseEnrollmentFactory(
            course_id='course-v1:edX+DemoX+Demo_Course',
            enterprise_customer_user=self.enterprise_customer_user,
        )
        other_enterprise_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=factories.EnterpriseCustomerFactory(),
        )
        factories.EnterpriseCourseEnrollmentFactory(
            course_id='course-v1:edX+OtherX+Other_Course',
            enterprise_customer_user=other_enterprise_customer_user,
        )

        result = self._call()

        assert result == ['course-v1:edX+DemoX+Demo_Course']

    def test_excludes_enrollments_of_unlinked_customer_user(self):
        """
        Enrollments belonging to an unlinked EnterpriseCustomerUser are not returned.
        """
        unlinked_user = factories.UserFactory()
        unlinked_customer_user = factories.EnterpriseCustomerUserFactory(
            user_id=unlinked_user.id,
            enterprise_customer=self.enterprise_customer,
            linked=False,
        )
        factories.EnterpriseCourseEnrollmentFactory(
            course_id='course-v1:edX+UnlinkedX+Unlinked_Course',
            enterprise_customer_user=unlinked_customer_user,
        )

        result = self._call(user=unlinked_user)

        assert not result

        # Sanity check that the enrollment above is only excluded because of ``linked``.
        unlinked_customer_user.linked = True
        unlinked_customer_user.save()
        assert self._call(user=unlinked_user) == ['course-v1:edX+UnlinkedX+Unlinked_Course']

    def test_returns_empty_list_when_no_enrollments(self):
        """
        An empty list is returned when the user has no enterprise course enrollments.
        """
        result = self._call()

        assert not result
