"""
Test the enterprise support APIs.
"""
from opaque_keys.edx.keys import CourseKey

from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings

from enterprise.platform_support.context import get_enterprise_event_context
from test_utils.factories import EnterpriseCourseEnrollmentFactory, EnterpriseCustomerUserFactory, UserFactory

from .mixins import EnterpriseServiceMockMixin

COURSE_ID = CourseKey.from_string('course-v1:edX+DemoX+Demo_Course')


@override_settings(ENABLE_ENTERPRISE_INTEGRATION=True)
class TestEnterpriseContext(EnterpriseServiceMockMixin, TestCase):
    """
    Test enterprise event context APIs.
    """

    @classmethod
    def setUpTestData(cls):
        """Create the enterprise service worker used by these tests."""
        cls.user = UserFactory.create(
            username=settings.ENTERPRISE_SERVICE_WORKER_USERNAME,
            email='ent_worker@example.com',
            password='password123',
        )
        super().setUpTestData()

    def test_get_enterprise_event_context(self):
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=self.user.id)
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=COURSE_ID,
        )
        assert get_enterprise_event_context(course_id=COURSE_ID, user_id=self.user.id) == \
               {'enterprise_uuid': str(enterprise_customer_user.enterprise_customer_id)}
