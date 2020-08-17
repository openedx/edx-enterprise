# -*- coding: utf-8 -*-
"""
URL definitions for Canvas API.
"""

from django.conf.urls import url

from integrated_channels.canvas.views import CanvasCompleteOAuthView

urlpatterns = [
    url(
        r'^oauth-complete$',
        CanvasCompleteOAuthView.as_view(),
        name='canvas-oauth-complete'
    ),
]
