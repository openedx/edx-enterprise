# -*- coding: utf-8 -*-
"""
enterprise_learner_portal serializer
"""
from __future__ import absolute_import, unicode_literals

from django.utils.translation import ugettext as _

from rest_framework import serializers

try:
    from lms.djangoapps.certificates.api import get_certificate_for_user
    from lms.djangoapps.program_enrollments.api.api import (
        get_due_dates,
        get_course_run_url,
        get_emails_enabled,
    )
except ImportError:
    get_certificate_for_user = None
    get_due_dates = None
    get_course_run_url = None
    get_emails_enabled = None

from enterprise.utils import NotConnectedToOpenEdX
from enterprise_learner_portal.utils import get_course_run_status


class EnterpriseCourseEnrollmentSerializer(serializers.Serializer):
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
        super(EnterpriseCourseEnrollmentSerializer, self).__init__(*args, **kwargs)

    def to_representation(self, instance):
        representation = super(EnterpriseCourseEnrollmentSerializer, self).to_representation(instance)

        request = self.context['request']
        user = request.user

        # Certificate
        certificate_info = get_certificate_for_user(
            user.username,
            instance['id']
        )
        representation['certificate_download_url'] = certificate_info.get('download_url')

        # Email enabled
        emails_enabled = get_emails_enabled(user, instance['id'])
        if emails_enabled is not None:
            representation['emails_enabled'] = emails_enabled

        representation['course_run_id'] = instance['id']
        representation['course_run_status'] = get_course_run_status(
            instance,
            certificate_info,
        )
        representation['start_date'] = instance['start']
        representation['end_date'] = instance['end']
        representation['display_name'] = instance['display_name_with_default']
        representation['course_run_url'] = get_course_run_url(request, instance['id'])
        representation['due_dates'] = get_due_dates(request, instance['id'], user)
        representation['pacing'] = instance['pacing']
        representation['org_name'] = instance['display_org_with_default']

        return representation
