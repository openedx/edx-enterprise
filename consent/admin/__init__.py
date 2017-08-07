# -*- coding: utf-8 -*-
"""
Django admin integration for the Consent application.
"""

from __future__ import absolute_import, unicode_literals

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from consent.models import DataSharingConsent


@admin.register(DataSharingConsent)
class DataSharingConsentAdmin(SimpleHistoryAdmin):
    """
    Django admin model for PendingEnrollment
    """

    class Meta(object):
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

    def has_add_permission(self, request):
        """
        Disable add permission for DataSharingConsent.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Disable deletion permission for DataSharingConsent.
        """
        return False
