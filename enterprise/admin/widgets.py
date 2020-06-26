# -*- coding: utf-8 -*-
"""
Widgets to be used in the enterprise djangoapp.
"""

from django.forms.widgets import Input


class SubmitInput(Input):
    """
    Widget for input type field
    """
    input_type = 'submit'
    template_name = 'django/forms/widgets/text.html'
