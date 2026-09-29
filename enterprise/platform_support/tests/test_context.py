"""
Test the enterprise support APIs.
"""
# These tests exercise openedx-platform fixtures (student factories, the modulestore,
# the completion app) which are not installed in this repo's standalone test
# environment, so pylint cannot resolve them here.
# pylint: disable=import-error
from common.djangoapps.student.tests.factories import CourseEnrollmentFactory, UserFactory
from openedx.core.djangolib.testing.utils import CacheIsolationTestCase, skip_unless_lms

from django.conf import settings
from django.test.utils import override_settings

from enterprise.platform_support.context import get_enterprise_event_context
from enterprise.platform_support.tests.factories import EnterpriseCourseEnrollmentFactory, EnterpriseCustomerUserFactory
from enterprise.platform_support.tests.mixins.enterprise import EnterpriseServiceMockMixin


@override_settings(ENABLE_ENTERPRISE_INTEGRATION=True)
@skip_unless_lms
class TestEnterpriseContext(EnterpriseServiceMockMixin, CacheIsolationTestCase):
    """
    Test enterprise event context APIs.
    """
    ENABLED_CACHES = ['default']

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
        course_enrollment = CourseEnrollmentFactory(user=self.user)
        course = course_enrollment.course
        enterprise_customer_user = EnterpriseCustomerUserFactory(user_id=self.user.id)
        EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=enterprise_customer_user,
            course_id=course.id
        )
        assert get_enterprise_event_context(course_id=course.id, user_id=self.user.id) == \
               {'enterprise_uuid': str(enterprise_customer_user.enterprise_customer_id)}
