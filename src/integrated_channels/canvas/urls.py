"""
URL definitions for Canvas API.
"""

from django.urls import path

from integrated_channels.canvas.views import CanvasCompleteOAuthView

urlpatterns = [
    path('oauth-complete', CanvasCompleteOAuthView.as_view(),
         name='canvas-oauth-complete'
         ),
]
