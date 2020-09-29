# -*- coding: utf-8 -*-
"""
URL definitions for Blackboard API.
"""

from django.conf.urls import url

from integrated_channels.blackboard.views import BlackboardCompleteOAuthView

urlpatterns = [
    url(
        r'^oauth-complete$',
        BlackboardCompleteOAuthView.as_view(),
        name='blackboard-oauth-complete'
    ),
]
