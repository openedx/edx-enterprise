# -*- coding: utf-8 -*-
"""
Django admin integration for the Consent application.
"""

from django_object_actions import DjangoObjectActions
from simple_history.admin import SimpleHistoryAdmin

from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import ugettext as _

from consent.models import DataSharingConsent, DataSharingConsentTextOverrides


@admin.register(DataSharingConsent)
class DataSharingConsentAdmin(SimpleHistoryAdmin):
    """
    Django admin model for PendingEnrollment
    """

    class Meta:
        """
        Meta class for ``DataSharingConsentAdmin``.
        """

        model = DataSharingConsent

    readonly_fields = (
        'enterprise_customer',
        'username',
        'course_id',
        'granted',
        'exists',
    )

    list_display = (
        'enterprise_customer',
        'username',
        'course_id',
        'granted',
        'exists',
    )

    ordering = (
        "username",
    )

    search_fields = (
        'enterprise_customer__name',
        'enterprise_customer__uuid',
        'username',
        'course_id',
    )


@admin.register(DataSharingConsentTextOverrides)
class DataSharingConsentTextOverridesAdmin(DjangoObjectActions, SimpleHistoryAdmin):
    """
    Django admin model for DataSharingConsentTextOverrides
    """
    change_actions = ("preview_as_course", "preview_as_program", )

    list_display = (
        'enterprise_customer',
        'top_paragraph',
        'published',
    )

    ordering = (
        "enterprise_customer",
    )

    search_fields = (
        'enterprise_customer__name',
        'enterprise_customer__uuid',
    )

    actions = ['preview_with_course']

    def preview(self, consent_page, course_id='', program_uuid=''):
        """
        Makes data sharing consent page url and querystring and redirects to it
        """
        params = {
            'preview_mode': 'true',
            'course_id': course_id,
            'program_uuid': program_uuid,
            'next': '/admin',
            'failure_url': '/admin',
            'enterprise_customer_uuid': consent_page.enterprise_customer.uuid
        }
        url = reverse('grant_data_sharing_permissions') + '?{}'.format(urlencode(params))
        return HttpResponseRedirect(url)

    def preview_as_course(self, request, consent_page):
        """
        Renders data sharing consent page in course context
        """
        return self.preview(consent_page, course_id='course-v1:edX+TestX+Test_Course')

    def preview_as_program(self, request, consent_page):
        """
        Renders data sharing consent page in program context
        """
        return self.preview(consent_page, program_uuid='25c10a26-0b00-0000-bd06-7813546c29eb')

    preview_as_course.label = _("Preview (course)")
    preview_as_course.short_description = _(
        "Preview the data sharing consent page rendered in the context of a course enrollment."
    )
    preview_as_program.label = _("Preview (program)")
    preview_as_program.short_description = _(
        "Preview the data sharing consent page rendered in the context of a program enrollment."
    )

    class Meta:
        """
        Meta class for ``DataSharingConsentTextOverridesAdmin``.
        """

        model = DataSharingConsentTextOverrides
