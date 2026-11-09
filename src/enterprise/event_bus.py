"""
Functions for serializing and emiting Open edX event bus signals.
"""
from openedx_events.enterprise.data import (
    EnterpriseCourseEnrollment,
    EnterpriseCustomerUser,
    LearnerCreditEnterpriseCourseEnrollment,
)
from openedx_events.enterprise.signals import LEARNER_CREDIT_COURSE_ENROLLMENT_REVOKED


def serialize_learner_credit_course_enrollment(learner_credit_course_enrollment):
    """
    Serializes the ``LearnerCreditEnterpriseCourseEnrollment`` into a defined set of attributes
    for use in the event-bus signal.
    """
    enterprise_course_enrollment = learner_credit_course_enrollment.enterprise_course_enrollment
    enterprise_customer_user = enterprise_course_enrollment.enterprise_customer_user

    enterprise_customer_user_data = EnterpriseCustomerUser(
        id=enterprise_customer_user.id,
        created=enterprise_customer_user.created,
        modified=enterprise_customer_user.modified,
        enterprise_customer_uuid=enterprise_customer_user.enterprise_customer.uuid,
        user_id=enterprise_customer_user.user_id,
        active=enterprise_customer_user.active,
        linked=enterprise_customer_user.linked,
        is_relinkable=enterprise_customer_user.is_relinkable,
        invite_key=enterprise_customer_user.invite_key.uuid if enterprise_customer_user.invite_key else None,
        should_inactivate_other_customers=enterprise_customer_user.should_inactivate_other_customers,
    )
    enterprise_course_enrollment_data = EnterpriseCourseEnrollment(
        id=enterprise_course_enrollment.id,
        created=enterprise_course_enrollment.created,
        modified=enterprise_course_enrollment.modified,
        enterprise_customer_user=enterprise_customer_user_data,
        course_id=enterprise_course_enrollment.course_id,
        saved_for_later=enterprise_course_enrollment.saved_for_later,
        source_slug=enterprise_course_enrollment.source.slug if enterprise_course_enrollment.source else None,
        unenrolled=enterprise_course_enrollment.unenrolled,
        unenrolled_at=enterprise_course_enrollment.unenrolled_at,
    )
    data = LearnerCreditEnterpriseCourseEnrollment(
        uuid=learner_credit_course_enrollment.uuid,
        created=learner_credit_course_enrollment.created,
        modified=learner_credit_course_enrollment.modified,
        fulfillment_type=learner_credit_course_enrollment.fulfillment_type,
        enterprise_course_entitlement_uuid=(
            learner_credit_course_enrollment.enterprise_course_entitlement.uuid
            if learner_credit_course_enrollment.enterprise_course_entitlement
            else None
        ),
        enterprise_course_enrollment=enterprise_course_enrollment_data,
        is_revoked=learner_credit_course_enrollment.is_revoked,
        transaction_id=learner_credit_course_enrollment.transaction_id,
    )
    return data


def send_learner_credit_course_enrollment_revoked_event(learner_credit_course_enrollment):
    """
    Sends the LEARNER_CREDIT_COURSE_ENROLLMENT_REVOKED openedx event.

    Args:
        learner_credit_course_enrollment (enterprise.models.LearnerCreditEnterpriseCourseEnrollment):
            An enterprise learner credit fulfillment record that was revoked.
    """
    LEARNER_CREDIT_COURSE_ENROLLMENT_REVOKED.send_event(
        learner_credit_course_enrollment=serialize_learner_credit_course_enrollment(learner_credit_course_enrollment),
    )
