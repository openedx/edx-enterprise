"""
URL definitions for Canvas API.
"""

from django.urls import path
from django.views.generic import TemplateView


from integrated_channels.canvas.views import CanvasCompleteOAuthView

urlpatterns = [
    path('oauth-complete', CanvasCompleteOAuthView.as_view())
    # path('oauth-complete', TemplateView.as_view(template_name="enterprise/admin/oauth_authorization_successful.html"), name='canvas-oauth-complete'),

]
