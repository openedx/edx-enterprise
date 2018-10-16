# -*- coding: utf-8 -*-
"""
URL definitions for enterprise api version 1 endpoint.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework.routers import DefaultRouter

from enterprise.api.v2 import views

router = DefaultRouter()  # pylint: disable=invalid-name

router.register("enterprise-customer", views.EnterpriseCustomerViewSetV2, 'enterprise-customer')
