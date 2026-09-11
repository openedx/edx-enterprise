"""
Pipeline steps for the support views filters.
"""
from crum import get_current_request
from openedx_filters.filters import PipelineStep

# This import will be replaced with an internal path in ENT-11576 when
# enterprise_support is migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.api import enterprise_customer_for_request
except ImportError:
    enterprise_customer_for_request = None

# This import will be replaced with an internal path in ENT-11576 when
# enterprise_support is migrated into edx-enterprise.
try:
    from openedx.features.enterprise_support.api import get_data_sharing_consents, get_enterprise_course_enrollments
    from openedx.features.enterprise_support.serializers import EnterpriseCourseEnrollmentSerializer
except ImportError:
    get_data_sharing_consents = None
    get_enterprise_course_enrollments = None
    EnterpriseCourseEnrollmentSerializer = None


class SupportContactEnterpriseTagStep(PipelineStep):
    """
    Append a support-ticket tag for linked customer-account requests.

    This step is intended to be registered as a pipeline step for the
    ``org.openedx.learning.support.contact.context.requested.v1`` filter.
    """

    def run_filter(self, context):  # pylint: disable=arguments-differ
        """
        Append 'enterprise_learner' to context['tags'] if the requester is linked to a customer account.
        """
        request = get_current_request()
        customer = enterprise_customer_for_request(request)
        tags = context.get('tags', [])
        if customer and 'enterprise_learner' not in tags:
            context = {**context, 'tags': [*tags, 'enterprise_learner']}

        return {'context': context}


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
        enterprise_course_enrollments = get_enterprise_course_enrollments(user)
        consents = get_data_sharing_consents(user)

        consent_by_key = {
            f'{consent.course_id}-{consent.enterprise_customer_id}': consent.serialize()
            for consent in consents
        }

        for ecr in enterprise_course_enrollments:
            serialized = EnterpriseCourseEnrollmentSerializer(ecr).data
            course_id = ecr.course_id
            enterprise_customer_id = ecr.enterprise_customer_user.enterprise_customer_id
            key = f'{course_id}-{enterprise_customer_id}'
            serialized['data_sharing_consent'] = consent_by_key.get(key)
            enrollment_data.setdefault(course_id, []).append(serialized)

        return {'enrollment_data': enrollment_data, 'user': user}
