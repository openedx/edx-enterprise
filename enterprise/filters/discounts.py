"""
Pipeline step for excluding certain learners from course discounts.
"""
from openedx_filters.filters import PipelineStep

# This import will be replaced with an internal path in epic 17 when
# enterprise_support is migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.utils import is_enterprise_learner
except ImportError:
    is_enterprise_learner = None


class DiscountEligibilityStep(PipelineStep):
    """
    Marks learners linked to an enterprise as ineligible for LMS-controlled discounts.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.discount.eligibility.check.requested.v1`` filter.

    LMS-controlled discounts (such as the first-purchase offer) are not applicable to
    learners whose enrollment is managed by an enterprise. This step queries the
    enterprise learner status and, if the user qualifies, sets ``is_eligible`` to
    ``False`` so the calling code skips the discount.
    """

    def run_filter(self, user, course_key, is_eligible):  # pylint: disable=arguments-differ
        """
        Return ``is_eligible=False`` if the user is an enterprise learner.

        Arguments:
            user (User): the Django User being checked for discount eligibility.
            course_key: identifies the course (passed through unchanged).
            is_eligible (bool): the current eligibility status.

        Returns:
            dict: updated pipeline data. ``is_eligible`` is ``False`` when the user is
            linked to an enterprise; otherwise the original ``is_eligible`` value is
            preserved.
        """
        if is_enterprise_learner(user):
            return {"user": user, "course_key": course_key, "is_eligible": False}
        return {"user": user, "course_key": course_key, "is_eligible": is_eligible}
