"""
Pipeline steps for the support views filters.
"""
import logging

from openedx_filters.filters import PipelineStep

log = logging.getLogger(__name__)

# These imports will be replaced with an internal path in ENT-11576 when
# enterprise_support is migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.api import (
        enterprise_customer_for_request,
        get_data_sharing_consents,
        get_enterprise_course_enrollments,
    )
    from openedx.features.enterprise_support.serializers import EnterpriseCourseEnrollmentSerializer
except ImportError:
    enterprise_customer_for_request = None
    get_data_sharing_consents = None
    get_enterprise_course_enrollments = None
    EnterpriseCourseEnrollmentSerializer = None


class SupportContactEnterpriseTagInjector(PipelineStep):
    """
    Append the 'enterprise_learner' tag to support tickets for enterprise users.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.support.contact.context.requested.v1`` filter.
    """

    def run_filter(self, tags, request, user):  # pylint: disable=arguments-differ
        """
        Append 'enterprise_learner' to tags if the user is linked to an enterprise customer.
        """
        if enterprise_customer_for_request is None:
            log.warning('enterprise_support.api is unavailable: skipping support contact enterprise tag')
            return {'tags': tags, 'request': request, 'user': user}

        enterprise_customer = enterprise_customer_for_request(request)
        if enterprise_customer and 'enterprise_learner' not in tags:
            tags = [*tags, 'enterprise_learner']

        return {'tags': tags, 'request': request, 'user': user}


class SupportEnterpriseEnrollmentDataInjector(PipelineStep):
    """
    Inject enterprise course enrollment data into the support enrollment view.

    Builds a dict of enterprise course enrollments (with data-sharing consent records)
    keyed by course_id.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.support.enrollment.data.requested.v1`` filter.
    """

    def run_filter(self, enrollment_data, user):  # pylint: disable=arguments-differ
        """
        Populate enrollment_data with enterprise course enrollment records for the user.
        """
        if get_enterprise_course_enrollments is None:
            log.warning('enterprise_support.api is unavailable: skipping support enrollment data injection')
            return {'enrollment_data': enrollment_data, 'user': user}

        enterprise_course_enrollments = get_enterprise_course_enrollments(user)
        consents = get_data_sharing_consents(user)

        consent_by_key = {
            f'{consent.course_id}-{consent.enterprise_customer_id}': consent.serialize()
            for consent in consents
        }

        enriched = dict(enrollment_data)
        for ecr in enterprise_course_enrollments:
            serialized = EnterpriseCourseEnrollmentSerializer(ecr).data
            course_id = ecr.course_id
            enterprise_customer_id = ecr.enterprise_customer_user.enterprise_customer_id
            key = f'{course_id}-{enterprise_customer_id}'
            serialized['data_sharing_consent'] = consent_by_key.get(key)
            enriched.setdefault(course_id, []).append(serialized)

        return {'enrollment_data': enriched, 'user': user}
