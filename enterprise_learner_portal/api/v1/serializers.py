# -*- coding: utf-8 -*-
"""
enterprise_learner_portal serializer
"""

from rest_framework import serializers

from django.utils.translation import ugettext as _

from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.utils import get_course_run_status

try:
    from lms.djangoapps.bulk_email.api import get_emails_enabled
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from lms.djangoapps.course_api.api import get_course_run_url
except ImportError:
    get_certificate_for_user = None
    get_course_run_url = None
    get_emails_enabled = None


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
        representation['start_date'] = course_overview['start']
        representation['end_date'] = course_overview['end']
        representation['display_name'] = course_overview['display_name_with_default']
        representation['course_run_url'] = get_course_run_url(request, course_run_id)
        representation['due_dates'] = []
        representation['pacing'] = course_overview['pacing']
        representation['org_name'] = course_overview['display_org_with_default']
        representation['is_revoked'] = instance.license.is_revoked if instance.license else False
        representation['is_enrollment_active'] = instance.is_active
        representation['mode'] = instance.mode

        return representation

    def _get_course_overview(self, course_run_id):
        """
        Get the appropriate course overview from the context.
        """
        for overview in self.context['course_overviews']:
            if overview['id'] == course_run_id:
                return overview

        return None
