"""
Pipeline step for enriching grade analytics event context.
"""
from openedx_filters.filters import PipelineStep

from enterprise.models import EnterpriseCourseEnrollment


class GradeEventContextEnricher(PipelineStep):
    """
    Enriches a grade analytics event context dict with the learner's enterprise UUID.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.grade.context.requested.v1`` filter.

    If the user is enrolled in the given course through an enterprise, the enterprise
    UUID is added to the context under the key ``"enterprise_uuid"``. If the user has
    no enterprise course enrollment, the context is returned unchanged.
    """

    def run_filter(self, context, user_id, course_id):  # pylint: disable=arguments-differ
        """
        Add enterprise UUID to the event context if the user has an enterprise enrollment.

        Arguments:
            context (dict): the event tracking context dict.
            user_id (int): the ID of the user whose grade event is being emitted.
            course_id (str or CourseKey): the course key for the grade event.

        Returns:
            dict: updated pipeline data with the enriched ``context`` dict.
        """
        uuids = EnterpriseCourseEnrollment.get_enterprise_uuids_with_user_and_course(
            str(user_id),
            str(course_id),
        )
        if uuids:
            return {"context": {**context, "enterprise_uuid": str(uuids[0])}}
        return {"context": context}
