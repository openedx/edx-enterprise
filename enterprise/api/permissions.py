# -*- coding: utf-8 -*-
"""
Filters for enterprise API.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework.permissions import DjangoObjectPermissions


class DjangoMultiObjectPermissions(DjangoObjectPermissions):
    """
    Permissions class for specifying a list of django permissions required.
    """

    django_permissions = []

    def get_required_permissions(self, method, model_cls):
        return self.django_permissions

    def get_required_object_permissions(self, method, model_cls):
        return self.django_permissions


class CreateEnterpriseCustomerCourseEnrollmentsPermissions(DjangoMultiObjectPermissions):
    """
    Permissions class for the create course enrollments endpoint.
    """

    django_permissions = [
        'enterprise.add_pendingenterprisecustomeruser',
        'enterprise.add_pendingenrollment'
        'enterprise.change_pendingenrollment'
        'enterprise.add_enterprisecourseenrollment',
        'enterprise.change_enterprisecourseenrollment',
    ]
