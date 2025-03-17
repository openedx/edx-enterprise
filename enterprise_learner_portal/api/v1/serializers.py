"""
enterprise_learner_portal serializer
"""
from urllib.parse import urlencode

from rest_framework import serializers

from django.conf import settings
from django.utils.translation import gettext as _

from enterprise.constants import EXEC_ED_COURSE_TYPE, PRODUCT_SOURCE_2U
from enterprise.models import EnterpriseCustomerUser
from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.utils import get_course_run_status, get_exec_ed_course_run_status

try:
    from lms.djangoapps.bulk_email.api import get_emails_enabled
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from lms.djangoapps.course_api.api import get_course_run_url
except ImportError:
    get_certificate_for_user = None
    get_course_run_url = None
    get_emails_enabled = None

try:
    from federated_content_connector.models import CourseDetails
except ImportError:
    CourseDetails = None


class EnterpriseCourseEnrollmentSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    """
    A serializer for course enrollment information for a given course
    and enterprise customer user.
    """

    def __init__(self, *args, **kwargs):
        if get_certificate_for_user is None:
            raise NotConnectedToOpenEdX(
                _('To use this EnterpriseCourseEnrollmentSerializer, this package must be '
                  'installed in an Open edX environment.')
            )
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        request = self.context['request']
        course_run_id = instance.course_id
        user = request.user

        # Course Overview
        course_overview = self._get_course_overview(course_run_id)

        # Certificate
        certificate_info = get_certificate_for_user(user.username, course_run_id) or {}
        representation['certificate_download_url'] = certificate_info.get('download_url')

        # Email enabled
        emails_enabled = get_emails_enabled(user, course_run_id)
        if emails_enabled is not None:
            representation['emails_enabled'] = emails_enabled

        representation['course_run_id'] = course_run_id
        representation['course_run_status'] = get_course_run_status(
            course_overview,
            certificate_info,
            instance
        )
        representation['created'] = instance.created.isoformat()
        representation['start_date'] = course_overview['start']
        representation['end_date'] = course_overview['end']
        representation['display_name'] = course_overview['display_name_with_default']
        representation['course_run_url'] = self._get_course_run_url(request, course_run_id)
        representation['due_dates'] = []
        representation['pacing'] = course_overview['pacing']
        representation['org_name'] = course_overview['display_org_with_default']
        representation['is_revoked'] = instance.license.is_revoked if instance.license else False
        representation['is_enrollment_active'] = instance.is_active
        representation['mode'] = instance.mode
        representation['resume_course_run_url'] = self._get_resume_course_run_url(course_run_id, request)

        if CourseDetails:
            course_details = CourseDetails.objects.filter(id=course_run_id).first()
            if course_details:
                representation['course_key'] = course_details.course_key
                representation['course_type'] = course_details.course_type
                representation['product_source'] = course_details.product_source
                representation['start_date'] = course_details.start_date or representation['start_date']
                representation['end_date'] = course_details.end_date or representation['end_date']
                representation['enroll_by'] = course_details.enroll_by

                if (course_details.product_source == PRODUCT_SOURCE_2U and
                        course_details.course_type == EXEC_ED_COURSE_TYPE):
                    representation['course_run_status'] = get_exec_ed_course_run_status(
                        course_details,
                        certificate_info,
                        instance
                    )
                    olc_course_id = course_details.external_identifier
                    representation['external_identifier'] = olc_course_id
                    representation['course_run_url'] = self._get_course_run_url(
                        request,
                        course_run_id,
                        olc_course_id
                    )

        return representation

    def _get_course_overview(self, course_run_id):
        """
        Get the appropriate course overview from the context.
        """
        for overview in self.context['course_overviews']:
            if overview['id'] == course_run_id:
                return overview

        return None

    def _get_course_run_url(self, request, course_run_id, olc_course_id=None):
        """
        Get the appropriate course url while incorporating Executive Education content.
        """
        course_run_url = get_course_run_url(request, course_run_id)
        exec_ed_base_url = getattr(settings, 'EXEC_ED_LANDING_PAGE', None)
        if exec_ed_base_url and exec_ed_base_url == course_run_url:
            active_enterprise_customer = EnterpriseCustomerUser.get_active_enterprise_users(request.user.id).first()
            if active_enterprise_customer and active_enterprise_customer.enterprise_customer.auth_org_id:
                params = {'org_id': active_enterprise_customer.enterprise_customer.auth_org_id}
                if olc_course_id:
                    params['course_id'] = olc_course_id
                course_run_url = '{}?{}'.format(exec_ed_base_url, urlencode(params))

        return course_run_url

    def _get_resume_course_run_url(self, course_run_id, request):
        """
        Converts a relative resume course run URL to an absolute URL.
        """
        resume_course_run_url = self.context['course_enrollments_resume_urls'].get(course_run_id)
        if resume_course_run_url:
            return request.build_absolute_uri(resume_course_run_url)
        return None
