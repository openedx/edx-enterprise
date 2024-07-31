"""
Tests for enterprise/event_bus.py
"""
import unittest

import ddt
from pytest import mark

from enterprise.event_bus import serialize_learner_credit_course_enrollment
from enterprise.models import EnterpriseEnrollmentSource
from test_utils import factories


@ddt.ddt
@mark.django_db
class TestEventBusSerializers(unittest.TestCase):
    """
    Test serializers for use with openedx-events events ("event bus").
    """

    def setUp(self):
        super().setUp()

        self.user = factories.UserFactory(is_active=True)
        self.enterprise_customer = factories.EnterpriseCustomerFactory()
        self.enterprise_user = factories.EnterpriseCustomerUserFactory(
            user_id=self.user.id,
            enterprise_customer=self.enterprise_customer,
        )
        self.enterprise_course_enrollment = factories.EnterpriseCourseEnrollmentFactory(
            enterprise_customer_user=self.enterprise_user,
            source=EnterpriseEnrollmentSource.get_source(EnterpriseEnrollmentSource.API),
        )
        self.learner_credit_course_enrollment = factories.LearnerCreditEnterpriseCourseEnrollmentFactory(
            enterprise_course_enrollment=self.enterprise_course_enrollment,
        )

    def test_serialize_learner_credit_course_enrollment(self):
        """
        Perform a basic test that the serializer drills down two levels into the enterprise user correctly.
        """
        data = serialize_learner_credit_course_enrollment(self.learner_credit_course_enrollment)
        assert data.uuid == self.learner_credit_course_enrollment.uuid
        assert data.enterprise_course_enrollment.id == self.enterprise_course_enrollment.id
        assert data.enterprise_course_enrollment.source_slug == self.enterprise_course_enrollment.source.slug
        assert data.enterprise_course_enrollment.enterprise_customer_user.id == self.enterprise_user.id
        assert data.enterprise_course_enrollment.enterprise_customer_user.enterprise_customer_uuid == \
            self.enterprise_customer.uuid
