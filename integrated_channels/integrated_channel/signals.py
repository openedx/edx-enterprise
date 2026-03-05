"""
Django signal handlers for integrated channels user retirement.
"""
from logging import getLogger

from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomerUser
from integrated_channels.degreed.models import DegreedLearnerDataTransmissionAudit
from integrated_channels.sap_success_factors.models import SapSuccessFactorsLearnerDataTransmissionAudit

logger = getLogger(__name__)

try:
    from openedx.core.djangoapps.user_api.accounts.signals import USER_RETIRE_LMS_CRITICAL
except ImportError:
    USER_RETIRE_LMS_CRITICAL = None


def retire_sapsf_data_transmission(sender, user, **kwargs):  # pylint: disable=unused-argument
    """
    Handle USER_RETIRE_LMS_CRITICAL signal: clear sapsf_user_id on audit records.

    Idempotent: only updates records where sapsf_user_id is not already empty.
    """
    for ent_user in EnterpriseCustomerUser.objects.filter(user_id=user.id):
        for enrollment in EnterpriseCourseEnrollment.objects.filter(enterprise_customer_user=ent_user):
            SapSuccessFactorsLearnerDataTransmissionAudit.objects.filter(
                enterprise_course_enrollment_id=enrollment.id,
            ).exclude(
                sapsf_user_id="",
            ).update(sapsf_user_id="")


def retire_degreed_data_transmission(sender, user, **kwargs):  # pylint: disable=unused-argument
    """
    Handle USER_RETIRE_LMS_CRITICAL signal: clear degreed_user_email on audit records.

    Idempotent: only updates records where degreed_user_email is not already empty.
    """
    for ent_user in EnterpriseCustomerUser.objects.filter(user_id=user.id):
        for enrollment in EnterpriseCourseEnrollment.objects.filter(enterprise_customer_user=ent_user):
            DegreedLearnerDataTransmissionAudit.objects.filter(
                enterprise_course_enrollment_id=enrollment.id,
            ).exclude(
                degreed_user_email="",
            ).update(degreed_user_email="")


if USER_RETIRE_LMS_CRITICAL is not None:
    USER_RETIRE_LMS_CRITICAL.connect(retire_sapsf_data_transmission)
    USER_RETIRE_LMS_CRITICAL.connect(retire_degreed_data_transmission)
