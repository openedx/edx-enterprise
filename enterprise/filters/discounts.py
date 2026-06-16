"""
Pipeline step for excluding certain learners from course discounts.
"""
import logging

from opaque_keys.edx.keys import CourseKey
from openedx_filters.filters import PipelineStep

from django.contrib.auth.models import AbstractBaseUser

try:
    from openedx_filters.learning.filters import DiscountEligibilityCheckRequested
except ImportError:
    DiscountEligibilityCheckRequested = None

log = logging.getLogger(__name__)

# This import will be replaced with an internal path in epic 17 when
# enterprise_support is migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.utils import is_enterprise_learner
except ImportError:
    is_enterprise_learner = None


class DiscountEligibilityEnterpriseStep(PipelineStep):
    """
    Marks learners linked to an enterprise as ineligible for LMS-controlled discounts.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.discount.eligibility.check.requested.v1`` filter.

    LMS-controlled discounts (such as the first-purchase offer) are not applicable to
    learners whose enrollment is managed by an enterprise. This step queries the
    enterprise learner status and, if the user qualifies, raises ``DiscountIneligible``
    to halt the pipeline and prevent the discount from being applied.
    """
    def run_filter(self, user: AbstractBaseUser, course_key: CourseKey, is_eligible: bool) -> dict:  # pylint: disable=arguments-differ
        """
        Raise ``DiscountIneligible`` if the user is an enterprise learner.

        Arguments:
            user (User): the Django User being checked for discount eligibility.
            course_key: identifies the course (passed through unchanged).
            is_eligible (bool): the current eligibility status.

        Returns:
            dict: updated pipeline data (unchanged) when the user is not an enterprise learner.

        Raises:
            DiscountEligibilityCheckRequested.DiscountIneligible: when the user is linked
            to an enterprise, halting further pipeline processing.
        """
        log.info(
            "DiscountEligibilityEnterpriseStep running: user_id=%s, course_key=%s",
            str(user.id),
            str(course_key),
        )
        if is_enterprise_learner(user):
            raise DiscountEligibilityCheckRequested.DiscountIneligible(
                "User is an enterprise learner and is not eligible for LMS-controlled discounts."
            )
        return {"user": user, "course_key": course_key, "is_eligible": is_eligible}
