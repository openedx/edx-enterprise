# -*- coding: utf-8 -*-
"""
Database models field validators.
"""

import os
import re

from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from enterprise.constants import CONTENT_FILTER_FIELD_TYPES as cftypes


def get_app_config():
    """
    :return Application configuration.
    """
    return apps.get_app_config("enterprise")


def validate_hex_color(value):
    """
    Validate value is suitable for a color hex value.
    """
    pattern = r'^#[a-fA-F0-9]{6}$'
    if not re.match(pattern, value):
        message = _('Value entered is not a valid hex color code.')
        raise ValidationError(message)


def validate_image_extension(value):
    """
    Validate that a particular image extension.
    """
    config = get_app_config()
    ext = os.path.splitext(value.name)[1]
    if config and not ext.lower() in config.valid_image_extensions:
        raise ValidationError(_("Unsupported file extension."))


def validate_image_size(image):
    """
    Validate that a particular image size.
    """
    config = get_app_config()
    valid_max_image_size_in_bytes = config.valid_max_image_size * 1024
    if config and not image.size <= valid_max_image_size_in_bytes:
        raise ValidationError(
            _("The logo image file size must be less than or equal to %s KB.") % config.valid_max_image_size)


def validate_content_filter_fields(content_filter):
    """
    Validate particular fields (if present) passed in through content_filter are certain types.
    """
    for key in cftypes:
        if key in content_filter.keys():
            if not isinstance(content_filter[key], cftypes[key]['type']):
                raise ValidationError(
                    "Content filter '%s' must be of type %s" % (key, cftypes[key]['type'])
                )
            if cftypes[key]['type'] == list:
                if not all(cftypes[key]['subtype'] == type(x) for x in content_filter[key]):
                    raise ValidationError(
                        "Content filter '%s' must contain values of type %s" % (
                            key, cftypes[key]['subtype']
                        )
                    )
